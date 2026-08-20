from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class WorkItemDocument(Base):
    __tablename__ = "work_item_documents"
    __table_args__ = (
        ForeignKeyConstraint(["note_id", "work_item_id"], ["work_item_notes.id", "work_item_notes.work_item_id"], name="fk_work_item_documents_note_owner", ondelete="RESTRICT"),
        CheckConstraint("(detached_at IS NULL) = (detached_by_user_id IS NULL)", name="ck_work_item_documents_detached"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_items.id", ondelete="RESTRICT"), nullable=False)
    note_id: Mapped[int | None] = mapped_column(BigInteger)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    attached_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    detached_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
