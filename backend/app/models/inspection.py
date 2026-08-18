from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import BusinessBase


class Inspection(BusinessBase):
    __tablename__ = "inspections"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="ck_inspections_status",
        ),
        CheckConstraint(
            "char_length(trim(title)) > 0",
            name="ck_inspections_title_not_empty",
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_inspections_coordinates_pair",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_inspections_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_inspections_longitude_range",
        ),
        CheckConstraint(
            "location_accuracy_m IS NULL OR location_accuracy_m >= 0",
            name="ck_inspections_location_accuracy_positive",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_inspections_completed_after_started",
        ),
        Index("ix_inspections_project_id", "project_id"),
        Index("ix_inspections_client_id", "client_id"),
        Index("ix_inspections_status", "status"),
        Index("ix_inspections_scheduled_at", "scheduled_at"),
        Index("ix_inspections_deleted_at", "deleted_at"),
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned", server_default="planned"
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_accuracy_m: Mapped[float | None] = mapped_column(Float)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )

    project = relationship("Project", back_populates="inspections")
    client = relationship("Client", back_populates="inspections")
    documents = relationship("Document", back_populates="inspection", passive_deletes=True)
