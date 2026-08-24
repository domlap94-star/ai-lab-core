from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import settings
from app.models.user import User


CONTROL_COMMANDS = {"start", "stop", "restart"}
CONTROL_TOKEN_TTL_SECONDS = 60
MAX_CONSUMED_TOKENS = 2048

logger = logging.getLogger("ai_lab.system_control")


class SystemControlValidation(ValueError):
    pass


class SystemControlUnavailable(RuntimeError):
    pass


class RuntimeSystemControlService:
    """Bounded authenticated bridge to the loopback-only Supervisor."""

    _consumed: dict[str, int] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        supervisor_url: str | None = None,
        *,
        verification_timeout_seconds: float = 30.0,
    ) -> None:
        self.supervisor_url = (
            supervisor_url or settings.vision_supervisor_url
        ).rstrip("/")
        self.verification_timeout_seconds = verification_timeout_seconds
        self._signing_key = hmac.new(
            settings.secret_key.encode(),
            b"next-stabil-system-control-token-v1",
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    @staticmethod
    def _session_hash(authorization: str) -> str:
        if not authorization.lower().startswith("bearer "):
            raise SystemControlValidation("system_control_session_invalid")
        return hashlib.sha256(authorization.encode()).hexdigest()

    def issue_token(
        self, *, command: str, actor: User, authorization: str
    ) -> tuple[str, datetime, str]:
        if command not in CONTROL_COMMANDS:
            raise SystemControlValidation("system_control_command_invalid")
        expires = datetime.now(timezone.utc) + timedelta(
            seconds=CONTROL_TOKEN_TTL_SECONDS
        )
        command_id = str(uuid4())
        payload = {
            "purpose": "next_stabil_system_control_v1",
            "command_id": command_id,
            "command": command,
            "user_id": actor.id,
            "auth_version": actor.auth_version,
            "session_hash": self._session_hash(authorization),
            "exp": int(expires.timestamp()),
        }
        encoded = self._b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        signature = self._b64encode(
            hmac.new(self._signing_key, encoded.encode(), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}", expires, command_id

    def _consume_token(
        self,
        *,
        token: str,
        command: str,
        actor: User,
        authorization: str,
    ) -> str:
        if command not in CONTROL_COMMANDS:
            raise SystemControlValidation("system_control_command_invalid")
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = self._b64encode(
                hmac.new(
                    self._signing_key, encoded.encode(), hashlib.sha256
                ).digest()
            )
            if not hmac.compare_digest(expected_signature, supplied_signature):
                raise ValueError
            payload = json.loads(self._b64decode(encoded).decode())
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SystemControlValidation("system_control_token_invalid") from error

        now = int(datetime.now(timezone.utc).timestamp())
        expected = {
            "purpose": "next_stabil_system_control_v1",
            "command": command,
            "user_id": actor.id,
            "auth_version": actor.auth_version,
            "session_hash": self._session_hash(authorization),
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise SystemControlValidation("system_control_token_binding_invalid")
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= now:
            raise SystemControlValidation("system_control_token_expired")
        command_id = payload.get("command_id")
        if not isinstance(command_id, str) or len(command_id) != 36:
            raise SystemControlValidation("system_control_token_invalid")

        with self._lock:
            self._consumed = {
                key: expiry
                for key, expiry in self._consumed.items()
                if expiry >= now
            }
            if command_id in self._consumed:
                raise SystemControlValidation("system_control_token_replayed")
            if len(self._consumed) >= MAX_CONSUMED_TOKENS:
                oldest = min(self._consumed, key=self._consumed.get)
                self._consumed.pop(oldest, None)
            self._consumed[command_id] = payload["exp"]
        return command_id

    def execute(
        self,
        *,
        token: str,
        command: str,
        actor: User,
        authorization: str,
    ) -> dict:
        command_id = self._consume_token(
            token=token,
            command=command,
            actor=actor,
            authorization=authorization,
        )
        try:
            accepted = self._request("POST", f"/{command}", authorization)
            if command == "restart" and accepted.get("transition_observed") is not True:
                raise SystemControlUnavailable("system_control_restart_transition_unverified")
            verified = self._verify(command, authorization)
            result = {
                "command_id": command_id,
                "command": command,
                "state": "succeeded" if verified else "failed",
                "accepted": accepted.get("status") == "accepted",
                "verification": "verified" if verified else "command_timeout",
            }
            logger.info(
                "system_control user_id=%s command=%s command_id=%s result=%s",
                actor.id,
                command,
                command_id,
                result["state"],
            )
            return result
        except Exception as error:
            logger.warning(
                "system_control user_id=%s command=%s command_id=%s result=failed error=%s",
                actor.id,
                command,
                command_id,
                error.__class__.__name__,
            )
            if isinstance(error, (SystemControlUnavailable, SystemControlValidation)):
                raise
            raise SystemControlUnavailable("system_control_supervisor_unavailable") from error

    def _verify(self, command: str, authorization: str) -> bool:
        deadline = time.monotonic() + self.verification_timeout_seconds
        while True:
            status = self._request("GET", "/status", authorization)
            running = status.get("system_running") is True
            if (command == "stop" and not running) or (
                command in {"start", "restart"} and running
            ):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(1)

    def _request(self, method: str, path: str, authorization: str) -> dict:
        request = Request(
            f"{self.supervisor_url}{path}",
            method=method,
            data=b"{}" if method == "POST" else None,
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=35) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            return payload
        except HTTPError as error:
            raise SystemControlUnavailable(
                "system_control_supervisor_rejected"
            ) from error
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemControlUnavailable(
                "system_control_supervisor_unavailable"
            ) from error


_system_control_service = RuntimeSystemControlService()


def get_runtime_system_control_service() -> RuntimeSystemControlService:
    return _system_control_service
