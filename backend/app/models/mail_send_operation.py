from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MailSendOperation(Base):
    __tablename__ = "mail_send_operations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), unique=True, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("candidate_sources.id", ondelete="RESTRICT"))
    client_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"))
    provider_message_id: Mapped[str | None] = mapped_column(String(1000), unique=True)
    provider_thread_id: Mapped[str | None] = mapped_column(String(1000))
    canonical_source_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("candidate_sources.id", ondelete="RESTRICT"), unique=True)
    provider_execution_ref: Mapped[str | None] = mapped_column(String(255))
    recipient_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    attachment_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    provider_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
