"""add document metadata fields

Revision ID: dbf64f24e0c4
Revises: 05b237160781
Create Date: 2026-08-10 20:43:16.639291
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dbf64f24e0c4"
down_revision: Union[str, Sequence[str], None] = "05b237160781"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "metadata_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "metadata_raw",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "metadata_normalized",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "metadata_error",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "metadata_extracted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_documents_metadata_status",
        "documents",
        "metadata_status IN "
        "('pending', 'processed', 'unsupported', 'failed')",
    )

    op.create_index(
        "ix_documents_metadata_status",
        "documents",
        ["metadata_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_documents_metadata_status",
        table_name="documents",
    )

    op.drop_constraint(
        "ck_documents_metadata_status",
        "documents",
        type_="check",
    )

    op.drop_column(
        "documents",
        "metadata_extracted_at",
    )

    op.drop_column(
        "documents",
        "metadata_error",
    )

    op.drop_column(
        "documents",
        "metadata_normalized",
    )

    op.drop_column(
        "documents",
        "metadata_raw",
    )

    op.drop_column(
        "documents",
        "metadata_status",
    )