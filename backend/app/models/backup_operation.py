from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


BACKUP_SCOPES = "'full','database','documents','qdrant','n8n_config'"
BACKUP_STAGES = (
    "'queued','validating','database','documents','qdrant','n8n',"
    "'configuration','release','verifying','completed','failed'"
)
RESTORE_STAGES = (
    "'queued','preflight','safety_backup','staging','database_restore',"
    "'documents_restore','qdrant_restore','n8n_config_restore','cutover',"
    "'restarting_services','post_validation','completed','failed',"
    "'rollback_required','approval_required'"
)


class BackupSchedule(Base):
    __tablename__ = "backup_schedules"
    __table_args__ = (
        UniqueConstraint("name", name="uq_backup_schedules_name"),
        CheckConstraint(f"scope IN ({BACKUP_SCOPES})", name="ck_backup_schedules_scope"),
        CheckConstraint("cadence IN ('daily','weekly','monthly')", name="ck_backup_schedules_cadence"),
        CheckConstraint("weekday IS NULL OR weekday BETWEEN 1 AND 7", name="ck_backup_schedules_weekday"),
        CheckConstraint("month_day IS NULL OR month_day BETWEEN 1 AND 31", name="ck_backup_schedules_month_day"),
        CheckConstraint(
            "(cadence = 'daily' AND weekday IS NULL AND month_day IS NULL) OR "
            "(cadence = 'weekly' AND weekday IS NOT NULL AND month_day IS NULL) OR "
            "(cadence = 'monthly' AND weekday IS NULL AND month_day IS NOT NULL)",
            name="ck_backup_schedules_cadence_fields",
        ),
        Index("ix_backup_schedules_enabled_next", "enabled", "next_run_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    local_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    weekday: Mapped[int | None] = mapped_column(Integer)
    month_day: Mapped[int | None] = mapped_column(Integer)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Warsaw", server_default="Europe/Warsaw")
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class BackupRun(Base):
    __tablename__ = "backup_runs"
    __table_args__ = (
        CheckConstraint(f"scope IN ({BACKUP_SCOPES})", name="ck_backup_runs_scope"),
        CheckConstraint("trigger IN ('manual','scheduled','pre_restore')", name="ck_backup_runs_trigger"),
        CheckConstraint("status IN ('queued','running','completed','failed')", name="ck_backup_runs_status"),
        CheckConstraint(f"stage IN ({BACKUP_STAGES})", name="ck_backup_runs_stage"),
        CheckConstraint("artifact_count >= 0", name="ck_backup_runs_artifact_count"),
        CheckConstraint("total_bytes >= 0", name="ck_backup_runs_total_bytes"),
        Index("ix_backup_runs_started_id", "started_at", "id"),
        Index("ix_backup_runs_status_started", "status", "started_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("backup_schedules.id", ondelete="SET NULL"))
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued")
    operation_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    checkpoint_path: Mapped[str | None] = mapped_column(String(700))
    manifest_path: Mapped[str | None] = mapped_column(String(700))
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RestoreRun(Base):
    __tablename__ = "restore_runs"
    __table_args__ = (
        CheckConstraint("mode IN ('database','full')", name="ck_restore_runs_mode"),
        CheckConstraint("status IN ('queued','running','completed','failed','rollback_required','approval_required')", name="ck_restore_runs_status"),
        CheckConstraint(f"stage IN ({RESTORE_STAGES})", name="ck_restore_runs_stage"),
        CheckConstraint("compatibility_result IN ('compatible','requires_migration_after_restore','older_supported_checkpoint','newer_unsupported_checkpoint','invalid')", name="ck_restore_runs_compatibility"),
        Index("ix_restore_runs_started_id", "started_at", "id"),
        Index("ix_restore_runs_status_started", "status", "started_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    backup_run_id: Mapped[int | None] = mapped_column(ForeignKey("backup_runs.id", ondelete="SET NULL"))
    checkpoint_path: Mapped[str] = mapped_column(String(700), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="approval_required", server_default="approval_required")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="approval_required", server_default="approval_required")
    pre_restore_backup_run_id: Mapped[int | None] = mapped_column(ForeignKey("backup_runs.id", ondelete="RESTRICT"))
    manifest_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    compatibility_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    compatibility_result: Mapped[str] = mapped_column(String(48), nullable=False)
    post_validation_status: Mapped[str | None] = mapped_column(String(48))
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
