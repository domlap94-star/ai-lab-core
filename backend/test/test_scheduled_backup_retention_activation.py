from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import ntpath

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.backup_operation import (
    BackupDeletionEvent,
    BackupPlanSyncEvent,
    BackupRun,
    BackupSchedule,
    ManagedBackup,
)
from app.models.user import User
from app.scripts import run_backup_schedule as scheduled_runner
from app.services.backup_restore_service import (
    BackupRestoreService,
    BackupRestoreValidation,
)
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()
PREFIX = "scheduled-retention-activation-fixture-"


class FakeStorageSupervisor:
    def __init__(self) -> None:
        self.total: dict[str, int] = {}
        self.free: dict[str, int] = {}
        self.deleted: list[dict] = []
        self.started: list[dict] = []
        self.size_by_checkpoint: dict[str, int] = {}

    @staticmethod
    def key(destination: str) -> str:
        return ntpath.normcase(ntpath.normpath(destination))

    def configure(self, destination: str, *, total: int = 1000, free: int) -> None:
        key = self.key(destination)
        self.total[key] = total
        self.free[key] = free

    def destination_preflight(self, destination: str) -> dict:
        key = self.key(destination)
        return {
            "available": True,
            "writable": True,
            "total_bytes": self.total.get(key, 1000),
            "free_bytes": self.free.get(key, 1000),
            "destination_identity": "synthetic-volume:" + key,
            "destination_filesystem": "NTFS",
        }

    def inspect_storage(self, destinations) -> dict:
        return {
            "items": [
                {
                    "normalized_destination": destination,
                    **self.destination_preflight(destination),
                }
                for destination in destinations
            ]
        }

    def delete_managed_backup(self, payload: dict) -> dict:
        checkpoint = self.key(payload["checkpoint_path"])
        destination = self.key(payload["destination_root"])
        reclaimed = self.size_by_checkpoint[checkpoint]
        self.deleted.append(dict(payload))
        self.free[destination] += reclaimed
        return {"actual_reclaimed_bytes": reclaimed}

    def start_backup(self, payload: dict) -> dict:
        self.started.append(dict(payload))
        return {
            "operation_id": f"synthetic-scheduled-{len(self.started)}",
            "stage": "validating",
        }


def add_plan(
    db,
    actor: User,
    suffix: str,
    destination: str,
    keep_days: int,
    *,
    auto_delete: bool = True,
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
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        auto_delete=auto_delete,
        minimum_free_percent=10,
        minimum_backups_to_keep=1,
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
    fake: FakeStorageSupervisor,
    plan: BackupSchedule,
    suffix: str,
    age: timedelta,
    *,
    size: int = 80,
    backup_run_id: int | None = None,
) -> ManagedBackup:
    checkpoint = plan.destination + "\\" + PREFIX + suffix
    item = ManagedBackup(
        backup_id=PREFIX + suffix,
        plan_id=plan.id,
        backup_run_id=backup_run_id,
        destination_root=plan.destination,
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
        integrity_status="verified",
        protected=False,
        lifecycle="available",
        created_at=datetime.now(timezone.utc) - age,
    )
    db.add(item)
    db.flush()
    fake.size_by_checkpoint[fake.key(checkpoint)] = size
    return item


def expect_error(expected: str, operation) -> None:
    try:
        operation()
    except BackupRestoreValidation as error:
        assert str(error) == expected, (str(error), expected)
    else:
        raise AssertionError(f"expected {expected}")


def reason_map(preview: dict) -> dict[str, str | None]:
    return {
        item["backup_id"]: item["reason"]
        for item in preview["ineligible_backups"]
    }


def cleanup(db) -> None:
    plan_ids = [
        row[0]
        for row in db.query(BackupSchedule.id)
        .filter(BackupSchedule.name.like(PREFIX + "%"))
        .all()
    ]
    backup_ids = [
        row[0]
        for row in db.query(ManagedBackup.id)
        .filter(ManagedBackup.backup_id.like(PREFIX + "%"))
        .all()
    ]
    if backup_ids:
        db.query(BackupDeletionEvent).filter(
            BackupDeletionEvent.backup_id.in_(backup_ids)
        ).delete(synchronize_session=False)
    db.query(ManagedBackup).filter(
        ManagedBackup.backup_id.like(PREFIX + "%")
    ).delete(synchronize_session=False)
    if plan_ids:
        db.query(BackupRun).filter(BackupRun.schedule_id.in_(plan_ids)).delete(
            synchronize_session=False
        )
        db.query(BackupPlanSyncEvent).filter(
            BackupPlanSyncEvent.plan_id.in_(plan_ids)
        ).delete(synchronize_session=False)
        db.query(BackupSchedule).filter(BackupSchedule.id.in_(plan_ids)).delete(
            synchronize_session=False
        )
    db.commit()


def main() -> None:
    fake = FakeStorageSupervisor()
    gate = {"enabled": False}
    original_service = scheduled_runner.BackupRestoreService
    scheduled_runner.BackupRestoreService = lambda db: BackupRestoreService(
        db,
        fake,
        allow_retention_delete=gate["enabled"],
    )
    with SessionLocal() as db:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        cleanup(db)
        actor = db.get(User, 900001)
        assert actor is not None
        try:
            # A: a configured automatic policy still cannot delete while the
            # production approval gate is disabled.
            gate_off = add_plan(db, actor, "gate-off", r"K:\gate-off", 14)
            fake.configure(gate_off.destination, free=50)
            add_backup(db, fake, gate_off, "gate-off-old-16d", timedelta(days=16))
            add_backup(db, fake, gate_off, "gate-off-old-15d", timedelta(days=15))
            add_backup(db, fake, gate_off, "gate-off-latest", timedelta(hours=1))
            db.commit()
            expect_error(
                "backup_retention_delete_approval_required",
                lambda: scheduled_runner.start_due_schedule(db, gate_off.id),
            )
            assert fake.deleted == []
            assert fake.started == []
            db.rollback()

            # B: an operator-managed policy never enters automatic deletion.
            operator = add_plan(
                db,
                actor,
                "operator",
                r"L:\operator",
                14,
                auto_delete=False,
            )
            fake.configure(operator.destination, free=50)
            add_backup(db, fake, operator, "operator-old", timedelta(days=20))
            add_backup(db, fake, operator, "operator-latest", timedelta(hours=1))
            db.commit()
            expect_error(
                "backup_retention_operator_action_required",
                lambda: scheduled_runner.start_due_schedule(db, operator.id),
            )
            assert fake.deleted == []
            assert fake.started == []
            db.rollback()

            # C: isolated opt-in uses the canonical oldest-first executor and
            # starts the backup only after the measured reserve is restored.
            gate["enabled"] = True
            enabled = add_plan(db, actor, "gate-on", r"M:\gate-on", 14)
            fake.configure(enabled.destination, free=50)
            oldest = add_backup(db, fake, enabled, "gate-on-oldest", timedelta(days=20))
            second = add_backup(db, fake, enabled, "gate-on-second", timedelta(days=16))
            add_backup(db, fake, enabled, "gate-on-latest", timedelta(hours=1))
            db.commit()
            run_id = scheduled_runner.start_due_schedule(db, enabled.id)
            assert [fake.key(item["checkpoint_path"]) for item in fake.deleted] == [
                fake.key(oldest.checkpoint_path),
                fake.key(second.checkpoint_path),
            ]
            assert len(fake.started) == 1
            assert fake.free[fake.key(enabled.destination)] == 210
            run = db.get(BackupRun, run_id)
            assert run is not None and run.status == "running"
            run.status = "completed"
            run.stage = "completed"
            run.verified = True
            db.commit()

            # D: post-backup retention excludes the just-created verified
            # backup while deleting an older eligible checkpoint.
            post = add_plan(db, actor, "post", r"N:\post", 14)
            fake.configure(post.destination, free=50)
            post_run = BackupRun(
                schedule_id=post.id,
                scope="database",
                trigger="scheduled",
                destination=post.destination,
                status="completed",
                stage="completed",
                operation_id="synthetic-post-retention",
                verified=True,
                created_by_user_id=actor.id,
            )
            db.add(post_run)
            db.flush()
            post_old = add_backup(db, fake, post, "post-old", timedelta(days=20))
            post_current = add_backup(
                db,
                fake,
                post,
                "post-current",
                timedelta(minutes=1),
                backup_run_id=post_run.id,
            )
            db.commit()
            before = len(fake.deleted)
            scheduled_runner.enforce_post_backup_retention(db, post_run)
            db.commit()
            assert len(fake.deleted) == before + 1
            assert fake.key(fake.deleted[-1]["checkpoint_path"]) == fake.key(
                post_old.checkpoint_path
            )
            db.refresh(post_current)
            assert post_current.lifecycle == "available"

            # E: full-day policy boundaries remain exact for both drive policy
            # classes; younger checkpoints stay ineligible.
            f_like = add_plan(db, actor, "f-like", r"O:\f-like", 14)
            fake.configure(f_like.destination, free=50)
            f_eligible = add_backup(
                db,
                fake,
                f_like,
                "f-eligible",
                timedelta(days=14, minutes=1),
            )
            f_protected = add_backup(
                db,
                fake,
                f_like,
                "f-protected",
                timedelta(days=13, hours=23),
            )
            add_backup(db, fake, f_like, "f-latest", timedelta(hours=1))
            e_like = add_plan(db, actor, "e-like", r"P:\e-like", 60)
            fake.configure(e_like.destination, free=50)
            e_eligible = add_backup(
                db,
                fake,
                e_like,
                "e-eligible",
                timedelta(days=60, minutes=1),
            )
            e_protected = add_backup(
                db,
                fake,
                e_like,
                "e-protected",
                timedelta(days=59, hours=23),
            )
            add_backup(db, fake, e_like, "e-latest", timedelta(hours=1))
            db.commit()
            f_preview = BackupRestoreService(db, fake).retention_preview(f_like)
            e_preview = BackupRestoreService(db, fake).retention_preview(e_like)
            assert f_eligible.backup_id in {
                item["backup_id"] for item in f_preview["eligible_backups"]
            }
            assert reason_map(f_preview)[f_protected.backup_id] == "keep_days"
            assert e_eligible.backup_id in {
                item["backup_id"] for item in e_preview["eligible_backups"]
            }
            assert reason_map(e_preview)[e_protected.backup_id] == "keep_days"

            # F: the executor does not delete a partial set when protected
            # backups make the reserve unattainable.
            insufficient = add_plan(db, actor, "insufficient", r"Q:\insufficient", 14)
            fake.configure(insufficient.destination, free=0)
            add_backup(db, fake, insufficient, "insufficient-old", timedelta(days=20))
            add_backup(db, fake, insufficient, "insufficient-latest", timedelta(hours=1))
            db.commit()
            before = len(fake.deleted)
            expect_error(
                "RETENTION_BLOCKED_INSUFFICIENT_SPACE",
                lambda: scheduled_runner.start_due_schedule(db, insufficient.id),
            )
            assert len(fake.deleted) == before
            db.rollback()

            # G: production/default configuration remains fail-closed. Only
            # the injected isolated-test service enabled real deletion above.
            assert settings.backup_retention_delete_enabled is False

            print("SCHEDULED_BACKUP_RETENTION_ACTIVATION_TESTS=PASS")
        finally:
            scheduled_runner.BackupRestoreService = original_service
            db.rollback()
            cleanup(db)


if __name__ == "__main__":
    main()
