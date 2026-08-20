"""Add recoverable admin trash and retention lifecycle.

Revision ID: followup_admin_trash_retention_20260820
Revises: followup_calendar_tasks_20260820
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_admin_trash_retention_20260820"
down_revision = "followup_calendar_tasks_20260820"
branch_labels = None
depends_on = None

_OLD_HISTORY_TYPES = (
    "client", "client_contact", "client_address", "client_workflow_status",
    "client_candidate", "candidate_merge", "ignored_mail_source", "user",
    "work_item", "work_item_note", "work_item_document", "absence_request",
)
_NEW_HISTORY_TYPES = _OLD_HISTORY_TYPES + ("document",)
_OLD_HISTORY_ACTIONS = (
    "created", "updated", "deleted", "restored", "status_changed",
    "accepted", "rejected", "merged", "activated", "deactivated",
)
_NEW_HISTORY_ACTIONS = _OLD_HISTORY_ACTIONS + ("trashed", "purged")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column("documents", sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_trashed_at", "documents", ["trashed_at"])
    op.create_index("ix_documents_purged_at", "documents", ["purged_at"])

    op.add_column("clients", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_clients_purged_at", "clients", ["purged_at"])

    op.add_column("users", sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_users_auth_version_nonnegative", "users", "auth_version >= 0")
    op.create_index("ix_users_trashed_at", "users", ["trashed_at"])
    op.create_index("ix_users_purged_at", "users", ["purged_at"])

    op.create_table(
        "trash_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="trashed"),
        sa.Column("safe_display_label", sa.String(255), nullable=False),
        sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trashed_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("purge_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("entity_type IN ('document','client','user')", name="ck_trash_entries_entity_type"),
        sa.CheckConstraint("state IN ('trashed','purging','blocked','restored','purged')", name="ck_trash_entries_state"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_trash_entries_attempt_count"),
        sa.CheckConstraint("purge_after = trashed_at + interval '7 days'", name="ck_trash_entries_exact_retention"),
    )
    op.create_index(
        "uq_trash_entries_active_entity", "trash_entries", ["entity_type", "entity_id"],
        unique=True, postgresql_where=sa.text("state IN ('trashed','purging','blocked')"),
    )
    op.create_index("ix_trash_entries_purge_queue", "trash_entries", ["state", "purge_after", "id"])
    op.create_index("ix_trash_entries_admin_list", "trash_entries", ["entity_type", "state", "trashed_at", "id"])

    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_entity_type", "change_history_events", f"entity_type IN ({_quoted(_NEW_HISTORY_TYPES)})")
    op.drop_constraint("ck_change_history_events_action", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_action", "change_history_events", f"action IN ({_quoted(_NEW_HISTORY_ACTIONS)})")


def downgrade() -> None:
    connection = op.get_bind()
    used = connection.execute(sa.text("SELECT count(*) FROM trash_entries")).scalar_one()
    marked = connection.execute(sa.text(
        "SELECT (SELECT count(*) FROM documents WHERE trashed_at IS NOT NULL OR purged_at IS NOT NULL) + "
        "(SELECT count(*) FROM clients WHERE purged_at IS NOT NULL) + "
        "(SELECT count(*) FROM users WHERE trashed_at IS NOT NULL OR purged_at IS NOT NULL OR auth_version <> 0)"
    )).scalar_one()
    history = connection.execute(sa.text(
        "SELECT count(*) FROM change_history_events WHERE entity_type='document' OR action IN ('trashed','purged')"
    )).scalar_one()
    if used or marked or history:
        raise RuntimeError("Refusing Trash downgrade after lifecycle data exists")
    op.drop_constraint("ck_change_history_events_action", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_action", "change_history_events", f"action IN ({_quoted(_OLD_HISTORY_ACTIONS)})")
    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_entity_type", "change_history_events", f"entity_type IN ({_quoted(_OLD_HISTORY_TYPES)})")
    op.drop_table("trash_entries")
    op.drop_index("ix_users_purged_at", table_name="users")
    op.drop_index("ix_users_trashed_at", table_name="users")
    op.drop_constraint("ck_users_auth_version_nonnegative", "users", type_="check")
    op.drop_column("users", "auth_version")
    op.drop_column("users", "purged_at")
    op.drop_column("users", "trashed_at")
    op.drop_index("ix_clients_purged_at", table_name="clients")
    op.drop_column("clients", "purged_at")
    op.drop_index("ix_documents_purged_at", table_name="documents")
    op.drop_index("ix_documents_trashed_at", table_name="documents")
    op.drop_column("documents", "purged_at")
    op.drop_column("documents", "trashed_at")
