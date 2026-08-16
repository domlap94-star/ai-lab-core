from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import BusinessBase


class ClientAddress(BusinessBase):
    __tablename__ = "client_addresses"
    __table_args__ = (
        CheckConstraint(
            "char_length(country_code) = 2",
            name="ck_client_addresses_country_code",
        ),
        CheckConstraint(
            "origin IN ('manual', 'gmail', 'sheets', 'migration', 'other')",
            name="ck_client_addresses_origin",
        ),
        Index("ix_client_addresses_client", "client_id"),
        Index("ix_client_addresses_source", "source_id"),
    )

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="Adres")
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    building_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(150), nullable=True)
    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False, default="PL", server_default="PL"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_sources.id", ondelete="RESTRICT"), nullable=True
    )

    client: Mapped["Client"] = relationship("Client", back_populates="address_records")
