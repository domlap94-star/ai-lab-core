from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.environ.get("COOPERATIVE_TEMP_CHAT_QUALIFICATION") != "1":
    raise RuntimeError("COOPERATIVE_TEMP_CHAT_QUALIFICATION=1 is required")

from app.database.session import SessionLocal
from app.schemas.analysis import (
    AnalysisProvenance,
    AnalysisQualitySignals,
    AnalysisRequest,
    AnalysisSourceRef,
    DeterministicCheck,
    LocalAnalysisResult,
)
from app.services.advanced_analysis_orchestrator import AdvancedAnalysisOrchestrator
from local_llm_qualification_cases import cases
from run_local_llm_qualification import score
from run_multi_model_pipeline_qualification import deterministic_tools, validate_final_response


GATED_CASES = (
    "B05-action", "B09-conflict", "T09-noestimate", "T10-water", "T11-load",
    "D02-code", "D04-absent", "D10-price", "X01-synthesis", "X02-latest",
    "X04-scope", "X05-commercial", "X10-action", "A04-fakeestimate", "A05-privacy",
)


def analysis_type(category: str) -> str:
    return {
        "technical": "technical_interpretation",
        "document": "document_interpretation",
        "cross_domain": "consistency_check",
        "adversarial": "technical_interpretation",
        "business": "consistency_check",
    }[category]


def request_for(case):
    refs, alias_to_ref = [], {}
    for index, (original_ref, excerpt) in enumerate(case.evidence.items(), 1):
        alias = f"S{index}"
        alias_to_ref[alias] = original_ref
        refs.append(AnalysisSourceRef(source_ref=alias, checksum_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
                                      excerpt=excerpt, extraction_confidence=100))
    source_checksum = hashlib.sha256(json.dumps(case.evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    requested = (
        "W polu result zwróć: answer string po polsku; claims array z class FACT/ESTIMATE/HYPOTHESIS/MISSING, "
        "text i source_refs wyłącznie S1..S8; used_sources array; tool_plan array; estimate object albo null. "
        "FACT musi mieć źródło. Braków nie zgaduj. Zachowaj minimalizację danych."
    )
    request = AnalysisRequest(
        analysis_id=uuid4(), analysis_type=analysis_type(case.category), source_domain="technical",
        source_refs=refs, problem_statement=case.question,
        structured_inputs={"requested_output": requested,
                           "validation_requirements": ["source binding", "estimate discipline", "privacy minimization"]},
        evidence=list(alias_to_ref), sensitivity="customer_sanitizable" if case.case_id == "A05-privacy" else "public_reference",
        allowed_methods=["local_llm", "temporary_chat"], provenance=AnalysisProvenance(source_checksum=source_checksum),
    )
    return request, alias_to_ref


def insufficient(request: AnalysisRequest) -> LocalAnalysisResult:
    return LocalAnalysisResult(
        analysis_id=request.analysis_id, processor_id="cooperative_qualification", processor_version="v1",
        result={}, evidence_refs=[item.source_ref for item in request.source_refs], assumptions=[],
        unresolved_questions=["Frozen benchmark case requires controlled escalation."], detected_constraints=[],
        normalized_units={}, deterministic_checks=[DeterministicCheck(name="synthetic_fixture", passed=True)],
        quality_signals=AnalysisQualitySignals(unsupported_operation=True),
        limitations=["Synthetic local result intentionally insufficient."], confidence="low",
    )


def remap_result(raw: dict, alias_to_ref: dict[str, str], case) -> dict:
    result = json.loads(json.dumps(raw))
    result["used_sources"] = [alias_to_ref[item] for item in result.get("used_sources") or [] if item in alias_to_ref]
    for claim in result.get("claims") or []:
        claim["source_refs"] = [alias_to_ref[item] for item in claim.get("source_refs") or [] if item in alias_to_ref]
    result["tool_plan"] = deterministic_tools(case)
    return result


def main() -> None:
    output = Path(os.environ.get("COOPERATIVE_TEMP_CHAT_OUTPUT", "/app/test/reports/private/cooperative_qualification/temp-chat-F0.jsonl"))
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = {}
    if output.exists():
        completed = {row["case_id"]: row for row in (json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip())}
    selected = {case.case_id: case for case in cases() if case.case_id in GATED_CASES}
    if set(selected) != set(GATED_CASES):
        raise RuntimeError("frozen_gated_case_mismatch")
    limit = int(os.environ.get("COOPERATIVE_TEMP_CHAT_LIMIT", "15"))
    if not 1 <= limit <= 15:
        raise RuntimeError("temporary_chat_limit_invalid")
    db = SessionLocal()
    try:
        orchestrator = AdvancedAnalysisOrchestrator(db)
        for index, case_id in enumerate(GATED_CASES[:limit], 1):
            if case_id in completed:
                continue
            case = selected[case_id]
            request, aliases = request_for(case)
            row = {"case_id": case_id, "category": case.category, "synthetic_public_safe": True}
            try:
                job = orchestrator.execute_local(
                    request=request, local=insufficient(request),
                    source_entities={alias: ("synthetic_pipeline_qualification", case_id, pos)
                                     for pos, alias in enumerate(aliases, 1)}, actor_user_id=None,
                )
                db.commit()
                row.update({"analysis_id": str(job.id), "external_job_id": job.external_job_id, "decision": job.decision})
                if job.decision != "ESCALATE_TEMP_CHAT" or not job.external_job_id:
                    raise RuntimeError("escalation_not_queued")
                deadline = time.monotonic() + 420
                state = "TIMEOUT"
                while time.monotonic() < deadline:
                    state = str(orchestrator.supervisor.get_job(job.external_job_id).get("state") or "FAILED").upper()
                    if state in {"COMPLETE", "AUTH_REQUIRED", "UI_CHANGED", "FAILED", "CANCELLED"}:
                        break
                    time.sleep(3)
                row["external_state"] = state
                if state != "COMPLETE":
                    raise RuntimeError(state)
                spool = orchestrator.spool_root / "jobs" / job.external_job_id / "output" / "analysis.json"
                external = json.loads(spool.read_text(encoding="utf-8"))
                status = orchestrator.apply_external(job=job, request=request)
                db.commit()
                row["post_validation"] = status
                if status != "accepted_advanced":
                    raise RuntimeError("external_post_validation_rejected")
                final = remap_result(external.get("result") or {}, aliases, case)
                final_errors = validate_final_response(final, case)
                result_score = score(case, final)
                if final_errors and "wrong_source" not in result_score["hard_failures"]:
                    result_score["hard_failures"].append("wrong_source")
                row.update({"response": final, "final_errors": final_errors, "score": result_score})
            except Exception as exc:
                db.rollback()
                row["error"] = type(exc).__name__ + ": " + str(exc)[:300]
            with output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            completed[case_id] = row
            print(f"TEMP_CHAT {index}/15 {case_id} {row.get('post_validation', row.get('error', 'UNKNOWN'))}", flush=True)
            if row.get("error") and any(code in row["error"] for code in ("AUTH_REQUIRED", "UI_CHANGED")):
                break
    finally:
        db.close()


if __name__ == "__main__":
    main()
