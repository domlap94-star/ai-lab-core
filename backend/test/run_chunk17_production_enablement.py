from __future__ import annotations

import hashlib
import json
import os
import time
from uuid import uuid4

if os.environ.get("CHUNK17_PRODUCTION_ENABLE_ACCEPTANCE") != "1":
    raise RuntimeError("CHUNK17_PRODUCTION_ENABLE_ACCEPTANCE=1 is required")
case = os.environ.get("CHUNK17_PRODUCTION_ENABLE_CASE", "").strip().lower()
if case not in {"restricted", "public", "sanitizable", "local"}:
    raise RuntimeError("invalid CHUNK17_PRODUCTION_ENABLE_CASE")

from app.core.config import settings
from app.database.session import SessionLocal
from app.schemas.analysis import (
    AnalysisProvenance, AnalysisQualitySignals, AnalysisRequest, AnalysisSourceRef,
    DeterministicCheck, LocalAnalysisResult,
)
from app.services.advanced_analysis_orchestrator import AdvancedAnalysisOrchestrator


FAKE_IDENTIFIERS = (
    "Test Company Alpha", "Jan Testowy", "test@example.invalid",
    "+48 500 000 017", "ul. Testowa 1", "client_id=999999",
)


def build_request() -> AnalysisRequest:
    fixtures = {
        "public": ("Synthetic public rule: pressure equals force divided by area.", "public_reference", 10, .005, 2),
        "sanitizable": (
            "Company: Test Company Alpha; Imię: Jan Testowy; email test@example.invalid; "
            "telefon +48 500 000 017; ul. Testowa 1; client_id=999999; "
            "Synthetic rule: pressure equals force divided by area.",
            "customer_sanitizable", 15, .005, 3,
        ),
        "restricted": ("Synthetic restricted rule: pressure equals force divided by area.",
                       "restricted_never_external", 20, .005, 4),
        "local": ("Synthetic local rule: pressure equals force divided by area.",
                  "public_reference", 8, .004, 2),
    }
    excerpt, sensitivity, force, area, expected = fixtures[case]
    checksum = hashlib.sha256(excerpt.encode()).hexdigest()
    return AnalysisRequest(
        analysis_id=uuid4(), analysis_type="formula_calculation", source_domain="calculation",
        source_refs=[AnalysisSourceRef(source_ref="S1", checksum_sha256=checksum, page=1,
                                       excerpt=excerpt, extraction_confidence=100)],
        problem_statement="Calculate the bounded synthetic pressure fixture.",
        structured_inputs={"expression": "force/area", "variables": {"force": force, "area": area},
                           "values": {"force": force, "area": area}, "expected_result": expected,
                           "result_unit": "MPa", "requested_output": "Return pressure in MPa."},
        units={"force": "kN", "area": "m2"}, formulas=["force/area"],
        constraints=[f"Expected deterministic result: {expected} MPa"], evidence=["S1"],
        sensitivity=sensitivity, allowed_methods=["deterministic_calculation", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum=checksum),
    )


def insufficient(request: AnalysisRequest) -> LocalAnalysisResult:
    return LocalAnalysisResult(
        analysis_id=request.analysis_id, processor_id="production_enablement_fixture",
        processor_version="v1", result={}, evidence_refs=["S1"], assumptions=[],
        unresolved_questions=["Controlled production enablement acceptance."],
        detected_constraints=[], normalized_units={}, deterministic_checks=[
            DeterministicCheck(name="controlled_local_capability", passed=True)
        ], quality_signals=AnalysisQualitySignals(unsupported_operation=True),
        limitations=["Synthetic adapter intentionally lacks this operation."], confidence="low",
    )


def main() -> None:
    if not settings.advanced_analysis_enabled:
        raise RuntimeError("production advanced analysis flag is not enabled")
    if settings.database_url.rsplit("/", 1)[-1] != "ai_lab":
        raise RuntimeError("production acceptance must bind to canonical ai_lab ledger")
    request = build_request()
    db = SessionLocal()
    try:
        orchestrator = AdvancedAnalysisOrchestrator(db)
        if case == "sanitizable":
            sanitized = orchestrator.sanitizer.sanitize(request)
            if any(value.lower() in sanitized.canonical_json.lower() for value in FAKE_IDENTIFIERS):
                raise AssertionError("synthetic identifier remained in sanitized package")
            print(f"SANITIZED_PACKAGE_BYTES={len(sanitized.canonical_json.encode('utf-8'))}")
            print(f"SANITIZED_PACKAGE_SHA256={sanitized.sha256}")
            print("SANITIZED_IDENTIFIERS_REMAINING=0")
        if case == "local":
            job = orchestrator.execute(request=request,
                source_entities={"S1": ("synthetic_production_enablement", case, 1)}, actor_user_id=None)
        else:
            job = orchestrator.execute_local(request=request, local=insufficient(request),
                source_entities={"S1": ("synthetic_production_enablement", case, 1)}, actor_user_id=None)
        db.commit()
        print(f"ANALYSIS_ID={job.id}")
        print(f"LOCAL_DECISION={job.decision}")
        if case == "restricted":
            if job.status != "review_required" or job.external_job_id is not None:
                raise AssertionError("restricted request did not fail closed")
            print("EXTERNAL_SUBMISSION=0"); print("FINAL_STATE=review_required"); return
        if case == "local":
            if job.status != "accepted_local" or job.external_job_id is not None:
                raise AssertionError("sufficient local request was externalized")
            print("EXTERNAL_SUBMISSION=0"); print("FINAL_STATE=accepted_local"); return
        if job.decision != "ESCALATE_TEMP_CHAT" or not job.external_job_id:
            raise AssertionError(f"synthetic escalation not queued: {job.error_code}")
        rejected_external = os.environ.get("CHUNK17_EXPECT_NOT_EXTERNAL_JOB_ID")
        if rejected_external and job.external_job_id == rejected_external:
            raise AssertionError("old terminal external job was reused")
        print(f"EXTERNAL_JOB_ID={job.external_job_id}")
        deadline = time.monotonic() + 300
        terminal = "TIMEOUT"
        while time.monotonic() < deadline:
            state = orchestrator.supervisor.get_job(job.external_job_id)
            terminal = str(state.get("state") or "FAILED").upper()
            if terminal in {"COMPLETE", "AUTH_REQUIRED", "UI_CHANGED", "FAILED", "CANCELLED"}: break
            time.sleep(3)
        print(f"TEMPORARY_CHAT_STATE={terminal}")
        if terminal != "COMPLETE": raise RuntimeError(terminal)
        if case == "sanitizable":
            result_path = orchestrator.spool_root / "jobs" / job.external_job_id / "output" / "analysis.json"
            raw_text = result_path.read_text(encoding="utf-8")
            if any(value.lower() in raw_text.lower() for value in FAKE_IDENTIFIERS):
                raise AssertionError("synthetic identifier reintroduced by external result")
            kinds = orchestrator.sanitizer.detect_sensitive_kinds(json.loads(raw_text))
            print("RESULT_IDENTIFIERS_REINTRODUCED=0")
            print("RESULT_SENSITIVE_KINDS=" + ",".join(sorted(kinds)))
        final = orchestrator.apply_external(job=job, request=request)
        db.commit()
        if final != "accepted_advanced":
            raise AssertionError(f"advanced result not accepted: {job.error_code}")
        print("LOCAL_POST_VALIDATION=PASS")
        if case == "public":
            before = orchestrator.supervisor.get_job(job.external_job_id)
            same = orchestrator.execute_local(request=request, local=insufficient(request),
                source_entities={"S1": ("synthetic_production_enablement", case, 1)}, actor_user_id=None)
            if same.id != job.id or same.external_job_id != job.external_job_id:
                raise AssertionError("same analysis retry changed durable binding")
            repeated = orchestrator.apply_external(job=same, request=request)
            db.commit()
            after = orchestrator.supervisor.get_job(job.external_job_id)
            if repeated != "accepted_advanced" or before.get("attempt_count") != after.get("attempt_count"):
                raise AssertionError("same analysis retry duplicated browser execution")
            print("SAME_ANALYSIS_RETRY=PASS")
            print("DUPLICATE_BROWSER_SUBMISSION=0")
        print("FINAL_STATE=accepted_advanced")
    finally: db.close()


if __name__ == "__main__": main()
