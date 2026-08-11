"""add document assets

Revision ID: 844bcf408c63
Revises: e4cf1c913159
Create Date: 2026-08-11 12:07:19.147339
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "844bcf408c63"
down_revision: Union[str, Sequence[str], None] = "e4cf1c913159"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_assets",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "asset_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "container_name",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "asset_type",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "source_format",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "mime_type",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "original_name",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column(
            "storage_path",
            sa.String(length=2000),
            nullable=False,
        ),
        sa.Column(
            "width",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "height",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "checksum_sha256",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "extraction_method",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "ocr_text",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "ocr_confidence",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "vision_analysis",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "processing_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "processing_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "processing_status IN "
            "('pending', 'extracted', 'processed', "
            "'no_text', 'unsupported', 'failed')",
            name="ck_document_assets_processing_status",
        ),
        sa.CheckConstraint(
            "asset_index >= 1",
            name="ck_document_assets_asset_index_positive",
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_document_assets_page_number_positive",
        ),
        sa.CheckConstraint(
            "width IS NULL OR width > 0",
            name="ck_document_assets_width_positive",
        ),
        sa.CheckConstraint(
            "height IS NULL OR height > 0",
            name="ck_document_assets_height_positive",
        ),
        sa.CheckConstraint(
            "ocr_confidence IS NULL OR "
            "(ocr_confidence >= 0 AND ocr_confidence <= 100)",
            name="ck_document_assets_ocr_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_assets_document_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "document_id",
            "asset_index",
            name="uq_document_assets_document_asset_index",
        ),
    )

    op.create_index(
        "ix_document_assets_document_id",
        "document_assets",
        ["document_id"],
        unique=False,
    )

    op.create_index(
        "ix_document_assets_processing_status",
        "document_assets",
        ["processing_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_assets_processing_status",
        table_name="document_assets",
    )

    op.drop_index(
        "ix_document_assets_document_id",
        table_name="document_assets",
    )

    op.drop_table(
        "document_assets",
    )