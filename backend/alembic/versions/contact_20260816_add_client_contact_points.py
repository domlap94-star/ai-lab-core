"""add client contact points

Revision ID: contact_20260816
Revises: userlife_20260815
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "contact_20260816"
down_revision: Union[str, Sequence[str], None] = "userlife_20260815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_contact_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('email', 'phone')", name="ck_client_contact_points_kind"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_contact_points_client_kind", "client_contact_points", ["client_id", "kind"])
    op.create_index(
        "uq_client_contact_points_client_kind_normalized",
        "client_contact_points",
        ["client_id", "kind", "normalized_value"],
        unique=True,
    )
    # Preserve each existing scalar as one contact. Deliberately do not split,
    # repair, or deduplicate historical values.
    op.execute(sa.text("""
        INSERT INTO client_contact_points
            (client_id, kind, value, normalized_value, is_primary, position)
        SELECT id, 'email', primary_email, lower(trim(primary_email)), true, 0
        FROM clients WHERE primary_email IS NOT NULL AND trim(primary_email) <> ''
    """))
    op.execute(sa.text("""
        INSERT INTO client_contact_points
            (client_id, kind, value, normalized_value, is_primary, position)
        SELECT id, 'phone', primary_phone,
               regexp_replace(primary_phone, '[^0-9+]', '', 'g'), true, 0
        FROM clients WHERE primary_phone IS NOT NULL AND trim(primary_phone) <> ''
    """))


def downgrade() -> None:
    op.drop_index("uq_client_contact_points_client_kind_normalized", table_name="client_contact_points")
    op.drop_index("ix_client_contact_points_client_kind", table_name="client_contact_points")
    op.drop_table("client_contact_points")
