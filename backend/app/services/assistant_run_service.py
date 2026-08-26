from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assistant_pipeline import AssistantRun, AssistantRunStage
from app.models.document_preparation_job import DocumentPreparationJob
from app.schemas.assistant_pipeline import (
    AssistantRunCreateRequest,
    AssistantRunListResponse,
    AssistantRunProgress,
    AssistantRunResponse,
    validate_bounded_json,
)
from app.schemas.unified_assistant import UnifiedAssistantResponse
from app.services.assistant_run_planner import (
    AssistantRunPlan,
    AssistantRunPlanner,
    EVIDENCE_CONTRACT_VERSION,
    ORCHESTRATOR_VERSION,
    POLICY_GENERATION,
)
from app.services.assistant_run_stage_service import AssistantRunStageService


class AssistantPipelineDisabled(RuntimeError):
    pass


class AssistantRunNotFound(RuntimeError):
    pass


class AssistantRunIdempotencyConflict(RuntimeError):
    pass


class AssistantRunActiveConflict(RuntimeError):
    pass


class AssistantRunService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def require_enabled() -> None:
        if not settings.assistant_pipeline_v2_enabled:
            raise AssistantPipelineDisabled("ASSISTANT_PIPELINE_V2_DISABLED")

    def create(
        self, *, request: AssistantRunCreateRequest, user_id: int
    ) -> AssistantRunResponse:
        self.require_enabled()
        plan = AssistantRunPlanner(self.db).plan(request)
        # One active V2 run per user is an explicit product policy.  Serialize
        # concurrent create calls without another schema change.
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :user_id)"),
            {"namespace": 20260826, "user_id": user_id},
        )
        request_payload = plan.request.model_dump(mode="json")
        validate_bounded_json(request_payload, field_name="request_payload")
        canonical = json.dumps({
            "request": request_payload,
            "orchestrator": ORCHESTRATOR_VERSION,
            "evidence_contract": EVIDENCE_CONTRACT_VERSION,
            "policy": POLICY_GENERATION,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        existing = self.db.query(AssistantRun).filter(
            AssistantRun.created_by_user_id == user_id,
            AssistantRun.attempt_id == request.attempt_id,
        ).one_or_none()
        if existing is not None:
            if existing.input_fingerprint != fingerprint:
                raise AssistantRunIdempotencyConflict("ATTEMPT_ID_REUSED")
            return self.response(existing)
        active = self.db.query(AssistantRun).filter(
            AssistantRun.created_by_user_id == user_id,
            AssistantRun.status.in_(["created", "queued", "running", "waiting"]),
        ).order_by(AssistantRun.created_at.desc()).first()
        if active is not None:
            raise AssistantRunActiveConflict(active.id)

        plan_json = plan.as_json()
        plan_hash = self._hash_json(plan_json)
        run = AssistantRun(
            id=str(uuid.uuid4()),
            created_by_user_id=user_id,
            attempt_id=request.attempt_id,
            api_version="assistant-runs-v2",
            orchestrator_version=ORCHESTRATOR_VERSION,
            evidence_contract_version=EVIDENCE_CONTRACT_VERSION,
            policy_generation=POLICY_GENERATION,
            input_fingerprint=fingerprint,
            request_payload=request_payload,
            target_scope=plan.target_scope,
            complexity=plan.complexity,
            status="queued",
            current_stage=self._first_work_stage(plan),
            plan=plan_json,
            plan_sha256=plan_hash,
            sensitivity=plan.sensitivity,
            priority=plan.priority,
        )
        self.db.add(run)
        AssistantRunStageService(self.db).create_plan(run, plan.stages)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(AssistantRun).filter(
                AssistantRun.created_by_user_id == user_id,
                AssistantRun.attempt_id == request.attempt_id,
            ).one()
            if existing.input_fingerprint != fingerprint:
                raise AssistantRunIdempotencyConflict("ATTEMPT_ID_REUSED")
            run = existing
        self.db.refresh(run)
        return self.response(run)

    def get_owned(self, *, run_id: str, user_id: int, lock: bool = False) -> AssistantRun:
        query = self.db.query(AssistantRun).filter(
            AssistantRun.id == run_id,
            AssistantRun.created_by_user_id == user_id,
        )
        if lock:
            query = query.with_for_update()
        run = query.one_or_none()
        if run is None:
            raise AssistantRunNotFound("ASSISTANT_RUN_NOT_FOUND")
        return run

    def get(self, *, run_id: str, user_id: int) -> AssistantRunResponse:
        self.require_enabled()
        return self.response(self.get_owned(run_id=run_id, user_id=user_id))

    def list_owned(
        self, *, user_id: int, active: bool = True, limit: int = 20
    ) -> AssistantRunListResponse:
        self.require_enabled()
        query = self.db.query(AssistantRun).filter(
            AssistantRun.created_by_user_id == user_id
        )
        if active:
            query = query.filter(AssistantRun.status.in_(["created", "queued", "running", "waiting"]))
        rows = query.order_by(AssistantRun.created_at.desc(), AssistantRun.id.desc()).limit(
            max(1, min(50, limit))
        ).all()
        return AssistantRunListResponse(items=[self.response(row) for row in rows])

    def cancel(self, *, run_id: str, user_id: int) -> AssistantRunResponse:
        self.require_enabled()
        run = self.get_owned(run_id=run_id, user_id=user_id, lock=True)
        if run.status in {"completed", "review_required", "failed", "cancelled"}:
            self.db.rollback()
            return self.response(run)
        AssistantRunStageService(self.db).cancel(run)
        self.db.commit()
        try:
            from app.services.assistant_run_dispatcher import cancel_active_run

            cancel_active_run(run.id)
        except Exception:
            pass
        self.db.refresh(run)
        return self.response(run)

    def finish(
        self,
        *,
        run: AssistantRun,
        response: UnifiedAssistantResponse,
    ) -> None:
        payload = response.model_dump(mode="json")
        validate_bounded_json(payload, field_name="result_payload")
        terminal = (
            "completed" if response.status in {"accepted_local", "accepted_advanced"}
            else "review_required" if response.status == "review_required"
            else "cancelled" if response.status == "cancelled"
            else "failed"
        )
        run.result_payload = payload
        run.result_payload_sha256 = self._hash_json(payload)
        run.status = terminal
        run.current_stage = None
        run.finished_at = datetime.now(UTC)
        run.heartbeat_at = run.finished_at
        self.db.flush()

    def response(self, run: AssistantRun) -> AssistantRunResponse:
        stage = None
        if run.current_stage:
            stage = self.db.query(AssistantRunStage).filter(
                AssistantRunStage.assistant_run_id == run.id,
                AssistantRunStage.stage_type == run.current_stage,
            ).order_by(AssistantRunStage.attempt.desc()).first()
        result = None
        if isinstance(run.result_payload, dict):
            result = UnifiedAssistantResponse.model_validate(run.result_payload)
        preparation = None
        if stage is not None and stage.document_preparation_job_id:
            preparation = self.db.get(
                DocumentPreparationJob, stage.document_preparation_job_id
            )
        projected_stage = self._projected_stage(run.current_stage, preparation)
        return AssistantRunResponse(
            run_id=run.id,
            attempt_id=run.attempt_id,
            status=run.status,
            current_stage=projected_stage,
            complexity=run.complexity,
            progress=AssistantRunProgress(
                current=stage.progress_current if stage else None,
                total=stage.progress_total if stage else None,
                unit=stage.progress_unit if stage else None,
                message=self._progress_message(run, stage, preparation),
            ),
            can_cancel=run.status in {"created", "queued", "running", "waiting"},
            poll_after_ms=1000 if run.status == "running" else 2500,
            recovery_generation=run.recovery_generation,
            result=result,
            error_code=stage.error_code if stage and run.status in {"failed", "review_required"} else None,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _first_work_stage(plan: AssistantRunPlan) -> str:
        return next(
            item["stage_type"] for item in plan.stages if item["stage_type"] != "planning"
        )

    @staticmethod
    def _hash_json(value: dict) -> str:
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _projected_stage(
        current_stage: str | None,
        preparation: DocumentPreparationJob | None,
    ) -> str | None:
        if current_stage != "waiting_for_material" or preparation is None:
            return current_stage
        return {
            "received": "waiting_for_material",
            "queued": "waiting_for_material",
            "validating": "preparing_material",
            "extracting": "preparing_material",
            "rendering": "preparing_material",
            "ocr_required": "waiting_for_vision",
            "ocr_processing": "preparing_material",
            "vision_processing": "analyzing_vision",
            "local_analysis": "building_intelligence",
            "indexing": "building_intelligence",
            "ready_for_ai": "validating_intelligence",
        }.get(preparation.stage, current_stage)

    @staticmethod
    def _progress_message(
        run: AssistantRun,
        stage: AssistantRunStage | None,
        preparation: DocumentPreparationJob | None = None,
    ) -> str:
        if run.status == "completed":
            return "Analiza zakończona."
        if run.status == "cancelled":
            return "Analiza została anulowana."
        if run.status in {"failed", "review_required"}:
            return "Analiza zakończyła się bez gotowej odpowiedzi."
        if run.current_stage == "waiting_for_material" and preparation is not None:
            preparation_messages = {
                "received": "Znalazłem dokument. Oczekuje na przygotowanie.",
                "queued": "Dokument czeka w kolejce do przygotowania.",
                "validating": "Sprawdzam plik i jego integralność.",
                "extracting": "Wyodrębniam treść dokumentu.",
                "rendering": "Przygotowuję strony dokumentu.",
                "ocr_required": "Dokument wymaga kontrolowanej analizy obrazu.",
                "ocr_processing": "Rozpoznaję treść skanu.",
                "vision_processing": "Analizuję materiał wizualny.",
                "local_analysis": "Tworzę techniczne podsumowanie dokumentu.",
                "indexing": "Porządkuję przygotowane informacje.",
                "ready_for_ai": "Dokument jest gotowy. Przygotowuję odpowiedź.",
            }
            return preparation_messages.get(
                preparation.stage,
                "Znalazłem dokument. Sprawdzam, czy jest gotowy.",
            )
        messages = {
            "resolving_targets": "Szukam właściwych materiałów.",
            "waiting_for_material": "Znalazłem dokument. Sprawdzam, czy jest gotowy.",
            "preparing_material": "Przygotowuję dokument do analizy.",
            "building_intelligence": "Tworzę techniczne podsumowanie dokumentu.",
            "validating_intelligence": "Sprawdzam przygotowane informacje i źródła.",
            "retrieving_case_evidence": "Zbieram dane dotyczące sprawy.",
            "retrieving_knowledge_base": "Sprawdzam bazę wiedzy.",
            "analyzing_local": "Analizuję zebrane dane lokalnie.",
            "reducing_findings": "Łączę wnioski z kilku źródeł.",
            "synthesizing": "Przygotowuję odpowiedź.",
            "validating_local": "Weryfikuję odpowiedź i źródła.",
            "waiting_for_vision": "Oczekuję na kontrolowaną analizę obrazu.",
            "analyzing_vision": "Analizuję materiał wizualny.",
            "waiting_for_advanced": "Oczekuję na kontrolowaną analizę rozszerzoną.",
            "analyzing_advanced": "Trwa kontrolowana analiza rozszerzona.",
            "validating_advanced": "Weryfikuję analizę rozszerzoną.",
            "finalizing": "Zapisuję gotowy wynik.",
        }
        return messages.get(run.current_stage or "", "Analiza jest w toku.")
