from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.backup_operation import BackupRun, BackupSchedule, ManagedBackup
from app.models.user import User
from app.schemas.admin_backup import BackupScheduleWrite
from app.services.backup_restore_service import BackupRestoreService


def _payload(item: BackupSchedule) -> BackupScheduleWrite:
    return BackupScheduleWrite(
        name=item.name,
        enabled=item.enabled,
        scope=item.scope,
        destination=item.destination,
        destination_type=item.destination_type,
        cadence=item.cadence,
        local_time=item.local_time,
        weekday=item.weekday,
        month_day=item.month_day,
        auto_delete=item.auto_delete,
        minimum_free_percent=item.minimum_free_percent,
        minimum_free_bytes=item.minimum_free_bytes,
        minimum_backups_to_keep=item.minimum_backups_to_keep,
        keep_last_n=item.keep_last_n,
        keep_days=item.keep_days,
        preserve_weekly_count=item.preserve_weekly_count,
        preserve_monthly_count=item.preserve_monthly_count,
        retention_trigger=item.retention_trigger,
        retention_local_time=item.retention_local_time,
        retention_weekday=item.retention_weekday,
    )


def start_due_schedule(db: Session, schedule_id: int) -> int:
    service = BackupRestoreService(db)
    service._lock()
    schedule = (
        db.query(BackupSchedule)
        .filter(BackupSchedule.id == schedule_id)
        .filter(BackupSchedule.deleted_at.is_(None))
        .with_for_update()
        .one_or_none()
    )
    if schedule is None:
        raise RuntimeError("backup_schedule_not_found")
    if not schedule.enabled:
        raise RuntimeError("backup_schedule_disabled")
    if schedule.last_reconciled_revision != schedule.plan_revision:
        raise RuntimeError("backup_schedule_not_reconciled")
    now = datetime.now(timezone.utc)
    if schedule.next_run_at > now + timedelta(seconds=60):
        raise RuntimeError("backup_schedule_not_due")
    actor = db.get(User, schedule.updated_by_user_id)
    if actor is None:
        raise RuntimeError("backup_schedule_actor_missing")
    try:
        host = service.destination_preflight(schedule.destination)
    except Exception:
        schedule.destination_status = "unavailable"
        schedule.last_destination_check_at = now
        schedule.sync_status = "destination_unavailable"
        db.commit()
        raise RuntimeError("backup_destination_unavailable")
    schedule.destination_status = "available" if host.get("available") and host.get("writable") else "unavailable"
    schedule.destination_identity = host.get("destination_identity")
    schedule.destination_filesystem = host.get("destination_filesystem")
    schedule.destination_total_bytes = host.get("total_bytes")
    schedule.destination_free_bytes = host.get("free_bytes")
    schedule.last_destination_check_at = now
    if schedule.destination_status != "available":
        schedule.sync_status = "destination_unavailable"
        db.commit()
        raise RuntimeError("backup_destination_unavailable")
    predicted_bytes = (
        db.query(ManagedBackup.total_bytes)
        .filter(ManagedBackup.plan_id == schedule.id, ManagedBackup.lifecycle == "available")
        .order_by(ManagedBackup.created_at.desc())
        .limit(1)
        .scalar()
        or 0
    )
    service.enforce_drive_retention(
        schedule,
        actor,
        predicted_backup_bytes=int(predicted_bytes),
    )
    run = service.start_backup(
        scope=schedule.scope,
        destination=schedule.destination,
        actor=actor,
        trigger="scheduled",
        schedule_id=schedule.id,
    )
    schedule.next_run_at = service.next_run(_payload(schedule), now=now)
    db.commit()
    return run.id


def wait_for_run(run_id: int, timeout_seconds: int = 21600) -> BackupRun:
    deadline = time.monotonic() + timeout_seconds
    while True:
        with SessionLocal() as db:
            run = db.get(BackupRun, run_id)
            if run is None:
                raise RuntimeError("backup_run_not_found")
            BackupRestoreService(db).refresh_run(run)
            db.commit()
            db.refresh(run)
            if run.status in {"completed", "failed"}:
                return run
        if time.monotonic() >= deadline:
            raise RuntimeError("backup_schedule_runner_timeout")
        time.sleep(5)


def enforce_post_backup_retention(db: Session, run: BackupRun) -> None:
    current = db.get(BackupRun, run.id)
    if (
        current is None
        or current.status != "completed"
        or not current.verified
        or current.schedule_id is None
    ):
        return
    schedule = db.get(BackupSchedule, current.schedule_id)
    if schedule is None:
        return
    actor = db.get(User, current.created_by_user_id)
    if actor is None:
        raise RuntimeError("backup_schedule_actor_missing")
    BackupRestoreService(db).enforce_drive_retention(
        schedule,
        actor,
        predicted_backup_bytes=0,
        exclude_backup_run_id=current.id,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule-id", type=int, required=True)
    args = parser.parse_args()
    if args.schedule_id <= 0:
        raise RuntimeError("backup_schedule_id_invalid")
    with SessionLocal() as db:
        run_id = start_due_schedule(db, args.schedule_id)
    run = wait_for_run(run_id)
    if run.status == "completed" and run.verified and run.schedule_id is not None:
        with SessionLocal() as db:
            enforce_post_backup_retention(db, run)
    print(
        f"SCHEDULED_BACKUP_RUN={run.id} status={run.status} "
        f"verified={str(run.verified).lower()} checkpoint={run.checkpoint_path or ''}"
    )
    if run.status != "completed" or not run.verified:
        raise RuntimeError(run.error_code or "scheduled_backup_failed")


if __name__ == "__main__":
    main()
