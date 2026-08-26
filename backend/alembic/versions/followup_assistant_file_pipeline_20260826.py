"""Add durable document preparation and Assistant wait state.

Revision ID: followup_assistant_file_pipeline_20260826
Revises: followup_backup_planner_retention_20260824

This revision is intentionally additive.  It creates no preparation jobs for
historical documents and stores no Assistant request/result payload during the
migration itself.
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_assistant_file_pipeline_20260826"
down_revision = "followup_backup_planner_retention_20260824"
branch_labels = None
depends_on = None


_ORIGINAL_ANALYSIS_STATUSES = (
    "'queued','local_processing','local_validating','advanced_queued',"
    "'advanced_processing','awaiting_auth','awaiting_ui_fix',"
    "'advanced_validating','accepted_local','accepted_advanced',"
    "'review_required','failed','cancelled'"
)

_FILE_PIPELINE_ANALYSIS_STATUSES = (
    "'queued','document_preparation_queued','document_preparation_running',"
    "'resume_queued','local_processing','local_validating','advanced_queued',"
    "'advanced_processing','awaiting_auth','awaiting_ui_fix',"
    "'advanced_validating','accepted_local','accepted_advanced',"
    "'review_required','failed','cancelled'"
)

_ORIGINAL_ACTIVE_ANALYSIS_STATUSES = (
    "'queued','local_processing','local_validating','advanced_queued',"
    "'advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating'"
)

_FILE_PIPELINE_ACTIVE_ANALYSIS_STATUSES = (
    "'queued','document_preparation_queued','document_preparation_running',"
    "'resume_queued','local_processing','local_validating','advanced_queued',"
    "'advanced_processing','awaiting_auth','awaiting_ui_fix','advanced_validating'"
)


def upgrade() -> None:
    op.create_table(
        "document_preparation_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("input_checksum", sa.String(64), nullable=False),
        sa.Column(
            "processor_generation",
            sa.String(40),
            nullable=False,
            server_default="document-preparation-v1",
        ),
        sa.Column("trigger", sa.String(24), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(32), nullable=False, server_default="received"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_code", sa.String(100)),
        sa.Column("retryability", sa.String(24)),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "trigger IN ('ingestion','assistant','operator_retry')",
            name="ck_document_preparation_jobs_trigger",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 3", name="ck_document_preparation_jobs_priority"),
        sa.CheckConstraint(
            "status IN ('queued','running','ready','failed','unsupported','integrity_failed','cancelled')",
            name="ck_document_preparation_jobs_status",
        ),
        sa.CheckConstraint(
            "stage IN ('received','validating','queued','extracting','rendering',"
            "'ocr_required','ocr_processing','vision_processing','local_analysis',"
            "'indexing','ready_for_ai','failed','unsupported','integrity_failed','cancelled')",
            name="ck_document_preparation_jobs_stage",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts",
            name="ck_document_preparation_jobs_attempts",
        ),
        sa.CheckConstraint(
            "retryability IS NULL OR retryability IN ('recoverable','unsupported','integrity','missing_file','owner_action')",
            name="ck_document_preparation_jobs_retryability",
        ),
        sa.UniqueConstraint(
            "document_id",
            "input_checksum",
            "processor_generation",
            name="uq_document_preparation_generation",
        ),
    )
    op.create_index(
        "ix_document_preparation_jobs_queue",
        "document_preparation_jobs",
        ["status", "priority", "queued_at", "id"],
    )
    op.create_index(
        "ix_document_preparation_jobs_stale",
        "document_preparation_jobs",
        ["status", "lease_expires_at", "id"],
    )
    op.create_index(
        "ix_document_preparation_jobs_document",
        "document_preparation_jobs",
        ["document_id", "created_at", "id"],
    )

    op.add_column("analysis_jobs", sa.Column("attempt_id", sa.String(80)))
    op.add_column("analysis_jobs", sa.Column("request_payload", sa.JSON()))
    op.add_column("analysis_jobs", sa.Column("result_payload", sa.JSON()))
    op.add_column(
        "analysis_jobs",
        sa.Column(
            "waiting_document_preparation_job_id",
            sa.String(36),
            sa.ForeignKey("document_preparation_jobs.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "analysis_jobs",
        sa.Column("resume_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("analysis_jobs", sa.Column("last_progress_at", sa.DateTime(timezone=True)))
    op.add_column("analysis_jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_analysis_jobs_attempt_id",
        "analysis_jobs",
        "attempt_id IS NULL OR (length(attempt_id) BETWEEN 8 AND 80 AND attempt_id ~ '^[A-Za-z0-9_-]+$')",
    )
    op.create_check_constraint(
        "ck_analysis_jobs_resume_generation",
        "analysis_jobs",
        "resume_generation >= 0",
    )
    op.create_index(
        "ix_analysis_jobs_waiting_preparation",
        "analysis_jobs",
        ["waiting_document_preparation_job_id", "status", "updated_at", "id"],
    )

    op.drop_index("uq_analysis_jobs_active_fingerprint", table_name="analysis_jobs")
    op.drop_constraint("ck_analysis_jobs_status", "analysis_jobs", type_="check")
    op.create_check_constraint(
        "ck_analysis_jobs_status",
        "analysis_jobs",
        f"status IN ({_FILE_PIPELINE_ANALYSIS_STATUSES})",
    )
    op.create_index(
        "uq_analysis_jobs_active_fingerprint",
        "analysis_jobs",
        ["analysis_type", "source_domain", "input_fingerprint"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({_FILE_PIPELINE_ACTIVE_ANALYSIS_STATUSES})"),
    )


def downgrade() -> None:
    op.drop_index("uq_analysis_jobs_active_fingerprint", table_name="analysis_jobs")
    op.drop_constraint("ck_analysis_jobs_status", "analysis_jobs", type_="check")
    op.create_check_constraint(
        "ck_analysis_jobs_status",
        "analysis_jobs",
        f"status IN ({_ORIGINAL_ANALYSIS_STATUSES})",
    )
    op.create_index(
        "uq_analysis_jobs_active_fingerprint",
        "analysis_jobs",
        ["analysis_type", "source_domain", "input_fingerprint"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({_ORIGINAL_ACTIVE_ANALYSIS_STATUSES})"),
    )

    op.drop_index("ix_analysis_jobs_waiting_preparation", table_name="analysis_jobs")
    op.drop_constraint("ck_analysis_jobs_resume_generation", "analysis_jobs", type_="check")
    op.drop_constraint("ck_analysis_jobs_attempt_id", "analysis_jobs", type_="check")
    for column in (
        "cancel_requested_at",
        "last_progress_at",
        "resume_generation",
        "waiting_document_preparation_job_id",
        "result_payload",
        "request_payload",
        "attempt_id",
    ):
        op.drop_column("analysis_jobs", column)

    op.drop_index("ix_document_preparation_jobs_document", table_name="document_preparation_jobs")
    op.drop_index("ix_document_preparation_jobs_stale", table_name="document_preparation_jobs")
    op.drop_index("ix_document_preparation_jobs_queue", table_name="document_preparation_jobs")
    op.drop_table("document_preparation_jobs")
