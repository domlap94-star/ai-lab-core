"""Add bounded Administrator backup and restore operation metadata.

Revision ID: followup_admin_backup_restore_ui_20260821
Revises: followup_work_item_realization_link_20260821
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_admin_backup_restore_ui_20260821"
down_revision = "followup_work_item_realization_link_20260821"
branch_labels = None
depends_on = None


BACKUP_SCOPES = "'full','database','documents','qdrant','n8n_config'"
BACKUP_STAGES = "'queued','validating','database','documents','qdrant','n8n','configuration','release','verifying','completed','failed'"
RESTORE_STAGES = "'queued','preflight','safety_backup','staging','database_restore','documents_restore','qdrant_restore','n8n_config_restore','cutover','restarting_services','post_validation','completed','failed','rollback_required','approval_required'"


def upgrade() -> None:
    op.create_table(
        "backup_schedules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("destination", sa.String(500), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("weekday", sa.Integer()),
        sa.Column("month_day", sa.Integer()),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="Europe/Warsaw"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"scope IN ({BACKUP_SCOPES})", name="ck_backup_schedules_scope"),
        sa.CheckConstraint("cadence IN ('daily','weekly','monthly')", name="ck_backup_schedules_cadence"),
        sa.CheckConstraint("weekday IS NULL OR weekday BETWEEN 1 AND 7", name="ck_backup_schedules_weekday"),
        sa.CheckConstraint("month_day IS NULL OR month_day BETWEEN 1 AND 31", name="ck_backup_schedules_month_day"),
        sa.CheckConstraint("(cadence = 'daily' AND weekday IS NULL AND month_day IS NULL) OR (cadence = 'weekly' AND weekday IS NOT NULL AND month_day IS NULL) OR (cadence = 'monthly' AND weekday IS NULL AND month_day IS NOT NULL)", name="ck_backup_schedules_cadence_fields"),
        sa.UniqueConstraint("name", name="uq_backup_schedules_name"),
    )
    op.create_index("ix_backup_schedules_enabled_next", "backup_schedules", ["enabled", "next_run_at", "id"])

    op.create_table(
        "backup_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("schedule_id", sa.BigInteger(), sa.ForeignKey("backup_schedules.id", ondelete="SET NULL")),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("destination", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("operation_id", sa.String(64), unique=True),
        sa.Column("checkpoint_path", sa.String(700)),
        sa.Column("manifest_path", sa.String(700)),
        sa.Column("artifact_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"scope IN ({BACKUP_SCOPES})", name="ck_backup_runs_scope"),
        sa.CheckConstraint("trigger IN ('manual','scheduled','pre_restore')", name="ck_backup_runs_trigger"),
        sa.CheckConstraint("status IN ('queued','running','completed','failed')", name="ck_backup_runs_status"),
        sa.CheckConstraint(f"stage IN ({BACKUP_STAGES})", name="ck_backup_runs_stage"),
        sa.CheckConstraint("artifact_count >= 0", name="ck_backup_runs_artifact_count"),
        sa.CheckConstraint("total_bytes >= 0", name="ck_backup_runs_total_bytes"),
    )
    op.create_index("ix_backup_runs_started_id", "backup_runs", ["started_at", "id"])
    op.create_index("ix_backup_runs_status_started", "backup_runs", ["status", "started_at", "id"])

    op.create_table(
        "restore_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("backup_run_id", sa.BigInteger(), sa.ForeignKey("backup_runs.id", ondelete="SET NULL")),
        sa.Column("checkpoint_path", sa.String(700), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="approval_required"),
        sa.Column("stage", sa.String(32), nullable=False, server_default="approval_required"),
        sa.Column("pre_restore_backup_run_id", sa.BigInteger(), sa.ForeignKey("backup_runs.id", ondelete="RESTRICT")),
        sa.Column("manifest_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("compatibility_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("compatibility_result", sa.String(48), nullable=False),
        sa.Column("post_validation_status", sa.String(48)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("mode IN ('database','full')", name="ck_restore_runs_mode"),
        sa.CheckConstraint("status IN ('queued','running','completed','failed','rollback_required','approval_required')", name="ck_restore_runs_status"),
        sa.CheckConstraint(f"stage IN ({RESTORE_STAGES})", name="ck_restore_runs_stage"),
        sa.CheckConstraint("compatibility_result IN ('compatible','requires_migration_after_restore','older_supported_checkpoint','newer_unsupported_checkpoint','invalid')", name="ck_restore_runs_compatibility"),
    )
    op.create_index("ix_restore_runs_started_id", "restore_runs", ["started_at", "id"])
    op.create_index("ix_restore_runs_status_started", "restore_runs", ["status", "started_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_restore_runs_status_started", table_name="restore_runs")
    op.drop_index("ix_restore_runs_started_id", table_name="restore_runs")
    op.drop_table("restore_runs")
    op.drop_index("ix_backup_runs_status_started", table_name="backup_runs")
    op.drop_index("ix_backup_runs_started_id", table_name="backup_runs")
    op.drop_table("backup_runs")
    op.drop_index("ix_backup_schedules_enabled_next", table_name="backup_schedules")
    op.drop_table("backup_schedules")
