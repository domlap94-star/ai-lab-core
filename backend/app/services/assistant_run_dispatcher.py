from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.ai.clients.ollama_client import OllamaClient
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.assistant_pipeline import (
    AssistantRun,
    AssistantRunStage,
    DocumentIntelligenceArtifact,
)
from app.models.document import Document
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.knowledge_base import AnalysisJob, KnowledgeBaseItem
from app.schemas.unified_assistant import (
    UnifiedAssistantRequest,
    UnifiedAssistantResponse,
    UnifiedClaim,
    UnifiedSource,
)
from app.services.assistant_run_material_service import AssistantRunMaterialService
from app.services.assistant_run_service import AssistantRunService
from app.services.assistant_run_stage_service import AssistantRunStageService
from app.services.document_intelligence_service import (
    ANALYZER_GENERATION,
    DocumentIntelligenceService,
)
from app.services.document_preparation_service import (
    DocumentPreparationService,
    PROCESSOR_GENERATION,
)
from app.services.local_model_resource_coordinator import LocalModelEmergencyAbort
from app.services.local_model_time_policy import (
    DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS,
    STANDARD_LOCAL_ABSOLUTE_SECONDS,
    V2_LOCAL_NUM_THREAD,
    V2_STANDARD_INITIAL_NUM_PREDICT,
    V2_STANDARD_TRUNCATION_RETRY_NUM_PREDICT,
    utc_iso,
)
from app.services.unified_assistant_service import UnifiedAssistantService


logger = logging.getLogger("ai_lab.assistant_pipeline_v2")
_ACTIVE_TASKS: dict[str, asyncio.Task] = {}


def cancel_active_run(run_id: str) -> None:
    task = _ACTIVE_TASKS.get(run_id)
    if task is not None and not task.done():
        task.cancel()


class StageStreamingOllamaClient:
    """Route V2 local calls through NDJSON and persist telemetry only."""

    def __init__(self, run_id: str, stage_id: str) -> None:
        self.run_id = run_id
        self.stage_id = stage_id
        self.base = OllamaClient()
        self._progress_lock = asyncio.Lock()
        self._last_progress_persisted_at = 0.0
        self._model: str | None = None
        self._phase: str | None = None
        self._phase_started_at: str | None = None

    async def generate(self, **kwargs) -> dict[str, Any]:
        self._model = str(kwargs["model"])
        await self._transition_phase("model_load")
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            result = await self.base.generate_streaming(
                model=kwargs["model"],
                prompt=kwargs["prompt"],
                format=kwargs.get("format"),
                options=kwargs.get("options"),
                think=kwargs.get("think"),
                keep_alive=kwargs.get("keep_alive"),
                on_progress=self._progress,
            )
            await self._transition_phase("validation")
            return result
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass

    async def unload(self, model: str) -> None:
        await self.base.unload(model)

    def resource_session(
        self,
        model: str,
        *,
        wait_timeout: float | None = None,
        on_wait=None,
        on_ready=None,
    ):
        async def combined_wait(reason: str) -> None:
            await self._resource_wait(reason)
            if on_wait is not None:
                result = on_wait(reason)
                if inspect.isawaitable(result):
                    await result

        async def combined_ready(reason: str) -> None:
            await self._resource_ready(reason)
            if on_ready is not None:
                result = on_ready(reason)
                if inspect.isawaitable(result):
                    await result

        return self.base.resource_session(
            model,
            wait_timeout=wait_timeout,
            on_wait=combined_wait,
            on_ready=combined_ready,
        )

    async def _resource_wait(self, reason: str) -> None:
        await asyncio.to_thread(self._persist_resource_state, reason, False)

    async def _resource_ready(self, reason: str) -> None:
        await asyncio.to_thread(self._persist_resource_state, reason, True)

    def _persist_resource_state(self, reason: str, ready: bool) -> None:
        db = SessionLocal()
        try:
            run = db.get(AssistantRun, self.run_id)
            stage = db.get(AssistantRunStage, self.stage_id)
            if run is None or stage is None or run.status == "cancelled" or run.cancel_requested_at:
                raise asyncio.CancelledError
            stages = AssistantRunStageService(db)
            manifest = dict(stage.result_manifest or {})
            manifest["local_resource"] = {
                "state": "admitted" if ready else "waiting",
                "reason": reason[:80],
            }
            if ready:
                stages.start(run, stage.stage_type)
                stages.progress(stage, manifest=manifest, substantive=False)
            else:
                stages.wait(run, stage.stage_type, manifest=manifest)
            db.commit()
        finally:
            db.close()

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(15)
            if self._phase == "model_load" and self._model:
                try:
                    residents = await self.base.resource_coordinator.provider.resident_models()
                    if any(item.name == self._model for item in residents):
                        await self._transition_phase("prompt_evaluation")
                except Exception:
                    # The independent resource monitor remains fail-closed. A
                    # transient residency probe cannot fabricate model progress.
                    pass
            await asyncio.to_thread(self._persist, None, False)

    async def _progress(self, telemetry: dict[str, int | bool | str]) -> None:
        # Ollama commonly emits one NDJSON event per generated token.  Durable
        # progress must be fresh, but a database transaction per token would
        # create avoidable pool/IO pressure.  Persist at a bounded cadence and
        # always persist the terminal event.
        if self._phase != "generation":
            self._phase = "generation"
            self._phase_started_at = utc_iso()
        now = time.monotonic()
        if not telemetry.get("done") and now - self._last_progress_persisted_at < 2.0:
            return
        async with self._progress_lock:
            now = time.monotonic()
            if not telemetry.get("done") and now - self._last_progress_persisted_at < 2.0:
                return
            await asyncio.to_thread(self._persist, telemetry, True)
            self._last_progress_persisted_at = now

    async def _transition_phase(self, phase: str) -> None:
        if self._phase == phase:
            return
        self._phase = phase
        self._phase_started_at = utc_iso()
        await asyncio.to_thread(self._persist_phase, phase)

    def _persist_phase(self, phase: str) -> None:
        db = SessionLocal()
        try:
            run = db.get(AssistantRun, self.run_id)
            stage = db.get(AssistantRunStage, self.stage_id)
            if run is None or stage is None or run.status == "cancelled" or run.cancel_requested_at:
                raise asyncio.CancelledError
            manifest = dict(stage.result_manifest or {})
            manifest["local_model_phase"] = {
                "phase": phase,
                "started_at": self._phase_started_at or utc_iso(),
            }
            AssistantRunStageService(db).progress(
                stage,
                manifest=manifest,
                substantive=True,
            )
            db.commit()
        finally:
            db.close()

    def _persist(
        self, telemetry: dict[str, int | bool | str] | None, substantive: bool
    ) -> None:
        db = SessionLocal()
        try:
            run = db.get(AssistantRun, self.run_id)
            stage = db.get(AssistantRunStage, self.stage_id)
            if run is None or stage is None or run.status == "cancelled" or run.cancel_requested_at:
                raise asyncio.CancelledError
            manifest = dict(stage.result_manifest or {})
            if self._phase and self._phase_started_at:
                manifest["local_model_phase"] = {
                    "phase": self._phase,
                    "started_at": self._phase_started_at,
                }
            if telemetry:
                manifest["ollama"] = {
                    key: value for key, value in telemetry.items()
                    if key in {
                        "chunks", "done", "load_duration", "prompt_eval_count",
                        "prompt_eval_duration", "eval_count", "eval_duration", "total_duration",
                        "done_reason",
                    }
                }
            AssistantRunStageService(db).progress(
                stage,
                current=(int(telemetry.get("eval_count", telemetry.get("chunks", 0))) if telemetry else None),
                unit="tokens" if telemetry and "eval_count" in telemetry else "chunks",
                manifest=manifest,
                substantive=substantive,
            )
            db.commit()
        finally:
            db.close()


def _claim_next_run() -> str | None:
    db = SessionLocal()
    try:
        stages = AssistantRunStageService(db)
        stages.recover_expired()
        run = db.query(AssistantRun).filter(
            AssistantRun.status.in_(["created", "queued", "waiting"]),
            AssistantRun.cancel_requested_at.is_(None),
        ).order_by(
            AssistantRun.priority.asc(), AssistantRun.created_at.asc(), AssistantRun.id.asc()
        ).with_for_update(skip_locked=True).first()
        if run is None:
            db.commit()
            return None
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        run.heartbeat_at = datetime.now(UTC)
        db.commit()
        return run.id
    finally:
        db.close()


def _timeout_code(run_id: str) -> str | None:
    db = SessionLocal()
    try:
        return AssistantRunStageService(db).timeout_code(run_id)
    finally:
        db.close()


def _record_interruption(run_id: str, error_code: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(AssistantRun, run_id)
        if run is None or run.status == "cancelled" or not run.current_stage:
            db.rollback()
            return
        AssistantRunStageService(db).retry_or_fail(run, run.current_stage, error_code)
        db.commit()
    finally:
        db.close()


def _record_resource_abort(run_id: str, error_code: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(AssistantRun, run_id)
        if run is None or run.status == "cancelled" or not run.current_stage:
            db.rollback()
            return
        AssistantRunStageService(db).retry_or_fail(
            run, run.current_stage, error_code
        )
        db.commit()
    finally:
        db.close()


def _review_response(run_id: str, message: str, stage: str) -> UnifiedAssistantResponse:
    return UnifiedAssistantResponse(
        request_id=run_id,
        answer="",
        status="review_required",
        progress="complete",
        target_scope="TARGET_01",
        claims=[],
        sources=[],
        used_tools=[],
        model=None,
        error_message=message,
        current_stage=stage,
        can_cancel=False,
    )


def _kb_catalog_response(run_id: str) -> UnifiedAssistantResponse:
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeBaseItem).filter(
            KnowledgeBaseItem.status == "current",
            KnowledgeBaseItem.archived_at.is_(None),
            KnowledgeBaseItem.processing_status == "processed",
        ).order_by(KnowledgeBaseItem.category, KnowledgeBaseItem.title).limit(12).all()
        if not rows:
            return _review_response(
                run_id,
                "Brak bieżących, gotowych materiałów w bazie wiedzy.",
                "retrieving_knowledge_base",
            )
        categories = sorted({row.category for row in rows})
        titles = [row.title for row in rows[:8]]
        answer = (
            "Baza wiedzy zawiera bieżące materiały w kategoriach: "
            + ", ".join(categories)
            + ". Przykładowe gotowe materiały: "
            + "; ".join(titles)
            + ". Wskaż temat lub konkretny tytuł, a przeanalizuję właściwe źródła."
        )
        claims = [UnifiedClaim(
            claim_id="C01",
            claim_class="FACT",
            text="Wymienione materiały są bieżącymi i przetworzonymi pozycjami bazy wiedzy.",
            source_refs=[f"K{index:02d}" for index in range(1, len(rows) + 1)],
        )]
        sources = [UnifiedSource(
            source_ref=f"K{index:02d}",
            source_type="knowledge_base",
            source_id=row.id,
            title=row.title,
            excerpt=f"Kategoria: {row.category}; status: bieżący i przetworzony.",
            why_used="Pozycja bieżącego katalogu bazy wiedzy.",
            supports_claim_ids=["C01"],
            route=f"/settings/knowledge-base?item={row.id}",
        ) for index, row in enumerate(rows, 1)]
        return UnifiedAssistantResponse(
            request_id=run_id,
            answer=answer,
            status="accepted_local",
            progress="complete",
            target_scope="TARGET_01",
            claims=claims,
            sources=sources,
            used_tools=["knowledge_base_catalog"],
            model=None,
            current_stage="knowledge_base_catalog",
            can_cancel=False,
        )
    finally:
        db.close()


async def _execute_run(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.query(AssistantRun).filter(AssistantRun.id == run_id).with_for_update().one_or_none()
        if run is None or run.status == "cancelled":
            db.rollback()
            return
        request = UnifiedAssistantRequest.model_validate(run.request_payload)
        plan = run.plan or {}
        intent = str(plan.get("intent") or "evidence_reasoning")
        resuming_advanced = run.current_stage == "waiting_for_advanced"
        stage_service = AssistantRunStageService(db)

        if intent == "system_meta":
            stage_service.start(run, "finalizing")
            response = await UnifiedAssistantService(db).ask(request=request, user_id=run.created_by_user_id)
            response = response.model_copy(update={"request_id": run.id})
            result_hash = AssistantRunService._hash_json(response.model_dump(mode="json"))
            stage_service.complete(
                run, "finalizing", result_kind="final_response",
                result_manifest={
                    "result_payload_sha256": result_hash,
                    "model_identity": "deterministic_system_manifest",
                    "model_contract": {"streaming": False},
                },
            )
            AssistantRunService(db).finish(run=run, response=response)
            db.commit()
            return

        if intent == "knowledge_base_catalog":
            stage_service.start(run, "retrieving_knowledge_base")
            db.commit()
            response = _kb_catalog_response(run.id)
            db.expire_all()
            run = db.get(AssistantRun, run_id)
            if run is None or run.status == "cancelled":
                db.rollback()
                return
            stage_service.complete(
                run, "retrieving_knowledge_base",
                result_manifest={"source_count": len(response.sources), "mode": "catalog"},
            )
            stage_service.start(run, "finalizing")
            result_hash = AssistantRunService._hash_json(response.model_dump(mode="json"))
            stage_service.complete(
                run, "finalizing", result_kind="final_response",
                result_manifest={
                    "result_payload_sha256": result_hash,
                    "model_identity": "deterministic_kb_catalog",
                    "model_contract": {"streaming": False},
                },
            )
            AssistantRunService(db).finish(run=run, response=response)
            db.commit()
            return

        service = UnifiedAssistantService(db)
        stage_service.start(run, "resolving_targets")
        resolution = service._resolve_required_document(request)
        if resolution is not None and resolution.state not in {"EXACT_MATCH", "UNIQUE_MATCH"}:
            response = service._document_resolution_response(request, resolution).model_copy(
                update={"request_id": run.id}
            )
            stage_service.complete(
                run, "resolving_targets",
                result_manifest={"resolution": resolution.state},
            )
            for name in (
                "waiting_for_material", "building_intelligence", "validating_intelligence",
                "retrieving_case_evidence", "retrieving_knowledge_base", "analyzing_local",
                "reducing_findings", "synthesizing", "validating_local",
                "waiting_for_advanced", "analyzing_advanced", "validating_advanced",
            ):
                stage_service.skip(run, name, "TERMINAL_TARGET_RESOLUTION")
            stage_service.start(run, "finalizing")
            stage_service.complete(run, "finalizing", result_kind="final_response")
            AssistantRunService(db).finish(run=run, response=response)
            db.commit()
            return
        if resolution is not None and resolution.document_id is not None:
            request = request.model_copy(update={"document_id": resolution.document_id})
            run.request_payload = request.model_dump(mode="json")
            run.target_scope = {**run.target_scope, "document_id": resolution.document_id}
        stage_service.complete(
            run, "resolving_targets",
            result_manifest={
                "document_resolution": resolution.state if resolution else "not_required",
                "document_id": resolution.document_id if resolution else request.document_id,
            },
        )

        artifact: DocumentIntelligenceArtifact | None = None
        document: Document | None = None
        if request.document_id is not None:
            document = db.get(Document, request.document_id)
            if document is None or (
                request.client_id is not None and document.client_id not in {None, request.client_id}
            ):
                raise ValueError("DOCUMENT_SCOPE_INVALID")
            checksum = (document.checksum_sha256 or "").casefold()
            artifact = DocumentIntelligenceService(db).accepted_baseline(
                document_id=document.id, checksum=checksum
            )
            preparation: DocumentPreparationJob | None = None
            if artifact is None:
                preparation, _ = DocumentPreparationService(db).get_or_create(
                    document=document,
                    trigger="assistant",
                    priority=0,
                    created_by_user_id=run.created_by_user_id,
                )
                if preparation.status in {"failed", "unsupported", "integrity_failed"}:
                    response = _review_response(
                        run.id,
                        "Nie udało się bezpiecznie przygotować dokumentu do analizy.",
                        preparation.stage,
                    )
                    AssistantRunMaterialService(db).attach_document(
                        run_id=run.id, document=document, required=True,
                        preparation_job_id=preparation.id, artifact=None,
                    )
                    stage_service.fail(run, "waiting_for_material", preparation.error_code or "MATERIAL_FAILED")
                    run.status = "review_required"
                    AssistantRunService(db).finish(run=run, response=response)
                    db.commit()
                    return
                if preparation.status == "ready":
                    artifact = DocumentIntelligenceService(db).accepted_baseline(
                        document_id=document.id, checksum=checksum
                    )
                    if artifact is None:
                        response = _review_response(
                            run.id,
                            "Dokument ma treść, ale nie ma zwalidowanej inteligencji dla bieżącej wersji.",
                            "building_intelligence",
                        )
                        stage_service.fail(run, "building_intelligence", "INTELLIGENCE_ARTIFACT_MISSING")
                        run.status = "review_required"
                        AssistantRunService(db).finish(run=run, response=response)
                        db.commit()
                        return
                else:
                    AssistantRunMaterialService(db).attach_document(
                        run_id=run.id, document=document, required=True,
                        preparation_job_id=preparation.id, artifact=None,
                    )
                    stage_service.wait(
                        run, "waiting_for_material",
                        document_preparation_job_id=preparation.id,
                        manifest={
                            "document_id": document.id,
                            "checksum": checksum,
                            "processor_generation": PROCESSOR_GENERATION,
                            "preparation_status": preparation.status,
                            "preparation_stage": preparation.stage,
                        },
                    )
                    db.commit()
                    try:
                        await OllamaClient().unload("qwen3.5:9b")
                    except Exception:
                        pass
                    return
            AssistantRunMaterialService(db).attach_document(
                run_id=run.id, document=document, required=True,
                preparation_job_id=artifact.preparation_job_id if artifact else None,
                artifact=artifact,
            )
            stage_service.complete(
                run, "waiting_for_material",
                result_manifest={"readiness": "intelligence_ready"},
                intelligence_artifact_id=artifact.id if artifact else None,
            )
            stage_service.complete(
                run, "building_intelligence",
                result_kind="intelligence_artifact",
                result_manifest={
                    "artifact_id": artifact.id,
                    "payload_sha256": artifact.payload_sha256,
                    "analyzer_generation": ANALYZER_GENERATION,
                },
                intelligence_artifact_id=artifact.id,
            )
            AssistantRunMaterialService.artifact_payload(artifact)
            stage_service.complete(
                run, "validating_intelligence",
                result_kind="intelligence_artifact",
                result_manifest={"artifact_id": artifact.id, "validation": "passed"},
                intelligence_artifact_id=artifact.id,
            )
        else:
            for name in ("waiting_for_material", "building_intelligence", "validating_intelligence"):
                stage_service.skip(run, name, "MATERIAL_NOT_REQUIRED")

        stage_service.start(run, "retrieving_case_evidence")
        kb_resolution = service._resolve_required_kb(request)
        collected = service._collect(request, kb_resolution=kb_resolution)
        AssistantRunMaterialService(db).bind_collected_sources(
            run_id=run.id, sources=collected.sources
        )
        case_count = sum(source.source_type != "knowledge_base" for source in collected.sources)
        kb_count = sum(source.source_type == "knowledge_base" for source in collected.sources)
        stage_service.complete(
            run, "retrieving_case_evidence",
            result_manifest={"source_count": case_count},
        )
        # GENERAL_KNOWLEDGE deliberately has no KB stage.  The dispatcher must
        # execute the deterministic plan rather than assume every non-fast run
        # includes every optional evidence domain.
        if stage_service.latest(run.id, "retrieving_knowledge_base") is not None:
            stage_service.start(run, "retrieving_knowledge_base")
            stage_service.complete(
                run, "retrieving_knowledge_base",
                result_manifest={"source_count": kb_count, "fail_open": True},
            )

        analysis_stage = stage_service.start(run, "analyzing_local")
        db.commit()
        payload = AssistantRunMaterialService.artifact_payload(artifact)
        streaming = StageStreamingOllamaClient(run.id, analysis_stage.id)
        reasoner = UnifiedAssistantService(
            db,
            llm_client=streaming,
            local_hard_seconds=(
                DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS
                if run.complexity == "deep"
                else STANDARD_LOCAL_ABSOLUTE_SECONDS
            ),
            local_num_ctx=4096,
            local_num_thread=V2_LOCAL_NUM_THREAD,
            advanced_queue_hard_seconds=600,
            advanced_external_hard_seconds=1800,
            release_db_before_model=True,
            document_intelligence_payload=payload,
        )
        response = await reasoner.ask(request=request, user_id=run.created_by_user_id)
        db.expire_all()
        run = db.get(AssistantRun, run_id)
        if run is None or run.status == "cancelled" or run.cancel_requested_at:
            db.rollback()
            return
        stage_service = AssistantRunStageService(db)
        stage_service.complete(
            run, "analyzing_local",
            result_kind="analysis_job" if response.status in {"advanced_queued", "advanced_processing"} else None,
            result_manifest={
                "disposition": response.status,
                "response_request_id": response.request_id,
                "model_identity": response.model or "deterministic_local",
                "model_contract": {
                    "num_ctx": 4096,
                    **(
                        {"num_thread": V2_LOCAL_NUM_THREAD}
                        if V2_LOCAL_NUM_THREAD is not None
                        else {"thread_policy": "ollama_auto"}
                    ),
                    "think": False,
                    "streaming": True,
                    "initial_num_predict": V2_STANDARD_INITIAL_NUM_PREDICT,
                    "truncation_retry_num_predict": V2_STANDARD_TRUNCATION_RETRY_NUM_PREDICT,
                    "truncation_retry_used": reasoner.local_truncation_retry_used,
                },
            },
            analysis_job_id=(
                response.request_id if response.status in {"advanced_queued", "advanced_processing"}
                else None
            ),
        )
        for name in ("reducing_findings", "synthesizing"):
            stage_service.skip(run, name, "QUALIFIED_F0_ADAPTER_COMPLETED_SYNTHESIS")
        stage_service.start(run, "validating_local")
        stage_service.complete(
            run, "validating_local",
            result_manifest={"disposition": response.status, "source_count": len(response.sources)},
        )
        if response.status in {"advanced_queued", "advanced_processing"}:
            stage_service.wait(
                run, "waiting_for_advanced",
                analysis_job_id=response.request_id,
                manifest={"analysis_job_id": response.request_id, "privacy_gate": "passed"},
            )
            db.commit()
            return
        if resuming_advanced:
            stage_service.complete(
                run, "waiting_for_advanced",
                result_kind="advanced_job",
                result_manifest={"disposition": response.status},
            )
            stage_service.start(run, "analyzing_advanced")
            stage_service.complete(
                run, "analyzing_advanced",
                result_kind="advanced_job",
                result_manifest={"disposition": response.status},
            )
            stage_service.start(run, "validating_advanced")
            stage_service.complete(
                run, "validating_advanced",
                result_manifest={"disposition": response.status},
            )
        else:
            for name in ("waiting_for_advanced", "analyzing_advanced", "validating_advanced"):
                stage_service.skip(run, name, "ADVANCED_NOT_REQUIRED")
        stage_service.start(run, "finalizing")
        response = response.model_copy(update={"request_id": run.id})
        result_hash = AssistantRunService._hash_json(response.model_dump(mode="json"))
        stage_service.complete(
            run, "finalizing", result_kind="final_response",
            result_manifest={
                "result_payload_sha256": result_hash,
                "model_identity": response.model or "deterministic_local",
                "model_contract": {
                    "num_ctx": 4096,
                    "think": False,
                    "streaming": True,
                    "initial_num_predict": V2_STANDARD_INITIAL_NUM_PREDICT,
                    "truncation_retry_num_predict": V2_STANDARD_TRUNCATION_RETRY_NUM_PREDICT,
                    "truncation_retry_used": reasoner.local_truncation_retry_used,
                },
            },
        )
        AssistantRunService(db).finish(run=run, response=response)
        db.commit()
    except LocalModelEmergencyAbort as error:
        db.rollback()
        db.close()
        await asyncio.to_thread(
            _record_resource_abort,
            run_id,
            str(error)[:100] or "LOCAL_RESOURCE_EMERGENCY",
        )
        logger.warning("Assistant Pipeline V2 resource abort: %s", str(error))
        return
    except asyncio.CancelledError:
        db.rollback()
        run = db.get(AssistantRun, run_id)
        if run is not None and run.status == "running" and run.current_stage:
            AssistantRunStageService(db).retry_or_fail(
                run, run.current_stage, "WORKER_INTERRUPTED"
            )
            db.commit()
        try:
            await OllamaClient().unload("qwen3.5:9b")
        except Exception:
            pass
        raise
    except Exception as error:
        db.rollback()
        run = db.get(AssistantRun, run_id)
        if run is not None and run.status != "cancelled":
            stage_type = run.current_stage or "finalizing"
            AssistantRunStageService(db).fail(
                run, stage_type, f"ASSISTANT_{error.__class__.__name__.upper()}"
            )
            response = _review_response(
                run.id,
                "Nie udało się zakończyć analizy. Możesz spróbować ponownie.",
                stage_type,
            )
            run.status = "review_required"
            AssistantRunService(db).finish(run=run, response=response)
            db.commit()
        logger.exception("Assistant Pipeline V2 run failed: %s", error.__class__.__name__)
    finally:
        db.close()


class AssistantRunDispatcher:
    POLL_SECONDS = 2

    async def run(self) -> None:
        logger.info("Assistant Pipeline V2 dispatcher started.")
        while True:
            try:
                run_id = await asyncio.to_thread(_claim_next_run)
                if run_id is None:
                    await asyncio.sleep(self.POLL_SECONDS)
                    continue
                task = asyncio.create_task(_execute_run(run_id), name=f"assistant-run-{run_id}")
                _ACTIVE_TASKS[run_id] = task
                timeout_code = None
                while not task.done():
                    await asyncio.wait({task}, timeout=5)
                    if task.done():
                        break
                    timeout_code = await asyncio.to_thread(_timeout_code, run_id)
                    if timeout_code:
                        await asyncio.to_thread(_record_interruption, run_id, timeout_code)
                        task.cancel()
                        break
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                finally:
                    _ACTIVE_TASKS.pop(run_id, None)
            except asyncio.CancelledError:
                for task in list(_ACTIVE_TASKS.values()):
                    task.cancel()
                raise
            except Exception as error:
                logger.warning("Assistant V2 dispatcher failure: %s", error.__class__.__name__)
                await asyncio.sleep(self.POLL_SECONDS)


def start_assistant_run_dispatcher() -> asyncio.Task | None:
    if not settings.assistant_pipeline_v2_enabled:
        logger.info("Assistant Pipeline V2 dispatcher disabled.")
        return None
    return asyncio.create_task(AssistantRunDispatcher().run(), name="assistant-run-dispatcher")
