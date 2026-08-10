"""extend documents for uploads and matching

Revision ID: 8002e151f16f
Revises: f497dd01236f
Create Date: 2026-08-04 10:19:08.049816

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8002e151f16f"
down_revision: Union[str, Sequence[str], None] = "f497dd01236f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "documents",
        sa.Column(
            "original_filename",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "storage_path",
            sa.String(length=2000),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "checksum_sha256",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "source_type",
            sa.String(length=30),
            server_default="manual_upload",
            nullable=False,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "external_id",
            sa.String(length=1000),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "gmail_message_id",
            sa.String(length=1000),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "gmail_thread_id",
            sa.String(length=1000),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "candidate_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "client_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "processing_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "processing_error",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "extracted_text",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "match_status",
            sa.String(length=30),
            server_default="unmatched",
            nullable=False,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "match_confidence",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "match_method",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.alter_column(
        "documents",
        "content_type",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )

    op.create_check_constraint(
        "ck_documents_source_type",
        "documents",
        "source_type IN ('manual_upload', 'gmail_attachment')",
    )

    op.create_check_constraint(
        "ck_documents_processing_status",
        "documents",
        "processing_status IN "
        "('pending', 'stored', 'extracting', 'processed', 'failed')",
    )

    op.create_check_constraint(
        "ck_documents_match_status",
        "documents",
        "match_status IN "
        "('unmatched', 'suggested', 'matched', 'confirmed', 'rejected')",
    )

    op.create_check_constraint(
        "ck_documents_match_confidence_range",
        "documents",
        "match_confidence IS NULL OR "
        "(match_confidence >= 0 AND match_confidence <= 1)",
    )

    op.create_index(
        "ix_documents_candidate_id",
        "documents",
        ["candidate_id"],
        unique=False,
    )

    op.create_index(
        "ix_documents_checksum_sha256",
        "documents",
        ["checksum_sha256"],
        unique=False,
    )

    op.create_index(
        "ix_documents_client_id",
        "documents",
        ["client_id"],
        unique=False,
    )

    op.create_index(
        "ix_documents_gmail_message_id",
        "documents",
        ["gmail_message_id"],
        unique=False,
    )

    op.create_index(
        "ix_documents_match_status",
        "documents",
        ["match_status"],
        unique=False,
    )

    op.create_index(
        "ix_documents_processing_status",
        "documents",
        ["processing_status"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_documents_source_external_id",
        "documents",
        ["source_type", "external_id"],
    )

    op.create_foreign_key(
        "fk_documents_candidate_id",
        "documents",
        "client_candidates",
        ["candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        "fk_documents_client_id",
        "documents",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "fk_documents_client_id",
        "documents",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_documents_candidate_id",
        "documents",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_documents_source_external_id",
        "documents",
        type_="unique",
    )

    op.drop_index(
        "ix_documents_processing_status",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_match_status",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_gmail_message_id",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_client_id",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_checksum_sha256",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_candidate_id",
        table_name="documents",
    )

    op.drop_constraint(
        "ck_documents_match_confidence_range",
        "documents",
        type_="check",
    )

    op.drop_constraint(
        "ck_documents_match_status",
        "documents",
        type_="check",
    )

    op.drop_constraint(
        "ck_documents_processing_status",
        "documents",
        type_="check",
    )

    op.drop_constraint(
        "ck_documents_source_type",
        "documents",
        type_="check",
    )

    op.alter_column(
        "documents",
        "content_type",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=100),
        existing_nullable=False,
    )

    op.drop_column(
        "documents",
        "updated_at",
    )

    op.drop_column(
        "documents",
        "matched_at",
    )

    op.drop_column(
        "documents",
        "match_method",
    )

    op.drop_column(
        "documents",
        "match_confidence",
    )

    op.drop_column(
        "documents",
        "match_status",
    )

    op.drop_column(
        "documents",
        "extracted_text",
    )

    op.drop_column(
        "documents",
        "processing_error",
    )

    op.drop_column(
        "documents",
        "processing_status",
    )

    op.drop_column(
        "documents",
        "client_id",
    )

    op.drop_column(
        "documents",
        "candidate_id",
    )

    op.drop_column(
        "documents",
        "gmail_thread_id",
    )

    op.drop_column(
        "documents",
        "gmail_message_id",
    )

    op.drop_column(
        "documents",
        "external_id",
    )

    op.drop_column(
        "documents",
        "source_type",
    )

    op.drop_column(
        "documents",
        "checksum_sha256",
    )

    op.drop_column(
        "documents",
        "storage_path",
    )

    op.drop_column(
        "documents",
        "original_filename",
    )