from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from summarize_multi_model_pipeline_qualification import load_latest, metrics, normalized_rows
from run_cooperative_model_validation import cross_check


def stage_metrics(path: Path, field: str) -> dict:
    rows = list(load_latest(path).values())
    eligible = [row for row in rows if not row.get("bypass")]
    error_field = field + "_errors"
    valid = [row for row in eligible if not row.get("error") and not row.get(error_field)]
    failures = Counter(code for row in eligible for code in row.get(error_field) or [])
    latencies = sorted(float(row.get("telemetry", {}).get("wall_seconds", 0)) for row in eligible)
    return {"cases": len(rows), "eligible": len(eligible), "admissible": len(valid),
            "validation_failed": sum(bool(row.get(error_field)) for row in eligible),
            "runtime_errors": sum(bool(row.get("error")) for row in eligible),
            "median_seconds": round(latencies[len(latencies) // 2], 2) if latencies else 0,
            "failure_codes": dict(failures)}


def capacity(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    samples = value["samples"]
    model = value["model"]
    resident_sizes = [item["size_gib"] for sample in samples for item in sample["ollama"] if item["name"] == model]
    query_tps = sorted(item["response_tokens_per_second"] for item in value["queries"])
    return {"model": model, "embedding": value["embedding_coexistence"],
            "model_runtime_gib": max(resident_sizes) if resident_sizes else None,
            "windows_min_gib": min(sample["windows"]["available_gib"] for sample in samples),
            "wsl_min_gib": min(sample["wsl"]["mem_available_gib"] for sample in samples),
            "pagefile_max_mib": max(sample["windows"]["pagefile_current_mib"] for sample in samples),
            "wsl_swap_max_gib": max(sample["wsl"]["swap_used_gib"] for sample in samples),
            "tokens_per_second_median": query_tps[len(query_tps) // 2],
            "cold_load_seconds": value["queries"][0]["load_seconds"],
            "warm_latency_seconds_median": sorted(item["wall_seconds"] for item in value["queries"])[len(value["queries"]) // 2],
            "unload_seconds": value["model_unload_seconds"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--qwen9", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    pipelines = {}
    for name, file in {
        "F0": Path(args.qwen9), "Q7": root / "qwen7-F.jsonl", "P4": root / "phi-F.jsonl",
        "Q7_TO_Q9": root / "qwen7-to-qwen9-f0.jsonl", "P4_TO_Q7": root / "phi-to-qwen7.jsonl",
    }.items():
        pipelines[name] = metrics(name, normalized_rows(load_latest(file)), escalation=True)
    result = {
        "pipelines": pipelines,
        "roles": {
            "qwen7_specialist": stage_metrics(root / "qwen7-specialist.stages.jsonl", "specialist"),
            "phi_planner": stage_metrics(root / "phi-planner.stages.jsonl", "planner"),
            "phi_specialist": stage_metrics(root / "phi-specialist.stages.jsonl", "specialist"),
            "qwen7_phi_validator": json.loads((root / "qwen7-phi-validator.summary.json").read_text(encoding="utf-8")),
            "qwen9_phi_validator": json.loads((root / "qwen9-f0-phi-validator.summary.json").read_text(encoding="utf-8")),
            "qwen7_qwen9_cross_check": cross_check(root / "qwen7-F.jsonl", Path(args.qwen9), root / "qwen7-qwen9.cross-check.json"),
        },
        "capacity": [capacity(root / name) for name in (
            "qwen7-capacity.json", "qwen7-embedding-capacity.json", "phi-capacity.json", "phi-embedding-capacity.json")],
        "co_residency": json.loads((root / "phi-qwen7-embedding-coresidency.json").read_text(encoding="utf-8-sig")),
        "temporary_chat": json.loads((root / "temp-chat-F0.summary.json").read_text(encoding="utf-8")),
    }
    # Keep the aggregate concise; detailed per-case/raw telemetry stays ignored.
    result["roles"]["qwen7_qwen9_cross_check"] = {
        key: result["roles"]["qwen7_qwen9_cross_check"][key]
        for key in ("cases", "agreement", "material_disagreement")
    }
    result["co_residency"] = {
        "combination": result["co_residency"]["combination"],
        "windows_min_gib": min(item["windows_available_gib"] for item in result["co_residency"]["samples"]),
        "wsl_min_gib": min(item["wsl"]["available_gib"] for item in result["co_residency"]["samples"]),
        "wsl_swap_max_gib": max(item["wsl"]["swap_used_gib"] for item in result["co_residency"]["samples"]),
        "health": result["co_residency"]["health"],
    }
    result["temporary_chat"].pop("results", None)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
