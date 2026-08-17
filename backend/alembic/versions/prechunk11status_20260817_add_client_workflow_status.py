"""add persistent client workflow status

Revision ID: prechunk11status_20260817
Revises: chunk10binspect_20260817
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "prechunk11status_20260817"
down_revision: Union[str, Sequence[str], None] = "chunk10binspect_20260817"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_workflow_statuses",
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('obsolete', 'in_progress', 'inspection', "
            "'completed', 'untouched', 'phone_contact')",
            name="ck_client_workflow_statuses_status",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_client_workflow_statuses_client",
        "client_workflow_statuses", ["client_id"], unique=True,
    )
    op.create_index(
        "ix_client_workflow_statuses_status",
        "client_workflow_statuses", ["status"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_workflow_statuses_status", table_name="client_workflow_statuses"
    )
    op.drop_index(
        "uq_client_workflow_statuses_client", table_name="client_workflow_statuses"
    )
    op.drop_table("client_workflow_statuses")
