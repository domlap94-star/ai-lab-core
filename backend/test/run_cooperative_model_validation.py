from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from local_llm_qualification_cases import cases
from run_local_llm_qualification import THRESHOLDS
from run_multi_model_pipeline_qualification import call_ollama, validate_final_response


VALIDATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "REJECT"]},
        "flagged_claim_ids": {"type": "array", "items": {"type": "string"}},
        "reason_codes": {"type": "array", "items": {"type": "string", "enum": [
            "UNSUPPORTED_CLAIM", "WRONG_SOURCE", "CONTRADICTION", "ESTIMATE_DISCIPLINE",
            "MISSING_EVIDENCE", "PRIVACY", "INCOMPLETE", "NONE",
        ]}},
    },
    "required": ["verdict", "flagged_claim_ids", "reason_codes"],
    "additionalProperties": False,
}


def load_latest(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["case_id"]] = row
    return rows


def expected_reject(row: dict) -> bool:
    result = row.get("score") or {}
    factual_evidence = 0.5 * (result.get("factual", 0) + result.get("evidence", 0))
    return bool(
        row.get("error")
        or row.get("final_errors")
        or result.get("hard_failures")
        or result.get("foreign_sources")
        or not result.get("privacy", False)
        or result.get("overall", 0) < THRESHOLDS["overall"]
        or factual_evidence < THRESHOLDS["factual_evidence"]
    )


def validator_prompt(case, row: dict) -> str:
    candidate = json.loads(json.dumps(row.get("response") or {}))
    for index, claim in enumerate(candidate.get("claims") or [], 1):
        claim["claim_id"] = f"C{index:02d}"
    return (
        "Jesteś wyłącznie niezależnym walidatorem odpowiedzi NEXT Stabil. Nie poprawiaj ani nie "
        "przepisuj odpowiedzi. Źródłem prawdy jest EVIDENCE, nie zgoda modeli. Odrzuć wynik, gdy "
        "zawiera niepoparty fakt, zły source_ref, sprzeczność, nieobronioną estymatę, istotny brak "
        "albo naruszenie prywatności. flagged_claim_ids może zawierać wyłącznie identyfikatory z "
        "CANDIDATE.claims. Gdy brak problemu zwróć PASS, pustą listę i reason_codes=[\"NONE\"].\n"
        f"QUESTION: {case.question}\n"
        f"EVIDENCE: {json.dumps(case.evidence, ensure_ascii=False, sort_keys=True)}\n"
        f"CANDIDATE: {json.dumps(candidate, ensure_ascii=False, sort_keys=True)}\n"
        "Zwróć wyłącznie JSON."
    )


def run_validator(candidate: Path, output: Path, base_url: str, model: str, resume: bool) -> dict:
    candidate_rows = load_latest(candidate)
    if output.exists() and not resume:
        output.unlink()
    completed = load_latest(output) if resume and output.exists() else {}
    case_by_id = {item.case_id: item for item in cases()}
    for index, case in enumerate(cases(), 1):
        if case.case_id in completed:
            continue
        source = candidate_rows[case.case_id]
        row = {"case_id": case.case_id, "expected_reject": expected_reject(source)}
        try:
            response, telemetry = call_ollama(base_url, model, validator_prompt(case, source), VALIDATOR_SCHEMA, 4096, 180)
            valid_claim_ids = {f"C{index:02d}" for index, _ in enumerate((source.get("response") or {}).get("claims", []), 1)}
            flagged = set(map(str, response.get("flagged_claim_ids") or []))
            validation_errors = []
            if flagged - valid_claim_ids:
                validation_errors.append("invented_claim_id")
            if response.get("verdict") == "PASS" and response.get("reason_codes") != ["NONE"]:
                validation_errors.append("pass_reason_mismatch")
            row.update({"validator": response, "validation_errors": validation_errors, "telemetry": telemetry})
        except Exception as exc:
            row["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        completed[case.case_id] = row
        print(f"validator {index}/50 {case.case_id} {row.get('validator', {}).get('verdict', 'ERROR')}", flush=True)
    rows = list(completed.values())
    valid = [row for row in rows if not row.get("error") and not row.get("validation_errors")]
    tp = sum(row["expected_reject"] and row["validator"]["verdict"] == "REJECT" for row in valid)
    fp = sum(not row["expected_reject"] and row["validator"]["verdict"] == "REJECT" for row in valid)
    fn = sum(row["expected_reject"] and row["validator"]["verdict"] == "PASS" for row in valid)
    summary = {
        "candidate": str(candidate), "validator_model": model, "cases": len(rows), "valid": len(valid),
        "expected_rejects": sum(row["expected_reject"] for row in valid), "true_positive_rejects": tp,
        "false_positive_rejects": fp, "missed_failures": fn,
        "median_latency_seconds": round(statistics.median(row["telemetry"]["wall_seconds"] for row in valid), 2) if valid else None,
    }
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def cross_check(left_path: Path, right_path: Path, output: Path) -> dict:
    left, right = load_latest(left_path), load_latest(right_path)
    rows = []
    for case in cases():
        a, b = left[case.case_id], right[case.case_id]
        a_sources = set(map(str, (a.get("response") or {}).get("used_sources") or []))
        b_sources = set(map(str, (b.get("response") or {}).get("used_sources") or []))
        a_score, b_score = a.get("score") or {}, b.get("score") or {}
        material = bool(
            a_sources != b_sources
            or bool(a_score.get("hard_failures")) != bool(b_score.get("hard_failures"))
            or abs(a_score.get("factual", 0) - b_score.get("factual", 0)) >= 25
            or abs(a_score.get("evidence", 0) - b_score.get("evidence", 0)) >= 25
        )
        rows.append({"case_id": case.case_id, "classification": "DISAGREE" if material else "AGREE",
                     "material": material, "left_sources": sorted(a_sources), "right_sources": sorted(b_sources)})
    summary = {"cases": len(rows), "agreement": sum(not row["material"] for row in rows),
               "material_disagreement": sum(row["material"] for row in rows), "results": rows}
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", default="http://ollama:11434")
    parser.add_argument("--validator-model", default="phi4-mini:latest")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cross-check-other")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = run_validator(Path(args.candidate), output, args.base_url, args.validator_model, args.resume)
    if args.cross_check_other:
        summary["cross_check"] = cross_check(Path(args.candidate), Path(args.cross_check_other), output.with_suffix(".cross-check.json"))
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
