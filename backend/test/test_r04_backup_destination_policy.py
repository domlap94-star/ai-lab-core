from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.admin_backup import BackupRunRequest
from app.services.backup_restore_service import (
    BackupRestoreService,
    BackupRestoreValidation,
)


def test_backup_destination_rejects_system_and_active_data_volumes() -> None:
    assert BackupRestoreService.validate_destination(r"F:\NEXT-Backups") == r"F:\NEXT-Backups"
    for destination in (r"C:\Backups", r"D:\Backups"):
        with pytest.raises(
            BackupRestoreValidation,
            match="backup_destination_system_or_data_volume_forbidden",
        ):
            BackupRestoreService.validate_destination(destination)


def test_legacy_manual_request_has_no_implicit_destination() -> None:
    with pytest.raises(ValidationError):
        BackupRunRequest(scope="database", confirmed=True)
