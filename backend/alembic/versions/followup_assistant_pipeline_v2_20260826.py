"""Add durable Assistant runs and document intelligence artifacts.

Revision ID: followup_assistant_pipeline_v2_20260826
Revises: followup_assistant_file_pipeline_20260826

This revision is intentionally additive.  It creates no runs, stages,
materials, intelligence artifacts, or historical processing work.  Existing
``analysis_jobs`` remain compute/advanced-analysis children and existing
``document_preparation_jobs`` remain material-preparation children.
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_assistant_pipeline_v2_20260826"
down_revision = "followup_assistant_file_pipeline_20260826"
branch_labels = None
depends_on = None


_RUN_STATES = (
    "'created','planning','resolving_targets','waiting_for_material',"
    "'preparing_material','retrieving_case_evidence','retrieving_knowledge_base',"
    "'analyzing_local','validating_local','waiting_for_vision','analyzing_vision',"
    "'waiting_for_advanced','analyzing_advanced','validating_advanced',"
    "'synthesizing','finalizing','completed','review_required','failed','cancelled'"
)

_ACTIVE_RUN_STATES = (
    "'created','planning','resolving_targets','waiting_for_material',"
    "'preparing_material','retrieving_case_evidence','retrieving_knowledge_base',"
    "'analyzing_local','validating_local','waiting_for_vision','analyzing_vision',"
    "'waiting_for_advanced','analyzing_advanced','validating_advanced',"
    "'synthesizing','finalizing'"
)

_STAGE_TYPES = (
    "'planning','resolving_targets','waiting_for_material','preparing_material',"
    "'retrieving_case_evidence','retrieving_knowledge_base','analyzing_local',"
    "'validating_local','waiting_for_vision','analyzing_vision',"
    "'waiting_for_advanced','analyzing_advanced','validating_advanced',"
    "'synthesizing','finalizing'"
)

_SENSITIVITIES = (
    "'public_reference','internal_non_sensitive','customer_sanitizable',"
    "'restricted_never_external'"
)


def upgrade() -> None:
    op.create_table(
        "document_intelligence_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("input_checksum", sa.String(64), nullable=False),
        sa.Column("analyzer_generation", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column(
            "validation_state",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sensitivity", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("validation_details", sa.JSON()),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("processor_id", sa.String(100), nullable=False),
        sa.Column("processor_version", sa.String(40), nullable=False),
        sa.Column("model_identity", sa.String(100)),
        sa.Column("tool_identity", sa.String(100)),
        sa.Column(
            "preparation_job_id",
            sa.String(36),
            sa.ForeignKey("document_preparation_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('baseline_document','baseline_visual','section_map')",
            name="ck_document_intelligence_artifacts_kind",
        ),
        sa.CheckConstraint(
            "status IN ('draft','validating','accepted','review_required','rejected','superseded')",
            name="ck_document_intelligence_artifacts_status",
        ),
        sa.CheckConstraint(
            "validation_state IN ('pending','passed','failed')",
            name="ck_document_intelligence_artifacts_validation",
        ),
        sa.CheckConstraint(
            f"sensitivity IN ({_SENSITIVITIES})",
            name="ck_document_intelligence_artifacts_sensitivity",
        ),
        sa.UniqueConstraint(
            "document_id",
            "input_checksum",
            "analyzer_generation",
            "kind",
            name="uq_document_intelligence_generation",
        ),
    )
    op.create_index(
        "ix_document_intelligence_artifacts_document",
        "document_intelligence_artifacts",
        ["document_id", "created_at", "id"],
    )
    op.create_index(
        "ix_document_intelligence_artifacts_preparation",
        "document_intelligence_artifacts",
        ["preparation_job_id", "status", "id"],
    )
    op.create_index(
        "uq_document_intelligence_current",
        "document_intelligence_artifacts",
        ["document_id", "kind"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'accepted' AND validation_state = 'passed' "
            "AND superseded_at IS NULL"
        ),
    )

    op.create_table(
        "document_intelligence_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "artifact_id",
            sa.String(36),
            sa.ForeignKey("document_intelligence_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_ref", sa.String(8), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_entity_id", sa.BigInteger()),
        sa.Column("page_number", sa.Integer()),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("excerpt_sha256", sa.String(64)),
        sa.Column("source_role", sa.String(24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source_kind IN ('document','document_page','document_asset','document_chunk','vision_observation')",
            name="ck_document_intelligence_sources_kind",
        ),
        sa.CheckConstraint(
            "source_role IN ('fact','measurement','conclusion','recommendation','warning','limitation','visual')",
            name="ck_document_intelligence_sources_role",
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name="ck_document_intelligence_sources_page",
        ),
        sa.UniqueConstraint(
            "artifact_id",
            "source_ref",
            name="uq_document_intelligence_sources_ref",
        ),
    )
    op.create_index(
        "ix_document_intelligence_sources_artifact",
        "document_intelligence_sources",
        ["artifact_id", "source_kind", "source_entity_id"],
    )

    op.create_table(
        "assistant_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.String(80), nullable=False),
        sa.Column(
            "api_version",
            sa.String(32),
            nullable=False,
            server_default="assistant-runs-v2",
        ),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("target_scope", sa.JSON(), nullable=False),
        sa.Column("complexity", sa.String(24), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="created"),
        sa.Column("current_stage", sa.String(40)),
        sa.Column("plan", sa.JSON()),
        sa.Column("result_payload", sa.JSON()),
        sa.Column("sensitivity", sa.String(30), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "recovery_generation",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"status IN ({_RUN_STATES})",
            name="ck_assistant_runs_status",
        ),
        sa.CheckConstraint(
            f"current_stage IS NULL OR current_stage IN ({_RUN_STATES})",
            name="ck_assistant_runs_current_stage",
        ),
        sa.CheckConstraint(
            "complexity IN ('fast','standard','deep','visual','external_candidate')",
            name="ck_assistant_runs_complexity",
        ),
        sa.CheckConstraint(
            f"sensitivity IN ({_SENSITIVITIES})",
            name="ck_assistant_runs_sensitivity",
        ),
        sa.CheckConstraint(
            "priority BETWEEN 0 AND 3",
            name="ck_assistant_runs_priority",
        ),
        sa.CheckConstraint(
            "recovery_generation >= 0",
            name="ck_assistant_runs_recovery_generation",
        ),
        sa.CheckConstraint(
            "length(attempt_id) BETWEEN 8 AND 80 AND attempt_id ~ '^[A-Za-z0-9_-]+$'",
            name="ck_assistant_runs_attempt_id",
        ),
        sa.UniqueConstraint(
            "created_by_user_id",
            "attempt_id",
            name="uq_assistant_runs_user_attempt",
        ),
    )
    op.create_index(
        "ix_assistant_runs_queue",
        "assistant_runs",
        ["status", "priority", "created_at", "id"],
        postgresql_where=sa.text(f"status IN ({_ACTIVE_RUN_STATES})"),
    )
    op.create_index(
        "ix_assistant_runs_owner",
        "assistant_runs",
        ["created_by_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_assistant_runs_heartbeat",
        "assistant_runs",
        ["status", "heartbeat_at", "id"],
        postgresql_where=sa.text(f"status IN ({_ACTIVE_RUN_STATES})"),
    )

    op.create_table(
        "assistant_run_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "assistant_run_id",
            sa.String(36),
            sa.ForeignKey("assistant_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_key", sa.String(80), nullable=False),
        sa.Column("stage_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("progress_current", sa.BigInteger()),
        sa.Column("progress_total", sa.BigInteger()),
        sa.Column("progress_unit", sa.String(24)),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("inactivity_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("absolute_cap_seconds", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("result_kind", sa.String(32)),
        sa.Column(
            "analysis_job_id",
            sa.String(36),
            sa.ForeignKey("analysis_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "document_preparation_job_id",
            sa.String(36),
            sa.ForeignKey("document_preparation_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "intelligence_artifact_id",
            sa.String(36),
            sa.ForeignKey("document_intelligence_artifacts.id", ondelete="SET NULL"),
        ),
        sa.Column("external_job_id", sa.String(64)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"stage_type IN ({_STAGE_TYPES})",
            name="ck_assistant_run_stages_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued','waiting','running','completed','skipped','failed','cancelled')",
            name="ck_assistant_run_stages_status",
        ),
        sa.CheckConstraint(
            "ordinal >= 0 AND attempt BETWEEN 1 AND 5 AND max_attempts BETWEEN 1 AND 5 AND attempt <= max_attempts",
            name="ck_assistant_run_stages_attempts",
        ),
        sa.CheckConstraint(
            "progress_current IS NULL OR progress_current >= 0",
            name="ck_assistant_run_stages_progress_current",
        ),
        sa.CheckConstraint(
            "progress_total IS NULL OR (progress_total >= 0 AND (progress_current IS NULL OR progress_current <= progress_total))",
            name="ck_assistant_run_stages_progress_total",
        ),
        sa.CheckConstraint(
            "inactivity_timeout_seconds BETWEEN 5 AND 7200 AND absolute_cap_seconds BETWEEN 10 AND 86400 AND inactivity_timeout_seconds <= absolute_cap_seconds",
            name="ck_assistant_run_stages_time_bounds",
        ),
        sa.CheckConstraint(
            "result_kind IS NULL OR result_kind IN ('intelligence_artifact','analysis_job','vision_job','advanced_job','final_response')",
            name="ck_assistant_run_stages_result_kind",
        ),
        sa.UniqueConstraint(
            "assistant_run_id",
            "stage_key",
            "attempt",
            name="uq_assistant_run_stage_attempt",
        ),
    )
    op.create_index(
        "ix_assistant_run_stages_run",
        "assistant_run_stages",
        ["assistant_run_id", "ordinal", "attempt", "id"],
    )
    op.create_index(
        "ix_assistant_run_stages_queue",
        "assistant_run_stages",
        ["status", "stage_type", "created_at", "id"],
        postgresql_where=sa.text("status IN ('queued','waiting','running')"),
    )
    op.create_index(
        "ix_assistant_run_stages_lease",
        "assistant_run_stages",
        ["status", "lease_expires_at", "heartbeat_at", "id"],
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "assistant_run_materials",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "assistant_run_id",
            sa.String(36),
            sa.ForeignKey("assistant_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_ref", sa.String(8), nullable=False),
        sa.Column("source_domain", sa.String(32), nullable=False),
        sa.Column("source_entity_type", sa.String(50), nullable=False),
        sa.Column("source_entity_id", sa.String(100), nullable=False),
        sa.Column("source_role", sa.String(24), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("readiness_level", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="resolving"),
        sa.Column("source_checksum", sa.String(64)),
        sa.Column("relevance_score", sa.Float()),
        sa.Column(
            "document_preparation_job_id",
            sa.String(36),
            sa.ForeignKey("document_preparation_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "intelligence_artifact_id",
            sa.String(36),
            sa.ForeignKey("document_intelligence_artifacts.id", ondelete="SET NULL"),
        ),
        sa.Column("sensitivity", sa.String(30), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source_domain IN ('client','candidate','document','mail','activity','visit','project','work_item','knowledge_base','calculation','visual','general')",
            name="ck_assistant_run_materials_domain",
        ),
        sa.CheckConstraint(
            "source_role IN ('case_fact','reference','visual','tool','global')",
            name="ck_assistant_run_materials_role",
        ),
        sa.CheckConstraint(
            "readiness_level IN ('file_validated','content_ready','intelligence_ready','query_ready','unavailable')",
            name="ck_assistant_run_materials_readiness",
        ),
        sa.CheckConstraint(
            "status IN ('resolving','waiting','ready','failed','skipped')",
            name="ck_assistant_run_materials_status",
        ),
        sa.CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)",
            name="ck_assistant_run_materials_relevance",
        ),
        sa.CheckConstraint(
            f"sensitivity IN ({_SENSITIVITIES})",
            name="ck_assistant_run_materials_sensitivity",
        ),
        sa.UniqueConstraint(
            "assistant_run_id",
            "source_ref",
            name="uq_assistant_run_materials_ref",
        ),
        sa.UniqueConstraint(
            "assistant_run_id",
            "source_domain",
            "source_entity_type",
            "source_entity_id",
            name="uq_assistant_run_materials_entity",
        ),
    )
    op.create_index(
        "ix_assistant_run_materials_run",
        "assistant_run_materials",
        ["assistant_run_id", "status", "readiness_level", "id"],
    )
    op.create_index(
        "ix_assistant_run_materials_preparation",
        "assistant_run_materials",
        ["document_preparation_job_id", "status", "id"],
    )
    op.create_index(
        "ix_assistant_run_materials_artifact",
        "assistant_run_materials",
        ["intelligence_artifact_id", "status", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_run_materials_artifact", table_name="assistant_run_materials")
    op.drop_index("ix_assistant_run_materials_preparation", table_name="assistant_run_materials")
    op.drop_index("ix_assistant_run_materials_run", table_name="assistant_run_materials")
    op.drop_table("assistant_run_materials")

    op.drop_index("ix_assistant_run_stages_lease", table_name="assistant_run_stages")
    op.drop_index("ix_assistant_run_stages_queue", table_name="assistant_run_stages")
    op.drop_index("ix_assistant_run_stages_run", table_name="assistant_run_stages")
    op.drop_table("assistant_run_stages")

    op.drop_index("ix_assistant_runs_heartbeat", table_name="assistant_runs")
    op.drop_index("ix_assistant_runs_owner", table_name="assistant_runs")
    op.drop_index("ix_assistant_runs_queue", table_name="assistant_runs")
    op.drop_table("assistant_runs")

    op.drop_index(
        "ix_document_intelligence_sources_artifact",
        table_name="document_intelligence_sources",
    )
    op.drop_table("document_intelligence_sources")

    op.drop_index(
        "uq_document_intelligence_current",
        table_name="document_intelligence_artifacts",
    )
    op.drop_index(
        "ix_document_intelligence_artifacts_preparation",
        table_name="document_intelligence_artifacts",
    )
    op.drop_index(
        "ix_document_intelligence_artifacts_document",
        table_name="document_intelligence_artifacts",
    )
    op.drop_table("document_intelligence_artifacts")
