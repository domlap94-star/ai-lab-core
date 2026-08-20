from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TrashEntry(Base):
    __tablename__ = "trash_entries"
    __table_args__ = (
        CheckConstraint("entity_type IN ('document','client','user')", name="ck_trash_entries_entity_type"),
        CheckConstraint("state IN ('trashed','purging','blocked','restored','purged')", name="ck_trash_entries_state"),
        CheckConstraint("attempt_count >= 0", name="ck_trash_entries_attempt_count"),
        CheckConstraint("purge_after = trashed_at + interval '7 days'", name="ck_trash_entries_exact_retention"),
        Index(
            "uq_trash_entries_active_entity",
            "entity_type",
            "entity_id",
            unique=True,
            postgresql_where=text("state IN ('trashed','purging','blocked')"),
        ),
        Index("ix_trash_entries_purge_queue", "state", "purge_after", "id"),
        Index("ix_trash_entries_admin_list", "entity_type", "state", "trashed_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="trashed", server_default="trashed")
    safe_display_label: Mapped[str] = mapped_column(String(255), nullable=False)
    trashed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trashed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restored_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    purge_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
