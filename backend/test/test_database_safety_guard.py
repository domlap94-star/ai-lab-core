from __future__ import annotations

import os

from sqlalchemy import create_engine

from test.support.database_safety import (
    UnsafeTestDatabaseError,
    assert_isolated_database,
    require_test_database_environment,
)

ACTUAL_ISOLATED_DATABASE = require_test_database_environment()

# Application settings are intentionally imported only after POSTGRES_DB has
# passed the environment guard; the engine URL is fixed at import time.
from app.core.config import settings


class _ScalarResult:
    def __init__(self, value: str) -> None:
        self.value = value

    def scalar_one(self) -> str:
        return self.value


class _FakeConnection:
    def __init__(self, database: str) -> None:
        self.database = database

    def execute(self, _statement):
        return _ScalarResult(self.database)


def require_raises(callback, expected_fragment: str) -> None:
    try:
        callback()
    except UnsafeTestDatabaseError as error:
        if expected_fragment not in str(error):
            raise AssertionError(f"Unexpected guard error: {error}") from error
    else:
        raise AssertionError("Database safety guard did not fail closed")


def main() -> None:
    original_postgres_db = os.environ.get("POSTGRES_DB")
    original_database_url = os.environ.get("DATABASE_URL")
    actual_isolated = ACTUAL_ISOLATED_DATABASE
    try:
        os.environ["DATABASE_URL"] = "postgresql+psycopg://ignored/ai_lab_test_fake"
        os.environ["POSTGRES_DB"] = "ai_lab"
        require_raises(
            lambda: assert_isolated_database(_FakeConnection("ai_lab")),
            "production database 'ai_lab'",
        )

        os.environ["POSTGRES_DB"] = "ai_lab_test_safety_expected"
        require_raises(
            lambda: assert_isolated_database(
                _FakeConnection("ai_lab_test_safety_other")
            ),
            "Database isolation mismatch",
        )

        os.environ["POSTGRES_DB"] = actual_isolated
        engine = create_engine(settings.database_url)
        try:
            assert_isolated_database(engine, actual_isolated)
        finally:
            engine.dispose()
    finally:
        if original_postgres_db is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = original_postgres_db
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url

    print("TEST_DATABASE_SAFETY_GUARD=PASS")
    print("database_url_cannot_override_postgres_db=PASS")
    print("actual_current_database_match=PASS")
    print("connection_environment_mismatch_rejected=PASS")


if __name__ == "__main__":
    main()
