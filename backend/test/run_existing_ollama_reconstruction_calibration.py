from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.client_reconstruction_evidence_service import (
    ClientReconstructionEvidenceService,
)
from app.services.client_reconstruction_policy_service import (
    ClientReconstructionPolicyService,
)
from app.services.local_ollama_client_reconstruction_service import (
    LocalOllamaClientReconstructionService,
)


REPORTS = Path(__file__).resolve().parent / "reports"
PRIVATE = REPORTS / "private"
MANIFEST = REPORTS / "ai_client_reconstruction_pilot_manifest.json"
HOLD_IDS = {13, 1745, 2256, 2560}


def run(*, model: str, limit: int) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = manifest["records"][:limit]
    run_id = datetime.now(timezone.utc).strftime("ollama-%Y%m%dT%H%M%SZ")
    results = []
    failures = []
    metrics = Counter()
    durations = []
    classifications = Counter()
    selection = {int(item["client_id"]): item["selection_class"] for item in records}
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        evidence = ClientReconstructionEvidenceService(db)
        policy = ClientReconstructionPolicyService(db)
        client = LocalOllamaClientReconstructionService(model=model)
        for record in records:
            client_id = int(record["client_id"])
            packet = evidence.build(client_id)
            packet_hash = evidence.sha256(packet)
            if packet_hash != record["evidence_packet_sha256"]:
                failures.append({"client_id": client_id, "error": "evidence_manifest_drift"})
                continue
            started = time.perf_counter()
            try:
                proposal, usage = client.evaluate(packet)
                validated = policy.validate(packet, proposal)
                elapsed = time.perf_counter() - started
                durations.append(elapsed)
                classifications[validated.classification] += 1
                metrics["schema_valid"] += 1
                metrics["input_tokens"] += int(usage["input_tokens"])
                metrics["output_tokens"] += int(usage["output_tokens"])
                if any("foreign evidence ref" in error for error in validated.validation_errors):
                    metrics["foreign_evidence_refs"] += 1
                unsupported = any(error.startswith("unsupported canonical_") for error in validated.validation_errors)
                if unsupported and proposal.confidence >= 0.95:
                    metrics["hallucinated_high_confidence"] += 1
                if client_id in HOLD_IDS and validated.classification == "HIGH_CONFIDENCE_REPAIR_CANDIDATE":
                    metrics["hold_unsafe"] += 1
                if selection[client_id] == "clean_control" and validated.classification != "KEEP":
                    metrics["clean_false_change"] += 1
                if validated.classification == "HIGH_CONFIDENCE_REPAIR_CANDIDATE":
                    metrics["high_confidence"] += 1
                    if proposal.evidence_refs and not validated.validation_errors:
                        metrics["high_confidence_covered"] += 1
                results.append({
                    "client_id": client_id,
                    "selection_class": selection[client_id],
                    "packet_sha256": packet_hash,
                    "proposal": proposal.model_dump(),
                    "policy": validated.model_dump(),
                    "usage": usage,
                    "latency_seconds": elapsed,
                })
                print(json.dumps({"client_id": client_id, "status": "ok", "classification": validated.classification,
                                  "tokens_per_second": round(float(usage["tokens_per_second"]), 2)}), flush=True)
            except Exception as error:
                failures.append({"client_id": client_id, "error_type": type(error).__name__, "error": str(error)[:500]})
                print(json.dumps({"client_id": client_id, "status": "failed", "error_type": type(error).__name__}), flush=True)
        db.rollback()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    result_path = PRIVATE / f"ollama_client_reconstruction_{run_id}_results.jsonl"
    failure_path = PRIVATE / f"ollama_client_reconstruction_{run_id}_failures.jsonl"
    result_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in results), encoding="utf-8")
    failure_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in failures), encoding="utf-8")
    if os.name == "nt":
        os.system(f'icacls "{PRIVATE}" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" "SYSTEM:(OI)(CI)F" >NUL')
    total = len(records)
    clean_total = sum(1 for item in records if item["selection_class"] == "clean_control")
    schema_rate = metrics["schema_valid"] / total if total else 0
    clean_rate = metrics["clean_false_change"] / clean_total if clean_total else 0
    coverage = (
        metrics["high_confidence_covered"] / metrics["high_confidence"]
        if metrics["high_confidence"]
        else None
    )
    summary = {
        "run_id": run_id, "model": model, "requested": total,
        "successful": len(results), "failed": len(failures),
        "schema_valid_rate": schema_rate,
        "classifications": dict(classifications),
        "clean_control_false_change_rate": clean_rate,
        "hallucinated_high_confidence": metrics["hallucinated_high_confidence"],
        "known_hold_failures": metrics["hold_unsafe"],
        "foreign_evidence_refs": metrics["foreign_evidence_refs"],
        "high_confidence_evidence_coverage": coverage,
        "input_tokens": metrics["input_tokens"], "output_tokens": metrics["output_tokens"],
        "average_latency_seconds": sum(durations) / len(durations) if durations else None,
        "decision": "READY_FOR_EXISTING_MODEL_FULL_DRY_RUN" if (
            total == 128 and schema_rate >= .99 and metrics["hallucinated_high_confidence"] == 0
            and metrics["hold_unsafe"] == 0 and metrics["foreign_evidence_refs"] == 0
            and clean_rate <= .05 and coverage == 1.0
        ) else ("SMOKE_PASS" if limit == 5 and schema_rate == 1 else "EXISTING_MODELS_INSUFFICIENT"),
        "production_db_writes": 0, "qdrant_writes": 0,
    }
    stem = "smoke" if limit == 5 else "pilot"
    (REPORTS / f"ollama_client_reconstruction_{stem}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (REPORTS / f"ollama_client_reconstruction_{stem}_summary.txt").write_text("\n".join(f"{k}: {v}" for k, v in summary.items()), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--limit", type=int, choices=(5, 128), required=True)
    arguments = parser.parse_args()
    raise SystemExit(0 if run(model=arguments.model, limit=arguments.limit)["failed"] == 0 else 1)
