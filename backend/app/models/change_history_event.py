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


class ChangeHistoryEvent(Base):
    __tablename__ = "change_history_events"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('client','client_contact','client_address',"
            "'client_workflow_status','client_candidate','candidate_merge',"
            "'ignored_mail_source','user','work_item','work_item_note',"
            "'work_item_document','absence_request','document',"
            "'knowledge_base_item','contact_person')",
            name="ck_change_history_events_entity_type",
        ),
        CheckConstraint(
            "action IN ('created','updated','deleted','restored',"
            "'status_changed','accepted','rejected','merged','activated',"
            "'deactivated','trashed','purged','processing_retried')",
            name="ck_change_history_events_action",
        ),
        UniqueConstraint(
            "source_key", name="uq_change_history_events_source_key"
        ),
        Index(
            "ix_change_history_events_created_id", "created_at", "id"
        ),
        Index(
            "ix_change_history_events_entity_created_id",
            "entity_type",
            "entity_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_change_history_events_actor_created_id",
            "actor_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    before_values: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    after_values: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
