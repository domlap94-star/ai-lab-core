from urllib.error import URLError
from unittest.mock import patch
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin_users import require_admin
from app.api.auth import get_current_user
from app.main import app
from app.services.runtime_system_status_service import (
    RuntimeSystemStatusService,
    get_runtime_system_status_service,
)
from app.services.runtime_system_control_service import (
    RuntimeSystemControlService,
    SystemControlValidation,
    get_runtime_system_control_service,
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
            "remote_control": {"state": "available"},
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
    assert response.json()["remote_control"]["state"] == "available"
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


class _Actor:
    id = 7
    auth_version = 3


class _ControlStub(RuntimeSystemControlService):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:8787", verification_timeout_seconds=0)
        self.commands = []

    def _request(self, method: str, path: str, authorization: str) -> dict:
        if method == "POST":
            self.commands.append(path)
            return {
                "status": "accepted",
                "transition_observed": path == "/restart",
            }
        return {"system_running": path == "/status" and self.commands[-1] != "/stop"}


def test_control_token_is_command_session_bound_and_single_use():
    service = _ControlStub()
    actor = _Actor()
    token, _, _ = service.issue_token(
        command="restart", actor=actor, authorization="Bearer session-a"
    )
    result = service.execute(
        token=token,
        command="restart",
        actor=actor,
        authorization="Bearer session-a",
    )
    assert result["state"] == "succeeded"
    assert service.commands == ["/restart"]
    try:
        service.execute(
            token=token,
            command="restart",
            actor=actor,
            authorization="Bearer session-a",
        )
    except SystemControlValidation as error:
        assert str(error) == "system_control_token_replayed"
    else:
        raise AssertionError("replayed control token was accepted")


def test_control_token_rejects_modified_command_and_session():
    service = _ControlStub()
    actor = _Actor()
    token, _, _ = service.issue_token(
        command="stop", actor=actor, authorization="Bearer session-a"
    )
    for command, authorization in (("start", "Bearer session-a"), ("stop", "Bearer session-b")):
        try:
            service.execute(
                token=token,
                command=command,
                actor=actor,
                authorization=authorization,
            )
        except SystemControlValidation as error:
            assert str(error) == "system_control_token_binding_invalid"
        else:
            raise AssertionError("modified control binding was accepted")


def test_control_api_requires_auth_and_rejects_invalid_command():
    assert TestClient(app).post(
        "/api/v1/admin/system-status/control/preflight",
        json={"command": "restart"},
    ).status_code == 401
    app.dependency_overrides[require_admin] = lambda: _Actor()
    app.dependency_overrides[get_runtime_system_control_service] = _ControlStub
    try:
        response = TestClient(app).post(
            "/api/v1/admin/system-status/control/preflight",
            json={"command": "shell"},
            headers={"Authorization": "Bearer session-a"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_control_api_rejects_normal_user():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=SimpleNamespace(name="User")
    )
    try:
        response = TestClient(app).post(
            "/api/v1/admin/system-status/control/preflight",
            json={"command": "restart"},
            headers={"Authorization": "Bearer synthetic-user"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
