"""Add the isolated Administrator Knowledge Base domain.

Revision ID: followup_admin_knowledge_base_20260821
Revises: followup_admin_backup_restore_ui_20260821
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_admin_knowledge_base_20260821"
down_revision = "followup_admin_backup_restore_ui_20260821"
branch_labels = None
depends_on = None


OLD_HISTORY_TYPES = (
    "'client','client_contact','client_address','client_workflow_status',"
    "'client_candidate','candidate_merge','ignored_mail_source','user',"
    "'work_item','work_item_note','work_item_document','absence_request','document'"
)
NEW_HISTORY_TYPES = OLD_HISTORY_TYPES + ",'knowledge_base_item'"
OLD_HISTORY_ACTIONS = (
    "'created','updated','deleted','restored','status_changed','accepted',"
    "'rejected','merged','activated','deactivated','trashed','purged'"
)
NEW_HISTORY_ACTIONS = OLD_HISTORY_ACTIONS + ",'processing_retried'"


def upgrade() -> None:
    op.create_table(
        "knowledge_base_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("publisher", sa.String(255)),
        sa.Column("version", sa.String(100)),
        sa.Column("effective_date", sa.Date()),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(20), nullable=False, server_default="current"),
        sa.Column("supersedes_id", sa.BigInteger(), sa.ForeignKey("knowledge_base_items.id", ondelete="SET NULL")),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(2000), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("processing_status", sa.String(24), nullable=False, server_default="uploaded"),
        sa.Column("processing_method", sa.String(24)),
        sa.Column("processing_error", sa.Text()),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('current','superseded')", name="ck_knowledge_base_items_status"),
        sa.CheckConstraint("processing_status IN ('uploaded','extracting','ocr','processed','failed')", name="ck_knowledge_base_items_processing_status"),
        sa.CheckConstraint("category IN ('norms','technical_datasheets','manuals','producer_materials','formulas','reference_calculations','other')", name="ck_knowledge_base_items_category"),
    )
    op.create_index("ix_knowledge_base_items_search", "knowledge_base_items", ["status", "category", "publisher"])
    op.create_index("ix_knowledge_base_items_checksum", "knowledge_base_items", ["checksum_sha256"])
    op.create_index("ix_knowledge_base_items_archived_at", "knowledge_base_items", ["archived_at"])
    op.create_table(
        "knowledge_base_pages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("knowledge_base_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("extraction_method", sa.String(24), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", "page_number", name="uq_knowledge_base_pages_item_page"),
    )
    op.create_index("ix_knowledge_base_pages_item_id", "knowledge_base_pages", ["item_id"])
    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_entity_type", "change_history_events", f"entity_type IN ({NEW_HISTORY_TYPES})")
    op.drop_constraint("ck_change_history_events_action", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_action", "change_history_events", f"action IN ({NEW_HISTORY_ACTIONS})")


def downgrade() -> None:
    # The downgraded schema cannot represent Knowledge Base audit events.
    # Remove only events owned by the domain that is being removed.
    op.execute("DELETE FROM change_history_events WHERE entity_type = 'knowledge_base_item'")
    op.drop_constraint("ck_change_history_events_action", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_action", "change_history_events", f"action IN ({OLD_HISTORY_ACTIONS})")
    op.drop_constraint("ck_change_history_events_entity_type", "change_history_events", type_="check")
    op.create_check_constraint("ck_change_history_events_entity_type", "change_history_events", f"entity_type IN ({OLD_HISTORY_TYPES})")
    op.drop_index("ix_knowledge_base_pages_item_id", table_name="knowledge_base_pages")
    op.drop_table("knowledge_base_pages")
    op.drop_index("ix_knowledge_base_items_archived_at", table_name="knowledge_base_items")
    op.drop_index("ix_knowledge_base_items_checksum", table_name="knowledge_base_items")
    op.drop_index("ix_knowledge_base_items_search", table_name="knowledge_base_items")
    op.drop_table("knowledge_base_items")
