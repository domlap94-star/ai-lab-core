from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


BackupScope = Literal["full", "database", "documents", "qdrant", "n8n_config"]
BackupCadence = Literal["daily", "weekly", "monthly"]
DestinationType = Literal["local_path", "removable_or_mounted_path", "network_path"]
RetentionTrigger = Literal["after_successful_backup", "daily", "custom_schedule"]
RestoreMode = Literal["database", "full"]


class BackupScheduleWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    scope: BackupScope
    destination: str = Field(min_length=3, max_length=500)
    destination_type: DestinationType = "local_path"
    cadence: BackupCadence
    local_time: time
    weekday: int | None = Field(None, ge=1, le=7)
    month_day: int | None = Field(None, ge=1, le=28)
    auto_delete: bool = False
    minimum_free_percent: int | None = Field(None, ge=0, le=95)
    minimum_free_bytes: int | None = Field(None, ge=0)
    minimum_backups_to_keep: int = Field(3, ge=1, le=1000)
    keep_last_n: int | None = Field(None, ge=0, le=1000)
    keep_days: int | None = Field(None, ge=0, le=36500)
    preserve_weekly_count: int | None = Field(None, ge=0, le=520)
    preserve_monthly_count: int | None = Field(None, ge=0, le=1200)
    retention_trigger: RetentionTrigger = "after_successful_backup"
    retention_local_time: time | None = None
    retention_weekday: int | None = Field(None, ge=1, le=7)

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
        if self.retention_trigger == "custom_schedule" and self.retention_local_time is None:
            raise ValueError("backup_retention_custom_time_required")
        if self.retention_trigger != "custom_schedule" and (
            self.retention_local_time is not None or self.retention_weekday is not None
        ):
            raise ValueError("backup_retention_custom_fields_invalid")
        return self


class BackupScheduleRead(BackupScheduleWrite):
    id: int
    timezone_name: str
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime
    destination_identity: str | None = None
    destination_filesystem: str | None = None
    destination_status: Literal["unknown", "available", "unavailable"] = "unknown"
    destination_last_seen_at: datetime | None = None
    destination_total_bytes: int | None = None
    destination_free_bytes: int | None = None
    plan_revision: int = 1
    last_reconciled_revision: int = 0
    sync_status: Literal["pending", "synced", "error", "disabled", "destination_unavailable"] = "pending"
    last_sync_at: datetime | None = None
    last_sync_error_code: str | None = None
    last_destination_check_at: datetime | None = None
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


class ManualBackupPreflightRequest(BaseModel):
    scope: BackupScope
    destination: str = Field(min_length=3, max_length=500)


class ManualBackupPreflight(BaseModel):
    normalized_destination: str
    available: bool
    writable: bool
    total_bytes: int
    free_bytes: int
    estimated_required_bytes: int | None = None
    predicted_free_bytes: int | None = None
    reserve_required_bytes: int = 0
    retention_impact: str = "not_applicable"
    token: str
    expires_at: datetime
    storage_location_id: str | None = None
    destination_display: str | None = None


class ManualBackupStartRequest(BaseModel):
    scope: BackupScope
    destination: str = Field(min_length=3, max_length=500)
    preflight_token: str = Field(min_length=32, max_length=2048)
    confirmed: bool


class HostStorageLocation(BaseModel):
    location_id: str
    display_label: str
    path_type: DestinationType
    available: bool
    writable: bool
    total_bytes: int
    free_bytes: int
    location_token: str
    expires_at: datetime


class HostStorageRegisterRequest(BaseModel):
    host_path: str = Field(min_length=3, max_length=500)


class HostStorageBrowseRequest(BaseModel):
    location_token: str = Field(min_length=32, max_length=4096)
    relative_path: str = Field(default="", max_length=500)


class HostStorageDirectory(BaseModel):
    name: str
    relative_path: str


class HostStorageBrowseResult(BaseModel):
    location_id: str
    relative_path: str
    display_path: str
    directories: list[HostStorageDirectory]


class ManualBackupV3PreflightRequest(BaseModel):
    scope: BackupScope
    location_token: str = Field(min_length=32, max_length=4096)
    relative_path: str = Field(default="", max_length=500)


class ManualBackupV3StartRequest(BaseModel):
    scope: BackupScope
    preflight_token: str = Field(min_length=32, max_length=4096)
    confirmed: bool


class BackupReconcileResult(BaseModel):
    processed: int
    succeeded: int
    failed: int
    superseded: int


class RetentionCandidate(BaseModel):
    backup_id: str
    created_at: datetime
    total_bytes: int
    protected: bool
    eligible: bool
    reason: str | None = None


class RetentionPreview(BaseModel):
    plan_id: int
    volume_identity: str | None = None
    current_total_bytes: int
    current_free_bytes: int
    required_free_bytes: int
    cleanup_target_free_bytes: int | None = None
    predicted_backup_bytes: int
    eligible_backups: list[RetentionCandidate]
    ineligible_backups: list[RetentionCandidate]
    proposed_deletions: list[RetentionCandidate]
    predicted_reclaimed_bytes: int
    predicted_final_free_bytes: int
    blocked_reason: str | None = None


class ManagedBackupRead(BaseModel):
    id: int
    backup_id: str
    plan_id: int | None
    destination_root: str
    checkpoint_path: str
    manifest_schema: str
    scope: str
    app_version: str
    source_head: str
    db_revision: str
    artifact_count: int
    total_bytes: int
    integrity_status: str
    protected: bool
    lifecycle: str
    error_code: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ManagedBackupDeleteRequest(BaseModel):
    confirmed: bool
    confirmation: str = Field(max_length=32)


class LegacyBackupCandidate(BaseModel):
    candidate_id: str
    checkpoint_path: str
    destination_root: str
    created_at: datetime | None = None
    scope: str | None = None
    app_version: str | None = None
    total_bytes: int = 0
    manifest_schema: str | None = None
    verified: bool
    integrity_status: Literal["verified", "unverified"]
    adoptable: bool
    already_managed: bool
    reason: str | None = None
    adoption_token: str | None = None
    classification: Literal[
        "ALREADY_MANAGED",
        "VERIFIED_ADOPTABLE",
        "NEEDS_VERIFICATION",
        "INVALID",
        "UNAVAILABLE",
        "VERIFICATION_FAILED",
    ]
    retryable: bool = False
    diagnostic_code: str | None = None


class LegacyBackupAdoptRequest(BaseModel):
    adoption_token: str = Field(min_length=32, max_length=4096)
    plan_id: int | None = Field(None, ge=1)
    confirmed: bool


class LegacyBackupAdoptResult(BaseModel):
    managed_backup: ManagedBackupRead
    already_managed: bool


class LegacyVerificationStartRequest(BaseModel):
    adoption_token: str = Field(min_length=32, max_length=4096)
    plan_id: int | None = Field(None, ge=1)
    confirmed: bool


class LegacyVerificationJob(BaseModel):
    job_id: str
    job_token: str
    state: Literal[
        "QUEUED",
        "VERIFYING_MANIFEST",
        "VERIFYING_FILES",
        "VERIFYING_CHECKSUMS",
        "READY_TO_ADOPT",
        "ADOPTING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]
    files_checked: int = 0
    files_total: int | None = None
    bytes_checked: int = 0
    bytes_total: int | None = None
    error_code: str | None = None
    retryable: bool = False
    managed_backup: ManagedBackupRead | None = None


class LegacyVerificationStatusRequest(BaseModel):
    job_token: str = Field(min_length=32, max_length=8192)


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
