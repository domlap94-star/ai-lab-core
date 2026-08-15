from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.client_identity_name_quality_service import ClientIdentityNameQualityService
from app.services.client_reconstruction_evidence_service import ClientReconstructionEvidenceService
from app.services.client_reconstruction_policy_service import ClientReconstructionPolicyService
from app.services.local_ollama_client_reconstruction_service import LocalOllamaClientReconstructionService


REPORTS = Path(__file__).resolve().parent / "reports"
PRIVATE = REPORTS / "private"
MANIFEST = REPORTS / "ai_client_reconstruction_pilot_manifest.json"
HOLD_IDS = {13, 1745, 2256, 2560}
HIGH_CONFIDENCE_THRESHOLD = 0.95
HIGH_CONFIDENCE_CLASS = "HIGH_CONFIDENCE_REPAIR_CANDIDATE"
OBVIOUS_ARTIFACT_CLASSES = {
    "email_artifact", "phone_artifact", "filename_artifact",
    "address_artifact", "prefix_artifact", "garbage_artifact",
}
AMBIGUOUS_CLASSES = {"abbreviated_identity"}


def _first_unselected(records: list[dict], classes: set[str], selected: set[int]) -> dict:
    return next(item for item in records if item["selection_class"] in classes and int(item["client_id"]) not in selected)


def select_smoke_records(records: list[dict], richness_by_id: dict[int, int]) -> list[dict]:
    """Select one stable record for each required smoke role."""
    selected: list[dict] = []
    selected_ids: set[int] = set()

    def add(item: dict) -> None:
        selected.append(item)
        selected_ids.add(int(item["client_id"]))

    add(_first_unselected(records, {"clean_control"}, selected_ids))
    add(_first_unselected(records, {"known_hold"}, selected_ids))
    add(_first_unselected(records, OBVIOUS_ARTIFACT_CLASSES, selected_ids))
    add(max(
        (item for item in records if int(item["client_id"]) not in selected_ids),
        key=lambda item: (richness_by_id.get(int(item["client_id"]), 0), -int(item["client_id"])),
    ))
    add(_first_unselected(records, AMBIGUOUS_CLASSES, selected_ids))
    return selected


def packet_richness(packet: dict[str, Any]) -> int:
    return len(packet.get("source_evidence", [])) * 10 + sum(
        len(item.get("evidence", [])) for item in packet.get("deterministic_projections", [])
    )


def identity_mutations(proposal: dict, current: dict) -> set[str]:
    quality = ClientIdentityNameQualityService
    mutations: set[str] = set()
    comparisons = (
        ("name", proposal.get("canonical_name"), current.get("name"), quality.normalize_identity),
        ("legal_name", proposal.get("canonical_legal_name"), current.get("legal_name"), quality.normalize_identity),
        ("email", proposal.get("canonical_email"), current.get("email"), quality.normalize_email),
        ("phone", proposal.get("canonical_phone"), current.get("phone"), quality.normalize_phone),
    )
    for field, proposed, existing, normalize in comparisons:
        if proposed is not None and normalize(proposed) != normalize(existing):
            mutations.add(field)
    entity_type = proposal.get("entity_type")
    if entity_type not in (None, "unknown") and entity_type != current.get("client_type"):
        mutations.add("entity_type")
    return mutations


def analyze_record(record: dict, current: dict) -> dict[str, Any]:
    proposal = record["proposal"]
    policy = record["policy"]
    classification = policy["classification"]
    errors = list(policy.get("validation_errors") or [])
    mutations = identity_mutations(proposal, current)
    unsupported_fields = {
        error.removeprefix("unsupported canonical_")
        for error in errors if error.startswith("unsupported canonical_")
    }
    unsupported = bool(unsupported_fields)
    unsupported_mutation = bool(unsupported_fields & mutations)
    foreign = any("foreign evidence ref" in error for error in errors)
    duplicate = bool(proposal.get("duplicate_risk") or policy.get("duplicate_client_ids") or classification == "POSSIBLE_DUPLICATE")
    conflict = bool(proposal.get("conflict_detected") or proposal.get("recommended_disposition") == "CONFLICT" or classification == "CONFLICT")
    high_proposal = float(proposal.get("confidence") or 0) >= HIGH_CONFIDENCE_THRESHOLD
    high_result = classification == HIGH_CONFIDENCE_CLASS
    critical_problem = bool(errors or duplicate or conflict)
    clean = record["selection_class"] == "clean_control"
    false_change = clean and unsupported_mutation
    clean_keep = clean and classification == "KEEP"
    clean_non_keep = clean and classification != "KEEP"
    return {
        "mutated_fields": sorted(mutations),
        "clean_keep": clean_keep,
        "clean_non_keep": clean_non_keep,
        "clean_false_change": false_change,
        "clean_abstention_or_rejection": clean_non_keep and not false_change,
        "unsupported_high_confidence_proposal": unsupported and high_proposal,
        "unsupported_high_confidence_bypass": unsupported and high_result,
        "foreign_evidence_proposal": foreign,
        "foreign_evidence_bypass": foreign and high_result,
        "duplicate_risk": duplicate,
        "duplicate_bypass": duplicate and high_result,
        "critical_policy_bypass": critical_problem and high_result,
        "known_hold_unsafe": int(record["client_id"]) in HOLD_IDS and high_result,
        "high_confidence": high_result,
        "high_confidence_covered": high_result and bool(proposal.get("evidence_refs")) and not errors,
    }


def summarize(*, model: str, records: list[dict], failures: list[dict], current_by_id: dict[int, dict], run_id: str, source_run: str | None = None) -> tuple[dict, list[dict]]:
    metrics = Counter()
    classifications = Counter()
    analyzed: list[dict] = []
    durations: list[float] = []
    for record in records:
        flags = analyze_record(record, current_by_id[int(record["client_id"])])
        analyzed.append({"client_id": record["client_id"], "metric_flags": flags})
        classifications[record["policy"]["classification"]] += 1
        metrics["schema_valid"] += 1
        metrics["input_tokens"] += int(record.get("usage", {}).get("input_tokens") or 0)
        metrics["output_tokens"] += int(record.get("usage", {}).get("output_tokens") or 0)
        if record.get("latency_seconds") is not None:
            durations.append(float(record["latency_seconds"]))
        for key, value in flags.items():
            if isinstance(value, bool) and value:
                metrics[key] += 1

    total = len(records) + len(failures)
    clean_total = sum(1 for item in records if item["selection_class"] == "clean_control")
    schema_rate = metrics["schema_valid"] / total if total else 0.0
    clean_rate = metrics["clean_false_change"] / clean_total if clean_total else 0.0
    high_count = metrics["high_confidence"]
    coverage: float | str = (
        metrics["high_confidence_covered"] / high_count
        if high_count else "N/A_NO_HIGH_CONFIDENCE_CANDIDATES"
    )
    coverage_pass = high_count == 0 or coverage == 1.0
    ready = bool(
        total == 128 and schema_rate >= 0.99
        and metrics["unsupported_high_confidence_proposal"] == 0
        and metrics["unsupported_high_confidence_bypass"] == 0
        and metrics["known_hold_unsafe"] == 0
        and metrics["foreign_evidence_proposal"] == 0
        and metrics["foreign_evidence_bypass"] == 0
        and clean_rate <= 0.05 and coverage_pass
        and metrics["critical_policy_bypass"] == 0
        and metrics["duplicate_bypass"] == 0
    )
    summary = {
        "run_id": run_id, "source_run": source_run, "model": model,
        "requested": total, "successful": len(records), "failed": len(failures),
        "schema_valid_rate": schema_rate, "classifications": dict(classifications),
        "clean_controls": clean_total, "clean_keep": metrics["clean_keep"],
        "clean_non_keep": metrics["clean_non_keep"],
        "clean_false_change": metrics["clean_false_change"],
        "clean_abstention_or_rejection": metrics["clean_abstention_or_rejection"],
        "clean_control_false_change_rate": clean_rate,
        "high_confidence_count": high_count,
        "high_confidence_covered": metrics["high_confidence_covered"],
        "high_confidence_evidence_coverage": coverage,
        "high_confidence_rate": high_count / total if total else 0.0,
        "unsupported_high_confidence_proposals": metrics["unsupported_high_confidence_proposal"],
        "unsupported_high_confidence_bypass": metrics["unsupported_high_confidence_bypass"],
        "foreign_evidence_proposals": metrics["foreign_evidence_proposal"],
        "foreign_evidence_bypass": metrics["foreign_evidence_bypass"],
        "known_hold_unsafe": metrics["known_hold_unsafe"],
        "duplicate_risk_count": metrics["duplicate_risk"],
        "possible_duplicate_count": classifications["POSSIBLE_DUPLICATE"],
        "duplicate_bypass": metrics["duplicate_bypass"],
        "critical_policy_bypass": metrics["critical_policy_bypass"],
        "input_tokens": metrics["input_tokens"], "output_tokens": metrics["output_tokens"],
        "average_latency_seconds": sum(durations) / len(durations) if durations else None,
        "decision": "READY_FOR_EXISTING_MODEL_FULL_DRY_RUN" if ready else "EXISTING_MODELS_INSUFFICIENT",
        "production_db_writes": 0, "qdrant_writes": 0,
    }
    return summary, analyzed


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_summary(summary: dict, stem: str) -> None:
    (REPORTS / f"ollama_client_reconstruction_{stem}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (REPORTS / f"ollama_client_reconstruction_{stem}_summary.txt").write_text("\n".join(f"{key}: {value}" for key, value in summary.items()), encoding="utf-8")


def recompute(raw_results: Path) -> dict:
    records = _read_jsonl(raw_results)
    run_id = datetime.now(timezone.utc).strftime("rescore-%Y%m%dT%H%M%SZ")
    current_by_id: dict[int, dict] = {}
    failures: list[dict] = []
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        evidence = ClientReconstructionEvidenceService(db)
        for record in records:
            client_id = int(record["client_id"])
            packet = evidence.build(client_id)
            if evidence.sha256(packet) != record["packet_sha256"]:
                failures.append({"client_id": client_id, "error": "evidence_packet_drift"})
                continue
            current_by_id[client_id] = packet["client"]
        db.rollback()
    valid = [item for item in records if int(item["client_id"]) in current_by_id]
    summary, analyzed = summarize(
        model="llama3.2:latest", records=valid, failures=failures,
        current_by_id=current_by_id, run_id=run_id, source_run=raw_results.name,
    )
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / f"ollama_client_reconstruction_{run_id}_metric_flags.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in analyzed), encoding="utf-8"
    )
    _write_summary(summary, "pilot_recomputed")
    print(json.dumps(summary), flush=True)
    return summary


def show_smoke_set() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = manifest["records"]
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        evidence = ClientReconstructionEvidenceService(db)
        richness = {
            int(item["client_id"]): packet_richness(evidence.build(int(item["client_id"])))
            for item in records
        }
        db.rollback()
    selected = select_smoke_records(records, richness)
    result = [
        {
            "client_id": int(item["client_id"]),
            "selection_class": item["selection_class"],
            "evidence_richness": richness[int(item["client_id"])],
        }
        for item in selected
    ]
    print(json.dumps(result), flush=True)
    return result


def run(*, model: str, limit: int) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    all_records = manifest["records"]
    run_id = datetime.now(timezone.utc).strftime("ollama-%Y%m%dT%H%M%SZ")
    results: list[dict] = []
    failures: list[dict] = []
    current_by_id: dict[int, dict] = {}
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        evidence = ClientReconstructionEvidenceService(db)
        packet_by_id = {int(item["client_id"]): evidence.build(int(item["client_id"])) for item in all_records}
        records = select_smoke_records(
            all_records, {key: packet_richness(value) for key, value in packet_by_id.items()}
        ) if limit == 5 else all_records
        policy = ClientReconstructionPolicyService(db)
        client = LocalOllamaClientReconstructionService(model=model)
        for record in records:
            client_id = int(record["client_id"])
            packet = packet_by_id[client_id]
            current_by_id[client_id] = packet["client"]
            packet_hash = evidence.sha256(packet)
            if packet_hash != record["evidence_packet_sha256"]:
                failures.append({"client_id": client_id, "error": "evidence_manifest_drift"})
                continue
            started = time.perf_counter()
            try:
                proposal, usage = client.evaluate(packet)
                validated = policy.validate(packet, proposal)
                results.append({
                    "client_id": client_id, "selection_class": record["selection_class"],
                    "packet_sha256": packet_hash, "proposal": proposal.model_dump(),
                    "policy": validated.model_dump(), "usage": usage,
                    "latency_seconds": time.perf_counter() - started,
                })
            except Exception as error:
                failures.append({"client_id": client_id, "error_type": type(error).__name__, "error": str(error)[:500]})
        db.rollback()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / f"ollama_client_reconstruction_{run_id}_results.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in results), encoding="utf-8")
    (PRIVATE / f"ollama_client_reconstruction_{run_id}_failures.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in failures), encoding="utf-8")
    summary, analyzed = summarize(model=model, records=results, failures=failures, current_by_id=current_by_id, run_id=run_id)
    (PRIVATE / f"ollama_client_reconstruction_{run_id}_metric_flags.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in analyzed), encoding="utf-8"
    )
    _write_summary(summary, "smoke" if limit == 5 else "pilot")
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int, choices=(5, 128))
    parser.add_argument("--recompute", type=Path)
    parser.add_argument("--show-smoke-set", action="store_true")
    arguments = parser.parse_args()
    if arguments.show_smoke_set:
        show_smoke_set()
        result = {"failed": 0}
    elif arguments.recompute:
        result = recompute(arguments.recompute)
    elif arguments.model and arguments.limit:
        result = run(model=arguments.model, limit=arguments.limit)
    else:
        parser.error("use --recompute PATH or both --model and --limit")
    if result["failed"]:
        raise RuntimeError("Calibration completed with failed records")
