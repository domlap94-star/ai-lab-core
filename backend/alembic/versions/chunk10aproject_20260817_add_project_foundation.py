"""Add Project foundation and nullable Document relation."""

from alembic import op
import sqlalchemy as sa

revision = "chunk10aproject_20260817"
down_revision = "chunk8doclink_20260817"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("building_number", sa.String(50), nullable=True),
        sa.Column("unit_number", sa.String(50), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("city", sa.String(150), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="PL"),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('planned', 'active', 'completed', 'cancelled')", name="ck_projects_status"),
        sa.CheckConstraint("char_length(trim(name)) > 0", name="ck_projects_name_not_empty"),
        sa.CheckConstraint("char_length(country_code) = 2", name="ck_projects_country_code_length"),
        sa.CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_projects_latitude_range"),
        sa.CheckConstraint("longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_projects_longitude_range"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_client_id", "projects", ["client_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])
    op.add_column("documents", sa.Column("project_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_documents_project_id", "documents", "projects", ["project_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_documents_project_id", "documents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_constraint("fk_documents_project_id", "documents", type_="foreignkey")
    op.drop_column("documents", "project_id")
    op.drop_index("ix_projects_deleted_at", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_client_id", table_name="projects")
    op.drop_table("projects")
