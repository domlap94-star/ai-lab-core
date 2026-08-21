from __future__ import annotations

from datetime import datetime, time, timezone
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from test.support.database_safety import assert_isolated_database, require_test_database_environment


def database_url(name: str) -> str:
    return (
        "postgresql+psycopg://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@"
        f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{name}"
    )


class FakeSupervisor:
    def __init__(self) -> None:
        self.started = []

    def start_backup(self, payload):
        self.started.append(payload)
        return {"operation_id": "00000000-0000-0000-0000-000000000001", "stage": "validating"}

    def backup_status(self, operation_id):
        return {
            "status": "completed", "stage": "completed", "verified": True,
            "checkpoint_path": r"C:\ai-lab-core-backups\fixture",
            "manifest_path": r"C:\ai-lab-core-backups\fixture\backup-manifest.json",
            "artifact_count": 7, "total_bytes": 1234, "error_code": None,
        }

    def discover(self, destinations):
        return {"items": [{
            "checkpoint_path": r"C:\ai-lab-core-backups\fixture",
            "created_at": "2026-08-21T10:00:00Z", "scope": "full",
            "app_version": "1.0.2+25", "source_head": "a" * 40,
            "db_revision": "followup_admin_backup_restore_ui_20260821",
            "total_bytes": 1234, "verified": True, "artifact_count": 7,
            "components": ["postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz", "qdrant.snapshot", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz"],
            "database_eligible": True, "full_eligible": False,
            "compatibility": "compatible",
            "error_code": "qdrant_restore_verification_required",
        }]}


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def expect_code(call, code: str) -> None:
    try:
        call()
    except Exception as error:
        require(str(error) == code, f"expected {code}, got {error}")
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = require_test_database_environment()
    engine = create_engine(database_url(name))
    from app.models.backup_operation import BackupRun, BackupSchedule
    from app.models.user import User
    from app.schemas.admin_backup import BackupScheduleWrite
    from app.services.backup_restore_service import BackupRestoreService

    with Session(engine) as db:
        assert_isolated_database(db, name)
        actor = db.query(User).filter(User.is_active.is_(True)).order_by(User.id).first()
        require(actor is not None, "isolated fixture has no active user")
        fake = FakeSupervisor()
        service = BackupRestoreService(db, fake)

        require(service.validate_destination(r"C:\ai-lab-core-backups") == r"C:\ai-lab-core-backups", "safe destination rejected")
        for unsafe in (r"C:\ai-lab-core", r"C:\ai-lab-core\data\documents", r"..\backup", r"C:\safe\..\ai-lab-core"):
            expected = "backup_destination_active_path" if "ai-lab-core" in unsafe and ".." not in unsafe else "backup_destination_invalid"
            expect_code(lambda value=unsafe: service.validate_destination(value), expected)

        daily = BackupScheduleWrite(name="daily", enabled=False, scope="full", destination=r"C:\ai-lab-core-backups", cadence="daily", local_time=time(3))
        before_dst = datetime(2026, 3, 28, 22, tzinfo=timezone.utc)
        next_run = service.next_run(daily, before_dst)
        require(next_run.astimezone().tzinfo is not None, "next run lost timezone")
        for index in range(10):
            payload = daily.model_copy(update={"name": f"schedule-{index}"})
            service.create_schedule(payload, actor)
        expect_code(lambda: service.create_schedule(daily.model_copy(update={"name": "eleventh"}), actor), "backup_schedule_limit_reached")
        db.rollback()

        run = service.start_backup(scope="database", destination=r"C:\ai-lab-core-backups", actor=actor)
        require(run.status == "running" and len(fake.started) == 1, "manual backup not delegated")
        service.refresh_run(run)
        require(run.status == "completed" and run.verified and run.artifact_count == 7, "backup completion not recorded")
        db.rollback()

        full_preview = service.preview(
            r"C:\ai-lab-core-backups\fixture",
            "full",
            "followup_admin_backup_restore_ui_20260821",
        )
        require(
            not full_preview["eligible"]
            and full_preview["error_code"] == "qdrant_restore_verification_required",
            "Full restore did not fail closed on Qdrant proof",
        )
        preview = service.preview(
            r"C:\ai-lab-core-backups\fixture",
            "database",
            "followup_admin_backup_restore_ui_20260821",
        )
        require(
            preview["eligible"] and preview["pre_restore_backup_required"],
            "Database restore preview unsafe",
        )
        expect_code(
            lambda: service.request_restore(checkpoint_path=preview["checkpoint_path"], mode="database", acknowledged=True, confirmation="WRONG", actor=actor, current_revision=preview["current_db_revision"]),
            "restore_confirmation_required",
        )
        expect_code(
            lambda: service.request_restore(checkpoint_path=preview["checkpoint_path"], mode="database", acknowledged=True, confirmation="PRZYWRÓĆ", actor=actor, current_revision=preview["current_db_revision"]),
            "production_restore_approval_required",
        )
        require(db.query(BackupRun).count() == 0 and db.query(BackupSchedule).count() == 0, "test rollback leaked metadata")

        from fastapi.testclient import TestClient
        from app.core.security import create_access_token
        from app.main import app

        regular = db.query(User).join(User.role).filter(User.is_active.is_(True), User.role.has(name="User")).first()
        require(regular is not None, "isolated fixture has no regular user")
        admin_token = create_access_token({"sub": actor.username, "auth_version": actor.auth_version})
        user_token = create_access_token({"sub": regular.username, "auth_version": regular.auth_version})
        http = TestClient(app)
        require(http.get("/api/v1/admin/backups/schedules").status_code == 401, "unauthenticated backup API allowed")
        require(
            http.get("/api/v1/admin/backups/schedules", headers={"Authorization": f"Bearer {user_token}"}).status_code == 403,
            "normal user reached backup API",
        )
        require(
            http.get("/api/v1/admin/backups/schedules", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200,
            "Administrator could not read backup schedules",
        )

    engine.dispose()
    print("FOLLOWUP_CHUNK15_BACKUP_RESTORE_SERVICE=PASS")
    print("production_restore_gate=PASS")
    print("schedule_limit=PASS")
    print("destination_guard=PASS")
    print("admin_authorization=PASS")


if __name__ == "__main__":
    main()
