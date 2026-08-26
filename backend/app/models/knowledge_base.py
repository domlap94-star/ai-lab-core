from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base_items"
    __table_args__ = (
        CheckConstraint("status IN ('current','superseded')", name="ck_knowledge_base_items_status"),
        CheckConstraint("processing_status IN ('uploaded','queued','extracting','ocr','processed','failed')", name="ck_knowledge_base_items_processing_status"),
        CheckConstraint("analysis_status IN ('not_required','local_pending','local_processing','local_accepted','advanced_required','advanced_queued','advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating','advanced_accepted','review_required','failed')", name="ck_knowledge_base_items_analysis_status"),
        CheckConstraint("indexing_status IN ('not_ready','pending','indexing','indexed','failed')", name="ck_knowledge_base_items_indexing_status"),
        CheckConstraint("category IN ('norms','technical_datasheets','manuals','producer_materials','formulas','reference_calculations','other')", name="ck_knowledge_base_items_category"),
        Index("ix_knowledge_base_items_search", "status", "category", "publisher"),
        Index("ix_knowledge_base_items_checksum", "checksum_sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(100))
    effective_date: Mapped[date | None] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="current", server_default="current")
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_base_items.id", ondelete="SET NULL"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded", server_default="uploaded")
    processing_method: Mapped[str | None] = mapped_column(String(30))
    processing_error: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[str] = mapped_column(String(30), nullable=False, default="local_pending", server_default="local_pending")
    analysis_error: Mapped[str | None] = mapped_column(String(100))
    analysis_reason: Mapped[str | None] = mapped_column(String(100))
    indexing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_ready", server_default="not_ready")
    extracted_text: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    pages: Mapped[list["KnowledgeBasePage"]] = relationship(back_populates="item", cascade="all, delete-orphan", passive_deletes=True, order_by="KnowledgeBasePage.page_number")
    processing_jobs: Mapped[list["KnowledgeBaseProcessingJob"]] = relationship(back_populates="item", cascade="all, delete-orphan", passive_deletes=True)
    analysis_artifacts: Mapped[list["KnowledgeBaseAnalysisArtifact"]] = relationship(back_populates="item", cascade="all, delete-orphan", passive_deletes=True)


class KnowledgeBasePage(Base):
    __tablename__ = "knowledge_base_pages"
    __table_args__ = (UniqueConstraint("item_id", "page_number", name="uq_knowledge_base_pages_item_page"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("knowledge_base_items.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    item: Mapped[KnowledgeBaseItem] = relationship(back_populates="pages")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','document_preparation_queued','document_preparation_running','resume_queued','local_processing','local_validating','advanced_queued','advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating','accepted_local','accepted_advanced','review_required','failed','cancelled')", name="ck_analysis_jobs_status"),
        CheckConstraint("sensitivity IN ('public_reference','internal_non_sensitive','customer_sanitizable','restricted_never_external')", name="ck_analysis_jobs_sensitivity"),
        Index("ix_analysis_jobs_status_updated", "status", "updated_at"),
        Index("uq_analysis_jobs_active_fingerprint", "analysis_type", "source_domain", "input_fingerprint", unique=True,
              postgresql_where=text("status IN ('queued','document_preparation_queued','document_preparation_running','resume_queued','local_processing','local_validating','advanced_queued','advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating')")),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    decision: Mapped[str | None] = mapped_column(String(30))
    sensitivity: Mapped[str] = mapped_column(String(30), nullable=False)
    processor_id: Mapped[str | None] = mapped_column(String(100))
    processor_version: Mapped[str | None] = mapped_column(String(40))
    model_identity: Mapped[str | None] = mapped_column(String(100))
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitized_package_hash: Mapped[str | None] = mapped_column(String(64))
    sanitized_package_size: Mapped[int | None] = mapped_column(Integer)
    external_job_id: Mapped[str | None] = mapped_column(String(36))
    reasoning_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    format_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quality_signals: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    attempt_id: Mapped[str | None] = mapped_column(String(80))
    request_payload: Mapped[dict | None] = mapped_column(JSON)
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    waiting_document_preparation_job_id: Mapped[str | None] = mapped_column(ForeignKey("document_preparation_jobs.id", ondelete="SET NULL"))
    resume_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    sources: Mapped[list["AnalysisJobSource"]] = relationship(back_populates="job", cascade="all, delete-orphan", passive_deletes=True)


class AnalysisJobSource(Base):
    __tablename__ = "analysis_job_sources"
    __table_args__ = (UniqueConstraint("analysis_job_id", "source_ref", name="uq_analysis_job_sources_ref"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(8), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(50), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(30), nullable=False)
    job: Mapped[AnalysisJob] = relationship(back_populates="sources")


class KnowledgeBaseProcessingJob(Base):
    __tablename__ = "knowledge_base_processing_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_knowledge_base_processing_jobs_status"),
        Index("uq_kb_processing_active_item", "item_id", unique=True, postgresql_where=text("status IN ('queued','running')")),
        Index("ix_kb_processing_status_created", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("knowledge_base_items.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", server_default="queued")
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(100))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    item: Mapped[KnowledgeBaseItem] = relationship(back_populates="processing_jobs")


class KnowledgeBaseAnalysisArtifact(Base):
    __tablename__ = "knowledge_base_analysis_artifacts"
    __table_args__ = (CheckConstraint("origin IN ('local','advanced')", name="ck_kb_analysis_artifacts_origin"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("knowledge_base_items.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_page_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_state: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    item: Mapped[KnowledgeBaseItem] = relationship(back_populates="analysis_artifacts")
