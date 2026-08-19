"""Add bounded Client activity events.

Revision ID: followup_client_activity_20260819
Revises: followup_candidate_merge_audit_20260819
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_client_activity_20260819"
down_revision = "followup_candidate_merge_audit_20260819"
branch_labels = None
depends_on = None


_EVENT_TYPES = (
    "call_initiated", "client_status_changed", "email_received", "email_sent",
    "document_added", "inspection_created", "candidate_merged", "task_created",
    "task_completed", "realization_created", "note_added",
)


def upgrade() -> None:
    allowed = ", ".join(f"'{value}'" for value in _EVENT_TYPES)
    op.create_table(
        "client_activity_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"event_type IN ({allowed})", name="ck_client_activity_events_type"),
        sa.CheckConstraint("direction IS NULL OR direction IN ('incoming', 'outgoing')", name="ck_client_activity_events_direction"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_client_activity_events_source_key"),
    )
    op.create_index(
        "ix_client_activity_events_client_occurred_id",
        "client_activity_events",
        ["client_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_activity_events_client_occurred_id", table_name="client_activity_events")
    op.drop_table("client_activity_events")
