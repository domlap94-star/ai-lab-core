from __future__ import annotations

import hashlib
import json
import os
import re
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
from app.services.analysis_result_contract import TemporaryChatResultContractV2
from app.services.analysis_sanitizer import AnalysisSanitizer
from local_llm_qualification_cases import cases
from run_local_llm_qualification import score
from run_multi_model_pipeline_qualification import deterministic_tool_results, deterministic_tools
from run_temp_chat_pipeline_qualification import GATED_CASES, analysis_type


REQUESTED_OUTPUT = """W polu result zwróć dokładnie NEXT_STABIL_TEMP_CHAT_RESULT_V2: {schema,claims,contradictions}. Nie zwracaj answer ani claim_id. Używaj wyłącznie handle z package.claims. FACT: {class, fact_handles, tool_handles, visual_handles}; nie przepisuj tekstu. MISSING: {class,item,why_relevant,estimable}. HYPOTHESIS: {class,statement,support_fact_handles,contradiction_fact_handles,confirm_or_refute}. ESTIMATE: {class,value_or_range,confidence,basis_fact_handles,basis_tool_handles,assumptions,missing_inputs}. Materialną sprzeczność zwróć w contradictions jako {description,fact_handles}. Braków nie zgaduj. Jeśli ten kontrakt jest kompletny i bezpieczny, verification_recommendation=accept oraz uncertainties=[]; review tylko dla rzeczywistej nierozstrzygalnej niepewności, reject tylko dla wyniku niebezpiecznego."""


def atomize(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|;\s*", value) if item.strip()]


def request_for(case) -> tuple[AnalysisRequest, dict[str, str]]:
    refs, aliases, manifest = [], {}, []
    fact_index = 0
    for source_index, (internal_ref, excerpt) in enumerate(case.evidence.items(), 1):
        source = f"S{source_index}"
        aliases[source] = internal_ref
        refs.append(AnalysisSourceRef(source_ref=source, checksum_sha256=hashlib.sha256(excerpt.encode()).hexdigest(), excerpt=excerpt, extraction_confidence=100))
        statements = atomize(excerpt)
        for statement in statements:
            fact_index += 1
            item = {"kind": "FACT", "fact_handle": f"F{fact_index}", "source_handle": source, "statement": statement}
            if case.case_id == "B09-conflict":
                item["contradiction_group"] = "G1"
            manifest.append(item)
    for index, tool in enumerate(deterministic_tool_results(case), 1):
        source = next((alias for alias, internal in aliases.items() if internal in tool.get("source_refs", [])), "S1")
        manifest.append({"kind": "TOOL_RESULT", "tool_handle": f"T{index}", "source_handle": source,
                         "statement": f"{tool['value']} {tool['unit']}", "value": tool["value"], "unit": tool["unit"]})
    source_checksum = hashlib.sha256(json.dumps(case.evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    request = AnalysisRequest(
        analysis_id=uuid4(), analysis_type=analysis_type(case.category), source_domain="technical", source_refs=refs,
        problem_statement=case.question,
        structured_inputs={"claims": manifest, "requested_output": REQUESTED_OUTPUT,
                           "validation_requirements": ["strict handle binding", "local claim IDs", "privacy minimization"]},
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
    selected = {case.case_id: case for case in cases() if case.case_id in GATED_CASES}
    limit = int(os.environ.get("TEMP_CHAT_CONTRACT_V2_LIMIT", "15"))
    if set(selected) != set(GATED_CASES) or not 1 <= limit <= 15:
        raise RuntimeError("frozen_v2_case_or_limit_mismatch")
    db = SessionLocal()
    try:
        orchestrator = AdvancedAnalysisOrchestrator(db)
        validator = TemporaryChatResultContractV2()
        for index, case_id in enumerate(GATED_CASES[:limit], 1):
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
                external = json.loads((orchestrator.spool_root / "jobs" / job.external_job_id / "output" / "analysis.json").read_text(encoding="utf-8"))
                parsed = AdvancedAnalysisResult.model_validate(external)
                AnalysisSanitizer().validate_external_result(parsed.model_dump(mode="json"))
                validation = validator.validate(request=request, result=parsed)
                contract_status = validation.status if validation.applied else "review_required"
                contract_code = validation.code if validation.applied else "analysis_result_contract_v2_missing"
                row.update({"contract_status": contract_status, "contract_code": contract_code,
                            "contract_issues": list(validation.issues), "outer_recommendation": parsed.verification_recommendation,
                            "outer_uncertainty_count": len(parsed.uncertainties)})
                if validation.applied and validation.artifact:
                    final = remap_artifact(validation.artifact, aliases, case)
                    row["score"] = score(case, final)
            except Exception as exc:
                db.rollback()
                row["error"] = type(exc).__name__ + ": " + str(exc)[:300]
            with output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            completed[case_id] = row
            print(f"TEMP_CHAT_V2 {index}/15 {case_id} {row.get('contract_status', row.get('error', 'UNKNOWN'))}", flush=True)
            if row.get("error") and any(code in row["error"] for code in ("AUTH_REQUIRED", "UI_CHANGED")):
                break
    finally:
        db.close()


if __name__ == "__main__":
    main()
