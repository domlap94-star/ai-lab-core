from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AgentExecution(Base):
    """Bounded operational audit for a future read-only Agent request."""

    __tablename__ = "agent_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'cancelled', 'blocked')",
            name="ck_agent_executions_status",
        ),
        CheckConstraint(
            "tool_count >= 0",
            name="ck_agent_executions_tool_count_nonnegative",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_executions_duration_nonnegative",
        ),
        UniqueConstraint("request_id", name="uq_agent_executions_request_id"),
        Index("ix_agent_executions_user_created_at", "user_id", "created_at"),
        Index("ix_agent_executions_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    tool_count: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    execution_metadata: Mapped[dict] = mapped_column(JSON, nullable=False)
