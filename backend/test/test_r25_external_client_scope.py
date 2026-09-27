from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.database.base import Base
from app.models.client import Client
from app.models.client_access_grant import ClientAccessGrant
from app.models.document import Document
from app.models.role import Role
from app.models.project import Project
from app.models.inspection import Inspection
from app.models.user import User
from app.services.client_scope_service import ClientScopeNotFound, ClientScopeService
from app.services.client_access_grant_service import ClientAccessGrantService
from app.repositories.project_repository import ProjectRepository
from app.repositories.inspection_repository import InspectionRepository
from app.api.auth import get_current_user
from app.api.client_access import router as client_access_router
from app.api.client_scope import guard_path_resource
from app.database.session import get_db


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def user(user_id: int, name: str, role: Role) -> User:
    return User(
        id=user_id,
        username=name,
        email=f"{name}@example.invalid",
        password_hash="not-used",
        is_active=True,
        role=role,
    )


def client(client_id: int, name: str) -> Client:
    return Client(
        id=client_id,
        client_type="company",
        name=name,
        country_code="PL",
    )


def main() -> None:
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
        for name in ("roles", "users", "industries", "clients", "projects", "work_items", "inspections", "client_access_grants")
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine, expire_on_commit=False) as db:
        admin_role = Role(id=1, name="Administrator", description="Admin")
        user_role = Role(id=2, name="User", description="User")
        external_role = Role(id=3, name="External", description="External")
        admin = user(1, "admin", admin_role)
        normal = user(2, "normal", user_role)
        external = user(3, "external", external_role)
        a = client(101, "Client A")
        b = client(102, "Client B")
        db.add_all([admin_role, user_role, external_role, admin, normal, external, a, b])
        db.flush()
        project_a = Project(
            id=998,
            client_id=a.id,
            name="Project A",
            status="active",
            country_code="PL",
            created_by_user_id=admin.id,
            updated_by_user_id=admin.id,
        )
        project_b = Project(
            id=999,
            client_id=b.id,
            name="Project B",
            status="active",
            country_code="PL",
            created_by_user_id=admin.id,
            updated_by_user_id=admin.id,
        )
        inspection_a = Inspection(id=701, client_id=a.id, project_id=project_a.id, title="Inspection A", status="planned")
        inspection_b = Inspection(id=702, client_id=b.id, project_id=project_b.id, title="Inspection B", status="planned")
        db.add_all([project_a, project_b, inspection_a, inspection_b])
        db.flush()
        grant = ClientAccessGrant(
            id=1001,
            client_id=a.id,
            external_user_id=external.id,
            granted_by_user_id=admin.id,
            granted_at=a.created_at,
        )
        db.add(grant)
        db.commit()

        policy = ClientScopeService(db)
        scoped = policy.scope_client_query(external, db.query(Client), Client.id)
        require([row.id for row in scoped.order_by(Client.id)] == [a.id], "External list leaked B")
        require(policy.can_access_client(external, a.id), "Grant A was ignored")
        require(not policy.can_access_client(external, b.id), "Direct B access leaked")
        projects, project_total = ProjectRepository(db).get_page(
            search=None, client_id=None, status=None, skip=0, limit=50, viewer=external
        )
        require(project_total == 1 and [row.id for row in projects] == [project_a.id], "Project list leaked B")
        inspections, inspection_total = InspectionRepository(db).get_page(
            search=None,
            project_id=None,
            client_id=None,
            status=None,
            date_from=None,
            date_to=None,
            skip=0,
            limit=50,
            viewer=external,
        )
        require(inspection_total == 1 and [row.id for row in inspections] == [inspection_a.id], "Inspection list leaked B")
        try:
            policy.require_client_access(external, b.id)
        except ClientScopeNotFound:
            pass
        else:
            raise AssertionError("B did not fail closed")

        require(
            [row.id for row in policy.scope_client_query(normal, db.query(Client), Client.id).order_by(Client.id)]
            == [a.id, b.id],
            "User behavior regressed",
        )

        grant.revoked_at = a.created_at
        grant.revoked_by_user_id = normal.id
        db.commit()
        require(not policy.can_access_client(external, a.id), "Revoke was not immediate")

        external.role = user_role
        db.commit()
        require(policy.can_access_client(external, b.id), "External -> User did not restore User scope")
        external.role = external_role
        db.commit()
        require(not policy.can_access_client(external, a.id), "Role restore ignored revoked history")

        regranted = ClientAccessGrantService(db).grant(
            client_id=a.id, external_user_id=external.id, actor=normal
        )
        require(regranted.active, "Regrant did not create an active record")
        require(regranted.id != grant.id, "Regrant overwrote audit history")
        active_retry = ClientAccessGrantService(db).grant(
            client_id=a.id, external_user_id=external.id, actor=normal
        )
        require(active_retry.id == regranted.id, "Grant retry was not idempotent")
        revoked = ClientAccessGrantService(db).revoke(
            client_id=a.id, external_user_id=external.id, actor=normal
        )
        require(revoked is not None and not revoked.active, "Revoke did not persist history")
        require(not policy.can_access_client(external, a.id), "Service revoke was not immediate")

        probe = FastAPI()
        probe.include_router(client_access_router, prefix="/api/v1")

        @probe.get("/api/v1/clients/{client_id}", dependencies=[Depends(guard_path_resource)])
        def guarded_client(client_id: int) -> dict[str, int]:
            return {"id": client_id}

        actor = {"value": normal}
        probe.dependency_overrides[get_current_user] = lambda: actor["value"]
        probe.dependency_overrides[get_db] = lambda: db
        http = TestClient(probe)
        created = http.post(
            "/api/v1/client-access/grants",
            json={"client_id": a.id, "external_user_id": external.id},
        )
        require(created.status_code == 201, f"HTTP grant failed: {created.text}")
        require(
            http.post(
                "/api/v1/client-access/grants",
                json={"client_id": a.id, "external_user_id": external.id},
            ).json()["id"]
            == created.json()["id"],
            "HTTP grant retry was not idempotent",
        )
        actor["value"] = external
        shared = http.get("/api/v1/client-access/shared-clients")
        require(shared.status_code == 200, shared.text)
        require([row["id"] for row in shared.json()] == [a.id], "Shared-client HTTP list leaked")
        require(http.get(f"/api/v1/clients/{a.id}").status_code == 200, "Granted A HTTP guard failed")
        require(http.get(f"/api/v1/clients/{b.id}").status_code == 404, "B direct ID did not return 404")
        require(http.get("/api/v1/client-access/grants").status_code == 403, "External managed grants")
        actor["value"] = normal
        require(
            http.delete(
                "/api/v1/client-access/grants",
                params={"client_id": a.id, "external_user_id": external.id},
            ).status_code
            == 204,
            "HTTP revoke failed",
        )
        actor["value"] = external
        require(http.get(f"/api/v1/clients/{a.id}").status_code == 404, "HTTP revoke was not immediate")
        http.close()

        conflicting = Document(
            id=501,
            filename="fixture.txt",
            original_filename="fixture.txt",
            content_type="text/plain",
            file_size=1,
            client_id=a.id,
            project_id=999,
        )
        resolved = policy.resolve_resource_client_scope(conflicting)
        require(not resolved.resolved, "Ambiguous document owner did not fail closed")

    migration = Path("backend/alembic/versions/r25_external_scope_20260927.py").read_text(encoding="utf-8")
    require("revoked_at IS NULL" in migration, "Partial active-grant uniqueness is missing")
    require("'External'" in migration, "External role seed is missing")
    require("client_access_grants" in migration, "Grant table migration is missing")
    print("R25_EXTERNAL_SCOPE_A_B_PASS")
    print("R25_REVOKE_AND_ROLE_CHANGE_PASS")
    print("R25_MIGRATION_CONTRACT_PASS")
    print("R25_HTTP_GRANT_AND_DIRECT_ID_PASS")


if __name__ == "__main__":
    main()
