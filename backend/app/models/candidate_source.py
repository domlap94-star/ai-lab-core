from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import BusinessBase


class CandidateSource(BusinessBase):
    __tablename__ = "candidate_sources"

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('gmail_message', 'gmail_thread', 'google_sheets_row')",
            name="ck_candidate_sources_source_type",
        ),
        Index(
            "ix_candidate_sources_candidate_id",
            "candidate_id",
        ),
        Index(
            "ix_candidate_sources_import_source_id",
            "import_source_id",
        ),
        Index(
            "ix_candidate_sources_import_run_id",
            "import_run_id",
        ),
        Index(
            "ix_candidate_sources_external_id",
            "external_id",
        ),
        UniqueConstraint(
            "import_source_id",
            "source_type",
            "external_id",
            name="uq_candidate_sources_external_reference",
        ),
    )

    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "client_candidates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    import_source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "import_sources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    import_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "import_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    external_id: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    external_parent_id: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    source_label: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )