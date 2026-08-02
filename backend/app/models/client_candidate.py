from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import BusinessBase


class ClientCandidate(BusinessBase):
    __tablename__ = "client_candidates"

    __table_args__ = (
        CheckConstraint(
            "client_type IN "
            "('company', 'person', 'institution', 'other')",
            name="ck_client_candidates_client_type",
        ),
        CheckConstraint(
            "status IN "
            "('pending', 'accepted', 'rejected', 'merged', 'duplicate')",
            name="ck_client_candidates_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_client_candidates_confidence_range",
        ),
        Index(
            "ix_client_candidates_status",
            "status",
        ),
        Index(
            "ix_client_candidates_tax_id",
            "tax_id",
        ),
        Index(
            "ix_client_candidates_primary_email",
            "primary_email",
        ),
        Index(
            "ix_client_candidates_matched_client_id",
            "matched_client_id",
        ),
        Index(
            "ix_client_candidates_import_run_id",
            "import_run_id",
        ),
    )

    import_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "import_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    client_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="other",
        server_default="other",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    legal_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    tax_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    industry_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "industries.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    primary_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    primary_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    street: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    building_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    unit_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="PL",
        server_default="PL",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    matched_client_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "clients.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )