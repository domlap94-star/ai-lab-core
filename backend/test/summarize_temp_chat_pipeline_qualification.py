from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from local_llm_qualification_cases import cases
from run_local_llm_qualification import score
from run_multi_model_pipeline_qualification import validate_final_response
from run_temp_chat_pipeline_qualification import GATED_CASES, remap_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--spool-root", default="/data/analysis-spool")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = {row["case_id"]: row for row in (json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip())}
    case_by_id = {case.case_id: case for case in cases()}
    scored = []
    for case_id in GATED_CASES:
        row, case = rows[case_id], case_by_id[case_id]
        aliases = {f"S{index}": ref for index, ref in enumerate(case.evidence, 1)}
        path = Path(args.spool_root) / "jobs" / row["external_job_id"] / "output" / "analysis.json"
        external = json.loads(path.read_text(encoding="utf-8"))
        final = remap_result(external.get("result") or {}, aliases, case)
        result = score(case, final)
        final_errors = validate_final_response(final, case)
        if final_errors and "wrong_source" not in result["hard_failures"]:
            result["hard_failures"].append("wrong_source")
        scored.append({"case_id": case_id, "post_validation": row.get("post_validation"),
                       "verification_recommendation": external.get("verification_recommendation"),
                       "score": result, "final_errors": final_errors})
    metrics = [row["score"] for row in scored]
    accepted = [row for row in scored if row["post_validation"] == "accepted_advanced"]
    summary = {
        "cases": len(scored), "jobs": len(scored),
        "accepted_advanced": len(accepted),
        "review_required": sum(row["post_validation"] == "review_required" for row in scored),
        "failed": sum(row["post_validation"] == "failed" for row in scored),
        "raw_external_overall": round(statistics.mean(item["overall"] for item in metrics), 2),
        "raw_external_factual_evidence": round(statistics.mean(0.5 * (item["factual"] + item["evidence"]) for item in metrics), 2),
        "raw_external_hard_failure_cases": sum(bool(item["hard_failures"]) for item in metrics),
        "raw_external_wrong_source_cases": sum(bool(item["foreign_sources"]) for item in metrics),
        "raw_external_privacy_failures": sum(not item["privacy"] for item in metrics),
        "accepted_overall": round(statistics.mean(row["score"]["overall"] for row in accepted), 2) if accepted else None,
        "accepted_factual_evidence": round(statistics.mean(0.5 * (row["score"]["factual"] + row["score"]["evidence"]) for row in accepted), 2) if accepted else None,
        "end_to_end_all_cases_accepted": len(accepted) == len(scored),
        "results": scored,
    }
    Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
