"""add canonical date-only inspection schedule

Revision ID: r26_step2_20260928
Revises: r25_external_scope_20260927
"""

from alembic import op
import sqlalchemy as sa


revision = "r26_step2_20260928"
down_revision = "r25_external_scope_20260927"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inspections", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.create_index("ix_inspections_scheduled_date", "inspections", ["scheduled_date"])
    op.execute(
        sa.text(
            "UPDATE inspections SET scheduled_date = "
            "COALESCE(timezone('Europe/Warsaw', scheduled_at)::date, "
            "timezone('Europe/Warsaw', started_at)::date) "
            "WHERE scheduled_date IS NULL "
            "AND (scheduled_at IS NOT NULL OR started_at IS NOT NULL)"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "R26 scheduled_date is forward-only; destructive downgrade requires separate approval"
    )
