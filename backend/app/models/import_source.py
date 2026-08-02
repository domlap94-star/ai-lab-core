from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import BusinessBase


class ImportSource(BusinessBase):
    __tablename__ = "import_sources"

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('gmail', 'google_sheets')",
            name="ck_import_sources_source_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'error')",
            name="ck_import_sources_status",
        ),
        Index(
            "ix_import_sources_source_type",
            "source_type",
        ),
        Index(
            "ix_import_sources_status",
            "status",
        ),
        Index(
            "ix_import_sources_external_account_id",
            "external_account_id",
        ),
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    external_account_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="inactive",
        server_default="inactive",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    configuration: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )