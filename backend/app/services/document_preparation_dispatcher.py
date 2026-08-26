from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.knowledge_base import AnalysisJob
from app.models.user import User
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.document_preparation_service import DocumentPreparationService


logger = logging.getLogger("ai_lab.document_preparation")


def process_one_preparation() -> str | None:
    db = SessionLocal()
    try:
        service = DocumentPreparationService(db)
        service.recover_expired()
        job_id = service.claim_next()
        db.commit()
        if job_id is None:
            return None
        service.process_claimed(job_id)
        return job_id
    except Exception:
        db.rollback()
        logger.exception("Document preparation iteration failed.")
        return None
    finally:
        db.close()


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
            or preparation.processor_generation != "document-preparation-v1"
            or user is None or not user.is_active or user.trashed_at is not None or user.purged_at is not None
        ):
            job.status = "failed"; job.error_code = "PREPARATION_RESUME_REVALIDATION_FAILED"
            job.finished_at = datetime.now(UTC); db.commit(); return
        request = UnifiedAssistantRequest.model_validate(job.request_payload)
        job.status = "local_processing"; job.last_progress_at = datetime.now(UTC)
        job.reasoning_attempt_count += 1
        db.commit()

        from app.services.unified_assistant_service import UnifiedAssistantService
        response = await UnifiedAssistantService(db).ask(request=request, user_id=user.id)
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

    async def run(self) -> None:
        logger.info("Document preparation dispatcher started.")
        while True:
            try:
                prepared = await asyncio.to_thread(process_one_preparation)
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


def start_document_preparation_dispatcher() -> asyncio.Task | None:
    if not settings.document_preparation_enabled:
        logger.info("Document preparation dispatcher disabled.")
        return None
    return asyncio.create_task(DocumentPreparationDispatcher().run(), name="document-preparation-dispatcher")
