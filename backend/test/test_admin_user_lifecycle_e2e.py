from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.security import hash_password
from app.database.base import Base
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.role import Role
from app.models.user import User
from app.models.user_lifecycle_event import UserLifecycleEvent
from app.services.user_lifecycle_service import (
    DEACTIVATED,
    UserLifecycleAuthorizationError,
    UserLifecycleConflictError,
    UserLifecycleService,
)


PASSWORD = "Lifecycle-Test-Password-2026"
NEW_PASSWORD = "Lifecycle-New-Password-2026"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@contextmanager
def isolated_database():
    schema = f"user_lifecycle_test_{uuid4().hex}"
    connection = engine.connect()
    assert_isolated_database(connection, TEST_DATABASE_NAME)
    outer = connection.begin()
    try:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        Base.metadata.create_all(
            bind=connection,
            tables=[
                Role.__table__,
                User.__table__,
                Conversation.__table__,
                Message.__table__,
                UserLifecycleEvent.__table__,
            ],
        )
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield db
        finally:
            db.close()
    finally:
        outer.rollback()
        connection.close()


def make_user(
    *,
    suffix: str,
    role: Role,
    is_active: bool = True,
) -> User:
    return User(
        username=f"lifecycle_{suffix}",
        email=f"lifecycle_{suffix}@example.invalid",
        password_hash=hash_password(PASSWORD),
        is_active=is_active,
        must_change_password=False,
        password_reset_requested=False,
        role=role,
    )


def login(client: TestClient, username: str, password: str = PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    require(response.status_code == 200, f"Login failed: {response.text}")
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    with isolated_database() as db:
        administrator = Role(name="Administrator", description="Admin")
        normal_role = Role(name="User", description="User")
        db.add_all([administrator, normal_role])
        db.flush()

        admin_a = make_user(suffix="admin_a", role=administrator)
        admin_b = make_user(suffix="admin_b", role=administrator)
        normal = make_user(suffix="normal", role=normal_role)
        inactive = make_user(
            suffix="inactive",
            role=normal_role,
            is_active=False,
        )
        audit_failure_target = make_user(
            suffix="audit_failure",
            role=normal_role,
        )
        db.add_all([admin_a, admin_b, normal, inactive, audit_failure_target])
        db.flush()
        conversation = Conversation(
            user_id=normal.id,
            title="Preserved lifecycle fixture",
            model="test-model",
        )
        db.add(conversation)
        db.flush()
        # Release fixture setup into the external transaction. Endpoint-level
        # rollback can then discard only its own savepoint; the outer rollback
        # still removes the entire isolated schema at test completion.
        db.commit()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                anonymous = client.post(
                    f"/api/v1/admin/users/{normal.id}/deactivate"
                )
                require(anonymous.status_code == 401, "Anonymous must be 401")

                normal_token = login(client, normal.username)
                normal_forbidden = client.post(
                    f"/api/v1/admin/users/{admin_b.id}/deactivate",
                    headers=headers(normal_token),
                )
                require(normal_forbidden.status_code == 403, "User must be 403")

                admin_token = login(client, admin_a.username)
                missing = client.post(
                    "/api/v1/admin/users/999999/deactivate",
                    headers=headers(admin_token),
                )
                require(missing.status_code == 404, "Missing target must be 404")

                inactive_result = client.post(
                    f"/api/v1/admin/users/{inactive.id}/deactivate",
                    headers=headers(admin_token),
                )
                require(
                    inactive_result.status_code == 409,
                    f"Inactive target must be 409: {inactive_result.text}",
                )
                require(
                    db.query(UserLifecycleEvent)
                    .filter(UserLifecycleEvent.target_user_id == inactive.id)
                    .count()
                    == 0,
                    "Inactive retry must not create audit",
                )

                self_result = client.post(
                    f"/api/v1/admin/users/{admin_a.id}/deactivate",
                    headers=headers(admin_token),
                )
                require(self_result.status_code == 409, "Self must be 409")
                require(admin_a.is_active, "Self target must remain active")
                require(
                    db.query(UserLifecycleEvent)
                    .filter(UserLifecycleEvent.target_user_id == admin_a.id)
                    .count()
                    == 0,
                    "Self rejection created audit",
                )

                try:
                    UserLifecycleService.ensure_admin_survives(
                        target_user_id=admin_a.id,
                        active_administrator_ids={admin_a.id},
                    )
                except UserLifecycleConflictError:
                    pass
                else:
                    raise AssertionError("Last-admin policy did not reject")

                admin_b_result = client.post(
                    f"/api/v1/admin/users/{admin_b.id}/deactivate",
                    headers=headers(admin_token),
                )
                require(admin_b_result.status_code == 200, admin_b_result.text)
                require(not admin_b.is_active, "Admin B must be inactive")
                require(admin_a.is_active, "Admin A must remain active")

                try:
                    UserLifecycleService(db).deactivate_user(
                        actor_user_id=admin_b.id,
                        target_user_id=admin_a.id,
                    )
                except UserLifecycleAuthorizationError:
                    db.rollback()
                else:
                    raise AssertionError("Stale inactive actor was accepted")
                require(admin_a.is_active, "Concurrent survivor must stay active")

                active_reset = client.post(
                    f"/api/v1/admin/users/{normal.id}/reset-password",
                    json={"temporary_password": NEW_PASSWORD},
                    headers=headers(admin_token),
                )
                require(active_reset.status_code == 200, active_reset.text)

                normal_token = login(client, normal.username, NEW_PASSWORD)
                before_identity = (
                    normal.username,
                    normal.email,
                    normal.role_id,
                    normal.password_hash,
                )
                normal_result = client.post(
                    f"/api/v1/admin/users/{normal.id}/deactivate",
                    headers=headers(admin_token),
                )
                require(normal_result.status_code == 200, normal_result.text)
                require(
                    normal_result.json()
                    == {
                        "status": "deactivated",
                        "user_id": normal.id,
                        "is_active": False,
                    },
                    "Unexpected deactivate response",
                )

                require(
                    client.get("/api/v1/auth/me", headers=headers(normal_token)).status_code
                    == 401,
                    "Existing token must fail /auth/me",
                )
                require(
                    client.get("/api/v1/users/me", headers=headers(normal_token)).status_code
                    == 401,
                    "Existing token must fail protected API",
                )
                inactive_login = client.post(
                    "/api/v1/auth/login",
                    data={"username": normal.username, "password": NEW_PASSWORD},
                )
                require(inactive_login.status_code == 401, "Inactive login must fail")
                require(
                    inactive_login.json()["detail"]
                    == "Incorrect username or password",
                    "Inactive login must remain generic",
                )

                db.refresh(normal)
                require(not normal.is_active, "Normal target must be inactive")
                require(
                    (
                        normal.username,
                        normal.email,
                        normal.role_id,
                        normal.password_hash,
                    )
                    == before_identity,
                    "Identity/password fields changed during deactivation",
                )
                require(
                    db.query(Conversation)
                    .filter(Conversation.user_id == normal.id)
                    .count()
                    == 1,
                    "Conversation must be preserved",
                )
                events = (
                    db.query(UserLifecycleEvent)
                    .filter(
                        UserLifecycleEvent.target_user_id == normal.id,
                        UserLifecycleEvent.action == DEACTIVATED,
                    )
                    .all()
                )
                require(len(events) == 1, "Exactly one audit event required")
                require(events[0].actor_user_id == admin_a.id, "Wrong actor")
                require(events[0].created_at is not None, "Missing timestamp")
                require(
                    set(events[0].__table__.columns.keys())
                    == {
                        "id",
                        "actor_user_id",
                        "target_user_id",
                        "action",
                        "created_at",
                    },
                    "Audit schema contains unexpected sensitive fields",
                )

                duplicate = client.post(
                    f"/api/v1/admin/users/{normal.id}/deactivate",
                    headers=headers(admin_token),
                )
                require(duplicate.status_code == 409, "Repeat must be 409")
                require(
                    db.query(UserLifecycleEvent)
                    .filter(UserLifecycleEvent.target_user_id == normal.id)
                    .count()
                    == 1,
                    "Repeat created duplicate audit",
                )

                password_before = normal.password_hash
                inactive_reset = client.post(
                    f"/api/v1/admin/users/{normal.id}/reset-password",
                    json={"temporary_password": PASSWORD},
                    headers=headers(admin_token),
                )
                require(inactive_reset.status_code == 409, "Inactive reset must be 409")
                db.refresh(normal)
                require(normal.password_hash == password_before, "Inactive password changed")

                def fail_audit(session, _flush_context, _instances) -> None:
                    if any(
                        isinstance(value, UserLifecycleEvent)
                        and value.target_user_id == audit_failure_target.id
                        for value in session.new
                    ):
                        raise RuntimeError("simulated audit failure")

                event.listen(db, "before_flush", fail_audit)
                try:
                    failed = client.post(
                        f"/api/v1/admin/users/{audit_failure_target.id}/deactivate",
                        headers=headers(admin_token),
                    )
                finally:
                    event.remove(db, "before_flush", fail_audit)
                require(failed.status_code == 500, "Audit failure must fail request")
                db.refresh(audit_failure_target)
                require(
                    audit_failure_target.is_active,
                    "Audit failure left partial deactivation",
                )
                require(
                    db.query(UserLifecycleEvent)
                    .filter(
                        UserLifecycleEvent.target_user_id
                        == audit_failure_target.id
                    )
                    .count()
                    == 0,
                    "Audit failure persisted event",
                )

                created = client.post(
                    "/api/v1/admin/users",
                    json={
                        "username": "lifecycle_created",
                        "email": "lifecycle_created@example.invalid",
                        "role": "User",
                        "temporary_password": PASSWORD,
                        "must_change_password": True,
                    },
                    headers=headers(admin_token),
                )
                require(created.status_code == 201, "Create regression failed")
                created_id = created.json()["id"]
                created_token = login(client, "lifecycle_created")
                created_me = client.get(
                    "/api/v1/auth/me",
                    headers=headers(created_token),
                )
                require(
                    created_me.status_code == 200
                    and created_me.json()["must_change_password"] is True,
                    "Forced password-change state regressed",
                )
                changed = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": PASSWORD,
                        "new_password": NEW_PASSWORD,
                    },
                    headers=headers(created_token),
                )
                require(changed.status_code == 200, "Change password regressed")
                login(client, "lifecycle_created", NEW_PASSWORD)

                reset_requested = client.post(
                    "/api/v1/auth/reset-password/request",
                    json={"identifier": "lifecycle_created"},
                )
                require(
                    reset_requested.status_code == 202,
                    "Password reset request regressed",
                )
                created_user = db.get(User, created_id)
                require(
                    created_user is not None
                    and created_user.password_reset_requested,
                    "Password reset request flag missing",
                )

                duplicate_inactive_identity = client.post(
                    "/api/v1/admin/users",
                    json={
                        "username": inactive.username,
                        "email": "other@example.invalid",
                        "role": "User",
                        "temporary_password": PASSWORD,
                        "must_change_password": True,
                    },
                    headers=headers(admin_token),
                )
                require(
                    duplicate_inactive_identity.status_code == 409,
                    "Inactive identity uniqueness was bypassed",
                )

                listed = client.get(
                    "/api/v1/admin/users",
                    headers=headers(admin_token),
                )
                require(listed.status_code == 200, "List regression failed")
                require(
                    all(row["id"] != normal.id for row in listed.json()),
                    "Inactive user appeared in the canonical active-user list",
                )
        finally:
            app.dependency_overrides.clear()

    print("ADMIN USER LIFECYCLE E2E: OK")
    print("physical deletes: 0")
    print("production user modifications: 0 (isolated schema rolled back)")


if __name__ == "__main__":
    main()
