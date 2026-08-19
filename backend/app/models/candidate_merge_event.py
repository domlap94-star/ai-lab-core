from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CandidateMergeEvent(Base):
    __tablename__ = "candidate_merge_events"
    __table_args__ = (
        CheckConstraint(
            "action = 'candidate_merged'",
            name="ck_candidate_merge_events_action",
        ),
        UniqueConstraint(
            "operation_id",
            name="uq_candidate_merge_events_operation_id",
        ),
        Index(
            "ix_candidate_merge_events_candidate_created",
            "candidate_id",
            "created_at",
        ),
        Index(
            "ix_candidate_merge_events_target_created",
            "target_client_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("client_candidates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    relation_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
