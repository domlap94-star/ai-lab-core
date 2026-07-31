from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import BusinessBase


class Client(BusinessBase):
    __tablename__ = "clients"

    __table_args__ = (
        CheckConstraint(
            "client_type IN "
            "('company', 'person', 'institution', 'other')",
            name="ck_clients_client_type",
        ),
        CheckConstraint(
            "char_length(country_code) = 2",
            name="ck_clients_country_code_length",
        ),
        CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_clients_name_not_empty",
        ),
        Index(
            "ix_clients_name",
            "name",
        ),
        Index(
            "ix_clients_tax_id",
            "tax_id",
        ),
        Index(
            "ix_clients_primary_email",
            "primary_email",
        ),
        Index(
            "ix_clients_city",
            "city",
        ),
        Index(
            "ix_clients_deleted_at",
            "deleted_at",
        ),
    )

    client_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    legal_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    tax_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    industry_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "industries.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    primary_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    primary_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    street: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    building_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    unit_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="PL",
        server_default="PL",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    industry: Mapped["Industry | None"] = relationship(
        "Industry",
        back_populates="clients",
    )