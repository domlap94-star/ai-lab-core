from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_llm_qualification_cases import cases
from run_multi_model_pipeline_qualification import summarize_pipeline


def load(path: Path) -> dict[str, dict]:
    return {row["case_id"]: row for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--specialist-results", required=True)
    parser.add_argument("--canonical-fallback", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    specialist, fallback = load(Path(args.specialist_results)), load(Path(args.canonical_fallback))
    rows = []
    for case in cases():
        candidate = specialist[case.case_id]
        if candidate.get("handoff") == "accepted" and not candidate.get("error"):
            row = candidate
        else:
            row = json.loads(json.dumps(fallback[case.case_id]))
            row.update({"pipeline": "validated_specialist", "handoff": "fallback",
                        "specialist_errors": candidate.get("specialist_errors") or [],
                        "synthesis_error": candidate.get("error")})
        rows.append(row)
    output = Path(args.output)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    summary = summarize_pipeline("validated_specialist", rows)
    summary.update({"accepted_handoffs": sum(row.get("handoff") == "accepted" for row in rows),
                    "fallbacks": sum(row.get("handoff") == "fallback" for row in rows),
                    "bounded_synthesis_failures_fell_back": sum(bool(row.get("synthesis_error")) for row in rows)})
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
