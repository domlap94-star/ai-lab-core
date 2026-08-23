from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from local_llm_qualification_cases import cases
from run_local_llm_qualification import THRESHOLDS, score
from run_multi_model_pipeline_qualification import (
    deterministic_tools,
    escalation_decision,
    validate_final_response,
)


def load_latest(path: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[row["case_id"]] = row
    return result


def normalized_rows(base: dict[str, dict], *, planner: dict[str, dict] | None = None) -> list[dict]:
    result = []
    for case in cases():
        original = base[case.case_id]
        if original.get("error"):
            result.append(original)
            continue
        row = json.loads(json.dumps(original))
        if planner is None:
            plan = deterministic_tools(case)
        else:
            stage = planner[case.case_id]
            plan = deterministic_tools(case) if stage.get("planner_errors") else list(map(str, stage["planner"].get("tool_plan") or []))
            row["planner_errors"] = stage.get("planner_errors") or []
            row["planner_telemetry"] = stage.get("telemetry") or {}
        row["response"]["tool_plan"] = plan
        row["score"] = score(case, row["response"])
        final_errors = validate_final_response(row["response"], case)
        row["final_errors"] = final_errors
        if final_errors and "wrong_source" not in row["score"]["hard_failures"]:
            row["score"]["hard_failures"].append("wrong_source")
        result.append(row)
    return result


def metrics(name: str, rows: list[dict], *, escalation: bool = False) -> dict:
    valid = [row for row in rows if row.get("score")]
    values = [row["score"] for row in valid]
    hard = [row for row in valid if row["score"]["hard_failures"]]
    fe = [0.5 * (item["factual"] + item["evidence"]) for item in values]
    technical = [row for row in valid if row["category"] in {"technical", "document"}]
    technical_score = statistics.mean(
        0.45 * row["score"]["factual"] + 0.35 * row["score"]["evidence"] +
        0.10 * (100 if row["score"]["estimate"] else 0) + 0.10 * row["score"]["polish"]
        for row in technical
    )
    decisions = [escalation_decision("customer_sanitizable" if row["case_id"] == "A05-privacy" else "public_reference", row["score"]) for row in valid]
    escalated = sum(item == "TEMP_CHAT_REQUIRED" for item in decisions) if escalation else 0
    local_rows = [row for row, decision in zip(valid, decisions) if not escalation or decision == "ACCEPT_LOCAL"]
    local_hard = sum(bool(row["score"]["hard_failures"]) for row in local_rows)
    overall = statistics.mean(item["overall"] for item in values)
    factual_evidence = statistics.mean(fe)
    raw_pass = (
        len(valid) == 50 and overall >= THRESHOLDS["overall"] and factual_evidence >= THRESHOLDS["factual_evidence"]
        and len(hard) / 50 <= 0.02 and not any("wrong_source" in item["hard_failures"] for item in values)
        and not any(not item["privacy"] for item in values)
    )
    return {
        "pipeline": name, "cases": len(rows), "successful": len(valid),
        "overall": round(overall, 2), "factual_evidence": round(factual_evidence, 2),
        "hard_failure_cases": len(hard), "wrong_source_cases": sum("wrong_source" in item["hard_failures"] for item in values),
        "privacy_failures": sum(not item["privacy"] for item in values),
        "technical_documentation_score": round(technical_score, 2),
        "cross_domain_score": round(statistics.mean(row["score"]["overall"] for row in valid if row["category"] == "cross_domain"), 2),
        "estimation_refusal_percent": round(100 * sum(item["estimate"] for item in values) / max(1, len(values)), 2),
        "local_latency_median_seconds": round(statistics.median(row["telemetry"]["wall_seconds"] for row in valid), 2),
        "planner_latency_median_seconds": round(statistics.median(row.get("planner_telemetry", {}).get("wall_seconds", 0) for row in valid), 2) if any(row.get("planner_telemetry") for row in valid) else 0,
        "source_claim_coverage_percent": round(100 * sum(not validate_final_response(row["response"], next(case for case in cases() if case.case_id == row["case_id"])) for row in valid) / max(1, len(valid)), 2),
        "escalation_rate_percent": round(100 * escalated / max(1, len(valid)), 2),
        "accepted_local_cases": len(local_rows), "accepted_local_hard_failures": local_hard,
        "accepted_local_overall": round(statistics.mean(row["score"]["overall"] for row in local_rows), 2),
        "accepted_local_factual_evidence": round(statistics.mean(0.5 * (row["score"]["factual"] + row["score"]["evidence"]) for row in local_rows), 2),
        "raw_local_production_gates_pass": raw_pass,
        "external_final_outputs_reexecuted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True)
    parser.add_argument("--b-stages")
    parser.add_argument("--c")
    parser.add_argument("--c-stages")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    a = normalized_rows(load_latest(Path(args.a)))
    result = {"A": metrics("A", a), "D": metrics("D", a, escalation=True), "F": metrics("F", a, escalation=True)}
    if args.b_stages:
        b = normalized_rows(load_latest(Path(args.a)), planner=load_latest(Path(args.b_stages)))
        result["B"] = metrics("B", b)
        result["E"] = metrics("E", b, escalation=True)
    if args.c:
        c = normalized_rows(load_latest(Path(args.c)))
        result["C"] = metrics("C", c)
    elif args.c_stages:
        stages = load_latest(Path(args.c_stages))
        c = metrics("C", a)
        eligible = [row for row in stages.values() if not row.get("bypass")]
        c.update({
            "specialist_cases": len(eligible),
            "specialist_admissible": sum(not row.get("error") and not row.get("specialist_errors") for row in eligible),
            "specialist_validation_failures": sum(bool(row.get("specialist_errors")) for row in eligible),
            "specialist_latency_median_seconds": round(statistics.median(row.get("telemetry", {}).get("wall_seconds", 0) for row in eligible), 2),
            "synthesizer_reruns_required": 0,
            "fallback": "all specialist artifacts rejected; output equals A",
        })
        result["C"] = c
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
