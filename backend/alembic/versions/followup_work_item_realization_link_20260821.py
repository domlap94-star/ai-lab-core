"""Link calendar realizations to canonical projects.

Revision ID: followup_work_item_realization_link_20260821
Revises: followup_admin_trash_retention_20260820
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_work_item_realization_link_20260821"
down_revision = "followup_admin_trash_retention_20260820"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_work_items_project_id", "work_items", ["project_id"], unique=True)


def downgrade() -> None:
    linked = op.get_bind().execute(
        sa.text("SELECT count(*) FROM work_items WHERE project_id IS NOT NULL")
    ).scalar_one()
    if linked:
        raise RuntimeError("Refusing realization-link downgrade while linked WorkItems exist")
    op.drop_index("ix_work_items_project_id", table_name="work_items")
    op.drop_column("work_items", "project_id")
