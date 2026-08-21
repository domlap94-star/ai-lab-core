from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.backup_operation import BackupRun, BackupSchedule
from app.models.user import User
from app.schemas.admin_backup import BackupScheduleWrite
from app.services.backup_restore_service import BackupRestoreService


def _payload(item: BackupSchedule) -> BackupScheduleWrite:
    return BackupScheduleWrite(
        name=item.name,
        enabled=item.enabled,
        scope=item.scope,
        destination=item.destination,
        cadence=item.cadence,
        local_time=item.local_time,
        weekday=item.weekday,
        month_day=item.month_day,
    )


def start_due_schedule(db: Session, schedule_id: int) -> int:
    service = BackupRestoreService(db)
    service._lock()
    schedule = (
        db.query(BackupSchedule)
        .filter(BackupSchedule.id == schedule_id)
        .with_for_update()
        .one_or_none()
    )
    if schedule is None:
        raise RuntimeError("backup_schedule_not_found")
    if not schedule.enabled:
        raise RuntimeError("backup_schedule_disabled")
    now = datetime.now(timezone.utc)
    if schedule.next_run_at > now + timedelta(seconds=60):
        raise RuntimeError("backup_schedule_not_due")
    actor = db.get(User, schedule.updated_by_user_id)
    if actor is None:
        raise RuntimeError("backup_schedule_actor_missing")
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule-id", type=int, required=True)
    args = parser.parse_args()
    if args.schedule_id <= 0:
        raise RuntimeError("backup_schedule_id_invalid")
    with SessionLocal() as db:
        run_id = start_due_schedule(db, args.schedule_id)
    run = wait_for_run(run_id)
    print(
        f"SCHEDULED_BACKUP_RUN={run.id} status={run.status} "
        f"verified={str(run.verified).lower()} checkpoint={run.checkpoint_path or ''}"
    )
    if run.status != "completed" or not run.verified:
        raise RuntimeError(run.error_code or "scheduled_backup_failed")


if __name__ == "__main__":
    main()
