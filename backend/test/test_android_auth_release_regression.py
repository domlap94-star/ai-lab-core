from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database.engine import engine
from app.database.session import SessionLocal
from app.main import app
from app.models.role import Role
from app.models.user import User
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()
PASSWORD = "Android-Auth-Diagnostic-2026"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with engine.connect() as connection:
        assert_isolated_database(connection, TEST_DATABASE_NAME)

    with TestClient(app, raise_server_exceptions=False) as http:
        with SessionLocal() as db:
            role = db.query(Role).filter(Role.name == "User").one_or_none()
            if role is None:
                role = Role(name="User", description="Synthetic test role")
                db.add(role)
                db.flush()
            active = User(
                username="android_auth_active",
                email="android-auth-active@example.invalid",
                password_hash=hash_password(PASSWORD),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                password_reset_requested=False,
            )
            disabled = User(
                username="android_auth_disabled",
                email="android-auth-disabled@example.invalid",
                password_hash=hash_password(PASSWORD),
                role_id=role.id,
                is_active=False,
                must_change_password=False,
                password_reset_requested=False,
            )
            db.add_all([active, disabled])
            db.commit()

        valid = http.post(
            "/api/v1/auth/login",
            data={"username": active.username, "password": PASSWORD},
        )
        require(valid.status_code == 200, f"valid login failed: {valid.status_code}")
        payload = valid.json()
        token = payload.get("access_token")
        require(isinstance(token, str) and bool(token), "valid login returned no token")

        current = http.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        require(current.status_code == 200, f"session check failed: {current.status_code}")
        require(current.json().get("username") == active.username, "session user mismatch")

        invalid_password = http.post(
            "/api/v1/auth/login",
            data={"username": active.username, "password": "invalid-password"},
        )
        require(invalid_password.status_code == 401, "invalid password was not rejected")

        disabled_login = http.post(
            "/api/v1/auth/login",
            data={"username": disabled.username, "password": PASSWORD},
        )
        require(disabled_login.status_code == 401, "disabled user was not rejected")

        expired = http.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer synthetic-expired-token"},
        )
        require(expired.status_code == 401, "invalid/expired token was not rejected")

    print("ANDROID AUTH RELEASE REGRESSION: PASS")


if __name__ == "__main__":
    main()
