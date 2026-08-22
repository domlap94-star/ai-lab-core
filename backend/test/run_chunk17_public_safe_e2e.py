from __future__ import annotations

import hashlib
import os
import time
from uuid import uuid4

from test.support.database_safety import assert_isolated_database, require_test_database_environment


TEST_DATABASE_NAME = require_test_database_environment()
if os.environ.get("CHUNK17_PUBLIC_SAFE_E2E") != "1":
    raise RuntimeError("CHUNK17_PUBLIC_SAFE_E2E=1 is required")

from app.core.config import settings
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


def main() -> None:
    text = "Synthetic public rule: pressure equals force divided by area."
    checksum = hashlib.sha256(text.encode()).hexdigest()
    request = AnalysisRequest(
        analysis_id=uuid4(), analysis_type="formula_calculation", source_domain="calculation",
        source_refs=[AnalysisSourceRef(source_ref="S1", checksum_sha256=checksum, page=1,
                                       excerpt=text, extraction_confidence=100)],
        problem_statement="Calculate the synthetic pressure fixture.",
        structured_inputs={"expression": "force/area", "variables": {"force": 12, "area": .4},
                           "values": {"force": 12, "area": .4}, "expected_result": 30,
                           "result_unit": "kPa", "requested_output": "Return pressure in kPa."},
        units={"force": "kN", "area": "m2"}, formulas=["force/area"],
        constraints=["Expected deterministic result: 30 kPa"], evidence=["S1"],
        sensitivity="public_reference",
        allowed_methods=["deterministic_calculation", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum=checksum),
    )
    deliberately_insufficient = LocalAnalysisResult(
        analysis_id=request.analysis_id, processor_id="synthetic_insufficient_adapter",
        processor_version="v1", result={}, evidence_refs=["S1"], assumptions=[],
        unresolved_questions=["Controlled escalation acceptance."], detected_constraints=[],
        normalized_units={}, deterministic_checks=[
            DeterministicCheck(name="controlled_local_capability", passed=True)
        ], quality_signals=AnalysisQualitySignals(unsupported_operation=True),
        limitations=["Synthetic adapter intentionally lacks this operation."], confidence="low",
    )
    db = SessionLocal()
    previous = settings.advanced_analysis_enabled
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        settings.advanced_analysis_enabled = True
        orchestrator = AdvancedAnalysisOrchestrator(db)
        job = orchestrator.execute_local(
            request=request, local=deliberately_insufficient,
            source_entities={"S1": ("synthetic_public_fixture", "chunk17", 1)},
            actor_user_id=None,
        )
        db.commit()
        if not job.external_job_id:
            raise AssertionError(f"synthetic escalation not queued: {job.error_code}")
        deadline = time.monotonic() + 300
        terminal = None
        while time.monotonic() < deadline:
            state = orchestrator.supervisor.get_job(job.external_job_id)
            terminal = str(state.get("state") or "").upper()
            if terminal in {"COMPLETE", "AUTH_REQUIRED", "UI_CHANGED", "FAILED", "CANCELLED"}:
                break
            time.sleep(3)
        if terminal != "COMPLETE":
            print(f"PUBLIC_SAFE_TEMP_CHAT_STATE={terminal or 'TIMEOUT'}")
            raise RuntimeError(terminal or "TIMEOUT")
        final = orchestrator.apply_external(job=job, request=request)
        db.commit()
        if final != "accepted_advanced":
            raise AssertionError(f"public-safe advanced result not accepted: {job.error_code}")
        print("PUBLIC_SAFE_TEMP_CHAT_E2E=PASS")
        print("CUSTOMER_DATA_EXTERNALIZED=0")
        print("FINAL_STATE=accepted_advanced")
    finally:
        settings.advanced_analysis_enabled = previous
        db.close()


if __name__ == "__main__":
    main()
