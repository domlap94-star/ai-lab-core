from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.client_reconstruction_evidence_service import ClientReconstructionEvidenceService
from app.services.client_reconstruction_policy_service import ClientReconstructionPolicyService
from app.services.local_ollama_client_reconstruction_service import LocalOllamaClientReconstructionService
from run_existing_ollama_reconstruction_calibration import analyze_record


REPORTS = Path(__file__).resolve().parent / "reports"
PRIVATE = REPORTS / "private"
DEFAULT_MANIFEST = REPORTS / "ai_client_reconstruction_pilot_manifest.json"
GIB = 1024 ** 3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_linux_memory() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        key, _, raw = line.partition(":")
        if key in {"MemAvailable", "SwapTotal", "SwapFree"}:
            values[key] = int(raw.strip().split()[0]) * 1024
    return {
        "wsl_available_bytes": values.get("MemAvailable", 0),
        "swap_used_bytes": values.get("SwapTotal", 0) - values.get("SwapFree", 0),
        "swap_free_bytes": values.get("SwapFree", 0),
    }


def read_ollama_state(base_url: str) -> dict[str, Any]:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/ps", timeout=10)
        response.raise_for_status()
        models = response.json().get("models") or []
    except Exception:
        models = []
    return {
        "resident_models": [str(item.get("name") or item.get("model")) for item in models],
        # Ollama exposes model allocation, not Docker RSS. The proof harness augments
        # this value with host docker-stats snapshots in its private telemetry report.
        "ollama_model_bytes": sum(int(item.get("size") or 0) for item in models),
    }


def default_telemetry(base_url: str) -> dict[str, Any]:
    return {**read_linux_memory(), **read_ollama_state(base_url), "timestamp": utc_now()}


def initial_checkpoint(*, run_id: str, model: str, batch_size: int,
                       start_offset: int, max_records: int,
                       manifest_path: Path) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "model": model,
        "batch_size": batch_size,
        "start_offset": start_offset,
        "max_records": max_records,
        "manifest_sha256": manifest_sha256(manifest_path),
        "completed_manifest_indices": [],
        "completed_client_ids": [],
        "failed_client_ids": [],
        "last_completed_index": None,
        "next_manifest_index": start_offset,
    }


def validate_checkpoint(checkpoint: dict[str, Any], *, model: str,
                        batch_size: int, start_offset: int, max_records: int,
                        manifest_path: Path) -> None:
    expected = {
        "model": model,
        "batch_size": batch_size,
        "start_offset": start_offset,
        "max_records": max_records,
        "manifest_sha256": manifest_sha256(manifest_path),
    }
    mismatches = [key for key, value in expected.items() if checkpoint.get(key) != value]
    if mismatches:
        raise RuntimeError("checkpoint mismatch: " + ", ".join(mismatches))


def selected_records(manifest: dict[str, Any], *, start_offset: int,
                     max_records: int) -> list[tuple[int, dict[str, Any]]]:
    records = manifest["records"]
    end = min(start_offset + max_records, len(records))
    return [(index, records[index]) for index in range(start_offset, end)]


def update_checkpoint(checkpoint: dict[str, Any], *, index: int, client_id: int,
                      failed: bool, window_end: int) -> None:
    checkpoint["completed_manifest_indices"].append(index)
    checkpoint["completed_client_ids"].append(client_id)
    if failed:
        checkpoint["failed_client_ids"].append(client_id)
    checkpoint["last_completed_index"] = index
    checkpoint["next_manifest_index"] = min(index + 1, window_end)


def should_reset_memory(telemetry: dict[str, Any], *, previous_model_bytes: int | None,
                        threshold_bytes: int = 2 * GIB) -> bool:
    low_memory = int(telemetry.get("wsl_available_bytes") or 0) < threshold_bytes
    current = int(telemetry.get("ollama_model_bytes") or 0)
    uncontrolled_growth = previous_model_bytes is not None and current > previous_model_bytes + GIB
    return low_memory or uncontrolled_growth


def unload_model(model: str, *, base_url: str = "http://ollama:11434",
                 timeout_seconds: float = 180) -> None:
    if model not in read_ollama_state(base_url)["resident_models"]:
        return
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
        timeout=60,
    )
    response.raise_for_status()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        state = read_ollama_state(base_url)
        if model not in state["resident_models"]:
            return
        time.sleep(1)
    raise RuntimeError(f"model did not unload: {model}")


def build_summary(results_path: Path, *, requested: int, run_id: str,
                  model: str, started: float) -> dict[str, Any]:
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line]
    successful = [row for row in rows if row["status"] == "completed"]
    classifications = Counter(row["policy"]["classification"] for row in successful)
    flags = Counter()
    durations = [float(row["latency_seconds"]) for row in rows if row.get("latency_seconds") is not None]
    tps: list[float] = []
    for row in successful:
        for key, value in row.get("metric_flags", {}).items():
            if isinstance(value, bool) and value:
                flags[key] += 1
        tps.append(float(row.get("usage", {}).get("tokens_per_second") or 0))
    ordered = sorted(durations)
    percentile = lambda p: ordered[max(0, min(len(ordered) - 1, int((len(ordered) * p + .999999) - 1)))] if ordered else None
    return {
        "run_id": run_id, "model": model, "requested": requested,
        "completed": len(successful), "failed": len(rows) - len(successful),
        "schema_valid": len(successful), "classifications": dict(classifications),
        "quality_flags": dict(flags), "total_runtime_seconds": sum(durations),
        "average_latency_seconds": statistics.mean(durations) if durations else None,
        "p50_latency_seconds": percentile(.50), "p95_latency_seconds": percentile(.95),
        "max_latency_seconds": max(durations) if durations else None,
        "average_tokens_per_second": statistics.mean(tps) if tps else None,
        "input_tokens": sum(int(row.get("usage", {}).get("input_tokens") or 0) for row in successful),
        "output_tokens": sum(int(row.get("usage", {}).get("output_tokens") or 0) for row in successful),
        "production_db_writes": 0, "qdrant_writes": 0,
    }


def run_batch(*, model: str, batch_size: int, start_offset: int,
              max_records: int, manifest_path: Path, checkpoint_path: Path,
              results_path: Path, summary_path: Path, resume: bool,
              invocation_limit: int | None = None,
              evaluator_factory: Callable[..., Any] = LocalOllamaClientReconstructionService,
              session_factory: Callable[[], Any] = SessionLocal,
              telemetry_reader: Callable[[str], dict[str, Any]] = default_telemetry,
              unload: Callable[[str], None] = unload_model) -> dict[str, Any]:
    started = time.perf_counter()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    window = selected_records(manifest, start_offset=start_offset, max_records=max_records)
    window_end = start_offset + len(window)
    if resume:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        validate_checkpoint(checkpoint, model=model, batch_size=batch_size,
                            start_offset=start_offset, max_records=max_records,
                            manifest_path=manifest_path)
    else:
        if checkpoint_path.exists() or results_path.exists():
            raise RuntimeError("run artifacts already exist; use --resume or a new run-id")
        checkpoint = initial_checkpoint(run_id=checkpoint_path.stem, model=model,
                                        batch_size=batch_size, start_offset=start_offset,
                                        max_records=max_records, manifest_path=manifest_path)
        atomic_json(checkpoint_path, checkpoint)
    completed = set(int(value) for value in checkpoint["completed_manifest_indices"])
    pending = [(index, item) for index, item in window if index not in completed]
    if invocation_limit is not None:
        pending = pending[:invocation_limit]
    previous_model_bytes: int | None = None
    processed = 0
    with session_factory() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        evidence = ClientReconstructionEvidenceService(db)
        policy = ClientReconstructionPolicyService(db)
        evaluator = evaluator_factory(model=model)
        for index, manifest_record in pending:
            client_id = int(manifest_record["client_id"])
            before = telemetry_reader(evaluator.base_url)
            packet = evidence.build(client_id)
            packet_hash = evidence.sha256(packet)
            if packet_hash != manifest_record["evidence_packet_sha256"]:
                raise RuntimeError(f"evidence manifest drift for client {client_id}")
            started_record = time.perf_counter()
            row: dict[str, Any] = {
                "run_id": checkpoint["run_id"], "batch_id": start_offset // batch_size,
                "manifest_index": index, "client_id": client_id,
                "selection_class": manifest_record["selection_class"],
                "packet_sha256": packet_hash, "timestamp": utc_now(),
            }
            failed = False
            try:
                proposal, usage = evaluator.evaluate(packet)
                validated = policy.validate(packet, proposal)
                row.update({"status": "completed", "proposal": proposal.model_dump(),
                            "policy": validated.model_dump(), "usage": usage})
                row["metric_flags"] = analyze_record(row, packet["client"])
            except Exception as error:
                failed = True
                row.update({"status": "failed", "error_type": type(error).__name__,
                            "error": str(error)[:500], "proposal": None,
                            "policy": None, "usage": {}})
            row["latency_seconds"] = time.perf_counter() - started_record
            after = telemetry_reader(evaluator.base_url)
            row["telemetry"] = {"before": before, "after": after}
            append_jsonl(results_path, row)
            update_checkpoint(checkpoint, index=index, client_id=client_id,
                              failed=failed, window_end=window_end)
            atomic_json(checkpoint_path, checkpoint)
            processed += 1
            if should_reset_memory(after, previous_model_bytes=previous_model_bytes):
                unload(model)
                recovered = telemetry_reader(evaluator.base_url)
                append_jsonl(results_path.with_name(results_path.stem + "_memory_resets.jsonl"), {
                    "run_id": checkpoint["run_id"], "manifest_index": index,
                    "before_unload": after, "after_unload": recovered, "timestamp": utc_now(),
                })
                if int(recovered.get("wsl_available_bytes") or 0) < 6 * GIB:
                    break
                previous_model_bytes = None
            else:
                previous_model_bytes = int(after.get("ollama_model_bytes") or 0)
        db.rollback()
    window_complete = all(index in set(checkpoint["completed_manifest_indices"]) for index, _ in window)
    if window_complete:
        unload(model)
        checkpoint["final_unload_completed"] = True
        checkpoint["final_unload_telemetry"] = telemetry_reader("http://ollama:11434")
        atomic_json(checkpoint_path, checkpoint)
    summary = build_summary(results_path, requested=len(window), run_id=checkpoint["run_id"],
                            model=model, started=started) if results_path.exists() else {
        "run_id": checkpoint["run_id"], "model": model, "requested": len(window),
        "completed": 0, "failed": 0, "new_inference_calls": 0,
    }
    summary["new_inference_calls"] = processed
    summary["next_manifest_index"] = checkpoint["next_manifest_index"]
    atomic_json(summary_path, summary)
    print(json.dumps(summary), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--start-offset", type=int, required=True)
    parser.add_argument("--max-records", type=int, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--invocation-limit", type=int)
    args = parser.parse_args()
    stem = f"ollama_batched_{args.run_id}"
    run_batch(model=args.model, batch_size=args.batch_size,
              start_offset=args.start_offset, max_records=args.max_records,
              manifest_path=args.manifest,
              checkpoint_path=PRIVATE / f"{stem}_checkpoint.json",
              results_path=PRIVATE / f"{stem}_results.jsonl",
              summary_path=PRIVATE / f"{stem}_summary.json",
              resume=args.resume, invocation_limit=args.invocation_limit)


if __name__ == "__main__":
    main()
