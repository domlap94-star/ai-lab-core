"""Add Client-owned Contact Persons without historical inference.

Revision ID: followup_contact_person_20260822
Revises: followup_admin_knowledge_base_20260821
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_contact_person_20260822"
down_revision = "followup_admin_knowledge_base_20260821"
branch_labels = None
depends_on = None


OLD_HISTORY_TYPES = (
    "'client','client_contact','client_address','client_workflow_status',"
    "'client_candidate','candidate_merge','ignored_mail_source','user',"
    "'work_item','work_item_note','work_item_document','absence_request',"
    "'document','knowledge_base_item'"
)
NEW_HISTORY_TYPES = OLD_HISTORY_TYPES + ",'contact_person'"


def upgrade() -> None:
    op.create_table(
        "contact_persons",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(150)),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_decision_maker", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_type", sa.String(50)),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("candidate_sources.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(trim(display_name)) > 0", name="ck_contact_persons_display_name_not_empty"),
        sa.CheckConstraint("origin IN ('manual','gmail','sheets','migration','other')", name="ck_contact_persons_origin"),
        sa.UniqueConstraint("id", "client_id", name="uq_contact_persons_id_client"),
    )
    op.create_index("ix_contact_persons_client_position", "contact_persons", ["client_id", "position", "id"])
    op.create_index("ix_contact_persons_source_id", "contact_persons", ["source_id"])
    op.create_index(
        "uq_contact_persons_active_preferred_client",
        "contact_persons",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND is_preferred"),
    )
    op.add_column("client_contact_points", sa.Column("contact_person_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_client_contact_points_person_client",
        "client_contact_points",
        "contact_persons",
        ["contact_person_id", "client_id"],
        ["id", "client_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_client_contact_points_contact_person_id", "client_contact_points", ["contact_person_id"])
    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint(
        "ck_change_history_events_entity_type",
        "change_history_events",
        f"entity_type IN ({NEW_HISTORY_TYPES})",
    )


def downgrade() -> None:
    op.execute("DELETE FROM change_history_events WHERE entity_type = 'contact_person'")
    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint(
        "ck_change_history_events_entity_type",
        "change_history_events",
        f"entity_type IN ({OLD_HISTORY_TYPES})",
    )
    op.drop_index("ix_client_contact_points_contact_person_id", table_name="client_contact_points")
    op.drop_constraint("fk_client_contact_points_person_client", "client_contact_points", type_="foreignkey")
    op.drop_column("client_contact_points", "contact_person_id")
    op.drop_index("uq_contact_persons_active_preferred_client", table_name="contact_persons")
    op.drop_index("ix_contact_persons_source_id", table_name="contact_persons")
    op.drop_index("ix_contact_persons_client_position", table_name="contact_persons")
    op.drop_table("contact_persons")
