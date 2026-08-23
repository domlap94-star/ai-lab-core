from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


_VALID_STATES = {"online", "offline", "unknown", "unavailable"}
_PUBLIC_SERVICE_ALLOWLIST = {
    "postgres",
    "qdrant",
    "ollama",
    "backend",
    "n8n",
    "open-webui",
}


class RuntimeSystemStatusService:
    """Read-only projection of private runtime state for authenticated admins."""

    def __init__(self, supervisor_url: str | None = None) -> None:
        self.supervisor_url = (
            supervisor_url or settings.vision_supervisor_url
        ).rstrip("/")

    def read(self, authorization: str) -> dict:
        request = Request(
            f"{self.supervisor_url}/status",
            method="GET",
            headers={"Authorization": authorization},
        )
        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid_supervisor_status")
            return self._project(payload)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ):
            return self._unknown_projection("supervisor_unreachable")

    @staticmethod
    def _state(value: object) -> str:
        if value is True:
            return "online"
        if value is False:
            return "offline"
        return "unknown"

    def _project(self, payload: dict) -> dict:
        raw_services = payload.get("services")
        services = (
            {
                str(name): self._state(value)
                for name, value in raw_services.items()
                if str(name) in _PUBLIC_SERVICE_ALLOWLIST
            }
            if isinstance(raw_services, dict)
            else {}
        )
        return {
            "backend": {"state": "online"},
            "supervisor": {
                "state": self._state(payload.get("supervisor_online")),
            },
            "next_stabil": {
                "state": self._state(payload.get("system_running")),
            },
            "services": services,
            "remote_control": {
                "state": "private_host_only",
            },
        }

    @staticmethod
    def _unknown_projection(reason: str) -> dict:
        assert "unknown" in _VALID_STATES
        return {
            "backend": {"state": "online"},
            "supervisor": {"state": "unknown", "reason": reason},
            "next_stabil": {"state": "unknown", "reason": reason},
            "services": {},
            "remote_control": {"state": "private_host_only"},
        }


def get_runtime_system_status_service() -> RuntimeSystemStatusService:
    return RuntimeSystemStatusService()
