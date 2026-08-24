from __future__ import annotations

import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


class BackupSupervisorUnavailable(RuntimeError):
    pass


class BackupSupervisorRejected(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BackupSupervisorClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.backup_supervisor_url).rstrip("/")
        self.bridge_key = hmac.new(
            settings.secret_key.encode(),
            b"next-stabil-backup-supervisor-v1",
            hashlib.sha256,
        ).hexdigest()

    def start_backup(self, payload: dict) -> dict:
        return self._request("POST", "/backup/run", payload)

    def backup_status(self, operation_id: str) -> dict:
        return self._request("GET", f"/backup/operations/{operation_id}")

    def discover(self, destinations: list[str], *, include_invalid: bool = False) -> dict:
        return self._request(
            "POST", "/backup/checkpoints",
            {"destinations": destinations, "include_invalid": include_invalid},
        )

    def inventory(self, destinations: list[str], *, include_invalid: bool = False) -> dict:
        return self._request(
            "POST", "/backup/checkpoints",
            {
                "destinations": destinations,
                "include_invalid": include_invalid,
                "verify": False,
            },
        )

    def verify_checkpoint(self, destination_root: str, checkpoint_path: str) -> dict:
        return self._request(
            "POST", "/backup/checkpoints/verify",
            {
                "destination_root": destination_root,
                "checkpoint_path": checkpoint_path,
            },
            timeout=300,
        )

    def preview_schedules(self, schedules: list[dict]) -> dict:
        return self._request("POST", "/backup/schedules/preview", {"schedules": schedules})

    def reconcile_schedules(self, schedules: list[dict]) -> dict:
        return self._request("POST", "/backup/schedules/reconcile", {"schedules": schedules})

    def destination_preflight(self, destination: str) -> dict:
        return self._request("POST", "/backup/destinations/preflight", {"destination": destination})

    def delete_managed_backup(self, payload: dict) -> dict:
        return self._request("POST", "/backup/managed/delete", payload)

    def _request(
        self, method: str, path: str, payload: dict | None = None, *, timeout: int = 30
    ) -> dict:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = Request(
            f"{self.base_url}{path}", method=method, data=body,
            headers={
                "X-Next-Stabil-Backup-Key": self.bridge_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
                code = str(payload.get("code") or payload.get("detail") or "backup_supervisor_rejected")
            except Exception:
                code = "backup_supervisor_rejected"
            raise BackupSupervisorRejected(code) from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise BackupSupervisorUnavailable("backup_supervisor_unavailable") from error
