from __future__ import annotations

import hashlib
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_preparation_job import DocumentPreparationJob
from app.services.document_file_safety_service import DocumentFileSafetyService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import resolve_document_storage_path
from app.services.unified_document_content_service import (
    FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE,
    FILE_FOUND_NATIVE_TEXT_AVAILABLE,
    FILE_FOUND_REQUIRES_OCR,
    INTEGRITY_MISMATCH,
    UnifiedDocumentContentService,
)


PROCESSOR_GENERATION = "document-preparation-v1"
LEASE_MINUTES = 45


class DocumentPreparationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(
        self, *, document: Document, trigger: str, priority: int,
        created_by_user_id: int | None = None,
    ) -> tuple[DocumentPreparationJob, bool]:
        checksum = (document.checksum_sha256 or "").strip().casefold()
        if len(checksum) != 64:
            raise ValueError("document_checksum_required")
        # Serialize generation decisions on the canonical Document row. This
        # enforces at most one active checksum/generation even though terminal
        # historical generations remain retained for audit.
        self.db.query(Document.id).filter(Document.id == document.id).with_for_update().one()
        active = self.db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.document_id == document.id,
            DocumentPreparationJob.status.in_(["queued", "running"]),
        ).one_or_none()
        if active is not None and (
            active.input_checksum != checksum
            or active.processor_generation != PROCESSOR_GENERATION
        ):
            raise ValueError("document_preparation_generation_active")
        existing = self.db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.document_id == document.id,
            DocumentPreparationJob.input_checksum == checksum,
            DocumentPreparationJob.processor_generation == PROCESSOR_GENERATION,
        ).one_or_none()
        if existing is not None:
            if priority < existing.priority and existing.status == "queued":
                existing.priority = priority
            return existing, False
        savepoint = self.db.begin_nested()
        try:
            job = DocumentPreparationJob(
                id=str(uuid.uuid4()), document_id=document.id, input_checksum=checksum,
                processor_generation=PROCESSOR_GENERATION, trigger=trigger,
                priority=max(0, min(3, priority)), status="queued", stage="queued",
                created_by_user_id=created_by_user_id,
            )
            self.db.add(job)
            self.db.flush()
            savepoint.commit()
            return job, True
        except IntegrityError:
            savepoint.rollback()
            existing = self.db.query(DocumentPreparationJob).filter(
                DocumentPreparationJob.document_id == document.id,
                DocumentPreparationJob.input_checksum == checksum,
                DocumentPreparationJob.processor_generation == PROCESSOR_GENERATION,
            ).one()
            if priority < existing.priority and existing.status == "queued":
                existing.priority = priority
            return existing, False

    def recover_expired(self) -> int:
        now = datetime.now(UTC)
        jobs = self.db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.status == "running",
            DocumentPreparationJob.lease_expires_at.is_not(None),
            DocumentPreparationJob.lease_expires_at < now,
        ).with_for_update(skip_locked=True).all()
        recovered = 0
        for job in jobs:
            if job.attempt_count >= job.max_attempts:
                self._terminal(job, "failed", "failed", "PREPARATION_ATTEMPTS_EXHAUSTED", "owner_action")
            else:
                job.status = "queued"; job.stage = "queued"; job.lease_owner = None; job.lease_expires_at = None
            recovered += 1
        return recovered

    def claim_next(self) -> str | None:
        now = datetime.now(UTC)
        age = func.least(3, func.floor(func.extract("epoch", now - DocumentPreparationJob.queued_at) / 1800))
        job = self.db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.status == "queued",
            DocumentPreparationJob.attempt_count < DocumentPreparationJob.max_attempts,
            DocumentPreparationJob.queued_at <= now,
        ).order_by((DocumentPreparationJob.priority - age).asc(), DocumentPreparationJob.queued_at, DocumentPreparationJob.id).with_for_update(skip_locked=True).first()
        if job is None:
            return None
        job.status = "running"; job.stage = "validating"; job.attempt_count += 1
        job.started_at = job.started_at or now
        job.lease_owner = f"{socket.gethostname()}:{os.getpid()}"
        job.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
        self.db.flush()
        return job.id

    def process_claimed(self, job_id: str) -> None:
        job = self.db.get(DocumentPreparationJob, job_id)
        if job is None or job.status != "running":
            return
        document = self.db.query(Document).filter(
            Document.id == job.document_id, Document.trashed_at.is_(None), Document.purged_at.is_(None)
        ).one_or_none()
        if document is None:
            self._terminal(job, "failed", "failed", "DOCUMENT_NOT_FOUND", "missing_file"); self.db.commit(); return
        try:
            path = resolve_document_storage_path(storage_path=document.storage_path or "", data_root=Path(settings.data_dir))
        except Exception:
            self._terminal(job, "failed", "failed", "DOCUMENT_FILE_NOT_FOUND", "missing_file"); self.db.commit(); return
        actual = self._sha256(path)
        if actual != job.input_checksum or actual != (document.checksum_sha256 or "").casefold():
            self._terminal(job, "integrity_failed", "integrity_failed", "DOCUMENT_STORAGE_INTEGRITY_MISMATCH", "integrity"); self.db.commit(); return
        safety = DocumentFileSafetyService().classify(
            path=path, original_filename=document.original_filename or document.filename,
            declared_mime=document.content_type,
        )
        if safety.state != "supported":
            status = "integrity_failed" if safety.state == "integrity_failed" else "unsupported"
            retry = "integrity" if status == "integrity_failed" else "unsupported"
            self._terminal(job, status, status, safety.error_code or "UNSUPPORTED_FORMAT", retry); self.db.commit(); return
        job.stage = "ocr_processing" if safety.detected_format in {"pdf", "image"} else "extracting"
        self.db.commit()
        result = DocumentProcessingService(self.db).process_document(document_id=document.id)
        self.db.expire_all()
        job = self.db.get(DocumentPreparationJob, job_id)
        document = self.db.get(Document, document.id)
        if job is None or job.status == "cancelled":
            return
        content = UnifiedDocumentContentService(self.db).access(document)
        if result.status == "processed" and content.state in {FILE_FOUND_NATIVE_TEXT_AVAILABLE, FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE}:
            self._terminal(job, "ready", "ready_for_ai", None, None)
        elif content.state == INTEGRITY_MISMATCH:
            self._terminal(job, "integrity_failed", "integrity_failed", "DOCUMENT_STORAGE_INTEGRITY_MISMATCH", "integrity")
        elif content.state == FILE_FOUND_REQUIRES_OCR:
            self._terminal(job, "failed", "ocr_required", "DOCUMENT_REQUIRES_CONTROLLED_VISION", "owner_action")
        else:
            if job.attempt_count < job.max_attempts:
                self._requeue(job, "DOCUMENT_PREPARATION_FAILED")
            else:
                self._terminal(job, "failed", "failed", "DOCUMENT_PREPARATION_FAILED", "owner_action")
        self.db.commit()

    @staticmethod
    def _terminal(job: DocumentPreparationJob, status: str, stage: str, error: str | None, retryability: str | None) -> None:
        job.status = status; job.stage = stage; job.error_code = error; job.retryability = retryability
        job.lease_owner = None; job.lease_expires_at = None; job.finished_at = datetime.now(UTC)

    @staticmethod
    def _requeue(job: DocumentPreparationJob, error: str) -> None:
        job.status = "queued"; job.stage = "queued"; job.error_code = error
        job.retryability = "recoverable"; job.lease_owner = None; job.lease_expires_at = None
        job.queued_at = datetime.now(UTC) + timedelta(seconds=15)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
