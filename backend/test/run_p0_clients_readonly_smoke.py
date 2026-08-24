from __future__ import annotations

from collections import Counter
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import func, or_

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.role import Role
from app.models.user import User


if os.environ.get("P0_CLIENTS_READONLY_SMOKE") != "1":
    raise RuntimeError("Set P0_CLIENTS_READONLY_SMOKE=1 explicitly")


BASE_URL = os.environ.get(
    "P0_CLIENTS_BASE_URL", "http://127.0.0.1:8000"
).rstrip("/")


def _blank(column):
    return or_(column.is_(None), func.length(func.trim(column)) == 0)


def _call(token: str, label: str, path: str) -> None:
    request = Request(
        BASE_URL + path,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
            print(f"{label}=HTTP_{response.status}/bytes_{len(body)}")
    except HTTPError as error:
        body = error.read()
        print(f"{label}=HTTP_{error.code}/bytes_{len(body)}")


def main() -> None:
    with SessionLocal() as db:
        invalid = (
            db.query(ClientAddress)
            .filter(
                ClientAddress.deleted_at.is_(None),
                _blank(ClientAddress.street),
                _blank(ClientAddress.building_number),
                _blank(ClientAddress.unit_number),
                _blank(ClientAddress.postal_code),
                _blank(ClientAddress.city),
            )
            .order_by(ClientAddress.id)
            .all()
        )
        if not invalid:
            raise RuntimeError("active_empty_address_fixture_not_found")
        print(f"INVALID_ACTIVE_ADDRESS_ROWS={len(invalid)}")
        classifications = Counter(
            (row.origin, row.source_type or "none") for row in invalid
        )
        print(
            "INVALID_ADDRESS_CLASSIFICATION="
            + ",".join(
                f"origin:{origin}/source_type:{source_type}/count:{count}"
                for (origin, source_type), count in sorted(classifications.items())
            )
        )
        target_id = invalid[0].client_id
        target_name = db.get(Client, target_id).name
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
        token = create_access_token(
            {"sub": actor.username, "auth_version": actor.auth_version}
        )

    _call(token, "CLIENTS_DEFAULT", "/api/v1/clients/page?" + urlencode({
        "sort_order": "newest", "skip": 0, "limit": 50,
    }))
    _call(token, "CLIENTS_LIMIT1", "/api/v1/clients/page?" + urlencode({
        "sort_order": "newest", "skip": 0, "limit": 1,
    }))
    _call(token, "CLIENTS_LEGACY", "/api/v1/clients?" + urlencode({
        "skip": 0, "limit": 100,
    }))
    _call(token, "CLIENTS_SEARCH", "/api/v1/clients/page?" + urlencode({
        "search": target_name, "sort_order": "newest", "skip": 0, "limit": 20,
    }))
    _call(token, "CLIENT_DETAIL", f"/api/v1/clients/{target_id}")
    _call(token, "GLOBAL_SEARCH", "/api/v1/search?" + urlencode({
        "q": target_name, "types": "client", "skip": 0, "limit": 10,
        "semantic": "false",
    }))
    _call(token, "DASHBOARD_ACTIVITY", "/api/v1/activity/recent?" + urlencode({
        "skip": 0, "limit": 1,
    }))
    _call(token, "BACKUP_MANAGED", "/api/v1/admin/backups/managed")
    _call(token, "BACKUP_LEGACY", "/api/v1/admin/backups/legacy-candidates")
    _call(token, "BACKUP_STORAGE", "/api/v1/admin/backups/storage-locations")


if __name__ == "__main__":
    main()
