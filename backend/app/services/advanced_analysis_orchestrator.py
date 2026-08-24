from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource
from app.schemas.analysis import AdvancedAnalysisResult, AnalysisRequest, LocalAnalysisResult
from app.schemas.analysis import TEMP_CHAT_RESULT_CONTRACT_V1, TEMP_CHAT_RESULT_CONTRACT_V2
from app.services.analysis_result_contract import TemporaryChatResultContractV2
from app.services.analysis_post_validator import AnalysisPostValidator
from app.services.analysis_quality_gate import AnalysisQualityGate
from app.services.analysis_sanitizer import AnalysisSanitizationError, AnalysisSanitizer
from app.services.analysis_supervisor_client import AnalysisSupervisorClient, AnalysisSupervisorUnavailable
from app.services.analysis_processors import AnalysisProcessorRegistry


class AnalysisIdempotencyConflict(RuntimeError):
    pass


class AdvancedAnalysisOrchestrator:
    def __init__(self, db: Session, *, supervisor=None) -> None:
        self.db = db
        self.supervisor = supervisor or AnalysisSupervisorClient()
        self.gate = AnalysisQualityGate()
        self.sanitizer = AnalysisSanitizer()
        self.validator = AnalysisPostValidator()
        self.processors = AnalysisProcessorRegistry.canonical()
        self.spool_root = (Path(settings.data_dir) / "analysis-spool").resolve()

    @staticmethod
    def fingerprint(request: AnalysisRequest) -> str:
        value = request.model_dump(mode="json")
        value.pop("analysis_id", None)
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def execute_local(self, *, request: AnalysisRequest, local: LocalAnalysisResult,
                      source_entities: dict[str, tuple[str, str, int | None]], actor_user_id: int | None) -> AnalysisJob:
        fingerprint = self.fingerprint(request)
        existing = self.db.get(AnalysisJob, str(request.analysis_id))
        if existing is not None:
            if existing.input_fingerprint != fingerprint:
                raise AnalysisIdempotencyConflict("analysis_idempotency_conflict")
            return existing
        active_statuses = ["queued", "local_processing", "local_validating", "advanced_queued",
                           "advanced_processing", "awaiting_auth", "awaiting_ui_fix", "advanced_validating"]
        existing = self.db.query(AnalysisJob).filter(
            AnalysisJob.analysis_type == request.analysis_type,
            AnalysisJob.source_domain == request.source_domain,
            AnalysisJob.input_fingerprint == fingerprint,
            AnalysisJob.status.in_(active_statuses),
        ).first()
        if existing is not None:
            raise AnalysisIdempotencyConflict("analysis_active_fingerprint_conflict")
        savepoint = self.db.begin_nested()
        try:
            job = AnalysisJob(
                id=str(request.analysis_id), analysis_type=request.analysis_type,
                source_domain=request.source_domain, status="local_validating",
                sensitivity=request.sensitivity, processor_id=local.processor_id,
                processor_version=local.processor_version, model_identity=local.model_identity,
                input_fingerprint=fingerprint, quality_signals=local.quality_signals.model_dump(),
                created_by_user_id=actor_user_id, started_at=datetime.now(UTC),
            )
            self.db.add(job)
            for source in request.source_refs:
                entity_type, entity_id, page = source_entities[source.source_ref]
                self.db.add(AnalysisJobSource(
                    analysis_job_id=job.id, source_ref=source.source_ref,
                    source_domain=request.source_domain, source_entity_type=entity_type,
                    source_entity_id=entity_id, page_number=page,
                    checksum_sha256=source.checksum_sha256, sensitivity=request.sensitivity,
                ))
            self.db.flush()
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            existing = self.db.query(AnalysisJob).filter(
                AnalysisJob.analysis_type == request.analysis_type,
                AnalysisJob.source_domain == request.source_domain,
                AnalysisJob.input_fingerprint == fingerprint,
                AnalysisJob.status.in_(active_statuses),
            ).first()
            if existing is None: raise
            if existing.id != str(request.analysis_id):
                raise AnalysisIdempotencyConflict("analysis_active_fingerprint_conflict")
            return existing
        except Exception:
            savepoint.rollback()
            raise
        decision = self.gate.evaluate(request, local)
        job.decision = decision.decision
        job.error_code = None if decision.decision == "ACCEPT_LOCAL" else decision.code
        if decision.decision == "ACCEPT_LOCAL":
            job.status = "accepted_local"; job.finished_at = datetime.now(UTC)
        elif decision.decision in {"REVIEW_REQUIRED", "FAIL"}:
            job.status = "review_required" if decision.decision == "REVIEW_REQUIRED" else "failed"
            job.finished_at = datetime.now(UTC)
        else:
            self._enqueue_advanced(job, request)
        self.db.flush()
        return job

    def execute(
        self,
        *,
        request: AnalysisRequest,
        source_entities: dict[str, tuple[str, str, int | None]],
        actor_user_id: int | None,
    ) -> AnalysisJob:
        """Run the canonical local-first processor before the shared quality gate."""
        local = self.processors.process(request)
        return self.execute_local(
            request=request,
            local=local,
            source_entities=source_entities,
            actor_user_id=actor_user_id,
        )

    def _enqueue_advanced(self, job: AnalysisJob, request: AnalysisRequest) -> None:
        try:
            sanitized = self.sanitizer.sanitize(request)
        except AnalysisSanitizationError as error:
            job.status = "review_required"; job.decision = "REVIEW_REQUIRED"
            job.error_code = str(error)[:100]; job.finished_at = datetime.now(UTC); return
        job.sanitized_package_hash = sanitized.sha256
        job.sanitized_package_size = len(sanitized.canonical_json.encode())
        if not settings.advanced_analysis_enabled:
            job.status = "advanced_queued"; job.error_code = "analysis_runtime_disabled"; return
        incoming = self.spool_root / "incoming" / sanitized.sha256
        incoming.mkdir(parents=True, exist_ok=True)
        package_path = incoming / "package.json"
        package_path.write_text(sanitized.canonical_json + "\n", encoding="utf-8")
        try:
            external = self.supervisor.create_job({
                "request_key": job.input_fingerprint, "analysis_id": job.id,
                "analysis_type": job.analysis_type, "package_sha256": sanitized.sha256,
                "contract_version": sanitized.package.contract_version,
                "incoming_relative_path": f"incoming/{sanitized.sha256}/package.json",
            })
        except AnalysisSupervisorUnavailable:
            job.status = "advanced_queued"; job.error_code = "analysis_supervisor_unavailable"; return
        job.external_job_id = str(external["job_id"])
        job.reasoning_attempt_count = max(job.reasoning_attempt_count, int(external.get("attempt_count") or 0))
        job.status = "advanced_processing" if external.get("state") == "RUNNING" else "advanced_queued"
        job.error_code = None

    def apply_external(self, *, job: AnalysisJob, request: AnalysisRequest) -> str:
        if not job.external_job_id: return job.status
        external = self.supervisor.get_job(job.external_job_id)
        state = str(external.get("state") or "FAILED").upper()
        mapping = {"QUEUED": "advanced_queued", "RUNNING": "advanced_processing",
                   "AUTH_REQUIRED": "awaiting_auth", "UI_CHANGED": "awaiting_ui_fix",
                   "CANCELLED": "cancelled", "FAILED": "failed"}
        if state != "COMPLETE":
            job.status = mapping.get(state, "failed")
            job.error_code = str(external.get("error_code") or state).lower()[:100]
            self.db.flush(); return job.status
        result_path = self.spool_root / "jobs" / job.external_job_id / "output" / "analysis.json"
        manifest_path = result_path.with_name("result_manifest.json")
        if not manifest_path.is_file():
            job.status = "failed"; job.decision = "rejected"
            job.error_code = "analysis_result_manifest_missing"; job.finished_at = datetime.now(UTC)
            self.db.flush(); return job.status
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        requested_contract = str(
            request.structured_inputs.get("contract_version") or TEMP_CHAT_RESULT_CONTRACT_V1
        )
        expected_manifest = {
            "job_id": job.external_job_id,
            "analysis_id": job.id,
            "package_sha256": job.sanitized_package_hash,
        }
        if any(str(manifest.get(key)) != str(value) for key, value in expected_manifest.items()):
            job.status = "failed"; job.decision = "rejected"
            job.error_code = "analysis_result_manifest_binding_invalid"; job.finished_at = datetime.now(UTC)
            self.db.flush(); return job.status
        raw_bytes = result_path.read_bytes()
        raw = json.loads(raw_bytes)
        if requested_contract == TEMP_CHAT_RESULT_CONTRACT_V2:
            expected_keys = {
                "schema_version", "job_id", "request_id", "contract_version",
                "worker_attempt", "created_at", "raw_result_hash", "parsed_v2",
                "validation_pending",
            }
            if (manifest.get("contract_version") != TEMP_CHAT_RESULT_CONTRACT_V2
                    or manifest.get("request_id") != job.id
                    or manifest.get("output_sha256") != hashlib.sha256(raw_bytes).hexdigest()
                    or manifest.get("raw_result_hash") != raw.get("raw_result_hash")
                    or set(raw) != expected_keys
                    or raw.get("schema_version") != "NEXT_STABIL_TEMP_CHAT_RESULT_ARTIFACT_V2"
                    or raw.get("job_id") != job.external_job_id
                    or raw.get("request_id") != job.id
                    or raw.get("contract_version") != TEMP_CHAT_RESULT_CONTRACT_V2
                    or raw.get("validation_pending") is not True
                    or raw.get("worker_attempt") not in {1, 2}
                    or not isinstance(raw.get("created_at"), str)
                    or not raw.get("created_at")
                    or not isinstance(raw.get("raw_result_hash"), str)
                    or len(raw.get("raw_result_hash")) != 64
                    or any(char not in "0123456789abcdef" for char in raw.get("raw_result_hash"))):
                job.status = "failed"; job.decision = "rejected"
                job.error_code = "analysis_v2_result_binding_invalid"; job.finished_at = datetime.now(UTC)
                self.db.flush(); return job.status
            local_envelope = AdvancedAnalysisResult(
                schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1",
                analysis_id=request.analysis_id,
                package_sha256=job.sanitized_package_hash or "",
                result=raw["parsed_v2"],
                source_refs=[item.source_ref for item in request.source_refs],
                assumptions=[], uncertainties=[], constraints_checked=[],
                normalized_units={}, formula_used=None, calculation_steps=[],
                verification_recommendation="accept",
            )
            try:
                self.sanitizer.validate_external_result(local_envelope.model_dump(mode="json"))
            except AnalysisSanitizationError as error:
                job.status = "review_required"; job.decision = "REVIEW_REQUIRED"
                job.error_code = str(error)[:100]; job.finished_at = datetime.now(UTC)
                self.db.flush(); return job.status
            contract = TemporaryChatResultContractV2().validate(request=request, result=local_envelope)
            if not contract.applied:
                job.status = "failed"; job.decision = "rejected"
                job.error_code = "analysis_v2_interoperability_failure"; job.finished_at = datetime.now(UTC)
                self.db.flush(); return job.status
            job.status = {"accepted_advanced": "accepted_advanced", "review_required": "review_required", "rejected": "failed"}[contract.status]
            job.decision = contract.status
            job.error_code = None if contract.status == "accepted_advanced" else contract.code
            job.finished_at = datetime.now(UTC)
            self.db.flush(); return job.status
        try:
            result = AdvancedAnalysisResult.model_validate(raw)
        except ValidationError:
            job.status = "failed"; job.decision = "rejected"
            job.error_code = "analysis_result_schema_invalid"; job.finished_at = datetime.now(UTC)
            self.db.flush(); return job.status
        try:
            self.sanitizer.validate_external_result(result.model_dump(mode="json"))
        except AnalysisSanitizationError as error:
            job.status = "review_required"; job.decision = "REVIEW_REQUIRED"
            job.error_code = str(error)[:100]; job.finished_at = datetime.now(UTC)
            self.db.flush(); return job.status
        validation = self.validator.validate(request=request, result=result, package_sha256=job.sanitized_package_hash or "")
        job.status = {"accepted_advanced": "accepted_advanced", "review_required": "review_required", "rejected": "failed"}[validation.status]
        job.decision = validation.status
        job.error_code = None if validation.status == "accepted_advanced" else validation.code
        job.finished_at = datetime.now(UTC)
        self.db.flush(); return job.status
