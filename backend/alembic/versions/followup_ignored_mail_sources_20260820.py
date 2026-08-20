"""Add bounded ignored mail source rules.

Revision ID: followup_ignored_mail_sources_20260820
Revises: followup_mail_send_ops_20260819
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_ignored_mail_sources_20260820"
down_revision = "followup_mail_send_ops_20260819"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ignored_mail_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rule_type", sa.String(length=16), nullable=False),
        sa.Column("normalized_value", sa.String(length=320), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rule_type IN ('email','domain')", name="ck_ignored_mail_sources_rule_type"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_type", "normalized_value", name="uq_ignored_mail_sources_rule"),
    )


def downgrade() -> None:
    op.drop_table("ignored_mail_sources")
