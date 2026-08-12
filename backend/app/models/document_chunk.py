from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_document_chunks_chunk_index_nonnegative",
        ),
        CheckConstraint(
            "token_count >= 0",
            name="ck_document_chunks_token_count_nonnegative",
        ),
        CheckConstraint(
            "character_count >= 0",
            name="ck_document_chunks_character_count_nonnegative",
        ),
        CheckConstraint(
            "page_from IS NULL OR page_from >= 1",
            name="ck_document_chunks_page_from_positive",
        ),
        CheckConstraint(
            "page_to IS NULL OR page_to >= 1",
            name="ck_document_chunks_page_to_positive",
        ),
        CheckConstraint(
            "page_from IS NULL OR page_to IS NULL OR page_to >= page_from",
            name="ck_document_chunks_page_range_valid",
        ),
        CheckConstraint(
            "embedding_status IN "
            "('pending', 'embedded', 'failed', 'stale', 'skipped')",
            name="ck_document_chunks_embedding_status",
        ),
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_chunk_index",
        ),
        Index(
            "ix_document_chunks_document_page",
            "document_id",
            "page_from",
            "page_to",
        ),
        Index(
            "ix_document_chunks_embedding_status",
            "embedding_status",
        ),
        Index(
            "ix_document_chunks_content_hash",
            "content_hash",
        ),
        Index(
            "ix_document_chunks_chunking_version",
            "chunking_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    page_from: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    page_to: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="document",
        server_default="document",
    )

    content_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="combined",
        server_default="combined",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    chunking_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1",
        server_default="v1",
    )

    embedding_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    embedding_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    vector_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    embedding_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    embedded_at: Mapped[datetime | None] = mapped_column(
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

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )
