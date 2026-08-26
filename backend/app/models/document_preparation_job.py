from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentPreparationJob(Base):
    __tablename__ = "document_preparation_jobs"
    __table_args__ = (
        CheckConstraint("trigger IN ('ingestion','assistant','operator_retry')", name="ck_document_preparation_jobs_trigger"),
        CheckConstraint("priority BETWEEN 0 AND 3", name="ck_document_preparation_jobs_priority"),
        CheckConstraint("status IN ('queued','running','ready','failed','unsupported','integrity_failed','cancelled')", name="ck_document_preparation_jobs_status"),
        CheckConstraint("stage IN ('received','validating','queued','extracting','rendering','ocr_required','ocr_processing','vision_processing','local_analysis','indexing','ready_for_ai','failed','unsupported','integrity_failed','cancelled')", name="ck_document_preparation_jobs_stage"),
        CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts", name="ck_document_preparation_jobs_attempts"),
        CheckConstraint("retryability IS NULL OR retryability IN ('recoverable','unsupported','integrity','missing_file','owner_action')", name="ck_document_preparation_jobs_retryability"),
        UniqueConstraint("document_id", "input_checksum", "processor_generation", name="uq_document_preparation_generation"),
        Index("ix_document_preparation_jobs_queue", "status", "priority", "queued_at", "id"),
        Index("ix_document_preparation_jobs_stale", "status", "lease_expires_at", "id"),
        Index("ix_document_preparation_jobs_document", "document_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    input_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    processor_generation: Mapped[str] = mapped_column(String(40), nullable=False, default="document-preparation-v1", server_default="document-preparation-v1")
    trigger: Mapped[str] = mapped_column(String(24), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2, server_default="2")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", server_default="queued")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="received", server_default="received")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    error_code: Mapped[str | None] = mapped_column(String(100))
    retryability: Mapped[str | None] = mapped_column(String(24))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
