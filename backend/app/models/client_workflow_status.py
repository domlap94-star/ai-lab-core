from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.mixins import BusinessBase


class ClientWorkflowStatus(BusinessBase):
    __tablename__ = "client_workflow_statuses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('obsolete', 'in_progress', 'inspection', "
            "'completed', 'untouched', 'phone_contact')",
            name="ck_client_workflow_statuses_status",
        ),
        Index("uq_client_workflow_statuses_client", "client_id", unique=True),
        Index("ix_client_workflow_statuses_status", "status"),
    )

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
