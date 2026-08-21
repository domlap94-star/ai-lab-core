from __future__ import annotations

from calendar import monthrange
from datetime import datetime, time, timedelta, timezone
import ntpath
import re
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.backup_operation import BackupRun, BackupSchedule, RestoreRun
from app.models.user import User
from app.schemas.admin_backup import BackupScheduleWrite, RestoreCandidate
from app.services.backup_supervisor_client import BackupSupervisorClient


OPERATION_LOCK_KEY = 0x4E455854424B5253
SAFE_SCOPES = {"full", "database", "documents", "qdrant", "n8n_config"}
SAFE_RESTORE_MODES = {"database", "full"}
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:\\")


class BackupRestoreConflict(ValueError):
    pass


class BackupRestoreValidation(ValueError):
    pass


class BackupRestoreService:
    def __init__(self, db: Session, supervisor: BackupSupervisorClient | None = None) -> None:
        self.db = db
        self.supervisor = supervisor or BackupSupervisorClient()

    @staticmethod
    def validate_destination(value: str) -> str:
        raw = value.strip().replace("/", "\\")
        if not WINDOWS_ABSOLUTE.match(raw) or any(part == ".." for part in raw.split("\\")):
            raise BackupRestoreValidation("backup_destination_invalid")
        resolved = ntpath.normpath(raw).rstrip("\\")
        lowered = resolved.casefold()
        blocked = (
            r"c:\ai-lab-core".casefold(),
            r"c:\ai-lab-core\data".casefold(),
            r"c:\ai-lab-core\data\documents".casefold(),
        )
        for root in blocked:
            if lowered == root or lowered.startswith(root + "\\"):
                raise BackupRestoreValidation("backup_destination_active_path")
        return resolved

    @staticmethod
    def next_run(payload: BackupScheduleWrite, now: datetime | None = None) -> datetime:
        zone = ZoneInfo("Europe/Warsaw")
        current = (now or datetime.now(timezone.utc)).astimezone(zone)

        def local_candidate(day) -> datetime:
            return datetime.combine(day, payload.local_time, tzinfo=zone)

        if payload.cadence == "daily":
            candidate = local_candidate(current.date())
            if candidate <= current:
                candidate = local_candidate(current.date() + timedelta(days=1))
        elif payload.cadence == "weekly":
            assert payload.weekday is not None
            delta = (payload.weekday - current.isoweekday()) % 7
            candidate = local_candidate(current.date() + timedelta(days=delta))
            if candidate <= current:
                candidate = local_candidate(candidate.date() + timedelta(days=7))
        else:
            assert payload.month_day is not None
            year, month = current.year, current.month
            day = min(payload.month_day, monthrange(year, month)[1])
            candidate = local_candidate(current.date().replace(day=day))
            if candidate <= current:
                month = 1 if month == 12 else month + 1
                year = year + 1 if current.month == 12 else year
                day = min(payload.month_day, monthrange(year, month)[1])
                candidate = local_candidate(current.date().replace(year=year, month=month, day=day))
        return candidate.astimezone(timezone.utc)

    def _lock(self) -> None:
        self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": OPERATION_LOCK_KEY})

    def _assert_no_operation(self, *, restore: bool = False) -> None:
        active_backup = self.db.query(BackupRun.id).filter(BackupRun.status.in_(("queued", "running"))).first()
        active_restore = self.db.query(RestoreRun.id).filter(RestoreRun.status.in_(("queued", "running"))).first()
        if active_restore:
            raise BackupRestoreConflict("restore_already_running")
        if active_backup:
            raise BackupRestoreConflict("backup_already_running" if not restore else "operation_conflict")

    def list_schedules(self) -> list[BackupSchedule]:
        return self.db.query(BackupSchedule).order_by(BackupSchedule.id).all()

    @staticmethod
    def schedule_host_payload(item: BackupSchedule) -> dict:
        return {
            "id": item.id,
            "enabled": item.enabled,
            "cadence": item.cadence,
            "local_time": item.local_time.strftime("%H:%M:%S"),
            "weekday": item.weekday,
            "month_day": item.month_day,
            "timezone_name": item.timezone_name,
        }

    def reconcile_schedules(self) -> dict:
        items = self.list_schedules()
        return self.supervisor.reconcile_schedules(
            [self.schedule_host_payload(item) for item in items]
        )

    def schedule_views(self) -> list[dict]:
        items = self.list_schedules()
        try:
            response = self.supervisor.preview_schedules(
                [self.schedule_host_payload(item) for item in items]
            )
            host = {
                str(item.get("task_name")): item
                for item in response.get("items", [])
            }
        except Exception:
            host = {}
        views = []
        for item in items:
            task_name = f"NEXT Stabil - Backup - {item.id}"
            status = host.get(task_name)
            actual = status.get("actual") if status else None
            last_run = (
                self.db.query(BackupRun)
                .filter(BackupRun.schedule_id == item.id)
                .order_by(BackupRun.started_at.desc(), BackupRun.id.desc())
                .first()
            )
            values = {
                column.name: getattr(item, column.name)
                for column in BackupSchedule.__table__.columns
            }
            values.update({
                "sync_status": str(status.get("sync_status")) if status else "sync_failed",
                "host_task_name": task_name,
                "host_enabled": bool(actual and actual.get("enabled")),
                "host_next_run_at": actual.get("next_run_at") if actual else None,
                "host_last_run_at": actual.get("last_run_at") if actual else None,
                "host_last_result": actual.get("last_result") if actual else None,
                "last_backup_at": last_run.started_at if last_run else None,
                "last_backup_result": last_run.status if last_run else None,
            })
            views.append(values)
        return views

    def create_schedule(self, payload: BackupScheduleWrite, actor: User) -> BackupSchedule:
        self._lock()
        if self.db.query(func.count(BackupSchedule.id)).scalar() >= 10:
            raise BackupRestoreConflict("backup_schedule_limit_reached")
        item = BackupSchedule(
            **payload.model_dump(exclude={"destination"}),
            destination=self.validate_destination(payload.destination),
            timezone_name="Europe/Warsaw",
            next_run_at=self.next_run(payload),
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def update_schedule(self, item: BackupSchedule, payload: BackupScheduleWrite, actor: User) -> BackupSchedule:
        values = payload.model_dump(exclude={"destination"})
        for field, value in values.items():
            setattr(item, field, value)
        item.destination = self.validate_destination(payload.destination)
        item.next_run_at = self.next_run(payload)
        item.updated_by_user_id = actor.id
        self.db.flush()
        return item

    def delete_schedule(self, item: BackupSchedule) -> None:
        self.db.delete(item)
        self.db.flush()

    def start_backup(self, *, scope: str, destination: str, actor: User, trigger: str = "manual", schedule_id: int | None = None) -> BackupRun:
        if scope not in SAFE_SCOPES:
            raise BackupRestoreValidation("backup_scope_invalid")
        self._lock()
        self._assert_no_operation()
        run = BackupRun(
            schedule_id=schedule_id,
            scope=scope,
            trigger=trigger,
            destination=self.validate_destination(destination),
            status="queued",
            stage="queued",
            created_by_user_id=actor.id,
        )
        self.db.add(run)
        self.db.flush()
        response = self.supervisor.start_backup({
            "run_id": run.id,
            "scope": scope,
            "destination": run.destination,
            "release": settings.backup_release_version,
            "trigger": trigger,
            "schedule_id": schedule_id,
        })
        run.operation_id = str(response["operation_id"])
        run.status = "running"
        run.stage = str(response.get("stage") or "validating")
        self.db.flush()
        return run

    def refresh_run(self, run: BackupRun) -> BackupRun:
        if run.status not in {"queued", "running"} or not run.operation_id:
            return run
        status = self.supervisor.backup_status(run.operation_id)
        run.status = str(status["status"])
        run.stage = str(status["stage"])
        run.checkpoint_path = status.get("checkpoint_path")
        run.manifest_path = status.get("manifest_path")
        run.artifact_count = int(status.get("artifact_count") or 0)
        run.total_bytes = int(status.get("total_bytes") or 0)
        run.verified = bool(status.get("verified"))
        run.error_code = status.get("error_code")
        if run.status in {"completed", "failed"}:
            run.finished_at = datetime.now(timezone.utc)
        self.db.flush()
        return run

    def discover(self) -> list[RestoreCandidate]:
        destinations = {self.validate_destination(settings.backup_root)}
        destinations.update(item.destination for item in self.list_schedules())
        payload = self.supervisor.discover(sorted(destinations))
        return [RestoreCandidate.model_validate(item) for item in payload.get("items", [])]

    def preview(self, checkpoint_path: str, mode: str, current_revision: str) -> dict:
        if mode not in SAFE_RESTORE_MODES:
            raise BackupRestoreValidation("restore_mode_invalid")
        candidates = {item.checkpoint_path.casefold(): item for item in self.discover()}
        key = ntpath.normpath(checkpoint_path).casefold()
        candidate = candidates.get(key)
        if candidate is None:
            raise BackupRestoreValidation("restore_checkpoint_not_validated")
        eligible = candidate.database_eligible if mode == "database" else candidate.full_eligible
        replaces = ["database"] if mode == "database" else [
            "database", "documents", "qdrant", "n8n_config", "configuration"
        ]
        return {
            "mode": mode,
            "checkpoint_path": candidate.checkpoint_path,
            "created_at": candidate.created_at,
            "app_version": candidate.app_version,
            "backup_db_revision": candidate.db_revision,
            "current_db_revision": current_revision,
            "compatibility": candidate.compatibility,
            "manifest_verified": candidate.verified,
            "eligible": eligible and candidate.compatibility in {"compatible", "older_supported_checkpoint", "requires_migration_after_restore"},
            "replaces": replaces,
            "service_interruption_required": True,
            "pre_restore_backup_required": True,
            "error_code": candidate.error_code,
        }

    def request_restore(self, *, checkpoint_path: str, mode: str, acknowledged: bool, confirmation: str, actor: User, current_revision: str) -> RestoreRun:
        if not acknowledged or confirmation != "PRZYWRÓĆ":
            raise BackupRestoreValidation("restore_confirmation_required")
        preview = self.preview(checkpoint_path, mode, current_revision)
        if not preview["eligible"]:
            raise BackupRestoreValidation(preview["error_code"] or "restore_checkpoint_ineligible")
        if not settings.production_restore_enabled:
            raise BackupRestoreConflict("production_restore_approval_required")
        self._lock()
        self._assert_no_operation(restore=True)
        # Production execution remains delegated to the host coordinator. The
        # gate above is false by default and is intentionally not enabled here.
        run = RestoreRun(
            checkpoint_path=preview["checkpoint_path"],
            mode=mode,
            status="approval_required",
            stage="approval_required",
            manifest_verified=True,
            compatibility_verified=True,
            compatibility_result=preview["compatibility"],
            error_code="production_restore_approval_required",
            created_by_user_id=actor.id,
        )
        self.db.add(run)
        self.db.flush()
        return run
