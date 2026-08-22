from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import BusinessBase


class ClientContactPoint(BusinessBase):
    __tablename__ = "client_contact_points"
    __table_args__ = (
        CheckConstraint("kind IN ('email', 'phone')", name="ck_client_contact_points_kind"),
        CheckConstraint(
            "origin IN ('manual', 'gmail', 'sheets', 'migration', 'other')",
            name="ck_client_contact_points_origin",
        ),
        Index(
            "uq_client_contact_points_client_kind_normalized",
            "client_id",
            "kind",
            "normalized_value",
            unique=True,
        ),
        Index("ix_client_contact_points_client_kind", "client_id", "kind"),
        Index("ix_client_contact_points_source_id", "source_id"),
        ForeignKeyConstraint(
            ["contact_person_id", "client_id"],
            ["contact_persons.id", "contact_persons.client_id"],
            name="fk_client_contact_points_person_client",
            ondelete="RESTRICT",
        ),
        Index("ix_client_contact_points_contact_person_id", "contact_person_id"),
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
    origin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_sources.id", ondelete="RESTRICT"), nullable=True
    )
    contact_person_id: Mapped[int | None] = mapped_column(nullable=True)

    client: Mapped["Client"] = relationship("Client", back_populates="contact_points")
    contact_person: Mapped["ContactPerson | None"] = relationship(
        "ContactPerson",
        back_populates="contact_points",
        primaryjoin="and_(ClientContactPoint.contact_person_id == ContactPerson.id, ClientContactPoint.client_id == ContactPerson.client_id)",
        foreign_keys="[ClientContactPoint.contact_person_id, ClientContactPoint.client_id]",
        overlaps="client,contact_points",
    )
