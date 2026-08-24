from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    DateTime,
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

    client_added_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    industry: Mapped["Industry | None"] = relationship(
        "Industry",
        back_populates="clients",
    )

    contact_points: Mapped[list["ClientContactPoint"]] = relationship(
        "ClientContactPoint",
        back_populates="client",
        order_by="ClientContactPoint.position, ClientContactPoint.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    contact_persons: Mapped[list["ContactPerson"]] = relationship(
        "ContactPerson",
        back_populates="client",
        order_by="ContactPerson.position, ContactPerson.id",
        passive_deletes=True,
    )

    @property
    def active_contact_persons(self):
        return [item for item in self.contact_persons if item.deleted_at is None]

    address_records: Mapped[list["ClientAddress"]] = relationship(
        "ClientAddress",
        back_populates="client",
        order_by="ClientAddress.position, ClientAddress.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="client",
        passive_deletes=True,
    )

    inspections: Mapped[list["Inspection"]] = relationship(
        "Inspection",
        back_populates="client",
        passive_deletes=True,
    )

    @property
    def emails(self):
        return [item for item in self.contact_points if item.kind == "email" and item.deleted_at is None]

    @property
    def phones(self):
        return [item for item in self.contact_points if item.kind == "phone" and item.deleted_at is None]

    @property
    def addresses(self):
        # Historical candidate merges could persist a country-only relation.
        # Such a row is not a usable address and cannot satisfy ClientAddressRead.
        # Keep the database evidence intact while omitting the invalid relation
        # from every read projection.
        return [
            item
            for item in self.address_records
            if item.deleted_at is None
            and any(
                isinstance(value, str) and bool(value.strip())
                for value in (
                    item.street,
                    item.building_number,
                    item.unit_number,
                    item.postal_code,
                    item.city,
                )
            )
        ]
