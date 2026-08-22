from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from test.support.database_safety import assert_isolated_database, require_test_database_environment


TEST_DATABASE_NAME = require_test_database_environment()

from app.database.session import SessionLocal
from app.core.config import settings
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource, KnowledgeBaseAnalysisArtifact
from app.schemas.analysis import (
    AnalysisProvenance, AnalysisQualitySignals, AnalysisRequest, AnalysisSourceRef,
    DeterministicCheck, LocalAnalysisResult,
)
from app.services.advanced_analysis_orchestrator import AdvancedAnalysisOrchestrator, AnalysisIdempotencyConflict


class SyntheticSupervisor:
    job_id = str(uuid4())
    def create_job(self, payload: dict) -> dict:
        return {"job_id": self.job_id, "state": "QUEUED", "attempt_count": 0}
    def get_job(self, job_id: str) -> dict:
        return {"job_id": job_id, "state": "COMPLETE"}


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def make_request(*, analysis_id=None, sensitivity="public_reference") -> AnalysisRequest:
    text = "Synthetic technical conflict: R = U / I, units V and A."
    checksum = hashlib.sha256(text.encode()).hexdigest()
    return AnalysisRequest(
        analysis_id=analysis_id or uuid4(), analysis_type="technical_interpretation",
        source_domain="knowledge_base",
        source_refs=[AnalysisSourceRef(source_ref="S1", checksum_sha256=checksum, page=1,
                                       excerpt=text, extraction_confidence=99)],
        problem_statement="Interpret the synthetic technical relation.",
        structured_inputs={}, units={}, formulas=["R = U / I"], constraints=[], evidence=["S1"],
        sensitivity=sensitivity, allowed_methods=["deterministic_parse", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum=checksum),
    )


def make_local(request: AnalysisRequest) -> LocalAnalysisResult:
    return LocalAnalysisResult(
        analysis_id=request.analysis_id, processor_id="synthetic", processor_version="v1",
        result={"formula": "R = U / I"}, evidence_refs=["S1"], assumptions=[],
        unresolved_questions=["Synthetic ambiguity"], detected_constraints=[], normalized_units={},
        deterministic_checks=[DeterministicCheck(name="source_present", passed=True)],
        quality_signals=AnalysisQualitySignals(model_uncertain=True), limitations=[], confidence="low",
    )


def main() -> None:
    db = SessionLocal()
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        db.query(KnowledgeBaseAnalysisArtifact).delete()
        db.query(AnalysisJobSource).delete()
        db.query(AnalysisJob).delete()
        db.commit()
        first_request = make_request()
        first = AdvancedAnalysisOrchestrator(db).execute_local(
            request=first_request, local=make_local(first_request),
            source_entities={"S1": ("synthetic_fixture", "1", 1)}, actor_user_id=None,
        )
        db.commit()
        require(first.status == "advanced_queued", "disabled runtime did not remain fail-closed")
        require(first.error_code == "analysis_runtime_disabled", "wrong disabled-runtime reason")
        same = AdvancedAnalysisOrchestrator(db).execute_local(
            request=first_request, local=make_local(first_request),
            source_entities={"S1": ("synthetic_fixture", "1", 1)}, actor_user_id=None,
        )
        require(same.id == first.id, "same analysis ID did not remain idempotent")
        require(db.query(AnalysisJob).count() == 1, "duplicate durable job created")
        changed_request = make_request(analysis_id=first_request.analysis_id)
        changed_request.problem_statement = "Changed immutable analysis input."
        try:
            AdvancedAnalysisOrchestrator(db).execute_local(
                request=changed_request, local=make_local(changed_request),
                source_entities={"S1": ("synthetic_fixture", "1", 1)}, actor_user_id=None,
            )
        except AnalysisIdempotencyConflict: pass
        else: raise AssertionError("same analysis ID accepted a different input fingerprint")
        concurrent_request = make_request()
        try:
            AdvancedAnalysisOrchestrator(db).execute_local(
                request=concurrent_request, local=make_local(concurrent_request),
                source_entities={"S1": ("synthetic_fixture", "1", 1)}, actor_user_id=None,
            )
        except AnalysisIdempotencyConflict: pass
        else: raise AssertionError("active fingerprint was cross-bound to another analysis ID")

        restricted_request = make_request(sensitivity="restricted_never_external")
        restricted = AdvancedAnalysisOrchestrator(db).execute_local(
            request=restricted_request, local=make_local(restricted_request),
            source_entities={"S1": ("synthetic_fixture", "2", 1)}, actor_user_id=None,
        )
        db.commit()
        require(restricted.status == "review_required", "restricted data did not fail closed")
        require(restricted.external_job_id is None, "restricted data reached external queue")

        previous_enabled = settings.advanced_analysis_enabled
        temporary_spool = Path(tempfile.mkdtemp(prefix="analysis-spool-"))
        try:
            settings.advanced_analysis_enabled = True
            calculation = make_request()
            calculation.analysis_type = "formula_calculation"
            calculation.structured_inputs = {
                "expression": "u/i", "expected_result": 23,
                "values": {"u": 230, "i": 10},
                "variables": {"u": 230, "i": 10},
                "requested_output": "calculate resistance",
            }
            calculation.formulas = ["u/i"]
            calculation_local = make_local(calculation)
            supervisor = SyntheticSupervisor()
            orchestrator = AdvancedAnalysisOrchestrator(db, supervisor=supervisor)
            orchestrator.spool_root = temporary_spool
            advanced = orchestrator.execute_local(
                request=calculation, local=calculation_local,
                source_entities={"S1": ("synthetic_fixture", "3", 1)}, actor_user_id=None,
            )
            db.commit()
            require(advanced.status == "advanced_queued" and advanced.external_job_id == supervisor.job_id,
                    "hard synthetic analysis was not externally queued")
            result_dir = temporary_spool / "jobs" / supervisor.job_id / "output"
            result_dir.mkdir(parents=True)
            result_dir.joinpath("analysis.json").write_text(json.dumps({
                "schema_version": "NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1",
                "analysis_id": str(calculation.analysis_id),
                "package_sha256": advanced.sanitized_package_hash,
                "result": {"value": 23}, "source_refs": ["S1"],
                "assumptions": [], "uncertainties": [], "constraints_checked": [],
                "normalized_units": {}, "formula_used": "u/i", "calculation_steps": ["230 / 10 = 23"],
                "verification_recommendation": "accept",
            }), encoding="utf-8")
            result_dir.joinpath("result_manifest.json").write_text(json.dumps({
                "job_id": supervisor.job_id,
                "analysis_id": str(calculation.analysis_id),
                "package_sha256": advanced.sanitized_package_hash,
                "format_retry_used": False,
            }), encoding="utf-8")
            require(orchestrator.apply_external(job=advanced, request=calculation) == "accepted_advanced",
                    "valid synthetic Temporary Chat result was not accepted")
            db.commit()
        finally:
            settings.advanced_analysis_enabled = previous_enabled
            shutil.rmtree(temporary_spool, ignore_errors=True)
        print("GLOBAL_ADVANCED_ANALYSIS_PERSISTENCE=PASS")
        print("ACTIVE_FINGERPRINT_IDEMPOTENCY=PASS")
        print("RESTRICTED_EXTERNALIZATION=0")
    finally:
        db.close()


if __name__ == "__main__":
    main()
