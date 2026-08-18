"""Make Inspection a client-owned record with an optional legacy Project."""

from alembic import op
import sqlalchemy as sa

revision = "inspectclient_20260818"
down_revision = "chunk11search_20260818"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "inspections",
        "project_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "inspections",
        "project_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
