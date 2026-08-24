"""Add durable multi-destination backup planner and managed retention ledger.

Revision ID: followup_backup_planner_retention_20260824
Revises: followup_contact_person_20260822
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_backup_planner_retention_20260824"
down_revision = "followup_contact_person_20260822"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backup_schedules", sa.Column("destination_type", sa.String(32), nullable=False, server_default="local_path"))
    op.add_column("backup_schedules", sa.Column("destination_identity", sa.String(255)))
    op.add_column("backup_schedules", sa.Column("destination_filesystem", sa.String(64)))
    op.add_column("backup_schedules", sa.Column("destination_status", sa.String(32), nullable=False, server_default="unknown"))
    op.add_column("backup_schedules", sa.Column("destination_last_seen_at", sa.DateTime(timezone=True)))
    op.add_column("backup_schedules", sa.Column("destination_total_bytes", sa.BigInteger()))
    op.add_column("backup_schedules", sa.Column("destination_free_bytes", sa.BigInteger()))
    op.add_column("backup_schedules", sa.Column("auto_delete", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("backup_schedules", sa.Column("minimum_free_percent", sa.Integer()))
    op.add_column("backup_schedules", sa.Column("minimum_free_bytes", sa.BigInteger()))
    op.add_column("backup_schedules", sa.Column("minimum_backups_to_keep", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("backup_schedules", sa.Column("keep_last_n", sa.Integer()))
    op.add_column("backup_schedules", sa.Column("keep_days", sa.Integer()))
    op.add_column("backup_schedules", sa.Column("preserve_weekly_count", sa.Integer()))
    op.add_column("backup_schedules", sa.Column("preserve_monthly_count", sa.Integer()))
    op.add_column("backup_schedules", sa.Column("retention_trigger", sa.String(32), nullable=False, server_default="after_successful_backup"))
    op.add_column("backup_schedules", sa.Column("retention_local_time", sa.Time()))
    op.add_column("backup_schedules", sa.Column("retention_weekday", sa.Integer()))
    op.add_column("backup_schedules", sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("backup_schedules", sa.Column("last_reconciled_revision", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("backup_schedules", sa.Column("sync_status", sa.String(32), nullable=False, server_default="pending"))
    op.add_column("backup_schedules", sa.Column("last_sync_at", sa.DateTime(timezone=True)))
    op.add_column("backup_schedules", sa.Column("last_sync_error_code", sa.String(100)))
    op.add_column("backup_schedules", sa.Column("last_destination_check_at", sa.DateTime(timezone=True)))
    op.add_column("backup_schedules", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_backup_schedules_destination_type", "backup_schedules", "destination_type IN ('local_path','removable_or_mounted_path','network_path')")
    op.create_check_constraint("ck_backup_schedules_destination_status", "backup_schedules", "destination_status IN ('unknown','available','unavailable')")
    op.create_check_constraint("ck_backup_schedules_minimum_free_percent", "backup_schedules", "minimum_free_percent IS NULL OR minimum_free_percent BETWEEN 0 AND 95")
    op.create_check_constraint("ck_backup_schedules_minimum_free_bytes", "backup_schedules", "minimum_free_bytes IS NULL OR minimum_free_bytes >= 0")
    op.create_check_constraint("ck_backup_schedules_minimum_keep", "backup_schedules", "minimum_backups_to_keep >= 1")
    op.create_check_constraint("ck_backup_schedules_optional_retention", "backup_schedules", "(keep_last_n IS NULL OR keep_last_n >= 0) AND (keep_days IS NULL OR keep_days >= 0) AND (preserve_weekly_count IS NULL OR preserve_weekly_count >= 0) AND (preserve_monthly_count IS NULL OR preserve_monthly_count >= 0)")
    op.create_check_constraint("ck_backup_schedules_retention_trigger", "backup_schedules", "retention_trigger IN ('after_successful_backup','daily','custom_schedule')")
    op.create_check_constraint("ck_backup_schedules_retention_weekday", "backup_schedules", "retention_weekday IS NULL OR retention_weekday BETWEEN 1 AND 7")
    op.create_check_constraint("ck_backup_schedules_revisions", "backup_schedules", "plan_revision >= 1 AND last_reconciled_revision >= 0 AND last_reconciled_revision <= plan_revision")
    op.create_check_constraint("ck_backup_schedules_sync_status", "backup_schedules", "sync_status IN ('pending','synced','error','disabled','destination_unavailable')")
    op.create_index("ix_backup_schedules_active_sync", "backup_schedules", ["deleted_at", "sync_status", "id"])

    op.create_table(
        "backup_plan_sync_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("backup_schedules.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(100)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("plan_revision >= 1", name="ck_backup_plan_sync_events_revision"),
        sa.CheckConstraint("operation IN ('upsert','remove')", name="ck_backup_plan_sync_events_operation"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed','superseded')", name="ck_backup_plan_sync_events_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_backup_plan_sync_events_attempts"),
        sa.UniqueConstraint("plan_id", "plan_revision", "operation", name="uq_backup_plan_sync_event_revision"),
    )
    op.create_index("ix_backup_plan_sync_events_pending", "backup_plan_sync_events", ["status", "created_at", "id"])

    op.create_table(
        "managed_backups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("backup_id", sa.String(64), nullable=False, unique=True),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("backup_schedules.id", ondelete="SET NULL")),
        sa.Column("backup_run_id", sa.BigInteger(), sa.ForeignKey("backup_runs.id", ondelete="SET NULL"), unique=True),
        sa.Column("destination_root", sa.String(700), nullable=False),
        sa.Column("checkpoint_path", sa.String(700), nullable=False, unique=True),
        sa.Column("manifest_path", sa.String(700), nullable=False),
        sa.Column("manifest_schema", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("app_version", sa.String(32), nullable=False),
        sa.Column("source_head", sa.String(40), nullable=False),
        sa.Column("db_revision", sa.String(128), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("integrity_status", sa.String(24), nullable=False, server_default="verified"),
        sa.Column("protected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lifecycle", sa.String(16), nullable=False, server_default="available"),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("artifact_count >= 0 AND total_bytes >= 0", name="ck_managed_backups_counts"),
        sa.CheckConstraint("integrity_status IN ('verified','invalid','missing','unknown')", name="ck_managed_backups_integrity"),
        sa.CheckConstraint("lifecycle IN ('available','deleting','deleted','missing','error')", name="ck_managed_backups_lifecycle"),
    )
    op.create_index("ix_managed_backups_plan_created", "managed_backups", ["plan_id", "created_at", "id"])
    op.create_index("ix_managed_backups_retention", "managed_backups", ["plan_id", "lifecycle", "protected", "created_at", "id"])

    op.create_table(
        "backup_deletion_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("backup_id", sa.BigInteger(), sa.ForeignKey("managed_backups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("backup_schedules.id", ondelete="SET NULL")),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("planned_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("actual_reclaimed_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(100)),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("mode IN ('manual','automatic')", name="ck_backup_deletion_events_mode"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed')", name="ck_backup_deletion_events_status"),
        sa.CheckConstraint("planned_bytes >= 0 AND actual_reclaimed_bytes >= 0", name="ck_backup_deletion_events_bytes"),
    )
    op.create_index("ix_backup_deletion_events_backup_created", "backup_deletion_events", ["backup_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_backup_deletion_events_backup_created", table_name="backup_deletion_events")
    op.drop_table("backup_deletion_events")
    op.drop_index("ix_managed_backups_retention", table_name="managed_backups")
    op.drop_index("ix_managed_backups_plan_created", table_name="managed_backups")
    op.drop_table("managed_backups")
    op.drop_index("ix_backup_plan_sync_events_pending", table_name="backup_plan_sync_events")
    op.drop_table("backup_plan_sync_events")
    op.drop_index("ix_backup_schedules_active_sync", table_name="backup_schedules")
    for name in (
        "ck_backup_schedules_sync_status", "ck_backup_schedules_revisions",
        "ck_backup_schedules_retention_weekday", "ck_backup_schedules_retention_trigger",
        "ck_backup_schedules_optional_retention", "ck_backup_schedules_minimum_keep",
        "ck_backup_schedules_minimum_free_bytes", "ck_backup_schedules_minimum_free_percent",
        "ck_backup_schedules_destination_status", "ck_backup_schedules_destination_type",
    ):
        op.drop_constraint(name, "backup_schedules", type_="check")
    for name in (
        "deleted_at", "last_destination_check_at", "last_sync_error_code", "last_sync_at",
        "sync_status", "last_reconciled_revision", "plan_revision", "retention_weekday",
        "retention_local_time", "retention_trigger", "preserve_monthly_count",
        "preserve_weekly_count", "keep_days", "keep_last_n", "minimum_backups_to_keep",
        "minimum_free_bytes", "minimum_free_percent", "auto_delete", "destination_free_bytes",
        "destination_total_bytes", "destination_last_seen_at", "destination_status",
        "destination_filesystem", "destination_identity", "destination_type",
    ):
        op.drop_column("backup_schedules", name)
