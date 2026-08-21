from __future__ import annotations

import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


class AnalysisSupervisorUnavailable(RuntimeError):
    pass


class AnalysisSupervisorClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.vision_supervisor_url).rstrip("/")
        self.bridge_key = hmac.new(settings.secret_key.encode(), b"next-stabil-analysis-supervisor-v1", hashlib.sha256).hexdigest()

    def health(self) -> dict: return self._request("GET", "/analysis/health")
    def create_job(self, payload: dict) -> dict: return self._request("POST", "/analysis/jobs", payload)
    def get_job(self, job_id: str) -> dict: return self._request("GET", f"/analysis/jobs/{job_id}")
    def cancel_job(self, job_id: str) -> dict: return self._request("POST", f"/analysis/jobs/{job_id}/cancel", {})
    def resume(self) -> dict: return self._request("POST", "/analysis/resume", {})

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = Request(f"{self.base_url}{path}", method=method, data=body,
                          headers={"X-Next-Stabil-Analysis-Key": self.bridge_key, "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise AnalysisSupervisorUnavailable from error
