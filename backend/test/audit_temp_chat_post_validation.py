from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("TEMP_CHAT_CONTRACT_V2_QUALIFICATION", "1")
os.environ.setdefault("COOPERATIVE_TEMP_CHAT_QUALIFICATION", "1")

from app.database.session import SessionLocal
from app.models.knowledge_base import AnalysisJob
from app.schemas.analysis import AdvancedAnalysisResult
from app.services.analysis_result_contract import TemporaryChatResultContractV2
from app.services.analysis_sanitizer import AnalysisSanitizationError, AnalysisSanitizer
from local_llm_qualification_cases import cases
from run_local_llm_qualification import score
from run_temp_chat_contract_v2_qualification import GATED_CASES, remap_artifact, request_for


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only audit of the fixed 15-case Temporary Chat corpus.")
    parser.add_argument("--spool-root", default="/data/analysis-spool")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def jobs_by_case() -> dict[str, AnalysisJob]:
    db = SessionLocal()
    try:
        rows = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.processor_id == "temp_chat_contract_v2_qualification")
            .order_by(AnalysisJob.created_at.asc())
            .all()
        )
        if len(rows) != len(GATED_CASES):
            raise RuntimeError(f"v2_job_count_mismatch:{len(rows)}")
        return dict(zip(GATED_CASES, rows, strict=True))
    finally:
        db.close()


def audit(spool_root: Path) -> dict:
    case_map = {item.case_id: item for item in cases()}
    jobs = jobs_by_case()
    validator = TemporaryChatResultContractV2()
    rows: list[dict] = []
    for case_id in GATED_CASES:
        case = case_map[case_id]
        request, aliases = request_for(case)
        # The request UUID is locally assigned and does not affect handle/scope validation.
        job = jobs[case_id]
        path = spool_root / "jobs" / str(job.external_job_id) / "output" / "analysis.json"
        row = {"case_id": case_id, "external_job_id": job.external_job_id}
        if not path.is_file():
            row.update({"status": "failed", "code": "external_output_missing", "issues": ["result_binding"]})
            rows.append(row)
            continue
        try:
            parsed = AdvancedAnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
            AnalysisSanitizer().validate_external_result(parsed.model_dump(mode="json"))
        except (ValueError, AnalysisSanitizationError) as error:
            row.update({"status": "failed", "code": type(error).__name__, "issues": ["schema_or_privacy"]})
            rows.append(row)
            continue
        # Binding identifiers are verified by the production manifest path.  This
        # audit isolates the nested representation contract, so it intentionally
        # validates a request-equivalent copy with the saved result identifiers.
        request.analysis_id = parsed.analysis_id
        outcome = validator.validate(request=request, result=parsed)
        if not outcome.applied:
            row.update({"status": "review_required", "code": "analysis_result_contract_v2_missing",
                        "issues": ["legacy_or_unstructured_result"]})
        else:
            row.update({"status": outcome.status, "code": outcome.code, "issues": list(outcome.issues)})
            if outcome.artifact:
                row["score"] = score(case, remap_artifact(outcome.artifact, aliases, case))
        row.update({"schema": (parsed.result or {}).get("schema"),
                    "outer_recommendation": parsed.verification_recommendation,
                    "outer_uncertainty_count": len(parsed.uncertainties)})
        rows.append(row)
    counts = {name: sum(row["status"] == name for row in rows)
              for name in ("accepted_advanced", "review_required", "failed", "rejected")}
    accepted = [row for row in rows if row["status"] == "accepted_advanced" and row.get("score")]
    return {
        "schema": "NEXT_STABIL_TEMP_CHAT_POST_VALIDATION_AUDIT_V1",
        "case_count": len(rows),
        "new_external_submissions": 0,
        "counts": counts,
        "accepted_score_mean": (
            round(sum(row["score"]["overall"] for row in accepted) / len(accepted), 2) if accepted else None
        ),
        "accepted_factual_evidence_min": (
            min(min(row["score"]["factual"], row["score"]["evidence"]) for row in accepted) if accepted else None
        ),
        "rows": rows,
    }


def main() -> None:
    args = parse_args()
    result = audit(Path(args.spool_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
