"""Add persistent read-only Agent execution audit.

Revision ID: chunk16audit_20260819
Revises: chunk15vision_20260818
"""

from alembic import op
import sqlalchemy as sa


revision = "chunk16audit_20260819"
down_revision = "chunk15vision_20260818"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_executions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "tool_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("execution_metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'cancelled', 'blocked')",
            name="ck_agent_executions_status",
        ),
        sa.CheckConstraint(
            "tool_count >= 0",
            name="ck_agent_executions_tool_count_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_executions_duration_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_agent_executions_request_id"),
    )
    op.create_index(
        "ix_agent_executions_user_created_at",
        "agent_executions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_executions_status_created_at",
        "agent_executions",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_executions_status_created_at",
        table_name="agent_executions",
    )
    op.drop_index(
        "ix_agent_executions_user_created_at",
        table_name="agent_executions",
    )
    op.drop_table("agent_executions")
