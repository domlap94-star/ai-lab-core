from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import BusinessBase


class ImportRun(BusinessBase):
    __tablename__ = "import_runs"

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('manual', 'scheduled', 'webhook')",
            name="ck_import_runs_trigger_type",
        ),
        CheckConstraint(
            "status IN "
            "('pending', 'running', 'completed', 'partial', 'failed', "
            "'cancelled')",
            name="ck_import_runs_status",
        ),
        Index(
            "ix_import_runs_source_id",
            "source_id",
        ),
        Index(
            "ix_import_runs_status",
            "status",
        ),
        Index(
            "ix_import_runs_started_at",
            "started_at",
        ),
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "import_sources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    trigger_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    records_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    candidates_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    duplicates_detected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    records_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    cursor_before: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    cursor_after: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    statistics: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )