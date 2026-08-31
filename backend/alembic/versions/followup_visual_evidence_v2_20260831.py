"""Add normalized Material V3 and Visual Evidence Pipeline V2 state.

Revision ID: followup_visual_evidence_v2_20260831
Revises: followup_assistant_chat_history_20260829

The revision is additive and performs no backfill.  PostgreSQL remains the
canonical workflow authority; no Supervisor or model work is started here.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "followup_visual_evidence_v2_20260831"
down_revision = "followup_assistant_chat_history_20260829"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())
HEX64 = "^[0-9a-f]{64}$"

_V3_PREPARATION_STAGES = (
    "'received','validating','queued','extracting','rendering','ocr_required',"
    "'ocr_processing','inventorying','material_ready',"
    "'material_ready_with_limitations','failed','unsupported',"
    "'integrity_failed','cancelled'"
)
_LEGACY_PREPARATION_STAGES = (
    "'received','validating','queued','extracting','rendering','ocr_required',"
    "'ocr_processing','vision_processing','local_analysis','indexing',"
    "'ready_for_ai','failed','unsupported','integrity_failed','cancelled'"
)
_ASSISTANT_STAGE_TYPES = (
    "'planning','resolving_targets','waiting_for_material','preparing_material',"
    "'building_intelligence','validating_intelligence','retrieving_case_evidence',"
    "'retrieving_knowledge_base','analyzing_local','validating_local',"
    "'waiting_for_vision','analyzing_vision','waiting_for_advanced',"
    "'analyzing_advanced','validating_advanced','reducing_findings',"
    "'synthesizing','finalizing','evaluating_visual_need','waiting_for_visual',"
    "'validating_visual','resynthesizing_local'"
)


def _hex_check(column: str) -> str:
    return f"{column} ~ '{HEX64}'"


def _json_bound(column: str, maximum: int) -> str:
    return f"octet_length({column}::text) <= {maximum}"


def _create_existing_table_extensions() -> None:
    op.add_column("document_preparation_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column("document_preparation_jobs", sa.Column("last_progress_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint(
        "uq_doc_prep_job_checksum", "document_preparation_jobs", ["id", "input_checksum"]
    )
    op.drop_constraint(
        "ck_document_preparation_jobs_stage", "document_preparation_jobs", type_="check"
    )
    op.create_check_constraint(
        "ck_document_preparation_jobs_stage",
        "document_preparation_jobs",
        "((processor_generation = 'document-preparation-v3' "
        f"AND stage IN ({_V3_PREPARATION_STAGES})) OR "
        "(processor_generation <> 'document-preparation-v3' "
        f"AND stage IN ({_LEGACY_PREPARATION_STAGES})))",
    )
    op.drop_index("ix_document_preparation_jobs_stale", table_name="document_preparation_jobs")
    op.create_index(
        "ix_document_preparation_jobs_stale",
        "document_preparation_jobs",
        ["status", "lease_expires_at", "heartbeat_at", "last_progress_at", "id"],
    )

    op.create_unique_constraint(
        "uq_document_pages_id_document", "document_pages", ["id", "document_id"]
    )
    op.create_unique_constraint(
        "uq_document_assets_id_document", "document_assets", ["id", "document_id"]
    )


def _create_material_tables() -> None:
    op.create_table(
        "document_material_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("preparation_job_id", sa.String(36), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("processor_generation", sa.String(64), nullable=False),
        sa.Column("material_fingerprint", sa.String(64), nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("limitation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limitations", JSONB),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_by_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_mat_gen_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["preparation_job_id", "source_checksum"],
            ["document_preparation_jobs.id", "document_preparation_jobs.input_checksum"],
            name="fk_mat_gen_prep_checksum",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["document_material_generations.id"], name="fk_mat_gen_superseded", ondelete="RESTRICT"),
        sa.CheckConstraint(_hex_check("source_checksum"), name="ck_mat_gen_source_sha"),
        sa.CheckConstraint(_hex_check("material_fingerprint"), name="ck_mat_gen_fingerprint"),
        sa.CheckConstraint(_hex_check("manifest_sha256"), name="ck_mat_gen_manifest_sha"),
        sa.CheckConstraint(_json_bound("manifest", 262144), name="ck_mat_gen_manifest_bound"),
        sa.CheckConstraint("limitations IS NULL OR octet_length(limitations::text) <= 65536", name="ck_mat_gen_limit_bound"),
        sa.CheckConstraint("source_count >= 1 AND limitation_count >= 0", name="ck_mat_gen_counts"),
        sa.CheckConstraint("superseded_by_id IS NULL OR superseded_at IS NOT NULL", name="ck_mat_gen_supersession"),
        sa.UniqueConstraint("preparation_job_id", name="uq_mat_gen_prep_job"),
        sa.UniqueConstraint("document_id", "material_fingerprint", name="uq_mat_gen_doc_fingerprint"),
        sa.UniqueConstraint("id", "document_id", name="uq_mat_gen_id_document"),
    )
    op.create_index(
        "uq_mat_gen_current",
        "document_material_generations",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
    )

    op.create_table(
        "document_material_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("material_generation_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(128), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("page_id", sa.BigInteger()),
        sa.Column("asset_id", sa.BigInteger()),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(255)),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("storage_ref", sa.String(2000)),
        sa.Column("payload", JSONB),
        sa.Column("payload_sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["material_generation_id", "document_id"], ["document_material_generations.id", "document_material_generations.document_id"], name="fk_mat_source_generation_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["page_id", "document_id"], ["document_pages.id", "document_pages.document_id"], name="fk_mat_source_page_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["asset_id", "document_id"], ["document_assets.id", "document_assets.document_id"], name="fk_mat_source_asset_document", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "source_kind IN ('document_file','document_text','page_text','page_ocr_text',"
            "'page_render','asset_original','asset_ocr_text','asset_render','table_structure')",
            name="ck_mat_sources_kind",
        ),
        sa.CheckConstraint(
            "((source_kind IN ('document_file','document_text') AND page_id IS NULL AND asset_id IS NULL) OR "
            "(source_kind IN ('page_text','page_ocr_text','page_render','table_structure') AND page_id IS NOT NULL AND asset_id IS NULL) OR "
            "(source_kind IN ('asset_original','asset_ocr_text','asset_render') AND page_id IS NULL AND asset_id IS NOT NULL))",
            name="ck_mat_sources_reference",
        ),
        sa.CheckConstraint(_hex_check("source_sha256"), name="ck_mat_sources_sha"),
        sa.CheckConstraint("payload_sha256 IS NULL OR payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_mat_sources_payload_sha"),
        sa.CheckConstraint("payload IS NULL OR octet_length(payload::text) <= 262144", name="ck_mat_sources_payload_bound"),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_mat_sources_bytes"),
        sa.UniqueConstraint("material_generation_id", "source_key", name="uq_mat_sources_generation_key"),
        sa.UniqueConstraint("id", "material_generation_id", "source_kind", "source_sha256", name="uq_mat_sources_exact"),
        sa.UniqueConstraint("id", "source_sha256", name="uq_mat_sources_id_sha"),
    )
    op.create_index("ix_mat_sources_generation", "document_material_sources", ["material_generation_id", "source_kind", "id"])

    op.create_table(
        "source_privacy_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("material_source_id", sa.String(36), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("disposition", sa.String(32), nullable=False),
        sa.Column("sanitization_state", sa.String(24), nullable=False),
        sa.Column("sanitized_payload_sha256", sa.String(64)),
        sa.Column("sanitized_spool_ref", sa.String(512)),
        sa.Column("authorized_payload_sha256", sa.String(64)),
        sa.Column("policy_generation", sa.String(64), nullable=False),
        sa.Column("sanitizer_generation", sa.String(64), nullable=False),
        sa.Column("assessment_fingerprint", sa.String(64), nullable=False),
        sa.Column("safe_metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "is_externalizable",
            sa.Boolean(),
            sa.Computed("disposition = 'allowed_external' AND authorized_payload_sha256 IS NOT NULL", persisted=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["material_source_id", "source_sha256"], ["document_material_sources.id", "document_material_sources.source_sha256"], name="fk_privacy_material_source", ondelete="RESTRICT"),
        sa.CheckConstraint("sensitivity IN ('safe_external','sanitizable_external','restricted_never_external')", name="ck_privacy_sensitivity"),
        sa.CheckConstraint("disposition IN ('allowed_external','rejected_external','restricted_never_external')", name="ck_privacy_disposition"),
        sa.CheckConstraint("sanitization_state IN ('not_required','passed','failed','not_permitted')", name="ck_privacy_sanitization"),
        sa.CheckConstraint(
            "((disposition = 'allowed_external' AND authorized_payload_sha256 IS NOT NULL) OR "
            "(disposition <> 'allowed_external' AND authorized_payload_sha256 IS NULL))",
            name="ck_privacy_authorized_hash",
        ),
        sa.CheckConstraint(
            "sensitivity <> 'restricted_never_external' OR "
            "(disposition = 'restricted_never_external' AND sanitization_state = 'not_permitted' "
            "AND sanitized_payload_sha256 IS NULL AND sanitized_spool_ref IS NULL AND authorized_payload_sha256 IS NULL)",
            name="ck_privacy_restricted",
        ),
        sa.CheckConstraint("sanitized_payload_sha256 IS NULL OR sanitized_payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_privacy_sanitized_sha"),
        sa.CheckConstraint("authorized_payload_sha256 IS NULL OR authorized_payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_privacy_authorized_sha"),
        sa.CheckConstraint(_hex_check("assessment_fingerprint"), name="ck_privacy_fingerprint"),
        sa.CheckConstraint("safe_metadata IS NULL OR octet_length(safe_metadata::text) <= 32768", name="ck_privacy_metadata_bound"),
        sa.UniqueConstraint("material_source_id", "source_sha256", "policy_generation", "sanitizer_generation", name="uq_privacy_source_generation"),
        sa.UniqueConstraint("id", "material_source_id", "source_sha256", "disposition", "authorized_payload_sha256", name="uq_privacy_authorized_target"),
    )


def _create_visual_planning_tables() -> None:
    op.create_table(
        "visual_analysis_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("initiated_by_user_id", sa.Integer()),
        sa.Column("initiating_service", sa.String(64)),
        sa.Column("request_idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("authorization_scope_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_manifest", JSONB, nullable=False),
        sa.Column("request_manifest_sha256", sa.String(64), nullable=False),
        sa.Column("source_planner_generation", sa.String(64), nullable=False),
        sa.Column("privacy_policy_generation", sa.String(64), nullable=False),
        sa.Column("detector_generation", sa.String(64), nullable=False),
        sa.Column("sanitizer_generation", sa.String(64), nullable=False),
        sa.Column("external_prompt_generation", sa.String(64), nullable=False),
        sa.Column("result_contract_generation", sa.String(64), nullable=False),
        sa.Column("transport_generation", sa.String(64), nullable=False),
        sa.Column("validator_generation", sa.String(64), nullable=False),
        sa.Column("artifact_assembler_generation", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("recovery_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("absolute_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_progress_at", sa.DateTime(timezone=True)),
        sa.Column("retryability", sa.String(24)),
        sa.Column("error_code", sa.String(128)),
        sa.Column("source_plan_fingerprint", sa.String(64)),
        sa.Column("work_fingerprint", sa.String(64)),
        sa.Column("visual_run_id", sa.String(36)),
        sa.Column("waiting_reason", sa.String(128)),
        sa.Column("terminal_reason", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], name="fk_visual_request_user", ondelete="RESTRICT"),
        sa.CheckConstraint("(initiated_by_user_id IS NOT NULL) <> (initiating_service IS NOT NULL)", name="ck_visual_request_initiator"),
        sa.CheckConstraint(
            "status IN ('created','waiting_material','evaluating_need','planning_sources','evaluating_policy',"
            "'freezing_work','work_attached','review_required','failed','cancelled')",
            name="ck_visual_request_status",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 3", name="ck_visual_request_priority"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts AND recovery_generation >= 0", name="ck_visual_request_attempts"),
        sa.CheckConstraint("retryability IS NULL OR retryability IN ('recoverable','owner_action','non_retryable')", name="ck_visual_request_retryability"),
        sa.CheckConstraint(
            "((status IN ('created','waiting_material','evaluating_need','planning_sources','evaluating_policy') "
            "AND visual_run_id IS NULL AND source_plan_fingerprint IS NULL AND work_fingerprint IS NULL) OR "
            "(status = 'freezing_work' AND visual_run_id IS NULL AND source_plan_fingerprint IS NOT NULL AND work_fingerprint IS NOT NULL) OR "
            "(status = 'work_attached' AND visual_run_id IS NOT NULL AND source_plan_fingerprint IS NOT NULL AND work_fingerprint IS NOT NULL) OR "
            "(status IN ('review_required','failed','cancelled') AND ((visual_run_id IS NULL AND source_plan_fingerprint IS NULL AND work_fingerprint IS NULL) OR "
            "(visual_run_id IS NULL AND source_plan_fingerprint IS NOT NULL AND work_fingerprint IS NOT NULL) OR "
            "(visual_run_id IS NOT NULL AND source_plan_fingerprint IS NOT NULL AND work_fingerprint IS NOT NULL))))",
            name="ck_visual_request_identity_state",
        ),
        sa.CheckConstraint(_hex_check("request_fingerprint"), name="ck_visual_request_fingerprint"),
        sa.CheckConstraint(_hex_check("authorization_scope_fingerprint"), name="ck_visual_request_scope_fp"),
        sa.CheckConstraint(_hex_check("request_manifest_sha256"), name="ck_visual_request_manifest_sha"),
        sa.CheckConstraint("source_plan_fingerprint IS NULL OR source_plan_fingerprint ~ '^[0-9a-f]{64}$'", name="ck_visual_request_plan_fp"),
        sa.CheckConstraint("work_fingerprint IS NULL OR work_fingerprint ~ '^[0-9a-f]{64}$'", name="ck_visual_request_work_fp"),
        sa.CheckConstraint(_json_bound("request_manifest", 262144), name="ck_visual_request_manifest_bound"),
        sa.UniqueConstraint("id", "authorization_scope_fingerprint", name="uq_visual_request_scope"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_request_run"),
    )
    op.create_index("uq_visual_request_user_key", "visual_analysis_requests", ["initiated_by_user_id", "request_idempotency_key"], unique=True, postgresql_where=sa.text("initiated_by_user_id IS NOT NULL"))
    op.create_index("uq_visual_request_service_key", "visual_analysis_requests", ["initiating_service", "request_idempotency_key"], unique=True, postgresql_where=sa.text("initiating_service IS NOT NULL"))
    op.create_index("uq_visual_request_active_fp", "visual_analysis_requests", ["authorization_scope_fingerprint", "request_fingerprint"], unique=True, postgresql_where=sa.text("status NOT IN ('review_required','failed','cancelled')"))
    op.create_index("ix_visual_request_queue", "visual_analysis_requests", ["status", "priority", "next_attempt_at", "created_at", "id"], postgresql_where=sa.text("status IN ('created','waiting_material','evaluating_need','planning_sources','evaluating_policy','freezing_work')"))
    op.create_index("ix_visual_request_lease", "visual_analysis_requests", ["status", "lease_expires_at", "heartbeat_at", "last_progress_at", "id"], postgresql_where=sa.text("lease_owner IS NOT NULL"))

    op.create_table(
        "visual_analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_request_id", sa.String(36), nullable=False),
        sa.Column("authorization_scope_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_plan_fingerprint", sa.String(64), nullable=False),
        sa.Column("work_fingerprint", sa.String(64), nullable=False),
        sa.Column("run_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued_external"),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("recovery_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_state", sa.String(16), nullable=False, server_default="none"),
        sa.Column("required_coverage_satisfied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("required_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("covered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("terminal_reason", sa.String(128)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["canonical_request_id", "authorization_scope_fingerprint"], ["visual_analysis_requests.id", "visual_analysis_requests.authorization_scope_fingerprint"], name="fk_visual_run_request_scope", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('queued_external','waiting_external','external_processing','validating_external','assembling','validating_artifact','publishing_artifact','auth_required','ui_changed','cancelling','completed','review_required','failed','cancelled','superseded')", name="ck_visual_run_status"),
        sa.CheckConstraint("coverage_state IN ('complete','partial','none')", name="ck_visual_run_coverage"),
        sa.CheckConstraint("required_count >= 0 AND covered_count >= 0 AND covered_count <= required_count", name="ck_visual_run_counts"),
        sa.CheckConstraint("run_generation >= 1 AND recovery_generation >= 0 AND priority BETWEEN 0 AND 3", name="ck_visual_run_generation"),
        sa.CheckConstraint(_hex_check("authorization_scope_fingerprint"), name="ck_visual_run_scope_fp"),
        sa.CheckConstraint(_hex_check("source_plan_fingerprint"), name="ck_visual_run_plan_fp"),
        sa.CheckConstraint(_hex_check("work_fingerprint"), name="ck_visual_run_work_fp"),
        sa.UniqueConstraint("id", "source_plan_fingerprint", "work_fingerprint", name="uq_visual_run_work_identity"),
    )
    op.create_index("uq_visual_run_active_work", "visual_analysis_runs", ["authorization_scope_fingerprint", "work_fingerprint"], unique=True, postgresql_where=sa.text("status IN ('queued_external','waiting_external','external_processing','validating_external','assembling','validating_artifact','publishing_artifact','auth_required','ui_changed','cancelling')"))
    op.create_index("ix_visual_run_queue", "visual_analysis_runs", ["status", "priority", "created_at", "id"], postgresql_where=sa.text("status NOT IN ('completed','review_required','failed','cancelled','superseded')"))

    op.create_foreign_key("fk_visual_request_run_work", "visual_analysis_requests", "visual_analysis_runs", ["visual_run_id", "source_plan_fingerprint", "work_fingerprint"], ["id", "source_plan_fingerprint", "work_fingerprint"], ondelete="RESTRICT")

    op.create_table(
        "visual_analysis_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("stage_key", sa.String(80), nullable=False),
        sa.Column("stage_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_progress_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("absolute_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("retryability", sa.String(24)),
        sa.Column("error_code", sa.String(128)),
        sa.Column("result_manifest", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["visual_run_id"], ["visual_analysis_runs.id"], name="fk_visual_stage_run", ondelete="RESTRICT"),
        sa.CheckConstraint("stage_type IN ('prepare_external_batches','dispatch_external_batches','wait_external_batches','validate_external_batches','assemble_artifact','publish_artifact','cleanup')", name="ck_visual_stage_type"),
        sa.CheckConstraint("status IN ('queued','waiting','running','completed','skipped','failed','cancelled')", name="ck_visual_stage_status"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 5 AND max_attempts BETWEEN 1 AND 5 AND attempt <= max_attempts", name="ck_visual_stage_attempts"),
        sa.CheckConstraint("result_manifest IS NULL OR octet_length(result_manifest::text) <= 131072", name="ck_visual_stage_result_bound"),
        sa.UniqueConstraint("visual_run_id", "stage_key", "attempt", name="uq_visual_stage_attempt"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_stage_id_run"),
    )
    op.create_index("ix_visual_stage_queue", "visual_analysis_stages", ["status", "next_attempt_at", "visual_run_id", "ordinal", "id"], postgresql_where=sa.text("status IN ('queued','waiting','running')"))
    op.create_index("ix_visual_stage_lease", "visual_analysis_stages", ["status", "lease_expires_at", "heartbeat_at", "last_progress_at", "id"], postgresql_where=sa.text("status = 'running'"))

    op.create_table(
        "visual_source_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("requirement_key", sa.String(80), nullable=False),
        sa.Column("necessity", sa.String(16), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("requested_locator_kind", sa.String(32), nullable=False),
        sa.Column("requested_locator", JSONB, nullable=False),
        sa.Column("requested_page_id", sa.BigInteger()),
        sa.Column("requested_asset_id", sa.BigInteger()),
        sa.Column("requirement_fingerprint", sa.String(64), nullable=False),
        sa.Column("availability_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("coverage_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("terminal_reason", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["visual_run_id"], ["visual_analysis_runs.id"], name="fk_visual_req_source_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_page_id"], ["document_pages.id"], name="fk_visual_req_source_page", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_asset_id"], ["document_assets.id"], name="fk_visual_req_source_asset", ondelete="RESTRICT"),
        sa.CheckConstraint("necessity IN ('required','helpful')", name="ck_visual_req_source_necessity"),
        sa.CheckConstraint("availability_status IN ('pending','available','unavailable','policy_blocked','omitted_by_bound')", name="ck_visual_req_source_availability"),
        sa.CheckConstraint("coverage_status IN ('pending','covered','not_covered')", name="ck_visual_req_source_coverage"),
        sa.CheckConstraint("NOT (requested_page_id IS NOT NULL AND requested_asset_id IS NOT NULL)", name="ck_visual_req_source_locator"),
        sa.CheckConstraint(_hex_check("requirement_fingerprint"), name="ck_visual_req_source_fingerprint"),
        sa.CheckConstraint(_json_bound("requested_locator", 32768), name="ck_visual_req_source_locator_bound"),
        sa.UniqueConstraint("visual_run_id", "requirement_key", name="uq_visual_req_source_key"),
        sa.UniqueConstraint("visual_run_id", "requirement_fingerprint", name="uq_visual_req_source_fp"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_req_source_id_run"),
    )

    op.create_table(
        "visual_analysis_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("material_source_id", sa.String(36), nullable=False),
        sa.Column("material_generation_id", sa.String(36), nullable=False),
        sa.Column("material_source_kind", sa.String(32), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_handle", sa.String(12), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("selection_status", sa.String(32), nullable=False),
        sa.Column("selection_reason", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["visual_run_id"], ["visual_analysis_runs.id"], name="fk_visual_source_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_source_id", "material_generation_id", "material_source_kind", "source_sha256"], ["document_material_sources.id", "document_material_sources.material_generation_id", "document_material_sources.source_kind", "document_material_sources.source_sha256"], name="fk_visual_source_material_exact", ondelete="RESTRICT"),
        sa.CheckConstraint("material_source_kind IN ('page_render','asset_render')", name="ck_visual_source_kind"),
        sa.CheckConstraint("selection_status IN ('selected_external_candidate','selected_local_only','unavailable','omitted_by_bound','not_selected')", name="ck_visual_source_selection"),
        sa.CheckConstraint(_hex_check("source_sha256"), name="ck_visual_source_sha"),
        sa.CheckConstraint("ordinal >= 0", name="ck_visual_source_ordinal"),
        sa.UniqueConstraint("visual_run_id", "source_handle", name="uq_visual_source_handle"),
        sa.UniqueConstraint("visual_run_id", "material_source_id", name="uq_visual_source_material"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_source_id_run"),
        sa.UniqueConstraint("id", "visual_run_id", "material_source_id", "source_sha256", name="uq_visual_source_exact"),
    )

    op.create_table(
        "visual_requirement_source_bindings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("visual_source_id", sa.String(36), nullable=False),
        sa.Column("binding_role", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["requirement_id", "visual_run_id"], ["visual_source_requirements.id", "visual_source_requirements.visual_run_id"], name="fk_visual_binding_requirement", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visual_source_id", "visual_run_id"], ["visual_analysis_sources.id", "visual_analysis_sources.visual_run_id"], name="fk_visual_binding_source", ondelete="RESTRICT"),
        sa.CheckConstraint("binding_role IN ('primary','supporting','comparison')", name="ck_visual_binding_role"),
        sa.UniqueConstraint("requirement_id", "visual_source_id", name="uq_visual_binding_pair"),
        sa.UniqueConstraint("id", "visual_run_id", "requirement_id", "visual_source_id", name="uq_visual_binding_exact"),
    )

    op.create_table(
        "visual_comparison_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("group_key", sa.String(80), nullable=False),
        sa.Column("comparison_kind", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["visual_run_id"], ["visual_analysis_runs.id"], name="fk_visual_cmp_group_run", ondelete="RESTRICT"),
        sa.UniqueConstraint("visual_run_id", "group_key", name="uq_visual_cmp_group_key"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_cmp_group_id_run"),
    )
    op.create_table(
        "visual_comparison_group_members",
        sa.Column("comparison_group_id", sa.String(36), primary_key=True),
        sa.Column("requirement_id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["comparison_group_id", "visual_run_id"], ["visual_comparison_groups.id", "visual_comparison_groups.visual_run_id"], name="fk_visual_cmp_member_group", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requirement_id", "visual_run_id"], ["visual_source_requirements.id", "visual_source_requirements.visual_run_id"], name="fk_visual_cmp_member_requirement", ondelete="RESTRICT"),
        sa.CheckConstraint("ordinal >= 0", name="ck_visual_cmp_member_ordinal"),
        sa.UniqueConstraint("comparison_group_id", "ordinal", name="uq_visual_cmp_member_ordinal"),
    )

    op.create_table(
        "visual_source_authorizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("visual_source_id", sa.String(36), nullable=False),
        sa.Column("material_source_id", sa.String(36), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("privacy_assessment_id", sa.String(36), nullable=False),
        sa.Column("authorization_outcome", sa.String(32), nullable=False),
        sa.Column("authorized_payload_sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["visual_source_id", "visual_run_id", "material_source_id", "source_sha256"], ["visual_analysis_sources.id", "visual_analysis_sources.visual_run_id", "visual_analysis_sources.material_source_id", "visual_analysis_sources.source_sha256"], name="fk_visual_auth_source_exact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["privacy_assessment_id", "material_source_id", "source_sha256", "authorization_outcome", "authorized_payload_sha256"], ["source_privacy_assessments.id", "source_privacy_assessments.material_source_id", "source_privacy_assessments.source_sha256", "source_privacy_assessments.disposition", "source_privacy_assessments.authorized_payload_sha256"], name="fk_visual_auth_privacy_exact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["privacy_assessment_id"], ["source_privacy_assessments.id"], name="fk_visual_auth_privacy", ondelete="RESTRICT"),
        sa.CheckConstraint("authorization_outcome IN ('allowed_external','rejected_external','restricted_never_external')", name="ck_visual_auth_outcome"),
        sa.CheckConstraint("((authorization_outcome = 'allowed_external' AND authorized_payload_sha256 IS NOT NULL) OR (authorization_outcome <> 'allowed_external' AND authorized_payload_sha256 IS NULL))", name="ck_visual_auth_payload"),
        sa.UniqueConstraint("visual_source_id", name="uq_visual_auth_source"),
        sa.UniqueConstraint("id", "visual_run_id", "visual_source_id", "authorized_payload_sha256", name="uq_visual_auth_exact"),
    )


def _create_transport_and_evidence_tables() -> None:
    op.create_table(
        "visual_analysis_consumers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_request_id", sa.String(36), nullable=False),
        sa.Column("visual_run_id", sa.String(36)),
        sa.Column("consumer_kind", sa.String(32), nullable=False),
        sa.Column("consumer_key", sa.String(80), nullable=False),
        sa.Column("assistant_run_id", sa.String(36)),
        sa.Column("owner_user_id", sa.Integer()),
        sa.Column("state", sa.String(24), nullable=False, server_default="attached"),
        sa.Column("required_for_answer", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("delivered_artifact_id", sa.String(36)),
        sa.Column("failure_code", sa.String(128)),
        sa.Column("satisfied_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["visual_request_id", "visual_run_id"], ["visual_analysis_requests.id", "visual_analysis_requests.visual_run_id"], name="fk_visual_consumer_request_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visual_run_id"], ["visual_analysis_runs.id"], name="fk_visual_consumer_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assistant_run_id"], ["assistant_runs.id"], name="fk_visual_consumer_assistant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_visual_consumer_owner", ondelete="RESTRICT"),
        sa.CheckConstraint("state IN ('attached','waiting','satisfied','cancelled','detached','failed')", name="ck_visual_consumer_state"),
        sa.CheckConstraint("((consumer_kind = 'assistant_run' AND assistant_run_id IS NOT NULL AND owner_user_id IS NULL) OR (consumer_kind = 'explicit_user_request' AND assistant_run_id IS NULL AND owner_user_id IS NOT NULL))", name="ck_visual_consumer_owner"),
        sa.CheckConstraint("state <> 'satisfied' OR (visual_run_id IS NOT NULL AND delivered_artifact_id IS NOT NULL AND satisfied_at IS NOT NULL)", name="ck_visual_consumer_delivery"),
        sa.UniqueConstraint("id", "assistant_run_id", name="uq_visual_consumer_id_assistant"),
    )
    op.create_index("uq_visual_consumer_assistant", "visual_analysis_consumers", ["assistant_run_id", "consumer_key"], unique=True, postgresql_where=sa.text("consumer_kind = 'assistant_run' AND assistant_run_id IS NOT NULL"))
    op.create_index("uq_visual_consumer_explicit", "visual_analysis_consumers", ["owner_user_id", "consumer_key"], unique=True, postgresql_where=sa.text("consumer_kind = 'explicit_user_request' AND owner_user_id IS NOT NULL"))
    op.create_index("ix_visual_consumer_run", "visual_analysis_consumers", ["visual_run_id", "state", "id"])

    op.create_table(
        "visual_external_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("visual_stage_id", sa.String(36), nullable=False),
        sa.Column("batch_ordinal", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("source_plan_fingerprint", sa.String(64), nullable=False),
        sa.Column("package_fingerprint", sa.String(64), nullable=False),
        sa.Column("package_sha256", sa.String(64), nullable=False),
        sa.Column("package_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sanitized_package", JSONB, nullable=False),
        sa.Column("transport_idempotency_key", sa.String(128), nullable=False),
        sa.Column("supervisor_external_job_id", sa.String(64)),
        sa.Column("worker_attempt", sa.Integer()),
        sa.Column("external_prompt_generation", sa.String(64), nullable=False),
        sa.Column("result_contract_generation", sa.String(64), nullable=False),
        sa.Column("transport_generation", sa.String(64), nullable=False),
        sa.Column("raw_response_sha256", sa.String(64)),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_progress_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("absolute_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("retryability", sa.String(24)),
        sa.Column("error_code", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("response_captured_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["visual_stage_id", "visual_run_id"], ["visual_analysis_stages.id", "visual_analysis_stages.visual_run_id"], name="fk_visual_batch_stage_run", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('created','queued','dispatched','waiting_response','response_captured','validating','validated','auth_required','ui_changed','failed','cancelled','superseded')", name="ck_visual_batch_status"),
        sa.CheckConstraint("((status IN ('created','queued','dispatched','waiting_response','auth_required','ui_changed') AND raw_response_sha256 IS NULL) OR (status IN ('response_captured','validating','validated') AND raw_response_sha256 IS NOT NULL) OR status IN ('failed','cancelled','superseded'))", name="ck_visual_batch_response_state"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 5 AND batch_ordinal >= 0 AND package_size_bytes >= 1", name="ck_visual_batch_bounds"),
        sa.CheckConstraint(_hex_check("source_plan_fingerprint"), name="ck_visual_batch_plan_fp"),
        sa.CheckConstraint(_hex_check("package_fingerprint"), name="ck_visual_batch_package_fp"),
        sa.CheckConstraint(_hex_check("package_sha256"), name="ck_visual_batch_package_sha"),
        sa.CheckConstraint("raw_response_sha256 IS NULL OR raw_response_sha256 ~ '^[0-9a-f]{64}$'", name="ck_visual_batch_raw_sha"),
        sa.CheckConstraint(_json_bound("sanitized_package", 1048576), name="ck_visual_batch_package_bound"),
        sa.UniqueConstraint("visual_run_id", "batch_ordinal", "attempt", name="uq_visual_batch_attempt"),
        sa.UniqueConstraint("transport_idempotency_key", name="uq_visual_batch_transport_key"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_batch_id_run"),
        sa.UniqueConstraint("id", "raw_response_sha256", name="uq_visual_batch_id_raw"),
    )
    op.create_index("uq_visual_batch_supervisor_job", "visual_external_batches", ["supervisor_external_job_id"], unique=True, postgresql_where=sa.text("supervisor_external_job_id IS NOT NULL"))
    op.create_index("ix_visual_batch_queue", "visual_external_batches", ["status", "next_attempt_at", "created_at", "id"], postgresql_where=sa.text("status IN ('created','queued','dispatched','waiting_response','response_captured','validating','auth_required','ui_changed')"))
    op.create_index("ix_visual_batch_lease", "visual_external_batches", ["status", "lease_expires_at", "heartbeat_at", "last_progress_at", "id"], postgresql_where=sa.text("lease_owner IS NOT NULL"))

    op.create_table(
        "visual_external_batch_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("visual_source_id", sa.String(36), nullable=False),
        sa.Column("source_authorization_id", sa.String(36), nullable=False),
        sa.Column("transmitted_sha256", sa.String(64), nullable=False),
        sa.Column("source_handle", sa.String(12), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["batch_id", "visual_run_id"], ["visual_external_batches.id", "visual_external_batches.visual_run_id"], name="fk_visual_batch_source_batch", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visual_source_id", "visual_run_id"], ["visual_analysis_sources.id", "visual_analysis_sources.visual_run_id"], name="fk_visual_batch_source_source", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_authorization_id", "visual_run_id", "visual_source_id", "transmitted_sha256"], ["visual_source_authorizations.id", "visual_source_authorizations.visual_run_id", "visual_source_authorizations.visual_source_id", "visual_source_authorizations.authorized_payload_sha256"], name="fk_visual_batch_source_auth", ondelete="RESTRICT"),
        sa.CheckConstraint(_hex_check("transmitted_sha256"), name="ck_visual_batch_source_sha"),
        sa.CheckConstraint("ordinal >= 0", name="ck_visual_batch_source_ordinal"),
        sa.UniqueConstraint("batch_id", "visual_source_id", name="uq_visual_batch_source_pair"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_batch_source_id_run"),
        sa.UniqueConstraint("id", "batch_id", "visual_run_id", name="uq_visual_batch_source_batch_run"),
        sa.UniqueConstraint("id", "batch_id", "visual_run_id", "visual_source_id", name="uq_visual_batch_source_exact"),
    )

    op.create_table(
        "visual_external_batch_source_requirements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("batch_source_id", sa.String(36), nullable=False),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["requirement_id", "visual_run_id"], ["visual_source_requirements.id", "visual_source_requirements.visual_run_id"], name="fk_visual_batch_req_requirement", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_source_id", "visual_run_id"], ["visual_external_batch_sources.id", "visual_external_batch_sources.visual_run_id"], name="fk_visual_batch_req_source", ondelete="RESTRICT"),
        sa.UniqueConstraint("batch_source_id", "requirement_id", name="uq_visual_batch_req_pair"),
        sa.UniqueConstraint("id", "visual_run_id", "batch_source_id", "requirement_id", name="uq_visual_batch_req_exact"),
    )

    op.create_table(
        "validated_visual_batch_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("external_batch_id", sa.String(36), nullable=False),
        sa.Column("raw_response_sha256", sa.String(64), nullable=False),
        sa.Column("validated_payload", JSONB),
        sa.Column("validated_payload_sha256", sa.String(64)),
        sa.Column("validation_state", sa.String(24), nullable=False),
        sa.Column("validation_error_code", sa.String(128)),
        sa.Column("validation_metadata", JSONB),
        sa.Column("validator_generation", sa.String(64), nullable=False),
        sa.Column("result_contract_generation", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["external_batch_id", "visual_run_id"], ["visual_external_batches.id", "visual_external_batches.visual_run_id"], name="fk_validated_visual_batch_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["external_batch_id", "raw_response_sha256"], ["visual_external_batches.id", "visual_external_batches.raw_response_sha256"], name="fk_validated_visual_batch_raw", ondelete="RESTRICT"),
        sa.CheckConstraint("validation_state IN ('accepted','rejected','stale')", name="ck_validated_visual_state"),
        sa.CheckConstraint("((validation_state = 'accepted' AND validated_payload IS NOT NULL AND validated_payload_sha256 IS NOT NULL AND validation_error_code IS NULL) OR (validation_state <> 'accepted' AND validated_payload IS NULL AND validated_payload_sha256 IS NULL))", name="ck_validated_visual_payload_state"),
        sa.CheckConstraint(_hex_check("raw_response_sha256"), name="ck_validated_visual_raw_sha"),
        sa.CheckConstraint("validated_payload_sha256 IS NULL OR validated_payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_validated_visual_payload_sha"),
        sa.CheckConstraint("validated_payload IS NULL OR octet_length(validated_payload::text) <= 1048576", name="ck_validated_visual_payload_bound"),
        sa.CheckConstraint("validation_metadata IS NULL OR octet_length(validation_metadata::text) <= 65536", name="ck_validated_visual_metadata_bound"),
        sa.UniqueConstraint("external_batch_id", name="uq_validated_visual_batch"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_validated_visual_id_run"),
        sa.UniqueConstraint("id", "external_batch_id", "visual_run_id", name="uq_validated_visual_exact"),
    )

    op.create_table(
        "visual_evidence_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("accepted_stage_id", sa.String(36), nullable=False),
        sa.Column("source_plan_fingerprint", sa.String(64), nullable=False),
        sa.Column("work_fingerprint", sa.String(64), nullable=False),
        sa.Column("artifact_fingerprint", sa.String(64), nullable=False),
        sa.Column("coverage_state", sa.String(16), nullable=False),
        sa.Column("required_coverage_satisfied", sa.Boolean(), nullable=False),
        sa.Column("required_count", sa.Integer(), nullable=False),
        sa.Column("covered_count", sa.Integer(), nullable=False),
        sa.Column("accepted_atom_count", sa.Integer(), nullable=False),
        sa.Column("accepted_source_count", sa.Integer(), nullable=False),
        sa.Column("limitation_metadata", JSONB),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("validator_generation", sa.String(64), nullable=False),
        sa.Column("result_contract_generation", sa.String(64), nullable=False),
        sa.Column("artifact_assembler_generation", sa.String(64), nullable=False),
        sa.Column("acceptance_consumer_count", sa.Integer(), nullable=False),
        sa.Column("acceptance_consumer_set_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_by_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["visual_run_id", "source_plan_fingerprint", "work_fingerprint"], ["visual_analysis_runs.id", "visual_analysis_runs.source_plan_fingerprint", "visual_analysis_runs.work_fingerprint"], name="fk_visual_artifact_run_work", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["accepted_stage_id", "visual_run_id"], ["visual_analysis_stages.id", "visual_analysis_stages.visual_run_id"], name="fk_visual_artifact_stage_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["visual_evidence_artifacts.id"], name="fk_visual_artifact_superseded", ondelete="RESTRICT"),
        sa.CheckConstraint("coverage_state IN ('complete','partial')", name="ck_visual_artifact_coverage"),
        sa.CheckConstraint("accepted_atom_count >= 1 AND accepted_source_count >= 1 AND acceptance_consumer_count >= 1", name="ck_visual_artifact_counts"),
        sa.CheckConstraint("required_count >= 0 AND covered_count >= 0 AND covered_count <= required_count", name="ck_visual_artifact_coverage_counts"),
        sa.CheckConstraint("coverage_state <> 'complete' OR required_coverage_satisfied", name="ck_visual_artifact_complete"),
        sa.CheckConstraint(_hex_check("artifact_fingerprint"), name="ck_visual_artifact_fingerprint"),
        sa.CheckConstraint(_hex_check("manifest_sha256"), name="ck_visual_artifact_manifest_sha"),
        sa.CheckConstraint(_hex_check("acceptance_consumer_set_sha256"), name="ck_visual_artifact_consumer_sha"),
        sa.CheckConstraint(_json_bound("manifest", 1048576), name="ck_visual_artifact_manifest_bound"),
        sa.CheckConstraint("limitation_metadata IS NULL OR octet_length(limitation_metadata::text) <= 65536", name="ck_visual_artifact_limit_bound"),
        sa.UniqueConstraint("id", "visual_run_id", name="uq_visual_artifact_id_run"),
    )
    op.create_index("uq_visual_artifact_current_work", "visual_evidence_artifacts", ["work_fingerprint"], unique=True, postgresql_where=sa.text("superseded_at IS NULL"))

    op.create_table(
        "visual_evidence_artifact_batches",
        sa.Column("artifact_id", sa.String(36), primary_key=True),
        sa.Column("validated_result_id", sa.String(36), primary_key=True),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id", "visual_run_id"], ["visual_evidence_artifacts.id", "visual_evidence_artifacts.visual_run_id"], name="fk_visual_artifact_batch_artifact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["validated_result_id", "visual_run_id"], ["validated_visual_batch_results.id", "validated_visual_batch_results.visual_run_id"], name="fk_visual_artifact_batch_result", ondelete="RESTRICT"),
    )

    op.create_table(
        "visual_evidence_atoms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("atom_key", sa.String(80), nullable=False),
        sa.Column("claim_class", sa.String(24), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("statement_sha256", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("comparison_group_key", sa.String(80)),
        sa.Column("numeric_value", sa.Numeric()),
        sa.Column("unit", sa.String(32)),
        sa.Column("qualifiers", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["artifact_id", "visual_run_id"], ["visual_evidence_artifacts.id", "visual_evidence_artifacts.visual_run_id"], name="fk_visual_atom_artifact", ondelete="RESTRICT"),
        sa.CheckConstraint("claim_class IN ('FACT','ESTIMATE','HYPOTHESIS','MISSING')", name="ck_visual_atom_class"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_visual_atom_confidence"),
        sa.CheckConstraint(_hex_check("statement_sha256"), name="ck_visual_atom_statement_sha"),
        sa.CheckConstraint("octet_length(statement) <= 32768", name="ck_visual_atom_statement_bound"),
        sa.CheckConstraint("qualifiers IS NULL OR octet_length(qualifiers::text) <= 32768", name="ck_visual_atom_qualifier_bound"),
        sa.UniqueConstraint("artifact_id", "atom_key", name="uq_visual_atom_key"),
        sa.UniqueConstraint("id", "artifact_id", "visual_run_id", name="uq_visual_atom_exact"),
    )

    op.create_table(
        "visual_evidence_atom_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("atom_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("visual_run_id", sa.String(36), nullable=False),
        sa.Column("validated_result_id", sa.String(36), nullable=False),
        sa.Column("external_batch_id", sa.String(36), nullable=False),
        sa.Column("batch_source_id", sa.String(36), nullable=False),
        sa.Column("batch_source_requirement_id", sa.BigInteger(), nullable=False),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("citation_role", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["atom_id", "artifact_id", "visual_run_id"], ["visual_evidence_atoms.id", "visual_evidence_atoms.artifact_id", "visual_evidence_atoms.visual_run_id"], name="fk_visual_atom_source_atom", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id", "validated_result_id"], ["visual_evidence_artifact_batches.artifact_id", "visual_evidence_artifact_batches.validated_result_id"], name="fk_visual_atom_source_artifact_result", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["validated_result_id", "external_batch_id", "visual_run_id"], ["validated_visual_batch_results.id", "validated_visual_batch_results.external_batch_id", "validated_visual_batch_results.visual_run_id"], name="fk_visual_atom_source_result", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_source_id", "external_batch_id", "visual_run_id"], ["visual_external_batch_sources.id", "visual_external_batch_sources.batch_id", "visual_external_batch_sources.visual_run_id"], name="fk_visual_atom_source_batch_source", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_source_requirement_id", "visual_run_id", "batch_source_id", "requirement_id"], ["visual_external_batch_source_requirements.id", "visual_external_batch_source_requirements.visual_run_id", "visual_external_batch_source_requirements.batch_source_id", "visual_external_batch_source_requirements.requirement_id"], name="fk_visual_atom_source_batch_requirement", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requirement_id", "visual_run_id"], ["visual_source_requirements.id", "visual_source_requirements.visual_run_id"], name="fk_visual_atom_source_requirement", ondelete="RESTRICT"),
        sa.CheckConstraint("citation_role IN ('support','contradiction','measurement','limitation')", name="ck_visual_atom_source_role"),
        sa.UniqueConstraint("atom_id", "validated_result_id", "batch_source_requirement_id", name="uq_visual_atom_source_path"),
    )

    op.create_foreign_key("fk_visual_consumer_delivered_artifact", "visual_analysis_consumers", "visual_evidence_artifacts", ["delivered_artifact_id", "visual_run_id"], ["id", "visual_run_id"], ondelete="RESTRICT")


def _extend_intelligence_and_assistant() -> None:
    op.add_column("document_intelligence_artifacts", sa.Column("material_generation_id", sa.String(36)))
    op.add_column("document_intelligence_artifacts", sa.Column("modality", sa.String(16)))
    op.add_column("document_intelligence_artifacts", sa.Column("source_set_fingerprint", sa.String(64)))
    op.add_column("document_intelligence_artifacts", sa.Column("superseded_by_id", sa.String(36)))
    op.create_foreign_key("fk_doc_intel_material_generation", "document_intelligence_artifacts", "document_material_generations", ["material_generation_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_doc_intel_superseded_by", "document_intelligence_artifacts", "document_intelligence_artifacts", ["superseded_by_id"], ["id"], ondelete="RESTRICT")
    op.drop_constraint("ck_document_intelligence_artifacts_kind", "document_intelligence_artifacts", type_="check")
    op.create_check_constraint("ck_document_intelligence_artifacts_kind", "document_intelligence_artifacts", "kind IN ('baseline_document','baseline_visual','section_map','baseline_text','text_section_map')")
    op.create_check_constraint("ck_doc_intel_v3_identity", "document_intelligence_artifacts", "((analyzer_generation = 'document-intelligence-v3-text' AND kind IN ('baseline_text','text_section_map') AND modality = 'text' AND material_generation_id IS NOT NULL AND source_set_fingerprint IS NOT NULL) OR (analyzer_generation <> 'document-intelligence-v3-text' AND kind NOT IN ('baseline_text','text_section_map') AND modality IS NULL AND material_generation_id IS NULL AND source_set_fingerprint IS NULL))")
    op.create_check_constraint("ck_doc_intel_source_set_sha", "document_intelligence_artifacts", "source_set_fingerprint IS NULL OR source_set_fingerprint ~ '^[0-9a-f]{64}$'")
    op.drop_constraint("uq_document_intelligence_generation", "document_intelligence_artifacts", type_="unique")
    op.create_index("uq_doc_intel_legacy_generation", "document_intelligence_artifacts", ["document_id", "input_checksum", "analyzer_generation", "kind", "artifact_key"], unique=True, postgresql_where=sa.text("analyzer_generation <> 'document-intelligence-v3-text'"))
    op.create_index("uq_doc_intel_v3_generation", "document_intelligence_artifacts", ["document_id", "material_generation_id", "analyzer_generation", "kind", "artifact_key", "source_set_fingerprint"], unique=True, postgresql_where=sa.text("analyzer_generation = 'document-intelligence-v3-text'"))

    op.add_column("document_intelligence_sources", sa.Column("material_source_id", sa.String(36)))
    op.add_column("document_intelligence_sources", sa.Column("material_source_sha256", sa.String(64)))
    op.create_check_constraint("ck_doc_intel_source_material_pair", "document_intelligence_sources", "(material_source_id IS NULL) = (material_source_sha256 IS NULL)")
    op.create_foreign_key("fk_doc_intel_source_material", "document_intelligence_sources", "document_material_sources", ["material_source_id", "material_source_sha256"], ["id", "source_sha256"], ondelete="RESTRICT")

    op.add_column("assistant_run_stages", sa.Column("visual_consumer_id", sa.String(36)))
    op.drop_constraint("ck_assistant_run_stages_type", "assistant_run_stages", type_="check")
    op.create_check_constraint("ck_assistant_run_stages_type", "assistant_run_stages", f"stage_type IN ({_ASSISTANT_STAGE_TYPES})")
    op.create_foreign_key("fk_assistant_stage_visual_consumer", "assistant_run_stages", "visual_analysis_consumers", ["visual_consumer_id", "assistant_run_id"], ["id", "assistant_run_id"], ondelete="RESTRICT")


def _create_deferred_integrity_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION visual_v2_check_comparison_group() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE target_id varchar(36); member_count integer;
        BEGIN
          target_id := CASE WHEN TG_TABLE_NAME = 'visual_comparison_groups' THEN COALESCE(NEW.id, OLD.id) ELSE COALESCE(NEW.comparison_group_id, OLD.comparison_group_id) END;
          IF EXISTS (SELECT 1 FROM visual_comparison_groups WHERE id = target_id) THEN
            SELECT count(*) INTO member_count FROM visual_comparison_group_members WHERE comparison_group_id = target_id;
            IF member_count < 2 THEN RAISE EXCEPTION 'visual_comparison_group_requires_two_members'; END IF;
          END IF;
          RETURN NULL;
        END $$;
        """
    )
    op.execute("CREATE CONSTRAINT TRIGGER ct_visual_cmp_group_members AFTER INSERT OR UPDATE OR DELETE ON visual_comparison_group_members DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION visual_v2_check_comparison_group()")
    op.execute("CREATE CONSTRAINT TRIGGER ct_visual_cmp_group_row AFTER INSERT OR UPDATE ON visual_comparison_groups DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION visual_v2_check_comparison_group()")

    op.execute(
        """
        CREATE FUNCTION visual_v2_check_artifact_acceptance() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE atom_count integer; source_count integer; consumer_count integer;
        BEGIN
          SELECT count(*) INTO atom_count FROM visual_evidence_atoms WHERE artifact_id = NEW.id;
          SELECT count(DISTINCT batch_source_id) INTO source_count FROM visual_evidence_atom_sources WHERE artifact_id = NEW.id;
          SELECT count(*) INTO consumer_count FROM visual_analysis_consumers WHERE visual_run_id = NEW.visual_run_id AND state IN ('attached','waiting','satisfied');
          IF atom_count <> NEW.accepted_atom_count OR atom_count < 1 THEN RAISE EXCEPTION 'visual_artifact_atom_count_mismatch'; END IF;
          IF source_count <> NEW.accepted_source_count OR source_count < 1 THEN RAISE EXCEPTION 'visual_artifact_source_count_mismatch'; END IF;
          IF consumer_count < 1 OR consumer_count < NEW.acceptance_consumer_count THEN RAISE EXCEPTION 'visual_artifact_without_active_consumer'; END IF;
          RETURN NULL;
        END $$;
        """
    )
    op.execute("CREATE CONSTRAINT TRIGGER ct_visual_artifact_acceptance AFTER INSERT OR UPDATE ON visual_evidence_artifacts DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION visual_v2_check_artifact_acceptance()")


def upgrade() -> None:
    _create_existing_table_extensions()
    _create_material_tables()
    _create_visual_planning_tables()
    _create_transport_and_evidence_tables()
    _extend_intelligence_and_assistant()
    _create_deferred_integrity_triggers()


_NEW_TABLES = (
    "visual_evidence_atom_sources", "visual_evidence_atoms", "visual_evidence_artifact_batches",
    "visual_evidence_artifacts", "validated_visual_batch_results",
    "visual_external_batch_source_requirements", "visual_external_batch_sources",
    "visual_external_batches", "visual_analysis_consumers", "visual_source_authorizations",
    "visual_comparison_group_members", "visual_comparison_groups",
    "visual_requirement_source_bindings", "visual_analysis_sources",
    "visual_source_requirements", "visual_analysis_stages", "visual_analysis_runs",
    "visual_analysis_requests", "source_privacy_assessments",
    "document_material_sources", "document_material_generations",
)


def _refuse_destructive_downgrade() -> None:
    connection = op.get_bind()
    for table in _NEW_TABLES:
        if connection.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')).scalar():
            raise RuntimeError(f"visual_evidence_v2_downgrade_refused:{table}_contains_data")
    guards = (
        ("document_preparation_jobs", "processor_generation = 'document-preparation-v3' OR heartbeat_at IS NOT NULL OR last_progress_at IS NOT NULL"),
        ("document_intelligence_artifacts", "material_generation_id IS NOT NULL OR modality IS NOT NULL OR source_set_fingerprint IS NOT NULL OR superseded_by_id IS NOT NULL"),
        ("document_intelligence_sources", "material_source_id IS NOT NULL OR material_source_sha256 IS NOT NULL"),
        ("assistant_run_stages", "visual_consumer_id IS NOT NULL OR stage_type IN ('evaluating_visual_need','waiting_for_visual','validating_visual','resynthesizing_local')"),
    )
    for table, predicate in guards:
        if connection.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" WHERE {predicate} LIMIT 1)')).scalar():
            raise RuntimeError(f"visual_evidence_v2_downgrade_refused:{table}_contains_v2_state")


def downgrade() -> None:
    _refuse_destructive_downgrade()

    op.execute("DROP TRIGGER ct_visual_artifact_acceptance ON visual_evidence_artifacts")
    op.execute("DROP FUNCTION visual_v2_check_artifact_acceptance()")
    op.execute("DROP TRIGGER ct_visual_cmp_group_members ON visual_comparison_group_members")
    op.execute("DROP TRIGGER ct_visual_cmp_group_row ON visual_comparison_groups")
    op.execute("DROP FUNCTION visual_v2_check_comparison_group()")

    op.drop_constraint("fk_assistant_stage_visual_consumer", "assistant_run_stages", type_="foreignkey")
    op.drop_constraint("ck_assistant_run_stages_type", "assistant_run_stages", type_="check")
    op.create_check_constraint("ck_assistant_run_stages_type", "assistant_run_stages", "stage_type IN ('planning','resolving_targets','waiting_for_material','preparing_material','building_intelligence','validating_intelligence','retrieving_case_evidence','retrieving_knowledge_base','analyzing_local','validating_local','waiting_for_vision','analyzing_vision','waiting_for_advanced','analyzing_advanced','validating_advanced','reducing_findings','synthesizing','finalizing')")
    op.drop_column("assistant_run_stages", "visual_consumer_id")

    op.drop_constraint("fk_doc_intel_source_material", "document_intelligence_sources", type_="foreignkey")
    op.drop_constraint("ck_doc_intel_source_material_pair", "document_intelligence_sources", type_="check")
    op.drop_column("document_intelligence_sources", "material_source_sha256")
    op.drop_column("document_intelligence_sources", "material_source_id")

    op.drop_index("uq_doc_intel_v3_generation", table_name="document_intelligence_artifacts")
    op.drop_index("uq_doc_intel_legacy_generation", table_name="document_intelligence_artifacts")
    op.drop_constraint("ck_doc_intel_source_set_sha", "document_intelligence_artifacts", type_="check")
    op.drop_constraint("ck_doc_intel_v3_identity", "document_intelligence_artifacts", type_="check")
    op.drop_constraint("ck_document_intelligence_artifacts_kind", "document_intelligence_artifacts", type_="check")
    op.create_check_constraint("ck_document_intelligence_artifacts_kind", "document_intelligence_artifacts", "kind IN ('baseline_document','baseline_visual','section_map')")
    op.create_unique_constraint("uq_document_intelligence_generation", "document_intelligence_artifacts", ["document_id", "input_checksum", "analyzer_generation", "kind", "artifact_key"])
    op.drop_constraint("fk_doc_intel_superseded_by", "document_intelligence_artifacts", type_="foreignkey")
    op.drop_constraint("fk_doc_intel_material_generation", "document_intelligence_artifacts", type_="foreignkey")
    op.drop_column("document_intelligence_artifacts", "superseded_by_id")
    op.drop_column("document_intelligence_artifacts", "source_set_fingerprint")
    op.drop_column("document_intelligence_artifacts", "modality")
    op.drop_column("document_intelligence_artifacts", "material_generation_id")

    # Break the two deliberate parent/consumer cycles before dependency-ordered
    # table removal.  No CASCADE is used.
    op.drop_constraint(
        "fk_visual_consumer_delivered_artifact",
        "visual_analysis_consumers",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_visual_request_run_work",
        "visual_analysis_requests",
        type_="foreignkey",
    )
    for table in _NEW_TABLES:
        op.drop_table(table)

    op.drop_constraint("uq_document_assets_id_document", "document_assets", type_="unique")
    op.drop_constraint("uq_document_pages_id_document", "document_pages", type_="unique")
    op.drop_index("ix_document_preparation_jobs_stale", table_name="document_preparation_jobs")
    op.create_index("ix_document_preparation_jobs_stale", "document_preparation_jobs", ["status", "lease_expires_at", "id"])
    op.drop_constraint("ck_document_preparation_jobs_stage", "document_preparation_jobs", type_="check")
    op.create_check_constraint("ck_document_preparation_jobs_stage", "document_preparation_jobs", f"stage IN ({_LEGACY_PREPARATION_STAGES})")
    op.drop_constraint("uq_doc_prep_job_checksum", "document_preparation_jobs", type_="unique")
    op.drop_column("document_preparation_jobs", "last_progress_at")
    op.drop_column("document_preparation_jobs", "heartbeat_at")
