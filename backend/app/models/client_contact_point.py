from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import BusinessBase


class ClientContactPoint(BusinessBase):
    __tablename__ = "client_contact_points"
    __table_args__ = (
        CheckConstraint("kind IN ('email', 'phone')", name="ck_client_contact_points_kind"),
        Index(
            "uq_client_contact_points_client_kind_normalized",
            "client_id",
            "kind",
            "normalized_value",
            unique=True,
        ),
        Index("ix_client_contact_points_client_kind", "client_id", "kind"),
    )

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    client: Mapped["Client"] = relationship("Client", back_populates="contact_points")
