"""Add the explicit Client business added date.

Revision ID: followup_clientdate_20260819
Revises: chunk16audit_20260819
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_clientdate_20260819"
down_revision = "chunk16audit_20260819"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("client_added_at", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "client_added_at")
