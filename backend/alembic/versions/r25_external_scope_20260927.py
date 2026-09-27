"""add External role and auditable client access grants

Revision ID: r25_external_scope_20260927
Revises: followup_assistant_chat_history_20260829
"""

from alembic import op
import sqlalchemy as sa


revision = "r25_external_scope_20260927"
down_revision = "followup_assistant_chat_history_20260829"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO roles (name, description) "
            "SELECT 'External', 'Client-scoped external user' "
            "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name='External')"
        )
    )
    op.create_table(
        "client_access_grants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("external_user_id", sa.BigInteger(), nullable=False),
        sa.Column("granted_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["external_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_client_access_grants_external_active_client",
        "client_access_grants",
        ["external_user_id", "revoked_at", "client_id"],
    )
    op.create_index(
        "ix_client_access_grants_client_active_external",
        "client_access_grants",
        ["client_id", "revoked_at", "external_user_id"],
    )
    op.create_index(
        "uq_client_access_grants_active_pair",
        "client_access_grants",
        ["client_id", "external_user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    # Grant history is deliberately retained by operational rollback. This
    # destructive Alembic downgrade is available only for an explicitly
    # approved schema rollback.
    op.drop_index("uq_client_access_grants_active_pair", table_name="client_access_grants")
    op.drop_index("ix_client_access_grants_client_active_external", table_name="client_access_grants")
    op.drop_index("ix_client_access_grants_external_active_client", table_name="client_access_grants")
    op.drop_table("client_access_grants")
    op.execute(
        sa.text(
            "DELETE FROM roles WHERE name='External' "
            "AND NOT EXISTS (SELECT 1 FROM users WHERE users.role_id=roles.id)"
        )
    )
