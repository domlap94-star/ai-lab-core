from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.environ.get("TEMP_CHAT_CONTRACT_V2_QUALIFICATION") != "1":
    raise RuntimeError("TEMP_CHAT_CONTRACT_V2_QUALIFICATION=1 is required")

from app.database.session import SessionLocal
from app.schemas.analysis import AdvancedAnalysisResult, AnalysisProvenance, AnalysisQualitySignals, AnalysisRequest, AnalysisSourceRef, DeterministicCheck, LocalAnalysisResult
from app.services.advanced_analysis_orchestrator import AdvancedAnalysisOrchestrator
from app.services.assistant_advanced_manifest import build_advanced_manifest
from app.services.analysis_result_contract import TemporaryChatResultContractV2
from app.services.analysis_sanitizer import AnalysisSanitizer
from local_llm_qualification_cases import cases
from run_local_llm_qualification import score
from run_multi_model_pipeline_qualification import deterministic_tool_results, deterministic_tools
from run_temp_chat_pipeline_qualification import GATED_CASES, analysis_type


FIXTURE = Path(__file__).parent / "fixtures" / "temp_chat_result_contract_v2_regression.json"
TARGET_SCOPES = json.loads(FIXTURE.read_text(encoding="utf-8")).get("target_scopes", {})


def request_for(case) -> tuple[AnalysisRequest, dict[str, str]]:
    refs, aliases, source_rows = [], {}, []
    for source_index, (internal_ref, excerpt) in enumerate(case.evidence.items(), 1):
        source = f"S{source_index}"
        aliases[source] = internal_ref
        refs.append(AnalysisSourceRef(source_ref=source, checksum_sha256=hashlib.sha256(excerpt.encode()).hexdigest(), excerpt=excerpt, extraction_confidence=100))
        source_rows.append((source, internal_ref, excerpt))
    tool_payloads = [
        {
            "tool": tool.get("tool"),
            "data": {
                key: value for key, value in tool.items()
                if key not in {"source_refs", "tool_result_id", "tool"}
            },
            "source_keys": list(tool.get("source_refs") or []),
        }
        for tool in deterministic_tool_results(case)
    ]
    advanced_manifest = build_advanced_manifest(
        question=case.question,
        sources=source_rows,
        tool_payloads=tool_payloads,
        default_analysis_type=analysis_type(case.category),
    )
    target_scope = None
    if case.case_id in TARGET_SCOPES:
        definition = TARGET_SCOPES[case.case_id]
        inverse = {internal: handle for handle, internal in aliases.items()}
        target_scope = {
            "scope_handle": definition["scope_handle"],
            "allowed_source_handles": [inverse[item] for item in definition["allowed_sources"]],
            "global_source_handles": [inverse[item] for item in definition["global_sources"]],
        }
    source_checksum = hashlib.sha256(json.dumps(case.evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    structured = {"contract_version": TemporaryChatResultContractV2.SCHEMA,
                  "claims": advanced_manifest.claims,
                  "requested_output": advanced_manifest.requested_output,
                  "validation_requirements": advanced_manifest.validation_requirements}
    if target_scope:
        structured["target_scope"] = target_scope
    request = AnalysisRequest(
        analysis_id=uuid4(), analysis_type=advanced_manifest.analysis_type, source_domain="technical", source_refs=refs,
        problem_statement=case.question,
        structured_inputs=structured,
        evidence=list(aliases), sensitivity="customer_sanitizable" if case.case_id == "A05-privacy" else "public_reference",
        allowed_methods=["local_llm", "temporary_chat"], provenance=AnalysisProvenance(source_checksum=source_checksum),
    )
    return request, aliases


def insufficient(request: AnalysisRequest) -> LocalAnalysisResult:
    return LocalAnalysisResult(
        analysis_id=request.analysis_id, processor_id="temp_chat_contract_v2_qualification", processor_version="v2",
        result={}, evidence_refs=[item.source_ref for item in request.source_refs], assumptions=[],
        unresolved_questions=["Frozen benchmark case requires controlled escalation."], detected_constraints=[],
        normalized_units={}, deterministic_checks=[DeterministicCheck(name="synthetic_fixture", passed=True)],
        quality_signals=AnalysisQualitySignals(unsupported_operation=True), limitations=["Synthetic V2 qualification."], confidence="low",
    )


def remap_artifact(artifact: dict, aliases: dict[str, str], case) -> dict:
    claims = []
    for item in artifact["claims"]:
        claims.append({"class": item["class"], "text": item["text"],
                       "source_refs": [aliases[ref] for ref in item.get("source_refs", [])]})
    used = sorted({ref for item in claims for ref in item["source_refs"]})
    estimate_claim = next((item for item in artifact["claims"] if item["class"] == "ESTIMATE"), None)
    estimate = None
    if estimate_claim:
        estimate = {"value_or_range": estimate_claim["text"], "confidence": estimate_claim["confidence"],
                    "basis": estimate_claim.get("source_refs", []), "assumptions": estimate_claim["assumptions"],
                    "missing_inputs": estimate_claim["missing_inputs"]}
    return {"answer": artifact["answer"], "claims": claims, "used_sources": used,
            "tool_plan": deterministic_tools(case), "estimate": estimate}


def main() -> None:
    output = Path(os.environ.get("TEMP_CHAT_CONTRACT_V2_OUTPUT", "/app/test/reports/private/cooperative_qualification/temp-chat-v2-F0.jsonl"))
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = list(map(json.loads, output.read_text(encoding="utf-8").splitlines())) if output.exists() else []
    completed = {row["case_id"]: row for row in existing if row.get("contract_status")}
    all_selected = {case.case_id: case for case in cases() if case.case_id in GATED_CASES}
    requested = [item.strip() for item in os.environ.get("TEMP_CHAT_CONTRACT_V2_CASES", ",".join(GATED_CASES)).split(",") if item.strip()]
    limit = int(os.environ.get("TEMP_CHAT_CONTRACT_V2_LIMIT", str(len(requested))))
    if (set(all_selected) != set(GATED_CASES) or not requested
            or len(requested) != len(set(requested)) or set(requested) - set(GATED_CASES)
            or not 1 <= limit <= 15):
        raise RuntimeError("frozen_v2_case_or_limit_mismatch")
    selected = {case_id: all_selected[case_id] for case_id in requested[:limit]}
    db = SessionLocal()
    try:
        orchestrator = AdvancedAnalysisOrchestrator(db)
        validator = TemporaryChatResultContractV2()
        for index, case_id in enumerate(requested[:limit], 1):
            if case_id in completed:
                continue
            case = selected[case_id]
            request, aliases = request_for(case)
            row = {"case_id": case_id, "synthetic_public_safe": True}
            try:
                job = orchestrator.execute_local(
                    request=request, local=insufficient(request),
                    source_entities={alias: ("synthetic_temp_chat_v2", case_id, pos) for pos, alias in enumerate(aliases, 1)},
                    actor_user_id=None,
                )
                db.commit()
                row.update({"analysis_id": str(job.id), "external_job_id": job.external_job_id, "decision": job.decision})
                if job.decision != "ESCALATE_TEMP_CHAT" or not job.external_job_id:
                    raise RuntimeError("escalation_not_queued")
                deadline, state = time.monotonic() + 420, "TIMEOUT"
                while time.monotonic() < deadline:
                    state = str(orchestrator.supervisor.get_job(job.external_job_id).get("state") or "FAILED").upper()
                    if state in {"COMPLETE", "AUTH_REQUIRED", "UI_CHANGED", "FAILED", "CANCELLED"}:
                        break
                    time.sleep(3)
                row["external_state"] = state
                if state != "COMPLETE":
                    raise RuntimeError(state)
                artifact = json.loads((orchestrator.spool_root / "jobs" / job.external_job_id / "output" / "analysis.json").read_text(encoding="utf-8"))
                parsed = AdvancedAnalysisResult(
                    schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1",
                    analysis_id=request.analysis_id, package_sha256=job.sanitized_package_hash,
                    result=artifact["parsed_v2"], source_refs=TemporaryChatResultContractV2.allowed_source_refs(request),
                    assumptions=[], uncertainties=[], constraints_checked=[], normalized_units={},
                    formula_used=None, calculation_steps=[], verification_recommendation="accept",
                )
                AnalysisSanitizer().validate_external_result(parsed.model_dump(mode="json"))
                validation = validator.validate(request=request, result=parsed)
                contract_status = orchestrator.apply_external(job=job, request=request)
                db.commit()
                contract_code = validation.code if validation.applied else "analysis_result_contract_v2_missing"
                row.update({"contract_status": contract_status, "contract_code": contract_code,
                            "contract_issues": list(validation.issues), "outer_recommendation": parsed.verification_recommendation,
                            "outer_uncertainty_count": len(parsed.uncertainties),
                            "primary_v2": artifact.get("contract_version") == TemporaryChatResultContractV2.SCHEMA,
                            "result_bound": contract_status in {"accepted_advanced", "review_required", "failed"},
                            "format_retry_used": int(artifact.get("worker_attempt") or 1) > 1})
                if validation.applied and validation.artifact:
                    final = remap_artifact(validation.artifact, aliases, case)
                    row["score"] = score(case, final)
            except Exception as exc:
                db.rollback()
                row["error"] = type(exc).__name__ + ": " + str(exc)[:300]
            with output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            completed[case_id] = row
            print(f"TEMP_CHAT_V2 {index}/{len(selected)} {case_id} {row.get('contract_status', row.get('error', 'UNKNOWN'))}", flush=True)
            if row.get("error") and any(code in row["error"] for code in ("AUTH_REQUIRED", "UI_CHANGED")):
                break
    finally:
        db.close()


if __name__ == "__main__":
    main()
