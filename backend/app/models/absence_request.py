from datetime import date, datetime
from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class AbsenceRequest(Base):
    __tablename__ = "absence_requests"
    __table_args__ = (
        CheckConstraint("absence_type IN ('vacation','day_off','sick_leave','other')", name="ck_absence_requests_type"),
        CheckConstraint("status IN ('requested','approved','rejected','cancelled')", name="ck_absence_requests_status"),
        CheckConstraint("end_date >= start_date", name="ck_absence_requests_dates"),
        CheckConstraint("note IS NULL OR char_length(note) <= 5000", name="ck_absence_requests_note_length"),
        CheckConstraint("review_note IS NULL OR char_length(review_note) <= 2000", name="ck_absence_requests_review_note_length"),
        CheckConstraint("version > 0", name="ck_absence_requests_version"),
        CheckConstraint("(status <> 'requested' OR (reviewed_by_user_id IS NULL AND reviewed_at IS NULL)) AND (status NOT IN ('approved','rejected') OR (reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL))", name="ck_absence_requests_reviewed"),
        CheckConstraint("(status = 'cancelled') = (cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL)", name="ck_absence_requests_cancelled"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    absence_type: Mapped[str] = mapped_column(String(24), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested", server_default="requested")
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
