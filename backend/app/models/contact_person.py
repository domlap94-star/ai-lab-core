from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import BusinessBase


class ContactPerson(BusinessBase):
    __tablename__ = "contact_persons"
    __table_args__ = (
        CheckConstraint(
            "char_length(trim(display_name)) > 0",
            name="ck_contact_persons_display_name_not_empty",
        ),
        CheckConstraint(
            "origin IN ('manual', 'gmail', 'sheets', 'migration', 'other')",
            name="ck_contact_persons_origin",
        ),
        UniqueConstraint("id", "client_id", name="uq_contact_persons_id_client"),
        Index("ix_contact_persons_client_position", "client_id", "position", "id"),
        Index("ix_contact_persons_source_id", "source_id"),
        Index(
            "uq_contact_persons_active_preferred_client",
            "client_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND is_preferred"),
        ),
    )

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_preferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_decision_maker: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_sources.id", ondelete="RESTRICT"), nullable=True
    )

    client: Mapped["Client"] = relationship("Client", back_populates="contact_persons")
    contact_points: Mapped[list["ClientContactPoint"]] = relationship(
        "ClientContactPoint",
        back_populates="contact_person",
        primaryjoin="and_(ContactPerson.id == ClientContactPoint.contact_person_id, ContactPerson.client_id == ClientContactPoint.client_id)",
        foreign_keys="[ClientContactPoint.contact_person_id, ClientContactPoint.client_id]",
        overlaps="client,contact_points",
        order_by="ClientContactPoint.position, ClientContactPoint.id",
    )
