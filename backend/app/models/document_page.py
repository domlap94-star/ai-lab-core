from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class DocumentPage(Base):
    __tablename__ = "document_pages"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_pages_document_page",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
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

    page_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    render_path: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    render_dpi: Mapped[int | None] = mapped_column(
        Integer,
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

    vision_analysis: Mapped[str | None] = mapped_column(
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
        back_populates="pages",
    )