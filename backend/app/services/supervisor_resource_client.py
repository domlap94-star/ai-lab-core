from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


class SupervisorResourceTelemetryUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowsResourceTelemetry:
    physical_total_bytes: int
    physical_available_bytes: int
    timestamp: datetime


class SupervisorResourceClient:
    """Read bounded host-memory telemetry over the private Supervisor bridge."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.vision_supervisor_url).rstrip("/")
        self.bridge_key = hmac.new(
            settings.secret_key.encode(),
            b"next-stabil-resource-supervisor-v1",
            hashlib.sha256,
        ).hexdigest()

    def snapshot(self) -> WindowsResourceTelemetry:
        request = Request(
            f"{self.base_url}/resource/telemetry",
            method="GET",
            headers={"X-Next-Stabil-Resource-Key": self.bridge_key},
        )
        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            total = int(payload["physical_total_bytes"])
            available = int(payload["physical_available_bytes"])
            timestamp = datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
            if total <= 0 or available < 0 or available > total:
                raise ValueError("invalid host-memory telemetry")
            return WindowsResourceTelemetry(
                physical_total_bytes=total,
                physical_available_bytes=available,
                timestamp=timestamp,
            )
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise SupervisorResourceTelemetryUnavailable(
                "LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE"
            ) from error
