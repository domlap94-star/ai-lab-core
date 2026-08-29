from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import ntpath

from app.database.session import SessionLocal
from app.models.backup_operation import (
    BackupDeletionEvent,
    BackupPlanSyncEvent,
    BackupRun,
    BackupSchedule,
    ManagedBackup,
    RestoreRun,
)
from app.models.user import User
from app.services.backup_restore_service import BackupRestoreService
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()
PREFIX = "retention-volume-fixture-"


class FakeStorageSupervisor:
    def __init__(self) -> None:
        self.total = {"E:\\": 1000, "F:\\": 1000}
        self.free = {"E:\\": 200, "F:\\": 200}
        self.inspect_calls = 0
        self.deleted: list[dict] = []
        self.fail_delete = False

    def inspect_storage(self, destinations):
        self.inspect_calls += 1
        return {
            "items": [
                {
                    "normalized_destination": destination,
                    "available": True,
                    "writable": True,
                    "total_bytes": self.total[self.identity(destination)],
                    "free_bytes": self.free[self.identity(destination)],
                    "destination_identity": self.identity(destination),
                }
                for destination in destinations
            ]
        }

    def delete_managed_backup(self, payload):
        if self.fail_delete:
            raise RuntimeError("synthetic_delete_failure")
        self.deleted.append(payload)
        identity = self.identity(payload["destination_root"])
        self.free[identity] += 80
        return {"actual_reclaimed_bytes": 80}

    @staticmethod
    def identity(destination: str) -> str:
        return ntpath.splitdrive(destination)[0].upper() + "\\"


def add_plan(
    db,
    actor: User,
    suffix: str,
    destination: str,
    keep_days: int,
    *,
    auto_delete: bool = True,
    minimum_keep: int = 1,
) -> BackupSchedule:
    item = BackupSchedule(
        name=PREFIX + suffix,
        enabled=True,
        scope="database",
        destination=destination,
        destination_type="local_path",
        cadence="daily",
        local_time=time(3),
        timezone_name="Europe/Warsaw",
        next_run_at=datetime.now(timezone.utc) + timedelta(days=1),
        auto_delete=auto_delete,
        minimum_free_percent=10,
        minimum_backups_to_keep=minimum_keep,
        keep_days=keep_days,
        retention_trigger="after_successful_backup",
        plan_revision=1,
        last_reconciled_revision=1,
        sync_status="synced",
        created_by_user_id=actor.id,
        updated_by_user_id=actor.id,
    )
    db.add(item)
    db.flush()
    return item


def add_backup(
    db,
    plan: BackupSchedule | None,
    suffix: str,
    age: timedelta,
    *,
    size: int = 80,
    protected: bool = False,
    integrity: str = "verified",
    backup_run_id: int | None = None,
) -> ManagedBackup:
    root = plan.destination if plan is not None else r"F:\unassigned"
    checkpoint = root + "\\" + PREFIX + suffix
    item = ManagedBackup(
        backup_id=PREFIX + suffix,
        plan_id=plan.id if plan is not None else None,
        backup_run_id=backup_run_id,
        destination_root=root,
        checkpoint_path=checkpoint,
        manifest_path=checkpoint + "\\backup-manifest.json",
        manifest_schema="NEXT_STABIL_BACKUP_V2",
        manifest_sha256=(suffix.encode().hex() + "0" * 64)[:64],
        scope="database",
        app_version="1.0.2+29",
        source_head="a" * 40,
        db_revision="followup_assistant_pipeline_v2_20260826",
        artifact_count=1,
        total_bytes=size,
        integrity_status=integrity,
        protected=protected,
        lifecycle="available",
        created_at=datetime.now(timezone.utc) - age,
    )
    db.add(item)
    db.flush()
    return item


def reason_map(preview: dict) -> dict[str, str | None]:
    return {
        item["backup_id"]: item["reason"]
        for item in preview["ineligible_backups"]
    }


def cleanup(db) -> None:
    owned = db.query(BackupSchedule.id).filter(BackupSchedule.name.like(PREFIX + "%"))
    owned_ids = [row[0] for row in owned.all()]
    backups = db.query(ManagedBackup.id).filter(ManagedBackup.backup_id.like(PREFIX + "%"))
    backup_ids = [row[0] for row in backups.all()]
    if backup_ids:
        db.query(BackupDeletionEvent).filter(
            BackupDeletionEvent.backup_id.in_(backup_ids)
        ).delete(synchronize_session=False)
    db.query(ManagedBackup).filter(ManagedBackup.backup_id.like(PREFIX + "%")).delete(
        synchronize_session=False
    )
    if owned_ids:
        db.query(BackupPlanSyncEvent).filter(
            BackupPlanSyncEvent.plan_id.in_(owned_ids)
        ).delete(synchronize_session=False)
        db.query(BackupSchedule).filter(BackupSchedule.id.in_(owned_ids)).delete(
            synchronize_session=False
        )
    db.query(RestoreRun).filter(RestoreRun.error_code == PREFIX + "restore").delete(
        synchronize_session=False
    )
    db.query(BackupRun).filter(BackupRun.error_code == PREFIX + "run").delete(
        synchronize_session=False
    )
    db.commit()


def main() -> None:
    fake = FakeStorageSupervisor()
    with SessionLocal() as db:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        cleanup(db)
        actor = db.get(User, 900001)
        assert actor is not None
        f_daily = add_plan(db, actor, "f-daily", r"F:\daily", 14)
        f_config = add_plan(db, actor, "f-config", r"F:\config", 14)
        e_archive = add_plan(db, actor, "e-archive", r"E:\archive", 60)
        db.commit()

        add_backup(db, f_daily, "f-old-15d", timedelta(days=15))
        add_backup(db, f_daily, "f-exact-14d", timedelta(days=14, seconds=1))
        add_backup(db, f_daily, "f-young", timedelta(days=13, hours=23))
        add_backup(db, f_daily, "f-protected", timedelta(days=30), protected=True)
        add_backup(db, f_daily, "f-unverified", timedelta(days=30), integrity="unknown")
        add_backup(db, f_daily, "f-latest", timedelta(hours=1))
        add_backup(db, f_config, "f-cross-plan-oldest", timedelta(days=20))
        add_backup(db, f_config, "f-config-latest", timedelta(hours=1))
        add_backup(db, e_archive, "e-old-61d", timedelta(days=61))
        add_backup(db, e_archive, "e-exact-60d", timedelta(days=60, seconds=1))
        add_backup(db, e_archive, "e-young", timedelta(days=59, hours=23))
        add_backup(db, e_archive, "e-latest", timedelta(hours=1))
        add_backup(db, None, "legacy-unassigned", timedelta(days=365))
        db.commit()

        service = BackupRestoreService(
            db,
            fake,
            allow_retention_delete=True,
        )

        # 20% free and a predicted backup that preserves 10% require no cleanup.
        preview = service.retention_preview(f_daily)
        assert preview["proposed_deletions"] == []
        preview = service.retention_preview(f_daily, predicted_backup_bytes=90)
        assert preview["proposed_deletions"] == []

        # Crossing 10% reclaims toward 12%, globally oldest first on F:.
        preview = service.retention_preview(f_daily, predicted_backup_bytes=150)
        assert preview["required_free_bytes"] == 100
        assert preview["cleanup_target_free_bytes"] == 120
        assert [item["backup_id"] for item in preview["proposed_deletions"]] == [
            PREFIX + "f-cross-plan-oldest"
        ]
        assert preview["predicted_final_free_bytes"] == 130
        reasons = reason_map(preview)
        assert reasons[PREFIX + "f-young"] == "keep_days"
        assert reasons[PREFIX + "f-protected"] == "protected"
        assert reasons[PREFIX + "f-unverified"] == "not_verified"
        assert reasons[PREFIX + "f-latest"] == "minimum_keep"
        assert PREFIX + "e-old-61d" not in reasons
        assert all(
            item["backup_id"] != PREFIX + "legacy-unassigned"
            for item in preview["eligible_backups"] + preview["ineligible_backups"]
        )
        assert any(
            item["backup_id"] == PREFIX + "f-exact-14d"
            for item in preview["eligible_backups"]
        )

        # E: uses its independent 60-full-day policy.
        fake.free["E:\\"] = 50
        preview_e = service.retention_preview(e_archive)
        reasons_e = reason_map(preview_e)
        assert reasons_e[PREFIX + "e-young"] == "keep_days"
        assert any(
            item["backup_id"] == PREFIX + "e-exact-60d"
            for item in preview_e["eligible_backups"]
        )
        assert preview_e["proposed_deletions"][0]["backup_id"] == PREFIX + "e-old-61d"

        # Active backup and restore checkpoints are absolute exclusions.
        active_run = BackupRun(
            schedule_id=f_daily.id,
            scope="database",
            trigger="scheduled",
            destination=f_daily.destination,
            status="running",
            stage="database",
            created_by_user_id=actor.id,
            error_code=PREFIX + "run",
        )
        db.add(active_run)
        db.flush()
        active_backup = add_backup(
            db,
            f_daily,
            "active-backup",
            timedelta(days=40),
            backup_run_id=active_run.id,
        )
        restore_target = add_backup(db, f_daily, "active-restore", timedelta(days=40))
        active_restore = RestoreRun(
            checkpoint_path=restore_target.checkpoint_path,
            mode="database",
            status="running",
            stage="database_restore",
            manifest_verified=True,
            compatibility_verified=True,
            compatibility_result="compatible",
            created_by_user_id=actor.id,
            error_code=PREFIX + "restore",
        )
        db.add(active_restore)
        db.commit()
        preview = service.retention_preview(f_daily, predicted_backup_bytes=150)
        reasons = reason_map(preview)
        assert reasons[active_backup.backup_id] == "active_backup"
        assert reasons[restore_target.backup_id] == "active_restore"

        # If eligible space cannot reach the target, fail closed.
        fake.free["F:\\"] = 0
        blocked = service.retention_preview(f_daily, predicted_backup_bytes=900)
        assert blocked["blocked_reason"] == "RETENTION_BLOCKED_INSUFFICIENT_SPACE"

        # Fresh planning is remeasured after each canonical deletion.
        active_run.status = "completed"
        active_restore.status = "completed"
        db.commit()
        current_preview = service.retention_preview(
            f_daily,
            predicted_backup_bytes=150,
            exclude_backup_run_id=active_run.id,
        )
        assert reason_map(current_preview)[active_backup.backup_id] == "current_backup"
        fake.free["F:\\"] = 50
        before_calls = fake.inspect_calls
        completed = service.enforce_drive_retention(f_daily, actor)
        assert fake.deleted
        assert fake.inspect_calls > before_calls
        assert completed["current_free_bytes"] >= completed["required_free_bytes"]

        # A host deletion failure stops immediately and records no false success.
        candidate_plan = add_plan(db, actor, "delete-failure", r"E:\failure", 60)
        add_backup(db, candidate_plan, "delete-failure-old", timedelta(days=100))
        add_backup(db, candidate_plan, "delete-failure-latest", timedelta(hours=1))
        db.commit()
        fake.free["E:\\"] = 50
        fake.fail_delete = True
        try:
            service.enforce_drive_retention(candidate_plan, actor)
        except RuntimeError as error:
            assert str(error) == "synthetic_delete_failure"
        else:
            raise AssertionError("failed deletion did not stop")

        cleanup(db)
        print("BACKUP_VOLUME_RETENTION_POLICY_TESTS=PASS")


if __name__ == "__main__":
    main()
