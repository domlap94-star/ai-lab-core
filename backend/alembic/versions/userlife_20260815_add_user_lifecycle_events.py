"""add durable user lifecycle events

Revision ID: userlife_20260815
Revises: authv1_20260813
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "userlife_20260815"
down_revision: Union[str, Sequence[str], None] = "authv1_20260813"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_lifecycle_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_lifecycle_events_actor_user_id",
        "user_lifecycle_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_user_lifecycle_events_target_user_id",
        "user_lifecycle_events",
        ["target_user_id"],
    )
    op.create_index(
        "ix_user_lifecycle_events_created_at",
        "user_lifecycle_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_lifecycle_events_created_at",
        table_name="user_lifecycle_events",
    )
    op.drop_index(
        "ix_user_lifecycle_events_target_user_id",
        table_name="user_lifecycle_events",
    )
    op.drop_index(
        "ix_user_lifecycle_events_actor_user_id",
        table_name="user_lifecycle_events",
    )
    op.drop_table("user_lifecycle_events")
