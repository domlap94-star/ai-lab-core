from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document_asset import DocumentAsset
    from app.models.document_chunk import DocumentChunk
    from app.models.document_page import DocumentPage


class Document(Base):
    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "source_type IN "
            "("
            "'manual_upload', "
            "'gmail_attachment', "
            "'camera_photo', "
            "'camera_video'"
            ")",
            name="ck_documents_source_type",
        ),
        CheckConstraint(
            "processing_status IN "
            "('pending', 'stored', 'extracting', 'processed', 'failed')",
            name="ck_documents_processing_status",
        ),
        CheckConstraint(
            "metadata_status IN "
            "('pending', 'processed', 'unsupported', 'failed')",
            name="ck_documents_metadata_status",
        ),
        CheckConstraint(
            "match_status IN "
            "('unmatched', 'suggested', 'matched', 'confirmed', 'rejected')",
            name="ck_documents_match_status",
        ),
        CheckConstraint(
            "match_confidence IS NULL OR "
            "(match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_documents_match_confidence_range",
        ),
        CheckConstraint(
            "latitude IS NULL OR "
            "(latitude >= -90 AND latitude <= 90)",
            name="ck_documents_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR "
            "(longitude >= -180 AND longitude <= 180)",
            name="ck_documents_longitude_range",
        ),
        CheckConstraint(
            "location_accuracy_m IS NULL OR "
            "location_accuracy_m >= 0",
            name="ck_documents_location_accuracy_positive",
        ),
        CheckConstraint(
            "archive_depth >= 0",
            name="ck_documents_archive_depth_positive",
        ),
        UniqueConstraint(
            "source_type",
            "external_id",
            name="uq_documents_source_external_id",
        ),
        Index(
            "ix_documents_client_id",
            "client_id",
        ),
        Index(
            "ix_documents_candidate_id",
            "candidate_id",
        ),
        Index(
            "ix_documents_processing_status",
            "processing_status",
        ),
        Index(
            "ix_documents_metadata_status",
            "metadata_status",
        ),
        Index(
            "ix_documents_match_status",
            "match_status",
        ),
        Index(
            "ix_documents_checksum_sha256",
            "checksum_sha256",
        ),
        Index(
            "ix_documents_parent_document_id",
            "parent_document_id",
        ),
        Index(
            "ix_documents_parent_archive_member",
            "parent_document_id",
            "archive_member_path",
        ),
        Index(
            "ix_documents_gmail_message_id",
            "gmail_message_id",
        ),
        Index(
            "ix_documents_inspection_session_id",
            "inspection_session_id",
        ),
        Index(
            "ix_documents_captured_at",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        nullable=False,
    )

    storage_path: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    parent_document_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    archive_member_path: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    archive_depth: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual_upload",
        server_default="manual_upload",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    gmail_message_id: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    gmail_thread_id: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    candidate_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "client_candidates.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    client_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "clients.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    location_accuracy_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    location_source: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    inspection_session_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    metadata_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    metadata_raw: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    metadata_normalized: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    metadata_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    metadata_extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    match_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="unmatched",
        server_default="unmatched",
    )

    match_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    match_method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    matched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    parent: Mapped["Document | None"] = relationship(
        "Document",
        remote_side="Document.id",
        back_populates="children",
        foreign_keys=[parent_document_id],
    )

    children: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="parent",
        foreign_keys=[parent_document_id],
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    pages: Mapped[list["DocumentPage"]] = relationship(
        "DocumentPage",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentPage.page_number",
    )

    assets: Mapped[list["DocumentAsset"]] = relationship(
        "DocumentAsset",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentAsset.asset_index",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )