from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.assistant_pipeline import AssistantRunStage
from app.models.document import Document
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.knowledge_base import AnalysisJob
from app.models.user import User
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.document_preparation_service import (
    LEASE_MINUTES,
    PROCESSOR_GENERATION,
    DocumentPreparationService,
    PreparationClaim,
    document_intelligence_resource_wait_code,
    is_document_intelligence_resource_wait,
)
from app.services.document_intelligence_service import build_document_intelligence
from app.services.vision_dispatcher import process_explicit_vision_document


logger = logging.getLogger("ai_lab.document_preparation")
INTELLIGENCE_HEARTBEAT_SECONDS = 30.0
RECOVERY_POLL_SECONDS = 10.0
_UNCHANGED = object()


def _assistant_preparation_has_no_active_waiters(
    db, job: DocumentPreparationJob
) -> bool:
    """Cancel only an Assistant-created preparation whose known consumers ended."""
    if job.trigger != "assistant":
        return False
    linked = db.query(AssistantRunStage.status).filter(
        AssistantRunStage.document_preparation_job_id == job.id,
    ).all()
    if not linked:
        return False
    if any(row[0] in {"queued", "waiting", "running"} for row in linked):
        return False
    legacy_active = db.query(AnalysisJob.id).filter(
        AnalysisJob.waiting_document_preparation_job_id == job.id,
        AnalysisJob.status.in_([
            "document_preparation_queued",
            "document_preparation_running",
            "resume_queued",
            "local_processing",
            "local_validating",
        ]),
    ).first()
    return legacy_active is None


class _PreparationIntelligenceHeartbeat:
    """Keep one live intelligence worker lease durable before streaming starts."""

    def __init__(
        self,
        claim: PreparationClaim,
        *,
        interval_seconds: float = INTELLIGENCE_HEARTBEAT_SECONDS,
        session_factory=None,
        now_factory=None,
        sleep=None,
    ) -> None:
        self.claim = claim
        self.interval_seconds = interval_seconds
        self.session_factory = session_factory or SessionLocal
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self.sleep = sleep or asyncio.sleep
        self.owner_task: asyncio.Task | None = None
        self.task: asyncio.Task | None = None

    def start(self, owner_task: asyncio.Task) -> bool:
        self.owner_task = owner_task
        if not self.refresh():
            return False
        self.task = asyncio.create_task(
            self._run(),
            name=f"document-intelligence-heartbeat-{self.claim.job_id}",
        )
        return True

    def refresh(
        self,
        *,
        wait_reason: str | object = _UNCHANGED,
        clear_wait: bool = False,
    ) -> bool:
        db = self.session_factory()
        try:
            job = db.query(DocumentPreparationJob).filter(
                DocumentPreparationJob.id == self.claim.job_id,
                DocumentPreparationJob.status == "running",
                DocumentPreparationJob.stage == "local_analysis",
                DocumentPreparationJob.lease_owner == self.claim.lease_owner,
            ).with_for_update().one_or_none()
            if job is None:
                db.rollback()
                return False
            if _assistant_preparation_has_no_active_waiters(db, job):
                now = self.now_factory()
                job.status = "cancelled"
                job.stage = "cancelled"
                job.error_code = "ASSISTANT_RUN_CANCELLED"
                job.retryability = None
                job.lease_owner = None
                job.lease_expires_at = None
                job.finished_at = now
                job.updated_at = now
                db.commit()
                return False
            now = self.now_factory()
            job.updated_at = now
            job.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
            if wait_reason is not _UNCHANGED:
                job.error_code = document_intelligence_resource_wait_code(
                    str(wait_reason)
                )
            elif clear_wait and is_document_intelligence_resource_wait(job.error_code):
                job.error_code = None
            db.commit()
            return True
        finally:
            db.close()

    async def resource_wait(self, reason: str) -> None:
        if not self.refresh(wait_reason=reason):
            raise asyncio.CancelledError

    async def resource_ready(self, _reason: str) -> None:
        if not self.refresh(clear_wait=True):
            raise asyncio.CancelledError

    async def progress(self, _telemetry: dict) -> None:
        if not self.refresh(clear_wait=True):
            raise asyncio.CancelledError

    async def _run(self) -> None:
        while True:
            await self.sleep(self.interval_seconds)
            try:
                active = self.refresh()
            except Exception:
                logger.exception("Document intelligence heartbeat failed.")
                continue
            if active:
                continue
            owner = self.owner_task
            if owner is not None and not owner.done():
                owner.cancel()
            return

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.task = None


def process_one_preparation() -> PreparationClaim | None:
    db = SessionLocal()
    try:
        service = DocumentPreparationService(db)
        service.recover_expired()
        claim = service.claim_next()
        db.commit()
        if claim is None:
            return None
        service.process_claimed(claim)
        return claim
    except Exception:
        db.rollback()
        logger.exception("Document preparation iteration failed.")
        return None
    finally:
        db.close()


async def process_preparation_intelligence(
    claim: PreparationClaim,
) -> str | None:
    db = SessionLocal()
    try:
        job = db.get(DocumentPreparationJob, claim.job_id)
        if (
            job is None
            or job.status != "running"
            or job.stage != "local_analysis"
            or job.lease_owner != claim.lease_owner
        ):
            return None
        document_id = job.document_id
    finally:
        db.close()

    parent_task = asyncio.current_task()
    if parent_task is None:
        raise RuntimeError("DOCUMENT_INTELLIGENCE_TASK_UNAVAILABLE")
    heartbeat = _PreparationIntelligenceHeartbeat(claim)
    last_persisted = datetime.min.replace(tzinfo=UTC)

    async def progress(_: dict) -> None:
        nonlocal last_persisted
        now = datetime.now(UTC)
        if now - last_persisted < timedelta(seconds=2):
            return
        await heartbeat.progress(_)
        last_persisted = now

    intelligence_task = asyncio.create_task(
        build_document_intelligence(
            document_id=document_id,
            preparation_job_id=claim.job_id,
            progress_callback=progress,
            on_resource_wait=heartbeat.resource_wait,
            on_resource_ready=heartbeat.resource_ready,
        ),
        name=f"document-intelligence-{claim.job_id}",
    )
    try:
        if not heartbeat.start(intelligence_task):
            intelligence_task.cancel()
            try:
                await intelligence_task
            except asyncio.CancelledError:
                pass
            return None
        artifact_id = await intelligence_task
        finish_db = SessionLocal()
        try:
            completed = DocumentPreparationService(
                finish_db
            ).complete_intelligence(claim, artifact_id)
            finish_db.commit()
        finally:
            finish_db.close()
        return artifact_id if completed else None
    except asyncio.CancelledError:
        recovery_db = SessionLocal()
        try:
            DocumentPreparationService(recovery_db).fail_intelligence(
                claim, "WORKER_INTERRUPTED"
            )
            recovery_db.commit()
        finally:
            recovery_db.close()
        if parent_task.cancelling():
            raise
        return None
    except Exception as error:
        finish_db = SessionLocal()
        try:
            DocumentPreparationService(finish_db).fail_intelligence(
                claim,
                f"INTELLIGENCE_{error.__class__.__name__.upper()}",
            )
            finish_db.commit()
        finally:
            finish_db.close()
        logger.warning("Document intelligence failed: %s", error.__class__.__name__)
        return None
    finally:
        await heartbeat.stop()
        if not intelligence_task.done():
            intelligence_task.cancel()
            try:
                await intelligence_task
            except asyncio.CancelledError:
                pass


async def process_preparation_vision(claim: PreparationClaim) -> bool:
    """Advance one exact preparation through the existing private Vision route."""
    db = SessionLocal()
    try:
        job = db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.id == claim.job_id,
            DocumentPreparationJob.status == "running",
            DocumentPreparationJob.lease_owner == claim.lease_owner,
        ).with_for_update().one_or_none()
        if job is None:
            return False
        if job.stage != "vision_processing":
            return job.stage == "local_analysis"
        if job.trigger == "ingestion":
            contained = DocumentPreparationService(
                db
            ).contain_ingestion_external_vision(claim)
            db.commit()
            return False if contained else job.stage == "local_analysis"
        document_id = job.document_id
    finally:
        db.close()

    await asyncio.to_thread(process_explicit_vision_document, document_id)
    finish_db = SessionLocal()
    try:
        job = finish_db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.id == claim.job_id,
            DocumentPreparationJob.status == "running",
            DocumentPreparationJob.stage == "vision_processing",
            DocumentPreparationJob.lease_owner == claim.lease_owner,
        ).with_for_update().one_or_none()
        document = finish_db.get(Document, document_id)
        if job is None or document is None:
            return False
        if document.vision_status in {"complete", "partial"}:
            job.stage = "local_analysis"
            job.status = "running"
            job.error_code = None
            job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=LEASE_MINUTES)
            finish_db.commit()
            return True
        DocumentPreparationService(finish_db).fail_intelligence(
            claim,
            f"VISION_{(document.vision_error_code or document.vision_status or 'FAILED').upper()}",
            expected_stage="vision_processing",
        )
        finish_db.commit()
        return False
    finally:
        finish_db.close()


def _next_waiting_id() -> str | None:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        # A crashed local resume is recoverable only after the previous hard
        # model deadline and cleanup margin have elapsed.
        db.query(AnalysisJob).filter(
            AnalysisJob.analysis_type == "unified_assistant_wait",
            AnalysisJob.status == "local_processing",
            AnalysisJob.last_progress_at < now - timedelta(minutes=4),
            AnalysisJob.cancel_requested_at.is_(None),
        ).update({AnalysisJob.status: "resume_queued"}, synchronize_session=False)
        row = db.query(AnalysisJob).join(
            DocumentPreparationJob,
            DocumentPreparationJob.id == AnalysisJob.waiting_document_preparation_job_id,
        ).filter(
            AnalysisJob.analysis_type == "unified_assistant_wait",
            AnalysisJob.status.in_(["document_preparation_queued", "document_preparation_running", "resume_queued"]),
            AnalysisJob.cancel_requested_at.is_(None),
            DocumentPreparationJob.status == "ready",
        ).order_by(AnalysisJob.created_at, AnalysisJob.id).with_for_update(skip_locked=True).first()
        if row is None:
            db.commit()
            return None
        if row.status != "resume_queued":
            row.status = "resume_queued"
            row.resume_generation += 1
        row.last_progress_at = now
        db.commit()
        return row.id
    finally:
        db.close()


async def resume_waiting_analysis(job_id: str) -> None:
    # This session is owned by the background consumer and never crosses from
    # an HTTP request. It remains bounded to one local reasoning attempt.
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).with_for_update().one_or_none()
        if job is None or job.status != "resume_queued" or job.cancel_requested_at is not None:
            db.rollback(); return
        preparation = db.get(DocumentPreparationJob, job.waiting_document_preparation_job_id)
        document = db.get(Document, preparation.document_id) if preparation else None
        user = db.get(User, job.created_by_user_id) if job.created_by_user_id else None
        if (
            preparation is None or preparation.status != "ready" or document is None
            or document.trashed_at is not None or document.purged_at is not None
            or document.checksum_sha256 != preparation.input_checksum
            or preparation.processor_generation != PROCESSOR_GENERATION
            or user is None or not user.is_active or user.trashed_at is not None or user.purged_at is not None
        ):
            job.status = "failed"; job.error_code = "PREPARATION_RESUME_REVALIDATION_FAILED"
            job.finished_at = datetime.now(UTC); db.commit(); return
        request = UnifiedAssistantRequest.model_validate(job.request_payload)
        job.status = "local_processing"; job.last_progress_at = datetime.now(UTC)
        job.reasoning_attempt_count += 1
        db.commit()

        from app.services.unified_assistant_service import UnifiedAssistantService
        response = await UnifiedAssistantService(
            db, release_db_before_model=True
        ).ask(request=request, user_id=user.id)
        db.expire_all()
        job = db.get(AnalysisJob, job_id)
        if job is None or job.cancel_requested_at is not None or job.status == "cancelled":
            db.rollback(); return
        payload = response.model_dump(mode="json")
        payload["request_id"] = job.id
        job.result_payload = payload
        if response.status in {"advanced_queued", "advanced_processing"}:
            job.status = "resume_queued"
        else:
            job.status = response.status if response.status in {
                "accepted_local", "accepted_advanced", "review_required", "failed", "cancelled"
            } else "failed"
            job.finished_at = datetime.now(UTC)
        job.last_progress_at = datetime.now(UTC)
        db.commit()
    except asyncio.CancelledError:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if job is not None and job.status != "cancelled":
            if job.reasoning_attempt_count < 3:
                job.status = "resume_queued"
                job.error_code = "ASSISTANT_RESUME_RETRYABLE"
            else:
                job.status = "failed"; job.error_code = "ASSISTANT_RESUME_FAILED"; job.finished_at = datetime.now(UTC)
            job.last_progress_at = datetime.now(UTC)
            db.commit()
        logger.warning("Assistant auto-resume failed: %s", error.__class__.__name__)
    finally:
        db.close()


class DocumentPreparationDispatcher:
    POLL_SECONDS = 2

    @staticmethod
    def _recover_expired_once() -> int:
        db = SessionLocal()
        try:
            recovered = DocumentPreparationService(db).recover_expired()
            db.commit()
            return recovered
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _recovery_loop(self) -> None:
        while True:
            try:
                recovered = await asyncio.to_thread(
                    self._recover_expired_once
                )
                if recovered:
                    logger.info(
                        "Recovered %s expired document preparation lease(s).",
                        recovered,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning(
                    "Document preparation recovery poll failed: %s",
                    error.__class__.__name__,
                )
            await asyncio.sleep(RECOVERY_POLL_SECONDS)

    async def run(self) -> None:
        logger.info("Document preparation dispatcher started.")
        recovery_task = asyncio.create_task(
            self._recovery_loop(),
            name="document-preparation-recovery",
        )
        try:
            while True:
                try:
                    prepared = await asyncio.to_thread(process_one_preparation)
                    if prepared is not None:
                        if await process_preparation_vision(prepared):
                            await process_preparation_intelligence(prepared)
                    waiting = await asyncio.to_thread(_next_waiting_id)
                    if waiting is not None:
                        await resume_waiting_analysis(waiting)
                    elif prepared is None:
                        await asyncio.sleep(self.POLL_SECONDS)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.warning("Document preparation dispatcher failure: %s", error.__class__.__name__)
                    await asyncio.sleep(self.POLL_SECONDS)
        finally:
            recovery_task.cancel()
            try:
                await recovery_task
            except asyncio.CancelledError:
                pass


def start_document_preparation_dispatcher() -> asyncio.Task | None:
    if not settings.document_preparation_enabled:
        logger.info("Document preparation dispatcher disabled.")
        return None
    return asyncio.create_task(DocumentPreparationDispatcher().run(), name="document-preparation-dispatcher")
