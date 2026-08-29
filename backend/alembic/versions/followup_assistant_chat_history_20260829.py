"""Add durable Assistant chat-history relationships.

Revision ID: followup_assistant_chat_history_20260829
Revises: followup_assistant_pipeline_v2_20260826

This revision is intentionally additive. Existing conversations remain legacy
chat rows, and existing Assistant runs/messages remain unbound. No historical
conversation or run backfill is performed.
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_assistant_chat_history_20260829"
down_revision = "followup_assistant_pipeline_v2_20260826"
branch_labels = None
depends_on = None


_DOWNGRADE_REFUSAL = "assistant_chat_history_downgrade_refused"


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "kind",
            sa.String(24),
            nullable=False,
            server_default="legacy_chat",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("last_activity_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "conversations",
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_check_constraint(
        "ck_conversations_kind",
        "conversations",
        "kind IN ('legacy_chat','assistant_v2')",
    )
    op.create_index(
        "ix_conversations_history_active",
        "conversations",
        [
            "user_id",
            "kind",
            sa.text("last_activity_at DESC"),
            sa.text("id DESC"),
        ],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "assistant_runs",
        sa.Column("conversation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_assistant_runs_conversation_id_conversations",
        "assistant_runs",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_assistant_runs_conversation_created",
        "assistant_runs",
        ["conversation_id", "created_at", "id"],
    )

    op.add_column(
        "messages",
        sa.Column("assistant_run_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_assistant_run_id_assistant_runs",
        "messages",
        "assistant_runs",
        ["assistant_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_messages_role",
        "messages",
        "role IN ('user','assistant')",
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at", "id"],
    )
    op.create_index(
        "uq_messages_assistant_run_role",
        "messages",
        ["assistant_run_id", "role"],
        unique=True,
        postgresql_where=sa.text("assistant_run_id IS NOT NULL"),
    )


def _downgrade_violations() -> list[str]:
    bind = op.get_bind()
    checks = (
        (
            "assistant_v2_conversation",
            "SELECT EXISTS (SELECT 1 FROM conversations WHERE kind <> 'legacy_chat')",
        ),
        (
            "conversation_deleted_at",
            "SELECT EXISTS (SELECT 1 FROM conversations WHERE deleted_at IS NOT NULL)",
        ),
        (
            "conversation_last_activity_at",
            "SELECT EXISTS (SELECT 1 FROM conversations WHERE last_activity_at IS NOT NULL)",
        ),
        (
            "assistant_run_conversation_id",
            "SELECT EXISTS (SELECT 1 FROM assistant_runs WHERE conversation_id IS NOT NULL)",
        ),
        (
            "message_assistant_run_id",
            "SELECT EXISTS (SELECT 1 FROM messages WHERE assistant_run_id IS NOT NULL)",
        ),
    )
    return [name for name, sql in checks if bool(bind.execute(sa.text(sql)).scalar_one())]


def downgrade() -> None:
    violations = _downgrade_violations()
    if violations:
        raise RuntimeError(f"{_DOWNGRADE_REFUSAL}:{','.join(violations)}")

    op.drop_index("uq_messages_assistant_run_role", table_name="messages")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_constraint("ck_messages_role", "messages", type_="check")
    op.drop_constraint(
        "fk_messages_assistant_run_id_assistant_runs",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "assistant_run_id")

    op.drop_index(
        "ix_assistant_runs_conversation_created",
        table_name="assistant_runs",
    )
    op.drop_constraint(
        "fk_assistant_runs_conversation_id_conversations",
        "assistant_runs",
        type_="foreignkey",
    )
    op.drop_column("assistant_runs", "conversation_id")

    op.drop_index("ix_conversations_history_active", table_name="conversations")
    op.drop_constraint("ck_conversations_kind", "conversations", type_="check")
    op.drop_column("conversations", "deleted_at")
    op.drop_column("conversations", "last_activity_at")
    op.drop_column("conversations", "kind")
