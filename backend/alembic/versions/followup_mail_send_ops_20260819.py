"""Add the bounded Global Mail send operation ledger.

Revision ID: followup_mail_send_ops_20260819
Revises: followup_mail_nullable_read_state_20260819
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "followup_mail_send_ops_20260819"
down_revision = "followup_mail_nullable_read_state_20260819"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_send_operations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("payload_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column("client_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=1000), nullable=True),
        sa.Column("provider_thread_id", sa.String(length=1000), nullable=True),
        sa.Column("canonical_source_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_execution_ref", sa.String(length=255), nullable=True),
        sa.Column("recipient_count", sa.SmallInteger(), nullable=False),
        sa.Column("attachment_count", sa.SmallInteger(), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("provider_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('compose','reply','forward')", name="ck_mail_send_operations_action"),
        sa.CheckConstraint("status IN ('pending','provider_accepted','canonical_synced','failed','unknown')", name="ck_mail_send_operations_status"),
        sa.CheckConstraint("recipient_count BETWEEN 1 AND 50", name="ck_mail_send_operations_recipient_count"),
        sa.CheckConstraint("attachment_count BETWEEN 0 AND 10", name="ck_mail_send_operations_attachment_count"),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 3", name="ck_mail_send_operations_attempt_count"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_message_id"], ["candidate_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["canonical_source_id"], ["candidate_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", name="uq_mail_send_operations_operation_id"),
        sa.UniqueConstraint("provider_message_id", name="uq_mail_send_operations_provider_message_id"),
        sa.UniqueConstraint("canonical_source_id", name="uq_mail_send_operations_canonical_source_id"),
    )
    op.create_index("ix_mail_send_operations_status_updated", "mail_send_operations", ["status", "updated_at"])
    op.create_index("ix_mail_send_operations_actor_created", "mail_send_operations", ["actor_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_mail_send_operations_actor_created", table_name="mail_send_operations")
    op.drop_index("ix_mail_send_operations_status_updated", table_name="mail_send_operations")
    op.drop_table("mail_send_operations")
