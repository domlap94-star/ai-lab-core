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
        sa.Column("source", sa.String(500), nullable=False),
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
        sa.Column("analysis_status", sa.String(30), nullable=False, server_default="local_pending"),
        sa.Column("analysis_error", sa.String(100)),
        sa.Column("analysis_reason", sa.String(100)),
        sa.Column("indexing_status", sa.String(20), nullable=False, server_default="not_ready"),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('current','superseded')", name="ck_knowledge_base_items_status"),
        sa.CheckConstraint("processing_status IN ('uploaded','queued','extracting','ocr','processed','failed')", name="ck_knowledge_base_items_processing_status"),
        sa.CheckConstraint("analysis_status IN ('not_required','local_pending','local_processing','local_accepted','advanced_required','advanced_queued','advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating','advanced_accepted','review_required','failed')", name="ck_knowledge_base_items_analysis_status"),
        sa.CheckConstraint("indexing_status IN ('not_ready','pending','indexing','indexed','failed')", name="ck_knowledge_base_items_indexing_status"),
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
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("source_domain", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("decision", sa.String(30)),
        sa.Column("sensitivity", sa.String(30), nullable=False),
        sa.Column("processor_id", sa.String(100)),
        sa.Column("processor_version", sa.String(40)),
        sa.Column("model_identity", sa.String(100)),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("sanitized_package_hash", sa.String(64)),
        sa.Column("sanitized_package_size", sa.Integer()),
        sa.Column("external_job_id", sa.String(36)),
        sa.Column("reasoning_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("format_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_signals", sa.JSON()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('queued','local_processing','local_validating','advanced_queued','advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating','accepted_local','accepted_advanced','review_required','failed','cancelled')", name="ck_analysis_jobs_status"),
        sa.CheckConstraint("sensitivity IN ('public_reference','internal_non_sensitive','customer_sanitizable','restricted_never_external')", name="ck_analysis_jobs_sensitivity"),
    )
    op.create_index("ix_analysis_jobs_status_updated", "analysis_jobs", ["status", "updated_at"])
    op.create_index("uq_analysis_jobs_active_fingerprint", "analysis_jobs", ["analysis_type", "source_domain", "input_fingerprint"], unique=True,
                    postgresql_where=sa.text("status IN ('queued','local_processing','local_validating','advanced_queued','advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating')"))
    op.create_table(
        "analysis_job_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("analysis_job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_ref", sa.String(8), nullable=False),
        sa.Column("source_domain", sa.String(50), nullable=False),
        sa.Column("source_entity_type", sa.String(50), nullable=False),
        sa.Column("source_entity_id", sa.String(100), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("sensitivity", sa.String(30), nullable=False),
        sa.UniqueConstraint("analysis_job_id", "source_ref", name="uq_analysis_job_sources_ref"),
    )
    op.create_index("ix_analysis_job_sources_analysis_job_id", "analysis_job_sources", ["analysis_job_id"])
    op.create_table(
        "knowledge_base_processing_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("knowledge_base_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(100)),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_knowledge_base_processing_jobs_status"),
    )
    op.create_index("ix_kb_processing_status_created", "knowledge_base_processing_jobs", ["status", "created_at"])
    op.create_index("uq_kb_processing_active_item", "knowledge_base_processing_jobs", ["item_id"], unique=True,
                    postgresql_where=sa.text("status IN ('queued','running')"))
    op.create_table(
        "knowledge_base_analysis_artifacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("knowledge_base_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_page_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("validation_state", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("origin IN ('local','advanced')", name="ck_kb_analysis_artifacts_origin"),
    )
    op.create_index("ix_kb_analysis_artifacts_item_id", "knowledge_base_analysis_artifacts", ["item_id"])
    op.create_index("ix_kb_analysis_artifacts_analysis_job_id", "knowledge_base_analysis_artifacts", ["analysis_job_id"])
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
    op.drop_index("ix_kb_analysis_artifacts_analysis_job_id", table_name="knowledge_base_analysis_artifacts")
    op.drop_index("ix_kb_analysis_artifacts_item_id", table_name="knowledge_base_analysis_artifacts")
    op.drop_table("knowledge_base_analysis_artifacts")
    op.drop_index("uq_kb_processing_active_item", table_name="knowledge_base_processing_jobs")
    op.drop_index("ix_kb_processing_status_created", table_name="knowledge_base_processing_jobs")
    op.drop_table("knowledge_base_processing_jobs")
    op.drop_index("ix_analysis_job_sources_analysis_job_id", table_name="analysis_job_sources")
    op.drop_table("analysis_job_sources")
    op.drop_index("uq_analysis_jobs_active_fingerprint", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_status_updated", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_index("ix_knowledge_base_pages_item_id", table_name="knowledge_base_pages")
    op.drop_table("knowledge_base_pages")
    op.drop_index("ix_knowledge_base_items_archived_at", table_name="knowledge_base_items")
    op.drop_index("ix_knowledge_base_items_checksum", table_name="knowledge_base_items")
    op.drop_index("ix_knowledge_base_items_search", table_name="knowledge_base_items")
    op.drop_table("knowledge_base_items")
