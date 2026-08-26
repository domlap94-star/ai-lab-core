from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.models.role import Role
from app.models.user import User


if os.environ.get("ASSISTANT_PIPELINE_V2_LIVE_SMOKE") != "1":
    raise RuntimeError("Set ASSISTANT_PIPELINE_V2_LIVE_SMOKE=1 explicitly")


BASE_URL = os.environ.get(
    "ASSISTANT_PIPELINE_V2_BASE_URL", "http://127.0.0.1:8000"
).rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except HTTPError as error:
        raw = error.read()
        parsed = json.loads(raw) if raw else {}
        return error.code, parsed


def _admin_token() -> str:
    with SessionLocal() as db:
        actor = (
            db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(
                User.is_active.is_(True),
                User.trashed_at.is_(None),
                Role.name.in_(("admin", "administrator", "Administrator")),
            )
            .order_by(User.id)
            .first()
        )
        if actor is None:
            raise RuntimeError("runtime_admin_not_found")
        return create_access_token(
            {"sub": actor.username, "auth_version": actor.auth_version}
        )


def main() -> None:
    payload = {
        "question": "Czym zajmuje się Asystent AI?",
        "attempt_id": datetime.now(UTC).strftime("v2smoke%Y%m%d%H%M%S%f"),
        "conversation": [],
    }
    unauth_status, _ = _request(
        "POST", "/api/v1/ai/assistant/runs", payload=payload
    )
    if unauth_status != 401:
        raise RuntimeError(f"unauthenticated_contract_failed:{unauth_status}")
    print("V2_UNAUTHENTICATED=HTTP_401")

    token = _admin_token()
    create_status, created = _request(
        "POST", "/api/v1/ai/assistant/runs", token=token, payload=payload
    )
    if create_status != 202:
        raise RuntimeError(f"create_failed:{create_status}")
    run_id = created["run_id"]
    print(
        "V2_CREATE="
        f"HTTP_202/status_{created['status']}/stage_{created.get('current_stage')}"
    )

    terminal = None
    for _ in range(30):
        status_code, current = _request(
            "GET", f"/api/v1/ai/assistant/runs/{run_id}", token=token
        )
        if status_code != 200:
            raise RuntimeError(f"poll_failed:{status_code}")
        if current["status"] in {"completed", "review_required", "failed", "cancelled"}:
            terminal = current
            break
        time.sleep(1)
    if terminal is None:
        raise RuntimeError("terminal_result_timeout")
    result = terminal.get("result") or {}
    source_types = sorted(
        {source.get("source_type", "unknown") for source in result.get("sources", [])}
    )
    if terminal["status"] != "completed" or result.get("status") != "accepted_local":
        raise RuntimeError(
            f"unexpected_terminal:{terminal['status']}/{result.get('status')}"
        )
    print(
        "V2_TERMINAL="
        f"status_{terminal['status']}/result_{result['status']}/"
        f"stage_{terminal.get('current_stage')}/sources_{','.join(source_types)}"
    )


if __name__ == "__main__":
    main()
