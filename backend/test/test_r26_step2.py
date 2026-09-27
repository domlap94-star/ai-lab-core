from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.api.client_access import router as client_access_router
from app.database.base import Base
from app.database.session import get_db
from app.models.client import Client
from app.models.client_access_grant import ClientAccessGrant
from app.models.role import Role
from app.models.user import User
from app.schemas.inspection import InspectionCreate, InspectionUpdate


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    migration = (Path(__file__).resolve().parents[1] / "alembic/versions/r26_step2_20260928.py").read_text(
        encoding="utf-8"
    )
    require("scheduled_date" in migration, "canonical date migration missing")
    require("Europe/Warsaw" in migration, "business timezone missing")
    require("WHERE scheduled_date IS NULL" in migration, "backfill overwrites data")
    require("raise RuntimeError" in migration, "forward-only downgrade guard missing")

    try:
        InspectionCreate(client_id=1)
    except ValidationError:
        pass
    else:
        raise AssertionError("create without date was accepted")
    canonical = InspectionCreate(client_id=1, scheduled_date=date(2026, 9, 27))
    require(canonical.scheduled_date == date(2026, 9, 27), "date changed")
    legacy = InspectionCreate(
        client_id=1, scheduled_at=datetime(2026, 9, 26, 22, 30, tzinfo=UTC)
    )
    require(legacy.scheduled_date == date(2026, 9, 27), "Warsaw date shifted")
    try:
        InspectionCreate.model_validate(
            {"client_id": 1, "scheduled_date": "2026-09-27T00:00:00Z"}
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("datetime accepted as scheduled_date")
    try:
        InspectionUpdate(
            scheduled_date=date(2026, 9, 28),
            started_at=datetime(2026, 9, 27, 10, tzinfo=UTC),
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("conflicting canonical and legacy dates accepted")

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.create_function("char_length", 1, len),
    )
    tables = [
        Base.metadata.tables[name]
        for name in ("roles", "users", "industries", "clients", "client_access_grants")
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine, expire_on_commit=False) as db:
        manager_role = Role(id=1, name="User", description="User")
        external_role = Role(id=2, name="External", description="External")
        manager = User(
            id=1,
            username="r26-manager",
            email="r26-manager@example.invalid",
            password_hash="unused",
            is_active=True,
            role=manager_role,
        )
        external = User(
            id=2,
            username="r26-external",
            email="r26-external@example.invalid",
            password_hash="unused",
            is_active=True,
            role=external_role,
        )
        clients = [
            Client(id=value, client_type="company", name=f"R26 Client {value}", country_code="PL")
            for value in (101, 102, 103)
        ]
        db.add_all([manager_role, external_role, manager, external, *clients])
        db.flush()
        grants = [
            ClientAccessGrant(
                id=value,
                client_id=client.id,
                external_user_id=external.id,
                granted_by_user_id=manager.id,
                granted_at=datetime(2026, 9, 28, 10, tzinfo=UTC),
            )
            for value, client in zip((201, 202, 203), clients)
        ]
        db.add_all(grants)
        db.commit()

        app = FastAPI()
        app.include_router(client_access_router, prefix="/api/v1")
        actor = {"value": manager}
        app.dependency_overrides[get_current_user] = lambda: actor["value"]
        app.dependency_overrides[get_db] = lambda: db
        http = TestClient(app)
        active_page = http.get("/api/v1/client-access/grants", params={"active": True})
        require(active_page.status_code == 200, active_page.text)
        require(active_page.json()["total"] == 3, "query-level active count failed")
        result = http.post(
            "/api/v1/client-access/grants/bulk-revoke",
            json={"grant_ids": [201, 201, 202]},
        )
        require(result.status_code == 200, result.text)
        require(result.json()["revoked_count"] == 2, "dedupe failed")
        db.refresh(grants[0])
        db.refresh(grants[1])
        require(grants[0].revoked_at == grants[1].revoked_at, "timestamps differ")
        require(grants[0].revoked_by_user_id == manager.id, "actor missing")

        stale = http.post(
            "/api/v1/client-access/grants/bulk-revoke",
            json={"grant_ids": [202, 203]},
        )
        require(stale.status_code == 409, stale.text)
        db.refresh(grants[2])
        require(grants[2].revoked_at is None, "atomic rollback failed")
        actor["value"] = external
        require(
            http.post(
                "/api/v1/client-access/grants/bulk-revoke",
                json={"grant_ids": [203]},
            ).status_code
            == 403,
            "External bulk revoke was not denied",
        )
        actor["value"] = manager
        require(
            http.post(
                "/api/v1/client-access/grants/bulk-revoke", json={"grant_ids": []}
            ).status_code
            == 422,
            "empty bulk list was accepted",
        )
        http.close()

    print("R26_STEP2_MIGRATION_AND_DATE_CONTRACT_PASS")
    print("R26_STEP2_BULK_REVOKE_ATOMIC_PASS")


if __name__ == "__main__":
    main()
