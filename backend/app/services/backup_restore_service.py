from __future__ import annotations

from calendar import monthrange
import base64
from datetime import datetime, time, timedelta, timezone
import hashlib
import hmac
import json
import ntpath
import re
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.backup_operation import (
    BackupDeletionEvent,
    BackupPlanSyncEvent,
    BackupRun,
    BackupSchedule,
    ManagedBackup,
    RestoreRun,
)
from app.models.user import User
from app.schemas.admin_backup import BackupScheduleWrite, RestoreCandidate
from app.services.backup_supervisor_client import BackupSupervisorClient


OPERATION_LOCK_KEY = 0x4E455854424B5253
SAFE_SCOPES = {"full", "database", "documents", "qdrant", "n8n_config"}
SAFE_RESTORE_MODES = {"database", "full"}
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:\\")
WINDOWS_UNC = re.compile(r"^\\\\[^\\]+\\[^\\]+\\")
PREFLIGHT_TTL_SECONDS = 300
ADOPTION_TTL_SECONDS = 600


class BackupRestoreConflict(ValueError):
    pass


class BackupRestoreValidation(ValueError):
    pass


class BackupRestoreService:
    def __init__(
        self,
        db: Session,
        supervisor: BackupSupervisorClient | None = None,
        *,
        allow_retention_delete: bool | None = None,
    ) -> None:
        self.db = db
        self.supervisor = supervisor or BackupSupervisorClient()
        # Real managed-backup deletion stays disabled until the separate
        # FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED gate is consumed.
        # Isolated tests opt in explicitly against synthetic roots.
        self.allow_retention_delete = (
            settings.backup_retention_delete_enabled
            if allow_retention_delete is None
            else allow_retention_delete
        )

    @staticmethod
    def validate_destination(value: str) -> str:
        raw = value.strip().replace("/", "\\")
        lowered_raw = raw.casefold()
        if lowered_raw.startswith(("\\\\?\\", "\\\\.\\")):
            raise BackupRestoreValidation("backup_destination_invalid")
        if not (WINDOWS_ABSOLUTE.match(raw) or WINDOWS_UNC.match(raw)) or any(part == ".." for part in raw.split("\\")):
            raise BackupRestoreValidation("backup_destination_invalid")
        resolved = ntpath.normpath(raw).rstrip("\\")
        drive, tail = ntpath.splitdrive(resolved)
        if not drive or not tail.strip("\\"):
            raise BackupRestoreValidation("backup_destination_root_forbidden")
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
        return self.db.query(BackupSchedule).filter(BackupSchedule.deleted_at.is_(None)).order_by(BackupSchedule.id).all()

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
            "plan_revision": item.plan_revision,
        }

    def ensure_reconciliation_events(self) -> int:
        created = 0
        for item in self.db.query(BackupSchedule).filter(BackupSchedule.last_reconciled_revision < BackupSchedule.plan_revision).all():
            operation = "remove" if item.deleted_at is not None else "upsert"
            exists = self.db.query(BackupPlanSyncEvent.id).filter(
                BackupPlanSyncEvent.plan_id == item.id,
                BackupPlanSyncEvent.plan_revision == item.plan_revision,
                BackupPlanSyncEvent.operation == operation,
            ).first()
            if not exists:
                self.db.add(BackupPlanSyncEvent(plan_id=item.id, plan_revision=item.plan_revision, operation=operation))
                created += 1
        self.db.flush()
        return created

    def _enqueue_sync(self, item: BackupSchedule, operation: str) -> BackupPlanSyncEvent:
        event = BackupPlanSyncEvent(plan_id=item.id, plan_revision=item.plan_revision, operation=operation)
        self.db.add(event)
        item.sync_status = "pending"
        item.last_sync_error_code = None
        self.db.flush()
        return event

    def reconcile_pending(self, limit: int = 20) -> dict:
        self.ensure_reconciliation_events()
        self.db.commit()
        stale_before = datetime.now(timezone.utc) - timedelta(minutes=5)
        events = self.db.query(BackupPlanSyncEvent).filter(
            or_(
                BackupPlanSyncEvent.status.in_(("pending", "failed")),
                and_(
                    BackupPlanSyncEvent.status == "running",
                    BackupPlanSyncEvent.started_at < stale_before,
                ),
            )
        ).order_by(BackupPlanSyncEvent.created_at, BackupPlanSyncEvent.id).limit(limit).all()
        result = {"processed": 0, "succeeded": 0, "failed": 0, "superseded": 0}
        for event in events:
            item = self.db.get(BackupSchedule, event.plan_id)
            result["processed"] += 1
            if item is None or item.plan_revision != event.plan_revision:
                event.status = "superseded"
                event.finished_at = datetime.now(timezone.utc)
                result["superseded"] += 1
                self.db.commit()
                continue
            event.status = "running"
            event.attempt_count += 1
            event.started_at = datetime.now(timezone.utc)
            self.db.commit()
            try:
                current = self.list_schedules()
                self.supervisor.reconcile_schedules([self.schedule_host_payload(plan) for plan in current])
                self.db.refresh(item)
                if item.plan_revision != event.plan_revision:
                    event.status = "superseded"
                    result["superseded"] += 1
                else:
                    event.status = "succeeded"
                    item.last_reconciled_revision = event.plan_revision
                    item.sync_status = "disabled" if item.deleted_at is not None or not item.enabled else "synced"
                    item.last_sync_at = datetime.now(timezone.utc)
                    item.last_sync_error_code = None
                    result["succeeded"] += 1
                event.finished_at = datetime.now(timezone.utc)
                event.error_code = None
                self.db.commit()
            except Exception as error:
                self.db.rollback()
                event = self.db.get(BackupPlanSyncEvent, event.id)
                item = self.db.get(BackupSchedule, event.plan_id) if event else None
                code = str(error)[:100] or "backup_scheduler_host_failure"
                if event:
                    event.status = "failed"
                    event.error_code = code
                    event.finished_at = datetime.now(timezone.utc)
                if item and item.plan_revision == event.plan_revision:
                    item.sync_status = "error"
                    item.last_sync_error_code = code
                self.db.commit()
                result["failed"] += 1
        return result

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
            sync_status="pending",
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        self.db.add(item)
        self.db.flush()
        self._enqueue_sync(item, "upsert")
        return item

    def update_schedule(self, item: BackupSchedule, payload: BackupScheduleWrite, actor: User) -> BackupSchedule:
        values = payload.model_dump(exclude={"destination"})
        for field, value in values.items():
            setattr(item, field, value)
        item.destination = self.validate_destination(payload.destination)
        item.next_run_at = self.next_run(payload)
        item.updated_by_user_id = actor.id
        item.plan_revision += 1
        item.sync_status = "pending"
        self.db.flush()
        self._enqueue_sync(item, "upsert")
        return item

    def delete_schedule(self, item: BackupSchedule) -> None:
        item.deleted_at = datetime.now(timezone.utc)
        item.enabled = False
        item.plan_revision += 1
        item.sync_status = "pending"
        self.db.flush()
        self._enqueue_sync(item, "remove")

    def destination_preflight(self, destination: str) -> dict:
        normalized = self.validate_destination(destination)
        result = self.supervisor.destination_preflight(normalized)
        return {**result, "normalized_destination": normalized}

    @staticmethod
    def _preflight_signature(payload: bytes) -> str:
        return hmac.new(settings.secret_key.encode(), b"next-stabil-manual-backup-v2|" + payload, hashlib.sha256).hexdigest()

    def issue_preflight_token(self, *, user_id: int, scope: str, destination: str) -> tuple[str, datetime, dict]:
        if scope not in SAFE_SCOPES:
            raise BackupRestoreValidation("backup_scope_invalid")
        host = self.destination_preflight(destination)
        if not host.get("available") or not host.get("writable"):
            raise BackupRestoreValidation("backup_destination_unavailable")
        expires = datetime.now(timezone.utc) + timedelta(seconds=PREFLIGHT_TTL_SECONDS)
        body = json.dumps({"u": user_id, "s": scope, "p": host["normalized_destination"], "e": int(expires.timestamp())}, separators=(",", ":"), sort_keys=True).encode()
        token = base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + self._preflight_signature(body)
        return token, expires, host

    def verify_preflight_token(self, *, token: str, user_id: int, scope: str, destination: str) -> str:
        try:
            encoded, signature = token.split(".", 1)
            body = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            if not hmac.compare_digest(signature, self._preflight_signature(body)):
                raise ValueError
            payload = json.loads(body)
        except Exception as error:
            raise BackupRestoreValidation("backup_preflight_token_invalid") from error
        normalized = self.validate_destination(destination)
        if payload != {"e": payload.get("e"), "p": normalized, "s": scope, "u": user_id}:
            raise BackupRestoreValidation("backup_preflight_token_binding_invalid")
        if int(payload["e"]) < int(datetime.now(timezone.utc).timestamp()):
            raise BackupRestoreValidation("backup_preflight_token_expired")
        return normalized

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
        if run.status == "completed" and run.verified and run.schedule_id is not None:
            self._register_managed_backup(run)
        self.db.flush()
        return run

    def _register_managed_backup(self, run: BackupRun) -> ManagedBackup | None:
        existing = self.db.query(ManagedBackup).filter(ManagedBackup.backup_run_id == run.id).one_or_none()
        if existing or not run.checkpoint_path:
            return existing
        discovered = self.supervisor.discover([run.destination]).get("items", [])
        item = next((value for value in discovered if ntpath.normcase(value.get("checkpoint_path", "")) == ntpath.normcase(run.checkpoint_path)), None)
        if not item or not item.get("verified") or not item.get("manifest_sha256"):
            return None
        managed = ManagedBackup(
            backup_id=str(run.operation_id or f"run-{run.id}"), plan_id=run.schedule_id, backup_run_id=run.id,
            destination_root=run.destination, checkpoint_path=run.checkpoint_path,
            manifest_path=str(item["manifest_path"]), manifest_schema=str(item.get("manifest_schema") or "NEXT_STABIL_BACKUP_V1"),
            manifest_sha256=str(item["manifest_sha256"]), scope=run.scope,
            app_version=str(item["app_version"]), source_head=str(item["source_head"]), db_revision=str(item["db_revision"]),
            artifact_count=int(item["artifact_count"]), total_bytes=int(item["total_bytes"]),
            integrity_status="verified", lifecycle="available", created_at=datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00")),
        )
        self.db.add(managed)
        self.db.flush()
        return managed

    def list_managed_backups(self) -> list[ManagedBackup]:
        return self.db.query(ManagedBackup).order_by(ManagedBackup.created_at.desc(), ManagedBackup.id.desc()).all()

    def _recognized_destinations(self) -> list[str]:
        destinations = {self.validate_destination(settings.backup_root)}
        destinations.update(item.destination for item in self.list_schedules())
        return sorted(destinations)

    def _inventory_items(self, *, include_invalid: bool = False) -> list[dict]:
        payload = self.supervisor.inventory(
            self._recognized_destinations(), include_invalid=include_invalid
        )
        unique: dict[str, dict] = {}
        for item in payload.get("items", []):
            checkpoint = str(item.get("checkpoint_path") or "")
            if not checkpoint:
                continue
            key = ntpath.normcase(ntpath.normpath(checkpoint))
            current = unique.get(key)
            # Overlapping approved roots can discover the same checkpoint.
            # The longest root is the most specific ownership boundary.
            if current is None or len(str(item.get("destination_root") or "")) > len(
                str(current.get("destination_root") or "")
            ):
                unique[key] = item
        return sorted(
            unique.values(),
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )

    @staticmethod
    def _inside_root(path: str, root: str) -> bool:
        normalized_path = ntpath.normpath(path).casefold()
        normalized_root = ntpath.normpath(root).rstrip("\\").casefold()
        return normalized_path.startswith(normalized_root + "\\")

    @staticmethod
    def _legacy_candidate_id(checkpoint_path: str, manifest_sha256: str) -> str:
        value = f"{ntpath.normcase(ntpath.normpath(checkpoint_path))}|{manifest_sha256.lower()}"
        return hashlib.sha256(value.encode()).hexdigest()[:32]

    def _issue_adoption_token(self, *, actor: User, item: dict) -> str:
        payload = {
            "purpose": "next_stabil_backup_adoption_v1",
            "user_id": actor.id,
            "checkpoint_path": str(item["checkpoint_path"]),
            "destination_root": str(item["destination_root"]),
            "manifest_sha256": str(item["manifest_sha256"]).lower(),
            "exp": int((datetime.now(timezone.utc) + timedelta(seconds=ADOPTION_TTL_SECONDS)).timestamp()),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        ).rstrip(b"=").decode()
        signature = hmac.new(
            settings.secret_key.encode(),
            b"next-stabil-backup-adoption-v1|" + encoded.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{encoded}.{signature}"

    def _decode_adoption_token(self, token: str, actor: User) -> dict:
        try:
            encoded, supplied = token.split(".", 1)
            expected = hmac.new(
                settings.secret_key.encode(),
                b"next-stabil-backup-adoption-v1|" + encoded.encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, supplied):
                raise ValueError
            payload = json.loads(
                base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BackupRestoreValidation("legacy_adoption_token_invalid") from error
        if payload.get("purpose") != "next_stabil_backup_adoption_v1" or payload.get("user_id") != actor.id:
            raise BackupRestoreValidation("legacy_adoption_token_binding_invalid")
        if not isinstance(payload.get("exp"), int) or payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
            raise BackupRestoreValidation("legacy_adoption_token_expired")
        return payload

    def legacy_candidates(self, actor: User) -> list[dict]:
        roots = self._recognized_destinations()
        items = self._inventory_items(include_invalid=True)
        managed_paths = {
            ntpath.normcase(ntpath.normpath(item.checkpoint_path))
            for item in self.list_managed_backups()
        }
        result = []
        for item in items:
            checkpoint = str(item.get("checkpoint_path") or "")
            root = str(item.get("destination_root") or "")
            recognized = root in roots and self._inside_root(checkpoint, root)
            verified = bool(item.get("verified"))
            schema = str(item.get("manifest_schema") or "") or None
            manifest_hash = str(item.get("manifest_sha256") or "").lower()
            already_managed = ntpath.normcase(ntpath.normpath(checkpoint)) in managed_paths
            adoptable = (
                recognized and schema == "NEXT_STABIL_BACKUP_V1"
                and bool(re.fullmatch(r"[a-f0-9]{64}", manifest_hash))
                and not already_managed
            )
            if already_managed:
                reason = "already_managed"
            elif not recognized:
                reason = "outside_recognized_root"
            elif schema != "NEXT_STABIL_BACKUP_V1":
                reason = "legacy_manifest_schema_required"
            elif not manifest_hash:
                reason = "manifest_hash_missing"
            else:
                reason = None
            result.append({
                "candidate_id": self._legacy_candidate_id(checkpoint, manifest_hash or "unverified"),
                "checkpoint_path": checkpoint,
                "destination_root": root,
                "created_at": item.get("created_at"),
                "scope": item.get("scope"),
                "app_version": item.get("app_version"),
                "total_bytes": int(item.get("total_bytes") or 0),
                "manifest_schema": schema,
                "verified": verified,
                "integrity_status": "verified" if verified else "unverified",
                "adoptable": adoptable,
                "already_managed": already_managed,
                "reason": reason,
                "adoption_token": self._issue_adoption_token(actor=actor, item=item) if adoptable else None,
            })
        return result

    def adopt_legacy_backup(self, *, token: str, plan_id: int | None, actor: User) -> tuple[ManagedBackup, bool]:
        bound = self._decode_adoption_token(token, actor)
        plan = None
        if plan_id is not None:
            plan = self.db.get(BackupSchedule, plan_id)
            if plan is None or plan.deleted_at is not None:
                raise BackupRestoreValidation("backup_schedule_not_found")
        roots = self._recognized_destinations()
        key = ntpath.normcase(ntpath.normpath(str(bound["checkpoint_path"])))
        item = self.supervisor.verify_checkpoint(
            str(bound["destination_root"]), str(bound["checkpoint_path"])
        )
        if not item.get("verified"):
            raise BackupRestoreValidation("legacy_adoption_candidate_changed")
        if str(item.get("manifest_schema") or "") != "NEXT_STABIL_BACKUP_V1":
            raise BackupRestoreValidation("legacy_manifest_schema_required")
        if str(item.get("manifest_sha256") or "").lower() != bound.get("manifest_sha256"):
            raise BackupRestoreValidation("legacy_adoption_manifest_changed")
        root = str(item.get("destination_root") or "")
        if root != bound.get("destination_root") or root not in roots or not self._inside_root(str(item["checkpoint_path"]), root):
            raise BackupRestoreValidation("legacy_adoption_root_invalid")
        if plan is not None and ntpath.normcase(plan.destination) != ntpath.normcase(root):
            raise BackupRestoreValidation("legacy_adoption_plan_root_mismatch")
        existing = self.db.query(ManagedBackup).filter(
            ManagedBackup.checkpoint_path == str(item["checkpoint_path"])
        ).one_or_none()
        if existing is not None:
            return existing, True
        matching_run = next(
            (
                run for run in self.db.query(BackupRun).filter(
                    BackupRun.status == "completed", BackupRun.verified.is_(True)
                ).all()
                if run.checkpoint_path and ntpath.normcase(ntpath.normpath(run.checkpoint_path)) == key
            ),
            None,
        )
        managed = ManagedBackup(
            backup_id="legacy-" + self._legacy_candidate_id(str(item["checkpoint_path"]), str(item["manifest_sha256"]))[:57],
            plan_id=plan.id if plan else None,
            backup_run_id=matching_run.id if matching_run else None,
            destination_root=root, checkpoint_path=str(item["checkpoint_path"]),
            manifest_path=str(item["manifest_path"]), manifest_schema="NEXT_STABIL_BACKUP_V1",
            manifest_sha256=str(item["manifest_sha256"]).lower(), scope=str(item["scope"]),
            app_version=str(item["app_version"]), source_head=str(item["source_head"]),
            db_revision=str(item["db_revision"]), artifact_count=int(item["artifact_count"]),
            total_bytes=int(item["total_bytes"]), integrity_status="verified",
            protected=False, lifecycle="available",
            created_at=datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00")),
        )
        self.db.add(managed); self.db.flush()
        return managed, False

    def retention_preview(
        self,
        plan: BackupSchedule,
        predicted_backup_bytes: int = 0,
        *,
        exclude_backup_run_id: int | None = None,
    ) -> dict:
        if plan.deleted_at is not None:
            raise BackupRestoreValidation("backup_plan_deleted")
        host = self.destination_preflight(plan.destination)
        total = int(host.get("total_bytes") or 0)
        free = int(host.get("free_bytes") or 0)
        percent = int(plan.minimum_free_percent or 0)
        required = max((total * percent + 99) // 100, int(plan.minimum_free_bytes or 0))
        backups = self.db.query(ManagedBackup).filter(
            ManagedBackup.plan_id == plan.id, ManagedBackup.lifecycle == "available"
        ).order_by(ManagedBackup.created_at.asc(), ManagedBackup.id.asc()).all()
        floor = max(plan.minimum_backups_to_keep, int(plan.keep_last_n or 0))
        keep_ids = {item.id for item in backups[-floor:]} if floor else set()
        age_cutoff = datetime.now(timezone.utc) - timedelta(days=plan.keep_days) if plan.keep_days is not None else None
        eligible = []
        ineligible = []
        for item in backups:
            reason = None
            if exclude_backup_run_id is not None and item.backup_run_id == exclude_backup_run_id: reason = "current_backup"
            elif item.protected: reason = "protected"
            elif item.id in keep_ids: reason = "minimum_keep"
            elif item.integrity_status != "verified": reason = "not_verified"
            elif age_cutoff is not None and item.created_at >= age_cutoff: reason = "keep_days"
            target = ineligible if reason else eligible
            target.append({"backup_id": item.backup_id, "created_at": item.created_at, "total_bytes": item.total_bytes, "protected": item.protected, "eligible": reason is None, "reason": reason})
        need = max(0, required + int(predicted_backup_bytes) - free)
        proposed = []
        reclaimed = 0
        for item in eligible:
            if reclaimed >= need: break
            proposed.append(item); reclaimed += int(item["total_bytes"])
        blocked = "RETENTION_BLOCKED_INSUFFICIENT_SPACE" if reclaimed < need else None
        return {
            "plan_id": plan.id, "current_total_bytes": total, "current_free_bytes": free,
            "required_free_bytes": required, "predicted_backup_bytes": int(predicted_backup_bytes),
            "eligible_backups": eligible, "ineligible_backups": ineligible,
            "proposed_deletions": proposed, "predicted_reclaimed_bytes": reclaimed,
            "predicted_final_free_bytes": free + reclaimed - int(predicted_backup_bytes), "blocked_reason": blocked,
        }

    def delete_managed_backup(self, item: ManagedBackup, actor: User, *, automatic: bool = False, reason: str = "manual_delete") -> BackupDeletionEvent:
        if not self.allow_retention_delete:
            raise BackupRestoreValidation("backup_retention_delete_approval_required")
        if item.lifecycle != "available" or item.protected or item.integrity_status != "verified":
            raise BackupRestoreValidation("managed_backup_not_eligible")
        active_restore = self.db.query(RestoreRun.id).filter(RestoreRun.status.in_(("queued", "running")), RestoreRun.checkpoint_path == item.checkpoint_path).first()
        active_run = self.db.query(BackupRun.id).filter(BackupRun.status.in_(("queued", "running")), BackupRun.id == item.backup_run_id).first()
        if active_restore or active_run:
            raise BackupRestoreConflict("managed_backup_active")
        event = BackupDeletionEvent(backup_id=item.id, plan_id=item.plan_id, mode="automatic" if automatic else "manual", reason=reason,
                                    planned_bytes=item.total_bytes, status="running", requested_by_user_id=None if automatic else actor.id)
        self.db.add(event); item.lifecycle = "deleting"; self.db.flush(); self.db.commit()
        self.db.refresh(event); self.db.refresh(item)
        try:
            result = self.supervisor.delete_managed_backup({
                "checkpoint_path": item.checkpoint_path, "destination_root": item.destination_root,
                "manifest_path": item.manifest_path, "manifest_sha256": item.manifest_sha256,
            })
            event.actual_reclaimed_bytes = int(result.get("actual_reclaimed_bytes") or 0)
            event.status = "succeeded"; event.finished_at = datetime.now(timezone.utc)
            item.lifecycle = "deleted"; item.deleted_at = event.finished_at
        except Exception as error:
            event.status = "failed"; event.error_code = str(error)[:100]; event.finished_at = datetime.now(timezone.utc)
            item.lifecycle = "error"; item.error_code = event.error_code
            self.db.commit()
            raise
        finally:
            self.db.flush()
        return event

    def discover(self) -> list[RestoreCandidate]:
        return [
            RestoreCandidate.model_validate(item)
            for item in self._inventory_items()
        ]

    def preview(self, checkpoint_path: str, mode: str, current_revision: str) -> dict:
        if mode not in SAFE_RESTORE_MODES:
            raise BackupRestoreValidation("restore_mode_invalid")
        candidates = {item.checkpoint_path.casefold(): item for item in self.discover()}
        key = ntpath.normpath(checkpoint_path).casefold()
        inventory_candidate = candidates.get(key)
        if inventory_candidate is None:
            raise BackupRestoreValidation("restore_checkpoint_not_validated")
        root = next(
            (value for value in self._recognized_destinations() if self._inside_root(checkpoint_path, value)),
            None,
        )
        if root is None:
            raise BackupRestoreValidation("restore_checkpoint_not_validated")
        candidate = RestoreCandidate.model_validate(
            self.supervisor.verify_checkpoint(root, inventory_candidate.checkpoint_path)
        )
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
