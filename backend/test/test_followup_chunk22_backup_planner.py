from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, time, timedelta, timezone
import ntpath
from time import perf_counter
from sqlalchemy import event as sqlalchemy_event

from app.database.session import SessionLocal
from app.models.backup_operation import BackupDeletionEvent, BackupPlanSyncEvent, BackupSchedule, ManagedBackup
from app.models.user import User
from app.schemas.admin_backup import BackupScheduleWrite
from app.services.backup_restore_service import BackupRestoreService, BackupRestoreValidation
from app.services import backup_plan_reconciler
from test.support.database_safety import assert_isolated_database, require_test_database_environment


TEST_DATABASE_NAME = require_test_database_environment()


class FakeSupervisor:
    def __init__(self) -> None:
        self.reconciled: list[list[dict]] = []
        self.fail = False
        self.fail_preview = False
        self.deleted: list[dict] = []
        self.previewed: list[list[dict]] = []
        self.inspect_calls = 0
        self.total_by_volume = {f"{letter}:\\": 1000 for letter in "DEFG"}
        self.free_by_volume = {f"{letter}:\\": 60 for letter in "DEFG"}

    def reconcile_schedules(self, schedules):
        if self.fail:
            raise RuntimeError("synthetic_task_failure")
        self.reconciled.append(schedules)
        return {"items": [], "prune": {"removed": [], "unmanaged": []}}

    def preview_schedules(self, schedules):
        if self.fail_preview:
            raise RuntimeError("synthetic_host_preview_failure")
        self.previewed.append(schedules)
        return {"items": []}

    def inspect_storage(self, destinations):
        self.inspect_calls += 1
        items = []
        for destination in destinations:
            identity = ntpath.splitdrive(destination)[0].upper() + "\\"
            items.append({
                "normalized_destination": destination,
                "available": True,
                "writable": True,
                "total_bytes": self.total_by_volume[identity],
                "free_bytes": self.free_by_volume[identity],
                "destination_identity": identity,
            })
        return {"items": items}

    def destination_preflight(self, destination):
        return {"available": True, "writable": True, "total_bytes": 1000, "free_bytes": 50}

    def delete_managed_backup(self, payload):
        self.deleted.append(payload)
        identity = ntpath.splitdrive(payload["destination_root"])[0].upper() + "\\"
        self.free_by_volume[identity] += 60
        return {"actual_reclaimed_bytes": 60}


def expect_code(call, code: str) -> None:
    try:
        call()
    except Exception as error:
        assert str(error) == code, (str(error), code)
    else:
        raise AssertionError(f"expected {code}")


async def assert_reconciler_wake_contract() -> None:
    original_once = backup_plan_reconciler._reconcile_once
    original_interval = backup_plan_reconciler.RECONCILE_INTERVAL_SECONDS
    calls: list[float] = []
    first = asyncio.Event()
    second = asyncio.Event()

    def record_cycle() -> None:
        calls.append(perf_counter())
        (first if len(calls) == 1 else second).set()

    backup_plan_reconciler._reconcile_once = record_cycle
    backup_plan_reconciler._wake_event.clear()
    task = asyncio.create_task(backup_plan_reconciler._run())
    try:
        await asyncio.wait_for(first.wait(), timeout=1)
        started = perf_counter()
        backup_plan_reconciler.wake_backup_plan_reconciler()
        await asyncio.wait_for(second.wait(), timeout=1)
        assert calls[1] - started < 1
    finally:
        task.cancel()
        backup_plan_reconciler._wake_event.set()
        with suppress(asyncio.CancelledError):
            await task
        backup_plan_reconciler._wake_event.clear()

    calls.clear()
    first.clear()
    second.clear()
    backup_plan_reconciler.RECONCILE_INTERVAL_SECONDS = 0.05
    task = asyncio.create_task(backup_plan_reconciler._run())
    try:
        await asyncio.wait_for(second.wait(), timeout=1)
        assert len(calls) >= 2
    finally:
        task.cancel()
        backup_plan_reconciler._wake_event.set()
        with suppress(asyncio.CancelledError):
            await task
        backup_plan_reconciler._wake_event.clear()
        backup_plan_reconciler._reconcile_once = original_once
        backup_plan_reconciler.RECONCILE_INTERVAL_SECONDS = original_interval


def payload(
    name: str,
    destination: str = r"D:\NEXT-Fixture",
    *,
    auto_delete: bool = False,
    keep_days: int | None = None,
) -> BackupScheduleWrite:
    return BackupScheduleWrite(
        name=name, enabled=True, scope="database", destination=destination,
        destination_type="local_path", cadence="daily", local_time=time(3, 0),
        auto_delete=auto_delete, minimum_free_percent=10, minimum_backups_to_keep=3,
        keep_days=keep_days,
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
        service.schedule_views()
        assert fake.previewed == []
        fake.fail_preview = True
        service.schedule_views()
        expect_code(service.schedule_host_status, "synthetic_host_preview_failure")
        fake.fail_preview = False
        statements: list[str] = []

        def record_statement(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        sqlalchemy_event.listen(db.bind, "before_cursor_execute", record_statement)
        try:
            service.schedule_views()
        finally:
            sqlalchemy_event.remove(db.bind, "before_cursor_execute", record_statement)
        assert 1 <= len(statements) <= 2, statements
        backup_plan_reconciler._wake_event.clear()
        backup_plan_reconciler.wake_backup_plan_reconciler()
        assert backup_plan_reconciler._wake_event.is_set()
        backup_plan_reconciler._wake_event.clear()
        asyncio.run(assert_reconciler_wake_contract())

        plan = service.create_schedule(payload("Planner fixture"), actor)
        db.commit(); db.refresh(plan)
        statements.clear()
        sqlalchemy_event.listen(db.bind, "before_cursor_execute", record_statement)
        try:
            service.schedule_views()
        finally:
            sqlalchemy_event.remove(db.bind, "before_cursor_execute", record_statement)
        assert len(statements) == 2, statements
        assert plan.sync_status == "pending" and plan.plan_revision == 1
        assert db.query(BackupPlanSyncEvent).filter_by(plan_id=plan.id, status="pending").count() == 1
        assert fake.reconciled == []
        result = service.reconcile_pending()
        db.refresh(plan)
        assert result["succeeded"] == 1 and plan.sync_status == "synced"
        assert plan.last_reconciled_revision == 1
        assert fake.reconciled[-1][0]["plan_revision"] == 1

        second = service.create_schedule(payload("Batch fixture", r"F:\Batch"), actor)
        service.update_schedule(plan, payload("Planner fixture", r"E:\NEXT-Fixture"), actor)
        db.commit()
        before_batches = len(fake.reconciled)
        result = service.reconcile_pending()
        db.refresh(plan); db.refresh(second)
        assert result["succeeded"] == 2
        assert len(fake.reconciled) == before_batches + 1
        assert plan.sync_status == "synced" and second.sync_status == "synced"

        service.update_schedule(plan, payload("Planner fixture", r"F:\NEXT-Fixture"), actor)
        service.update_schedule(plan, payload("Planner fixture", r"E:\NEXT-Fixture-2"), actor)
        db.commit(); db.refresh(plan)
        assert plan.plan_revision == 4
        result = service.reconcile_pending()
        db.refresh(plan)
        assert result["superseded"] >= 1 and plan.last_reconciled_revision == 4

        service.update_schedule(plan, payload("Planner fixture", r"G:\NEXT-Fixture"), actor)
        db.commit(); fake.fail = True
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["failed"] == 1 and plan.sync_status == "error"
        fake.fail = False
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["succeeded"] == 1 and plan.sync_status == "synced"

        plan.auto_delete = True
        plan.keep_days = 0
        db.commit(); db.refresh(plan)

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
        assert preview["cleanup_target_free_bytes"] == 120
        assert [item["backup_id"] for item in preview["proposed_deletions"]] == ["fixture-1"]
        assert preview["blocked_reason"] is None
        protected = db.query(ManagedBackup).filter_by(backup_id="fixture-0").one()
        expect_code(
            lambda: BackupRestoreService(db, fake).delete_managed_backup(protected, actor),
            "backup_retention_delete_approval_required",
        )
        expect_code(lambda: service.delete_managed_backup(protected, actor), "managed_backup_not_eligible")
        completed = service.enforce_drive_retention(plan, actor)
        eligible = db.query(ManagedBackup).filter_by(backup_id="fixture-1").one()
        assert completed["current_free_bytes"] == 120
        assert eligible.lifecycle == "deleted" and len(fake.deleted) == 1
        assert fake.inspect_calls >= 2

        service.delete_schedule(plan)
        service.delete_schedule(second)
        db.commit(); db.refresh(plan)
        assert plan.deleted_at is not None
        fake.fail = True
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["failed"] == 2 and plan.sync_status == "error"
        fake.fail = False
        result = service.reconcile_pending(); db.refresh(plan)
        assert result["succeeded"] == 2 and plan.sync_status == "disabled"
        db.refresh(second)
        assert second.sync_status == "disabled"
        assert all(item["id"] != plan.id for item in fake.reconciled[-1])
        assert db.query(ManagedBackup).filter_by(plan_id=plan.id).count() == 5
        print("BACKUP_PLANNER_ISOLATED_TESTS=PASS")


if __name__ == "__main__":
    main()
