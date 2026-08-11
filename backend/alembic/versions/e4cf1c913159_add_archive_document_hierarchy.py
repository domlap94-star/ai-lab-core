"""add archive document hierarchy

Revision ID: e4cf1c913159
Revises: dbf64f24e0c4
Create Date: 2026-08-11 11:11:43.932599
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4cf1c913159"
down_revision: Union[str, Sequence[str], None] = "dbf64f24e0c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "parent_document_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "archive_member_path",
            sa.String(length=2000),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "archive_depth",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_documents_archive_depth_positive",
        "documents",
        "archive_depth >= 0",
    )

    op.create_index(
        "ix_documents_parent_archive_member",
        "documents",
        [
            "parent_document_id",
            "archive_member_path",
        ],
        unique=False,
    )

    op.create_index(
        "ix_documents_parent_document_id",
        "documents",
        [
            "parent_document_id",
        ],
        unique=False,
    )

    op.create_foreign_key(
        "fk_documents_parent_document_id",
        "documents",
        "documents",
        [
            "parent_document_id",
        ],
        [
            "id",
        ],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_parent_document_id",
        "documents",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_documents_parent_document_id",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_parent_archive_member",
        table_name="documents",
    )

    op.drop_constraint(
        "ck_documents_archive_depth_positive",
        "documents",
        type_="check",
    )

    op.drop_column(
        "documents",
        "archive_depth",
    )

    op.drop_column(
        "documents",
        "archive_member_path",
    )

    op.drop_column(
        "documents",
        "parent_document_id",
    )