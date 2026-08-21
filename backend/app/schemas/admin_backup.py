from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


BackupScope = Literal["full", "database", "documents", "qdrant", "n8n_config"]
BackupCadence = Literal["daily", "weekly", "monthly"]
RestoreMode = Literal["database", "full"]


class BackupScheduleWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    scope: BackupScope
    destination: str = Field(min_length=3, max_length=500)
    cadence: BackupCadence
    local_time: time
    weekday: int | None = Field(None, ge=1, le=7)
    month_day: int | None = Field(None, ge=1, le=28)

    @field_validator("name", "destination")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_cadence_fields(self):
        valid = (
            self.cadence == "daily" and self.weekday is None and self.month_day is None
        ) or (
            self.cadence == "weekly" and self.weekday is not None and self.month_day is None
        ) or (
            self.cadence == "monthly" and self.weekday is None and self.month_day is not None
        )
        if not valid:
            raise ValueError("Invalid cadence fields")
        if time(2, 0) <= self.local_time < time(3, 0):
            raise ValueError("backup_schedule_dst_unsafe_time")
        return self


class BackupScheduleRead(BackupScheduleWrite):
    id: int
    timezone_name: str
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime
    sync_status: Literal["synced", "pending_sync", "sync_failed"] = "pending_sync"
    host_task_name: str | None = None
    host_enabled: bool = False
    host_next_run_at: datetime | None = None
    host_last_run_at: datetime | None = None
    host_last_result: int | None = None
    last_backup_at: datetime | None = None
    last_backup_result: str | None = None
    model_config = {"from_attributes": True}


class BackupRunRequest(BaseModel):
    scope: BackupScope
    destination: str = Field(default="C:\\ai-lab-core-backups", min_length=3, max_length=500)
    confirmed: bool


class BackupRunRead(BaseModel):
    id: int
    schedule_id: int | None
    scope: BackupScope
    trigger: str
    destination: str
    status: str
    stage: str
    checkpoint_path: str | None
    manifest_path: str | None
    artifact_count: int
    total_bytes: int
    verified: bool
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None
    model_config = {"from_attributes": True}


class BackupRunPage(BaseModel):
    items: list[BackupRunRead]
    total: int
    skip: int
    limit: int


class RestoreCandidate(BaseModel):
    checkpoint_path: str
    created_at: datetime
    scope: BackupScope
    app_version: str
    source_head: str
    db_revision: str
    total_bytes: int
    verified: bool
    artifact_count: int
    components: list[str]
    database_eligible: bool
    full_eligible: bool
    compatibility: Literal[
        "compatible",
        "requires_migration_after_restore",
        "older_supported_checkpoint",
        "newer_unsupported_checkpoint",
        "invalid",
    ]
    error_code: str | None = None


class RestorePreviewRequest(BaseModel):
    checkpoint_path: str = Field(min_length=3, max_length=700)
    mode: RestoreMode


class RestorePreview(BaseModel):
    mode: RestoreMode
    checkpoint_path: str
    created_at: datetime
    app_version: str
    backup_db_revision: str
    current_db_revision: str
    compatibility: str
    manifest_verified: bool
    eligible: bool
    replaces: list[str]
    service_interruption_required: bool
    pre_restore_backup_required: bool = True
    error_code: str | None = None


class RestoreRequest(RestorePreviewRequest):
    acknowledged: bool
    confirmation: str = Field(max_length=32)


class RestoreRunRead(BaseModel):
    id: int
    backup_run_id: int | None
    checkpoint_path: str
    mode: RestoreMode
    status: str
    stage: str
    pre_restore_backup_run_id: int | None
    manifest_verified: bool
    compatibility_verified: bool
    compatibility_result: str
    post_validation_status: str | None
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None
    model_config = {"from_attributes": True}
