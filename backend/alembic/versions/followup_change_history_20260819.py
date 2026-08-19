"""Add bounded generic admin change history.

Revision ID: followup_change_history_20260819
Revises: followup_client_activity_20260819
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_change_history_20260819"
down_revision = "followup_client_activity_20260819"
branch_labels = None
depends_on = None


_ENTITY_TYPES = (
    "client",
    "client_contact",
    "client_address",
    "client_workflow_status",
    "client_candidate",
    "candidate_merge",
)
_ACTIONS = (
    "created",
    "updated",
    "deleted",
    "restored",
    "status_changed",
    "accepted",
    "rejected",
    "merged",
)


def upgrade() -> None:
    entity_types = ", ".join(f"'{value}'" for value in _ENTITY_TYPES)
    actions = ", ".join(f"'{value}'" for value in _ACTIONS)
    op.create_table(
        "change_history_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("before_values", sa.JSON(), nullable=False),
        sa.Column("after_values", sa.JSON(), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=True),
        sa.Column("source_key", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"entity_type IN ({entity_types})",
            name="ck_change_history_events_entity_type",
        ),
        sa.CheckConstraint(
            f"action IN ({actions})",
            name="ck_change_history_events_action",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_key", name="uq_change_history_events_source_key"
        ),
    )
    op.create_index(
        "ix_change_history_events_created_id",
        "change_history_events",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_change_history_events_entity_created_id",
        "change_history_events",
        ["entity_type", "entity_id", "created_at", "id"],
    )
    op.create_index(
        "ix_change_history_events_actor_created_id",
        "change_history_events",
        ["actor_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_change_history_events_actor_created_id",
        table_name="change_history_events",
    )
    op.drop_index(
        "ix_change_history_events_entity_created_id",
        table_name="change_history_events",
    )
    op.drop_index(
        "ix_change_history_events_created_id",
        table_name="change_history_events",
    )
    op.drop_table("change_history_events")
