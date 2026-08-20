"""Add the operational calendar, work items, notes, documents and absences.

Revision ID: followup_calendar_tasks_20260820
Revises: followup_change_history_entity_types_20260820
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_calendar_tasks_20260820"
down_revision = "followup_change_history_entity_types_20260820"
branch_labels = None
depends_on = None


_OLD_HISTORY_TYPES = (
    "client", "client_contact", "client_address", "client_workflow_status",
    "client_candidate", "candidate_merge", "ignored_mail_source", "user",
)
_NEW_HISTORY_TYPES = _OLD_HISTORY_TYPES + (
    "work_item", "work_item_note", "work_item_document", "absence_request",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_type", sa.String(24), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("timezone_name", sa.String(64), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("assignee_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("client_id", sa.BigInteger(), sa.ForeignKey("clients.id", ondelete="RESTRICT")),
        sa.Column("party_name", sa.String(255), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("item_type IN ('task','order','realization','reminder','event')", name="ck_work_items_type"),
        sa.CheckConstraint("status IN ('todo','in_progress','completed','cancelled')", name="ck_work_items_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_work_items_priority"),
        sa.CheckConstraint("char_length(trim(title)) > 0", name="ck_work_items_title"),
        sa.CheckConstraint("description IS NULL OR char_length(description) <= 20000", name="ck_work_items_description_length"),
        sa.CheckConstraint("due_at IS NULL OR start_at IS NULL OR due_at >= start_at", name="ck_work_items_time_order"),
        sa.CheckConstraint("item_type <> 'event' OR start_at IS NOT NULL", name="ck_work_items_event_start"),
        sa.CheckConstraint("item_type <> 'reminder' OR due_at IS NOT NULL", name="ck_work_items_reminder_due"),
        sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_work_items_completed"),
        sa.CheckConstraint("NOT all_day OR (start_at IS NOT NULL AND due_at IS NOT NULL AND char_length(trim(timezone_name)) > 0)", name="ck_work_items_all_day"),
        sa.CheckConstraint("version > 0", name="ck_work_items_version"),
    )
    op.create_index("ix_work_items_start_active", "work_items", ["start_at", "id"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_work_items_due_active", "work_items", ["due_at", "id"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_work_items_status_due_active", "work_items", ["status", "due_at", "id"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_work_items_assignee_status_due_active", "work_items", ["assignee_user_id", "status", "due_at", "id"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_work_items_client_type_created_active", "work_items", ["client_id", "item_type", sa.text("created_at DESC"), sa.text("id DESC")], postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "work_item_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("work_item_id", sa.BigInteger(), sa.ForeignKey("work_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("char_length(trim(text)) BETWEEN 1 AND 10000", name="ck_work_item_notes_text"),
        sa.CheckConstraint("version > 0", name="ck_work_item_notes_version"),
        sa.UniqueConstraint("id", "work_item_id", name="uq_work_item_notes_id_item"),
    )
    op.create_index("ix_work_item_notes_item_active", "work_item_notes", ["work_item_id", "created_at", "id"], postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "work_item_documents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("work_item_id", sa.BigInteger(), sa.ForeignKey("work_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note_id", sa.BigInteger(), nullable=True),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attached_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("detached_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("detached_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["note_id", "work_item_id"], ["work_item_notes.id", "work_item_notes.work_item_id"], name="fk_work_item_documents_note_owner", ondelete="RESTRICT"),
        sa.CheckConstraint("(detached_at IS NULL) = (detached_by_user_id IS NULL)", name="ck_work_item_documents_detached"),
    )
    op.create_index("ix_work_item_documents_item", "work_item_documents", ["work_item_id", "created_at", "id"])
    op.create_index("uq_work_item_documents_active", "work_item_documents", ["work_item_id", "document_id"], unique=True, postgresql_where=sa.text("detached_at IS NULL"))

    op.create_table(
        "absence_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requester_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("absence_type", sa.String(24), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("cancelled_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("absence_type IN ('vacation','day_off','sick_leave','other')", name="ck_absence_requests_type"),
        sa.CheckConstraint("status IN ('requested','approved','rejected','cancelled')", name="ck_absence_requests_status"),
        sa.CheckConstraint("end_date >= start_date", name="ck_absence_requests_dates"),
        sa.CheckConstraint("note IS NULL OR char_length(note) <= 5000", name="ck_absence_requests_note_length"),
        sa.CheckConstraint("review_note IS NULL OR char_length(review_note) <= 2000", name="ck_absence_requests_review_note_length"),
        sa.CheckConstraint("version > 0", name="ck_absence_requests_version"),
        sa.CheckConstraint("(status <> 'requested' OR (reviewed_by_user_id IS NULL AND reviewed_at IS NULL)) AND (status NOT IN ('approved','rejected') OR (reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL))", name="ck_absence_requests_reviewed"),
        sa.CheckConstraint("(status = 'cancelled') = (cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL)", name="ck_absence_requests_cancelled"),
    )
    op.create_index("ix_absence_requests_requester_range", "absence_requests", ["requester_user_id", "start_date", "end_date"])
    op.create_index("ix_absence_requests_status_range", "absence_requests", ["status", "start_date", "end_date"])

    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_entity_type", "change_history_events", f"entity_type IN ({_quoted(_NEW_HISTORY_TYPES)})")


def downgrade() -> None:
    connection = op.get_bind()
    feature_rows = sum(connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one() for table in ("work_items", "work_item_notes", "work_item_documents", "absence_requests"))
    history_rows = connection.execute(sa.text("SELECT count(*) FROM change_history_events WHERE entity_type IN ('work_item','work_item_note','work_item_document','absence_request')")).scalar_one()
    if feature_rows or history_rows:
        raise RuntimeError("Refusing destructive CHUNK 13 downgrade while feature or audit rows exist")
    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_entity_type", "change_history_events", f"entity_type IN ({_quoted(_OLD_HISTORY_TYPES)})")
    op.drop_table("absence_requests")
    op.drop_table("work_item_documents")
    op.drop_table("work_item_notes")
    op.drop_table("work_items")
