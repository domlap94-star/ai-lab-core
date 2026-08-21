from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        CheckConstraint("item_type IN ('task','order','realization','reminder','event')", name="ck_work_items_type"),
        CheckConstraint("status IN ('todo','in_progress','completed','cancelled')", name="ck_work_items_status"),
        CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_work_items_priority"),
        CheckConstraint("char_length(trim(title)) > 0", name="ck_work_items_title"),
        CheckConstraint("description IS NULL OR char_length(description) <= 20000", name="ck_work_items_description_length"),
        CheckConstraint("due_at IS NULL OR start_at IS NULL OR due_at >= start_at", name="ck_work_items_time_order"),
        CheckConstraint("item_type <> 'event' OR start_at IS NOT NULL", name="ck_work_items_event_start"),
        CheckConstraint("item_type <> 'reminder' OR due_at IS NOT NULL", name="ck_work_items_reminder_due"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_work_items_completed"),
        CheckConstraint("NOT all_day OR (start_at IS NOT NULL AND due_at IS NOT NULL AND char_length(trim(timezone_name)) > 0)", name="ck_work_items_all_day"),
        CheckConstraint("version > 0", name="ck_work_items_version"),
        Index("ix_work_items_start_active", "start_at", "id", postgresql_where="deleted_at IS NULL"),
        Index("ix_work_items_due_active", "due_at", "id", postgresql_where="deleted_at IS NULL"),
        Index("ix_work_items_status_due_active", "status", "due_at", "id", postgresql_where="deleted_at IS NULL"),
        Index("ix_work_items_assignee_status_due_active", "assignee_user_id", "status", "due_at", "id", postgresql_where="deleted_at IS NULL"),
        Index("ix_work_items_project_id", "project_id", unique=True),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    timezone_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="todo", server_default="todo")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", server_default="normal")
    assignee_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    client_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"))
    project_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="RESTRICT"))
    party_name: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    project: Mapped["Project | None"] = relationship("Project", back_populates="work_item")
