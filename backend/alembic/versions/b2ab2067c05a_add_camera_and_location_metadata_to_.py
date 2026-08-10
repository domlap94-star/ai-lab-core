"""add camera and location metadata to documents

Revision ID: b2ab2067c05a
Revises: 8002e151f16f
Create Date: 2026-08-09 11:46:20.418217

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2ab2067c05a"
down_revision: Union[str, Sequence[str], None] = "8002e151f16f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================
    # New camera / location columns
    # ==========================================================

    op.add_column(
        "documents",
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "latitude",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "longitude",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "location_accuracy_m",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "location_source",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "inspection_session_id",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # ==========================================================
    # Replace source_type constraint
    # ==========================================================

    op.drop_constraint(
        "ck_documents_source_type",
        "documents",
        type_="check",
    )

    op.create_check_constraint(
        "ck_documents_source_type",
        "documents",
        "source_type IN ("
        "'manual_upload', "
        "'gmail_attachment', "
        "'camera_photo', "
        "'camera_video'"
        ")",
    )

    # ==========================================================
    # GPS validation constraints
    # ==========================================================

    op.create_check_constraint(
        "ck_documents_latitude_range",
        "documents",
        "latitude IS NULL OR "
        "(latitude >= -90 AND latitude <= 90)",
    )

    op.create_check_constraint(
        "ck_documents_longitude_range",
        "documents",
        "longitude IS NULL OR "
        "(longitude >= -180 AND longitude <= 180)",
    )

    op.create_check_constraint(
        "ck_documents_location_accuracy_positive",
        "documents",
        "location_accuracy_m IS NULL OR "
        "location_accuracy_m >= 0",
    )

    # ==========================================================
    # Indexes
    # ==========================================================

    op.create_index(
        "ix_documents_captured_at",
        "documents",
        ["captured_at"],
        unique=False,
    )

    op.create_index(
        "ix_documents_inspection_session_id",
        "documents",
        ["inspection_session_id"],
        unique=False,
    )


def downgrade() -> None:
    # ==========================================================
    # Indexes
    # ==========================================================

    op.drop_index(
        "ix_documents_inspection_session_id",
        table_name="documents",
    )

    op.drop_index(
        "ix_documents_captured_at",
        table_name="documents",
    )

    # ==========================================================
    # GPS validation constraints
    # ==========================================================

    op.drop_constraint(
        "ck_documents_location_accuracy_positive",
        "documents",
        type_="check",
    )

    op.drop_constraint(
        "ck_documents_longitude_range",
        "documents",
        type_="check",
    )

    op.drop_constraint(
        "ck_documents_latitude_range",
        "documents",
        type_="check",
    )

    # ==========================================================
    # Restore old source_type constraint
    # ==========================================================

    op.drop_constraint(
        "ck_documents_source_type",
        "documents",
        type_="check",
    )

    op.create_check_constraint(
        "ck_documents_source_type",
        "documents",
        "source_type IN ("
        "'manual_upload', "
        "'gmail_attachment'"
        ")",
    )

    # ==========================================================
    # Columns
    # ==========================================================

    op.drop_column(
        "documents",
        "inspection_session_id",
    )

    op.drop_column(
        "documents",
        "location_source",
    )

    op.drop_column(
        "documents",
        "location_accuracy_m",
    )

    op.drop_column(
        "documents",
        "longitude",
    )

    op.drop_column(
        "documents",
        "latitude",
    )

    op.drop_column(
        "documents",
        "captured_at",
    )