from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import and_, or_

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_processing_service import DocumentProcessingService
from app.services.vision_processing_service import VisionProcessingService


logger = logging.getLogger("ai_lab.vision")


def process_one_vision_document(document_id: int, *, explicit: bool = False):
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            return None
        if document.processing_status in {"stored", "pending", "extracting"}:
            DocumentProcessingService(db).process_document(document_id=document.id)
        return VisionProcessingService(db).advance(
            document.id,
            explicit=explicit or not document.vision_auto_eligible,
        )
    finally:
        db.close()


def process_explicit_vision_document(document_id: int) -> None:
    # The HTTP/background caller is bounded; the persistent dispatcher keeps
    # pending manual requests alive across process restarts and worker retries.
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        result = process_one_vision_document(document_id, explicit=True)
        if result is None or result.status not in {"pending", "queued", "processing"}:
            return
        time.sleep(2)


class VisionDispatcher:
    POLL_SECONDS = 10

    def next_document_id(self) -> int | None:
        db = SessionLocal()
        try:
            now = datetime.now(UTC)
            row = (
                db.query(Document.id)
                .filter(
                    or_(
                        Document.vision_auto_eligible.is_(True),
                        and_(
                            Document.vision_auto_eligible.is_(False),
                            Document.vision_status != "not_evaluated",
                        ),
                    ),
                    Document.vision_status.in_([
                        "not_evaluated", "pending", "queued", "processing",
                        "failed_retryable", "pending_auth", "ui_changed",
                    ]),
                    Document.vision_attempt_count < 3,
                    or_(Document.vision_next_retry_at.is_(None), Document.vision_next_retry_at <= now),
                )
                .order_by(Document.created_at.asc(), Document.id.asc())
                .first()
            )
            return row[0] if row else None
        finally:
            db.close()

    async def run(self) -> None:
        logger.info("Vision dispatcher started.")
        while True:
            try:
                document_id = await asyncio.to_thread(self.next_document_id)
                if document_id is None:
                    await asyncio.sleep(self.POLL_SECONDS)
                    continue
                await asyncio.to_thread(process_one_vision_document, document_id)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Vision dispatcher iteration failed: %s", error.__class__.__name__)
                await asyncio.sleep(self.POLL_SECONDS)


def start_vision_dispatcher() -> asyncio.Task | None:
    if not settings.vision_automation_enabled:
        logger.info("Vision automation remains disabled pending acceptance gate.")
        return None
    return asyncio.create_task(VisionDispatcher().run(), name="vision-dispatcher")
