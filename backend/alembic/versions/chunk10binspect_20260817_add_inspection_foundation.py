"""Add Inspection foundation and nullable Document relation."""

from alembic import op
import sqlalchemy as sa

revision = "chunk10binspect_20260817"
down_revision = "chunk10aproject_20260817"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location_accuracy_m", sa.Float(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'cancelled')", name="ck_inspections_status"),
        sa.CheckConstraint("char_length(trim(title)) > 0", name="ck_inspections_title_not_empty"),
        sa.CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_inspections_coordinates_pair"),
        sa.CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_inspections_latitude_range"),
        sa.CheckConstraint("longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_inspections_longitude_range"),
        sa.CheckConstraint("location_accuracy_m IS NULL OR location_accuracy_m >= 0", name="ck_inspections_location_accuracy_positive"),
        sa.CheckConstraint("completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at", name="ck_inspections_completed_after_started"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspections_project_id", "inspections", ["project_id"])
    op.create_index("ix_inspections_client_id", "inspections", ["client_id"])
    op.create_index("ix_inspections_status", "inspections", ["status"])
    op.create_index("ix_inspections_scheduled_at", "inspections", ["scheduled_at"])
    op.create_index("ix_inspections_deleted_at", "inspections", ["deleted_at"])
    op.add_column("documents", sa.Column("inspection_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_documents_inspection_id",
        "documents",
        "inspections",
        ["inspection_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_documents_inspection_id", "documents", ["inspection_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_inspection_id", table_name="documents")
    op.drop_constraint("fk_documents_inspection_id", "documents", type_="foreignkey")
    op.drop_column("documents", "inspection_id")
    op.drop_index("ix_inspections_deleted_at", table_name="inspections")
    op.drop_index("ix_inspections_scheduled_at", table_name="inspections")
    op.drop_index("ix_inspections_status", table_name="inspections")
    op.drop_index("ix_inspections_client_id", table_name="inspections")
    op.drop_index("ix_inspections_project_id", table_name="inspections")
    op.drop_table("inspections")
