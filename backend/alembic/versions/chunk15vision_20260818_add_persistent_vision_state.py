"""Add persistent Vision processing state.

Revision ID: chunk15vision_20260818
Revises: inspectclient_20260818
"""

from alembic import op
import sqlalchemy as sa


revision = "chunk15vision_20260818"
down_revision = "inspectclient_20260818"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("vision_classification", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "vision_status",
            sa.String(length=30),
            server_default="not_evaluated",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "vision_auto_eligible",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "vision_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("vision_next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("vision_error_code", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("vision_analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("vision_schema_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("vision_source_checksum", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_documents_vision_auto_eligible_status",
        "documents",
        ["vision_auto_eligible", "vision_status"],
        unique=False,
    )
    op.create_index(
        "ix_documents_vision_next_retry_at",
        "documents",
        ["vision_next_retry_at"],
        unique=False,
    )

    _add_source_state("document_pages")
    op.create_index(
        "ix_document_pages_vision_status",
        "document_pages",
        ["vision_status"],
        unique=False,
    )

    _add_source_state("document_assets")
    op.create_index(
        "ix_document_assets_vision_status",
        "document_assets",
        ["vision_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_assets_vision_status", table_name="document_assets")
    _drop_source_state("document_assets")

    op.drop_index("ix_document_pages_vision_status", table_name="document_pages")
    _drop_source_state("document_pages")

    op.drop_index("ix_documents_vision_next_retry_at", table_name="documents")
    op.drop_index(
        "ix_documents_vision_auto_eligible_status",
        table_name="documents",
    )
    for column in (
        "vision_source_checksum",
        "vision_schema_version",
        "vision_analyzed_at",
        "vision_error_code",
        "vision_next_retry_at",
        "vision_attempt_count",
        "vision_auto_eligible",
        "vision_status",
        "vision_classification",
    ):
        op.drop_column("documents", column)


def _add_source_state(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            "vision_status",
            sa.String(length=30),
            server_default="not_evaluated",
            nullable=False,
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            "vision_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        table_name,
        sa.Column("vision_error_code", sa.String(length=100), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("vision_analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("vision_schema_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("vision_source_checksum", sa.String(length=64), nullable=True),
    )


def _drop_source_state(table_name: str) -> None:
    for column in (
        "vision_source_checksum",
        "vision_schema_version",
        "vision_analyzed_at",
        "vision_error_code",
        "vision_attempt_count",
        "vision_status",
    ):
        op.drop_column(table_name, column)
