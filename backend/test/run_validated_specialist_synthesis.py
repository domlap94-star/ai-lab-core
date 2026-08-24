from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from local_llm_qualification_cases import cases
from run_local_llm_qualification import SCHEMA as FINAL_SCHEMA
from run_local_llm_qualification import score
from run_multi_model_pipeline_qualification import (
    call_ollama,
    deterministic_tools,
    normalized_specialist_graph,
    reasoner_prompt,
    summarize_pipeline,
    unload_model,
    validate_final_response,
    validate_graph,
)


def load_latest(path: Path) -> dict[str, dict]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[row["case_id"]] = row
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-cache", required=True)
    parser.add_argument("--fallback-results", required=True)
    parser.add_argument("--reasoner-model", required=True)
    parser.add_argument("--base-url", default="http://ollama:11434")
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()
    stages = load_latest(Path(args.stage_cache))
    fallback = load_latest(Path(args.fallback_results))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = load_latest(output) if args.resume and output.exists() else {}
    if args.retry_errors:
        completed = {case_id: row for case_id, row in completed.items() if not row.get("error")}
        output.write_text("".join(json.dumps(completed[item.case_id], ensure_ascii=False) + "\n" for item in cases() if item.case_id in completed), encoding="utf-8")
    for index, case in enumerate(cases(), 1):
        if case.case_id in completed:
            continue
        stage = stages[case.case_id]
        admissible = not stage.get("bypass") and not stage.get("error") and not stage.get("specialist_errors")
        if not admissible:
            row = json.loads(json.dumps(fallback[case.case_id]))
            row.update({"pipeline": "validated_specialist", "handoff": "fallback",
                        "specialist_errors": stage.get("specialist_errors") or ([stage["error"]] if stage.get("error") else [])})
        else:
            row = {"case_id": case.case_id, "category": case.category, "pipeline": "validated_specialist", "handoff": "accepted"}
            try:
                graph = normalized_specialist_graph(case, stage["specialist"])
                plan = deterministic_tools(case)
                response, telemetry = call_ollama(args.base_url, args.reasoner_model, reasoner_prompt(case, graph, plan), FINAL_SCHEMA, 4096, 360)
                response["tool_plan"] = plan
                result = score(case, response)
                final_errors = validate_final_response(response, case)
                if final_errors and "wrong_source" not in result["hard_failures"]:
                    result["hard_failures"].append("wrong_source")
                row.update({"specialist": stage["specialist"], "specialist_errors": [],
                            "specialist_telemetry": stage.get("telemetry") or {},
                            "evidence_graph_sha256": hashlib.sha256(json.dumps(graph, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                            "graph_errors": validate_graph(graph, case), "final_errors": final_errors,
                            "response": response, "telemetry": telemetry, "score": result})
            except Exception as exc:
                row["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        completed[case.case_id] = row
        print(f"handoff {index}/50 {case.case_id} {row['handoff']} {row.get('score', {}).get('overall', 'ERROR')}", flush=True)
    rows = [completed[case.case_id] for case in cases()]
    summary = summarize_pipeline("validated_specialist", rows)
    summary.update({"reasoner_model": args.reasoner_model,
                    "accepted_handoffs": sum(row.get("handoff") == "accepted" for row in rows),
                    "fallbacks": sum(row.get("handoff") == "fallback" for row in rows)})
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    unload_model(args.base_url, args.reasoner_model)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
