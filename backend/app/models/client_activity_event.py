from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ClientActivityEvent(Base):
    __tablename__ = "client_activity_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('call_initiated','client_status_changed','email_received','email_sent','document_added','inspection_created','candidate_merged','task_created','task_completed','realization_created','note_added')",
            name="ck_client_activity_events_type",
        ),
        CheckConstraint("direction IS NULL OR direction IN ('incoming','outgoing')", name="ck_client_activity_events_direction"),
        UniqueConstraint("source_key", name="uq_client_activity_events_source_key"),
        Index("ix_client_activity_events_client_occurred_id", "client_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
