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
        self.reconciled = []

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
        }, {
            "checkpoint_path": r"C:\ai-lab-core-backups\verified-fixture",
            "created_at": "2026-08-21T14:30:00Z", "scope": "full",
            "app_version": "1.0.2+25", "source_head": "b" * 40,
            "db_revision": "followup_admin_backup_restore_ui_20260821",
            "total_bytes": 5678, "verified": True, "artifact_count": 7,
            "components": ["postgres.dump", "document-storage.tar.gz", "release-stable.tar.gz", "qdrant.snapshot", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz"],
            "database_eligible": True, "full_eligible": True,
            "compatibility": "compatible", "error_code": None,
        }]}

    def preview_schedules(self, schedules):
        return {"items": [{
            "task_name": f"NEXT Stabil - Backup - {item['id']}",
            "sync_status": "synced",
            "actual": {
                "enabled": item["enabled"], "next_run_at": "2026-08-22T03:00:00+02:00",
                "last_run_at": None, "last_result": 0,
            } if item["enabled"] else None,
        } for item in schedules]}

    def reconcile_schedules(self, schedules):
        self.reconciled.append(schedules)
        return {"items": [{"sync_status": "synced"} for _ in schedules], "prune": {"removed": [], "unmanaged": []}}


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
    from app.models.backup_operation import (
        BackupDeletionEvent,
        BackupPlanSyncEvent,
        BackupRun,
        BackupSchedule,
        ManagedBackup,
        RestoreRun,
    )
    from app.models.user import User
    from app.models.role import Role
    from app.schemas.admin_backup import BackupScheduleWrite
    from app.services.backup_restore_service import BackupRestoreService

    with Session(engine) as db:
        assert_isolated_database(db, name)
        # A production-copy fixture may contain legitimate operational history.
        # Normalize only the disposable isolated database before bounded tests.
        db.query(BackupDeletionEvent).delete(synchronize_session=False)
        db.query(ManagedBackup).delete(synchronize_session=False)
        db.query(BackupPlanSyncEvent).delete(synchronize_session=False)
        db.query(RestoreRun).delete(synchronize_session=False)
        db.query(BackupRun).delete(synchronize_session=False)
        db.query(BackupSchedule).delete(synchronize_session=False)
        db.commit()
        actor = (
            db.query(User)
            .join(User.role)
            .filter(
                User.is_active.is_(True),
                User.username == "backup-isolated-admin",
                User.role.has(name="Administrator"),
            )
            .order_by(User.id)
            .first()
        )
        if actor is None:
            password_source = db.query(User).filter(User.is_active.is_(True)).order_by(User.id).first()
            admin_role = db.query(Role).filter(Role.name == "Administrator").one_or_none()
            if admin_role is None:
                admin_role = Role(name="Administrator", description="Synthetic isolated administrator role")
                db.add(admin_role)
                db.flush()
            actor = db.query(User).filter(User.username == "backup-isolated-admin").one_or_none()
            if actor is None:
                actor = User(
                    username="backup-isolated-admin",
                    email="backup-isolated-admin@example.invalid",
                    password_hash=password_source.password_hash,
                    is_active=True,
                    role_id=admin_role.id,
                )
                db.add(actor)
            else:
                actor.role_id = admin_role.id
            db.commit()
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
        winter = service.next_run(daily, datetime(2026, 1, 10, 0, tzinfo=timezone.utc))
        summer = service.next_run(daily, datetime(2026, 7, 10, 0, tzinfo=timezone.utc))
        require(winter.hour == 2 and summer.hour == 1, "Warsaw DST UTC mapping drifted")
        monthly = daily.model_copy(
            update={"name": "monthly", "cadence": "monthly", "month_day": 28}
        )
        monthly_next = service.next_run(
            monthly, datetime(2026, 1, 29, 0, tzinfo=timezone.utc)
        )
        require(
            monthly_next.month == 2
            and monthly_next.day == 28
            and monthly_next.hour == 2,
            "Monthly Windows-safe occurrence drifted",
        )
        try:
            BackupScheduleWrite(
                name="monthly-unsafe",
                enabled=True,
                scope="database",
                destination=r"C:\ai-lab-core-backups",
                cadence="monthly",
                local_time=time(3),
                month_day=29,
            )
        except Exception:
            pass
        else:
            raise AssertionError("Windows-inexact monthly day accepted")
        try:
            BackupScheduleWrite(name="dst", enabled=True, scope="database", destination=r"C:\ai-lab-core-backups", cadence="daily", local_time=time(2, 30))
        except Exception as error:
            require("backup_schedule_dst_unsafe_time" in str(error), "DST-unsafe time returned wrong validation")
        else:
            raise AssertionError("DST-unsafe schedule time accepted")
        for index in range(10):
            payload = daily.model_copy(update={"name": f"schedule-{index}"})
            service.create_schedule(payload, actor)
        expect_code(lambda: service.create_schedule(daily.model_copy(update={"name": "eleventh"}), actor), "backup_schedule_limit_reached")
        db.rollback()

        synced = service.create_schedule(daily.model_copy(update={"name": "synced", "enabled": True}), actor)
        service.reconcile_pending()
        require(fake.reconciled[-1][0]["id"] == synced.id, "schedule reconciliation lost canonical ID")
        view = service.schedule_views()[0]
        require(view["sync_status"] == "synced" and view["host_enabled"], "host schedule status not projected")
        db.rollback()

        run = service.start_backup(scope="database", destination=r"C:\ai-lab-core-backups", actor=actor)
        require(run.status == "running" and len(fake.started) == 1, "manual backup not delegated")
        expect_code(
            lambda: service.start_backup(
                scope="database",
                destination=r"C:\ai-lab-core-backups",
                actor=actor,
            ),
            "backup_already_running",
        )
        require(len(fake.started) == 1, "operation lock delegated a duplicate backup")
        service.refresh_run(run)
        require(run.status == "completed" and run.verified and run.artifact_count == 7, "backup completion not recorded")
        db.rollback()

        scheduled_item = service.create_schedule(
            daily.model_copy(update={"name": "scheduled-run", "scope": "database", "enabled": True}), actor
        )
        scheduled = service.start_backup(scope="database", destination=r"C:\ai-lab-core-backups", actor=actor, trigger="scheduled", schedule_id=scheduled_item.id)
        require(fake.started[-1]["trigger"] == "scheduled" and fake.started[-1]["schedule_id"] == scheduled_item.id, "scheduled identity not delegated")
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
        verified_full = service.preview(
            r"C:\ai-lab-core-backups\verified-fixture",
            "full",
            "followup_admin_backup_restore_ui_20260821",
        )
        require(
            verified_full["eligible"] and verified_full["error_code"] is None,
            "Verified Full restore candidate remained blocked",
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
        db.query(BackupDeletionEvent).delete(synchronize_session=False)
        db.query(ManagedBackup).delete(synchronize_session=False)
        db.query(BackupPlanSyncEvent).delete(synchronize_session=False)
        db.query(RestoreRun).delete(synchronize_session=False)
        db.query(BackupRun).delete(synchronize_session=False)
        db.query(BackupSchedule).delete(synchronize_session=False)
        db.commit()
        require(db.query(BackupRun).count() == 0 and db.query(BackupSchedule).count() == 0, "test cleanup leaked metadata")

        from fastapi.testclient import TestClient
        from app.core.security import create_access_token
        from app.main import app

        regular = db.query(User).join(User.role).filter(User.is_active.is_(True), User.role.has(name="User")).first()
        if regular is None:
            regular_role = db.query(Role).filter(Role.name == "User").one_or_none()
            if regular_role is None:
                regular_role = Role(name="User", description="Synthetic isolated test role")
                db.add(regular_role)
                db.flush()
            regular = db.query(User).filter(User.username == "backup-isolated-user").one_or_none()
            if regular is None:
                regular = User(
                    username="backup-isolated-user",
                    email="backup-isolated-user@example.invalid",
                    password_hash=actor.password_hash,
                    is_active=True,
                    role_id=regular_role.id,
                )
                db.add(regular)
            else:
                regular.role_id = regular_role.id
            db.commit()
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
