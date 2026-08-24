from __future__ import annotations

from collections import Counter
import json
import os
import statistics
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.services.backup_supervisor_client import BackupSupervisorClient


if os.environ.get("CHUNK22_RUNTIME_READONLY_ACCEPTANCE") != "1":
    raise RuntimeError("Set CHUNK22_RUNTIME_READONLY_ACCEPTANCE=1 explicitly")


BASE_URL = "http://127.0.0.1:8000/api/v1/admin/backups"


def admin_token() -> str:
    with SessionLocal() as db:
        user = (
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
        if user is None:
            raise RuntimeError("runtime_admin_not_found")
        return create_access_token(
            {"sub": user.username, "auth_version": user.auth_version}
        )


def get_json(path: str, token: str) -> tuple[object, float]:
    started = time.perf_counter()
    request = Request(
        BASE_URL + path,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    return payload, time.perf_counter() - started


def post_json(path: str, token: str, payload: dict) -> tuple[object, float]:
    started = time.perf_counter()
    request = Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    return result, time.perf_counter() - started


def percentile(values: list[float], value: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * value)))
    return ordered[index]


def main() -> None:
    token = admin_token()
    paths = {
        "managed": "/managed",
        "legacy": "/legacy-candidates",
        "checkpoints": "/restore-candidates",
        "history": "/runs?limit=50",
        "storage": "/storage-locations",
    }
    timing: dict[str, list[float]] = {key: [] for key in paths}
    payloads: dict[str, object] = {}
    for _ in range(5):
        for name, path in paths.items():
            payloads[name], duration = get_json(path, token)
            timing[name].append(duration)

    legacy = list(payloads["legacy"])
    storage = list(payloads["storage"])
    if not storage:
        raise RuntimeError("runtime_storage_location_not_found")
    selected = storage[0]
    browsed, _ = post_json(
        "/storage-locations/browse",
        token,
        {"location_token": selected["location_token"], "relative_path": ""},
    )
    preflight, _ = post_json(
        "/manual-v3/preflight",
        token,
        {
            "scope": "database",
            "location_token": selected["location_token"],
            "relative_path": "",
        },
    )
    classifications = Counter(str(item.get("classification")) for item in legacy)
    candidates = [
        item
        for item in legacy
        if item.get("manifest_schema") == "NEXT_STABIL_BACKUP_V1"
        and item.get("checkpoint_path")
        and item.get("destination_root")
    ]
    if not candidates:
        raise RuntimeError("runtime_legacy_candidate_not_found")
    largest = max(candidates, key=lambda item: int(item.get("total_bytes") or 0))
    supervisor = BackupSupervisorClient()
    job_id = str(uuid4())
    status = supervisor.start_legacy_verification(
        job_id=job_id,
        destination_root=str(largest["destination_root"]),
        checkpoint_path=str(largest["checkpoint_path"]),
    )
    started = time.perf_counter()
    responsive_samples: list[float] = []
    while status.get("state") not in {"READY_TO_ADOPT", "FAILED", "CANCELLED"}:
        if time.perf_counter() - started > 900:
            supervisor.cancel_legacy_verification(job_id)
            raise RuntimeError("runtime_large_verification_timeout")
        _, duration = get_json("/managed", token)
        responsive_samples.append(duration)
        time.sleep(2)
        status = supervisor.legacy_verification_status(job_id)

    print("CHUNK22_RUNTIME_READONLY_ACCEPTANCE=PASS")
    print(f"legacy_candidates={len(legacy)}")
    print(f"storage_locations={len(storage)}")
    print(f"storage_root_directories={len(browsed.get('directories') or [])}")
    print(f"manual_v3_preflight={'PASS' if preflight.get('token') else 'FAIL'}")
    print(
        "legacy_classifications="
        + ",".join(f"{key}:{value}" for key, value in sorted(classifications.items()))
    )
    print(f"large_candidate_bytes={int(largest.get('total_bytes') or 0)}")
    print(f"large_verification_state={status.get('state')}")
    print(f"large_verification_seconds={time.perf_counter() - started:.3f}")
    for name, values in timing.items():
        print(
            f"{name}_p50_ms={statistics.median(values) * 1000:.1f} "
            f"{name}_p95_ms={percentile(values, 0.95) * 1000:.1f}"
        )
    if responsive_samples:
        print(
            "managed_during_verification_p95_ms="
            f"{percentile(responsive_samples, 0.95) * 1000:.1f}"
        )


if __name__ == "__main__":
    main()
