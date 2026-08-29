from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        Index(
            "ix_messages_conversation_created",
            "conversation_id",
            "created_at",
            "id",
        ),
        Index(
            "uq_messages_assistant_run_role",
            "assistant_run_id",
            "role",
            unique=True,
            postgresql_where=text("assistant_run_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    assistant_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "assistant_runs.id",
            ondelete="SET NULL",
            name="fk_messages_assistant_run_id_assistant_runs",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    assistant_run: Mapped["AssistantRun | None"] = relationship(
        "AssistantRun",
        back_populates="messages",
    )
