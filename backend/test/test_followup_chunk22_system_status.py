from urllib.error import URLError
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.admin_users import require_admin
from app.main import app
from app.services.runtime_system_status_service import (
    RuntimeSystemStatusService,
    get_runtime_system_status_service,
)


class _StatusStub:
    def __init__(self) -> None:
        self.authorization = None

    def read(self, authorization: str) -> dict:
        self.authorization = authorization
        return {
            "backend": {"state": "online"},
            "supervisor": {"state": "online"},
            "next_stabil": {"state": "online"},
            "services": {"backend": "online"},
            "remote_control": {"state": "private_host_only"},
        }


def test_admin_status_is_read_only_bounded_and_forwards_token():
    stub = _StatusStub()
    app.dependency_overrides[require_admin] = lambda: object()
    app.dependency_overrides[get_runtime_system_status_service] = lambda: stub
    try:
        response = TestClient(app).get(
            "/api/v1/admin/system-status",
            headers={"Authorization": "Bearer synthetic-admin-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["supervisor"]["state"] == "online"
    assert response.json()["remote_control"]["state"] == "private_host_only"
    assert stub.authorization == "Bearer synthetic-admin-token"


def test_private_supervisor_failure_is_unknown_not_offline():
    service = RuntimeSystemStatusService("http://127.0.0.1:1")
    with patch(
        "app.services.runtime_system_status_service.urlopen",
        side_effect=URLError("synthetic-unreachable"),
    ):
        result = service.read("Bearer synthetic")

    assert result["backend"]["state"] == "online"
    assert result["supervisor"]["state"] == "unknown"
    assert result["next_stabil"]["state"] == "unknown"
    assert result["services"] == {}


def test_positive_private_status_distinguishes_online_and_offline():
    result = RuntimeSystemStatusService()._project(
        {
            "supervisor_online": True,
            "system_running": False,
            "services": {
                "backend": True,
                "qdrant": False,
                "private-debug-path": True,
            },
        }
    )
    assert result["supervisor"]["state"] == "online"
    assert result["next_stabil"]["state"] == "offline"
    assert result["services"] == {"backend": "online", "qdrant": "offline"}


def test_missing_private_fields_are_unknown():
    result = RuntimeSystemStatusService()._project({"services": {}})
    assert result["supervisor"]["state"] == "unknown"
    assert result["next_stabil"]["state"] == "unknown"


def test_system_status_requires_authentication():
    response = TestClient(app).get("/api/v1/admin/system-status")
    assert response.status_code == 401
