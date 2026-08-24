from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from app.database.session import SessionLocal
from app.models.backup_operation import BackupDeletionEvent, BackupPlanSyncEvent, BackupSchedule, ManagedBackup
from app.models.user import User
from app.schemas.admin_backup import BackupScheduleWrite
from app.services.backup_restore_service import BackupRestoreService, BackupRestoreValidation
from test.support.database_safety import assert_isolated_database, require_test_database_environment


TEST_DATABASE_NAME = require_test_database_environment()


class FakeSupervisor:
    def __init__(self) -> None:
        self.reconciled: list[list[dict]] = []
        self.fail = False
        self.deleted: list[dict] = []

    def reconcile_schedules(self, schedules):
        if self.fail:
            raise RuntimeError("synthetic_task_failure")
        self.reconciled.append(schedules)
        return {"items": [], "prune": {"removed": [], "unmanaged": []}}

    def preview_schedules(self, schedules):
        return {"items": []}

    def destination_preflight(self, destination):
        return {"available": True, "writable": True, "total_bytes": 1000, "free_bytes": 50}

    def delete_managed_backup(self, payload):
        self.deleted.append(payload)
        return {"actual_reclaimed_bytes": 60}


def expect_code(call, code: str) -> None:
    try:
        call()
    except Exception as error:
        assert str(error) == code, (str(error), code)
    else:
        raise AssertionError(f"expected {code}")


def payload(name: str, destination: str = r"D:\NEXT-Fixture") -> BackupScheduleWrite:
    return BackupScheduleWrite(
        name=name, enabled=True, scope="database", destination=destination,
        destination_type="local_path", cadence="daily", local_time=time(3, 0),
        auto_delete=False, minimum_free_percent=10, minimum_backups_to_keep=3,
        retention_trigger="after_successful_backup",
    )


def main() -> None:
    fake = FakeSupervisor()
    with SessionLocal() as db:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        db.query(BackupDeletionEvent).delete()
        db.query(ManagedBackup).delete()
        db.query(BackupPlanSyncEvent).delete()
        db.query(BackupSchedule).filter(BackupSchedule.id.notin_((101, 102))).delete()
        for existing in db.query(BackupSchedule).all():
            existing.last_reconciled_revision = existing.plan_revision
            existing.sync_status = "synced" if existing.enabled else "disabled"
        db.commit()
        actor = db.get(User, 900001)
        assert actor is not None
        service = BackupRestoreService(db, fake, allow_retention_delete=True)

        rolled_back = service.create_schedule(payload("Rollback fixture"), actor)
        rolled_back_id = rolled_back.id
        db.rollback()
        assert db.get(BackupSchedule, rolled_back_id) is None
        assert db.query(BackupPlanSyncEvent).filter_by(plan_id=rolled_back_id).count() == 0
        assert fake.reconciled == []

        plan = service.create_schedule(payload("Planner fixture"), actor)
        db.commit(); db.refresh(plan)
        assert plan.sync_status == "pending" and plan.plan_revision == 1
        assert db.query(BackupPlanSyncEvent).filter_by(plan_id=plan.id, status="pending").count() == 1
        assert fake.reconciled == []
        result = service.reconcile_pending()
        db.refresh(plan)
        assert result["succeeded"] == 1 and plan.sync_status == "synced"
        assert plan.last_reconciled_revision == 1
        assert fake.reconciled[-1][0]["plan_revision"] == 1

        service.update_schedule(plan, payload("Planner fixture", r"E:\NEXT-Fixture"), actor)
        service.update_schedule(plan, payload("Planner fixture", r"F:\NEXT-Fixture"), actor)
        db.commit(); db.refresh(plan)
        assert plan.plan_revision == 3
        result = service.reconcile_pending()
        db.refresh(plan)
        assert result["superseded"] >= 1 and plan.last_reconciled_revision == 3

        service.update_schedule(plan, payload("Planner fixture", r"G:\NEXT-Fixture"), actor)
        db.commit(); fake.fail = True
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["failed"] == 1 and plan.sync_status == "error"
        fake.fail = False
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["succeeded"] == 1 and plan.sync_status == "synced"

        token, expires, host = service.issue_preflight_token(user_id=actor.id, scope="database", destination=r"D:\Manual")
        assert expires > datetime.now(timezone.utc) and host["writable"]
        assert service.verify_preflight_token(token=token, user_id=actor.id, scope="database", destination=r"D:\Manual") == r"D:\Manual"
        expect_code(lambda: service.verify_preflight_token(token=token, user_id=actor.id, scope="database", destination=r"D:\Changed"), "backup_preflight_token_binding_invalid")
        assert service.validate_destination(r"\\server\share\NEXT") == r"\\server\share\NEXT"
        expect_code(lambda: service.validate_destination(r"\\?\C:\unsafe"), "backup_destination_invalid")
        expect_code(lambda: service.validate_destination("D:\\"), "backup_destination_root_forbidden")

        now = datetime.now(timezone.utc)
        for index, (size, protected) in enumerate(((20, True), (60, False), (70, False), (80, False), (90, False))):
            db.add(ManagedBackup(
                backup_id=f"fixture-{index}", plan_id=plan.id,
                destination_root=plan.destination, checkpoint_path=rf"{plan.destination}\fixture-{index}",
                manifest_path=rf"{plan.destination}\fixture-{index}\backup-manifest.json",
                manifest_schema="NEXT_STABIL_BACKUP_V2", manifest_sha256=f"{index:064x}",
                scope="database", app_version="1.0.2+29", source_head="a" * 40,
                db_revision="followup_backup_planner_retention_20260824", artifact_count=1,
                total_bytes=size, integrity_status="verified", protected=protected,
                lifecycle="available", created_at=now - timedelta(days=10 - index),
            ))
        db.commit()
        preview = service.retention_preview(plan)
        assert preview["required_free_bytes"] == 100
        assert [item["backup_id"] for item in preview["proposed_deletions"]] == ["fixture-1"]
        assert preview["blocked_reason"] is None
        protected = db.query(ManagedBackup).filter_by(backup_id="fixture-0").one()
        expect_code(
            lambda: BackupRestoreService(db, fake).delete_managed_backup(protected, actor),
            "backup_retention_delete_approval_required",
        )
        expect_code(lambda: service.delete_managed_backup(protected, actor), "managed_backup_not_eligible")
        eligible = db.query(ManagedBackup).filter_by(backup_id="fixture-1").one()
        event = service.delete_managed_backup(eligible, actor)
        db.commit()
        assert event.status == "succeeded" and event.actual_reclaimed_bytes == 60
        assert eligible.lifecycle == "deleted" and len(fake.deleted) == 1

        service.delete_schedule(plan)
        db.commit(); db.refresh(plan)
        assert plan.deleted_at is not None
        fake.fail = True
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["failed"] == 1 and plan.sync_status == "error"
        fake.fail = False
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["succeeded"] == 1 and plan.sync_status == "disabled"
        assert all(item["id"] != plan.id for item in fake.reconciled[-1])
        assert db.query(ManagedBackup).filter_by(plan_id=plan.id).count() == 5
        print("BACKUP_PLANNER_ISOLATED_TESTS=PASS")


if __name__ == "__main__":
    main()
