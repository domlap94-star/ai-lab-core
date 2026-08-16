from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentClientLinkEvent(Base):
    __tablename__ = "document_client_link_events"
    __table_args__ = (
        CheckConstraint("action IN ('LINK', 'UNLINK', 'MOVE')", name="ck_document_client_link_events_action"),
        Index("ix_document_client_link_events_document", "document_id", "created_at"),
        Index("ix_document_client_link_events_actor", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    old_client_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True
    )
    new_client_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True
    )
    previous_candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("client_candidates.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="manual")
    evidence_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reversal_of_event_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("document_client_link_events.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
