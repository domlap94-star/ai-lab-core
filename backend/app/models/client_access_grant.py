from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ClientAccessGrant(Base):
    """Auditable client access granted to an External user."""

    __tablename__ = "client_access_grants"
    __table_args__ = (
        Index(
            "ix_client_access_grants_external_active_client",
            "external_user_id",
            "revoked_at",
            "client_id",
        ),
        Index(
            "ix_client_access_grants_client_active_external",
            "client_id",
            "revoked_at",
            "external_user_id",
        ),
        Index(
            "uq_client_access_grants_active_pair",
            "client_id",
            "external_user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    external_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    granted_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client = relationship("Client")
    external_user = relationship("User", foreign_keys=[external_user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by_user_id])
