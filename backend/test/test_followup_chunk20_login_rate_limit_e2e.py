from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database.engine import engine
from app.database.session import SessionLocal
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.services.login_rate_limiter import login_rate_limiter
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()
PASSWORD = "Chunk20-Rate-Limit-Synthetic-2026"
TEST_USERNAMES = ("chunk20_rate_active", "chunk20_rate_disabled")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with engine.connect() as connection:
        assert_isolated_database(connection, TEST_DATABASE_NAME)

    login_rate_limiter.reset_for_tests()
    try:
        with SessionLocal() as db:
            db.query(User).filter(User.username.in_(TEST_USERNAMES)).delete(
                synchronize_session=False
            )
            db.commit()
            role = db.query(Role).filter(Role.name == "User").one_or_none()
            if role is None:
                role = Role(name="User", description="Synthetic test role")
                db.add(role)
                db.flush()
            active = User(
                username="chunk20_rate_active",
                email="chunk20-rate-active@example.invalid",
                password_hash=hash_password(PASSWORD),
                role_id=role.id,
                is_active=True,
                must_change_password=False,
                password_reset_requested=False,
            )
            disabled = User(
                username="chunk20_rate_disabled",
                email="chunk20-rate-disabled@example.invalid",
                password_hash=hash_password(PASSWORD),
                role_id=role.id,
                is_active=False,
                must_change_password=False,
                password_reset_requested=False,
            )
            db.add_all([active, disabled])
            db.commit()

        with TestClient(app, raise_server_exceptions=False) as http:
            for attempt in range(4):
                response = http.post(
                    "/api/v1/auth/login",
                    data={"username": active.username, "password": "wrong"},
                    headers={"X-Forwarded-For": f"198.51.100.{attempt + 1}"},
                )
                require(response.status_code == 401, "burst blocked before threshold")

            threshold = http.post(
                "/api/v1/auth/login",
                data={"username": active.username, "password": "wrong"},
                headers={"X-Forwarded-For": "203.0.113.250"},
            )
            require(threshold.status_code == 429, "spoofed XFF bypassed threshold")
            require(threshold.headers.get("Retry-After") == "60", "retry bound missing")

            valid = http.post(
                "/api/v1/auth/login",
                data={"username": active.username, "password": PASSWORD},
                headers={"X-Forwarded-For": "192.0.2.99"},
            )
            require(valid.status_code == 200, "valid credential was locked out")

            for username in ("chunk20_missing", disabled.username):
                login_rate_limiter.reset_for_tests()
                statuses = []
                for _ in range(5):
                    response = http.post(
                        "/api/v1/auth/login",
                        data={"username": username, "password": "wrong"},
                    )
                    statuses.append(response.status_code)
                require(statuses == [401, 401, 401, 401, 429], "anti-enumeration drift")

        print("CHUNK20_LOGIN_RATE_LIMIT_E2E=PASS")
        print("CHUNK20_LOGIN_RATE_LIMIT_ANTI_ENUMERATION=PASS")
        print("CHUNK20_LOGIN_RATE_LIMIT_VALID_BYPASS=PASS")
        print("CHUNK20_LOGIN_RATE_LIMIT_XFF_SPOOF=PASS")
    finally:
        login_rate_limiter.reset_for_tests()
        with SessionLocal() as db:
            db.query(User).filter(User.username.in_(TEST_USERNAMES)).delete(
                synchronize_session=False
            )
            db.commit()


if __name__ == "__main__":
    main()
