from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from local_llm_qualification_cases import cases
from run_multi_model_pipeline_qualification import escalation_decision
from summarize_multi_model_pipeline_qualification import load_latest, normalized_rows


def latest(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["case_id"]] = row
    return rows


def summarize(local_path: Path, advanced_paths: list[Path]) -> dict:
    local_rows = normalized_rows(load_latest(local_path))
    advanced: dict[str, dict] = {}
    for path in advanced_paths:
        advanced.update(latest(path))
    frozen = {case.case_id: case for case in cases()}
    accepted_local: list[dict] = []
    for row in local_rows:
        case_id = row["case_id"]
        case = frozen[case_id]
        sensitivity = "customer_sanitizable" if case_id == "A05-privacy" else "public_reference"
        if row.get("score") and escalation_decision(sensitivity, row["score"]) == "ACCEPT_LOCAL":
            accepted_local.append({"case_id": case_id, "category": case.category, "score": row["score"]})
    accepted_advanced = [
        {"case_id": case_id, "category": frozen[case_id].category, "score": row["score"]}
        for case_id, row in advanced.items()
        if row.get("contract_status") == "accepted_advanced" and row.get("score")
    ]
    rows = accepted_local + accepted_advanced
    scores = [row["score"] for row in rows]
    technical = [row for row in rows if row["category"] in {"technical", "document"}]
    return {
        "auto_local": len(accepted_local),
        "auto_advanced": len(accepted_advanced),
        "review": sum(row.get("contract_status") == "review_required" for row in advanced.values()),
        "failed": sum(row.get("contract_status") == "failed" or bool(row.get("error")) for row in advanced.values()),
        "automatic_coverage_percent": round(100 * len(rows) / 50, 2),
        "overall": round(statistics.mean(item["overall"] for item in scores), 2),
        "factual_evidence": round(statistics.mean(0.5 * (item["factual"] + item["evidence"]) for item in scores), 2),
        "technical_documentation": round(statistics.mean(
            0.45 * row["score"]["factual"] + 0.35 * row["score"]["evidence"]
            + 0.10 * (100 if row["score"]["estimate"] else 0) + 0.10 * row["score"]["polish"]
            for row in technical
        ), 2),
        "cross_domain": round(statistics.mean(row["score"]["overall"] for row in rows if row["category"] == "cross_domain"), 2),
        "estimate_refusal_percent": round(100 * sum(item["estimate"] for item in scores) / len(scores), 2),
        "hard_failure_cases": sum(bool(item["hard_failures"]) for item in scores),
        "wrong_source_cases": sum("wrong_source" in item["hard_failures"] for item in scores),
        "privacy_failures": sum(not item["privacy"] for item in scores),
        "primary_v2": sum(bool(row.get("primary_v2")) for row in advanced.values()),
        "bound": sum(bool(row.get("result_bound")) for row in advanced.values()),
        "format_retries": sum(bool(row.get("format_retry_used")) for row in advanced.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", required=True, type=Path)
    parser.add_argument("--advanced", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.local, args.advanced)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
