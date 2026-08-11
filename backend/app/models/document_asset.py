from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentAsset(Base):
    __tablename__ = "document_assets"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "asset_index",
            name="uq_document_assets_document_asset_index",
        ),
        CheckConstraint(
            "asset_index >= 1",
            name="ck_document_assets_asset_index_positive",
        ),
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_document_assets_page_number_positive",
        ),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="ck_document_assets_width_positive",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="ck_document_assets_height_positive",
        ),
        CheckConstraint(
            "ocr_confidence IS NULL OR "
            "(ocr_confidence >= 0 AND ocr_confidence <= 100)",
            name="ck_document_assets_ocr_confidence_range",
        ),
        CheckConstraint(
            "processing_status IN "
            "("
            "'pending', "
            "'extracted', "
            "'processed', "
            "'no_text', "
            "'unsupported', "
            "'failed'"
            ")",
            name="ck_document_assets_processing_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    asset_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    container_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    asset_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    source_format: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    original_name: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    storage_path: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    extraction_method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    ocr_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ocr_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    vision_analysis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    processing_error: Mapped[str | None] = mapped_column(
        Text,
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

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="assets",
    )