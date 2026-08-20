from __future__ import annotations

from collections.abc import Mapping
import os
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session


PRODUCTION_DATABASES = frozenset({"ai_lab"})
_SAFE_TEST_DATABASE = re.compile(
    r"^ai_lab_(?:test(?:_[a-z0-9]+)+|chunk[a-z0-9_]*|isolated(?:_[a-z0-9]+)+)$"
)


class UnsafeTestDatabaseError(RuntimeError):
    """Raised before a mutating test can use a non-isolated database."""


def require_test_database_environment(
    expected_database: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Validate POSTGRES_DB before any application engine is imported."""

    values = os.environ if environ is None else environ
    configured = values.get("POSTGRES_DB", "").strip()
    if configured in PRODUCTION_DATABASES:
        raise UnsafeTestDatabaseError(
            "Refusing mutating test against production database 'ai_lab'. "
            "Set POSTGRES_DB to an explicitly created isolated test database."
        )
    if not configured:
        raise UnsafeTestDatabaseError(
            "Refusing mutating test without an explicit POSTGRES_DB test database."
        )
    if not _SAFE_TEST_DATABASE.fullmatch(configured):
        raise UnsafeTestDatabaseError(
            f"Refusing mutating test against unsafe database name {configured!r}. "
            "Use ai_lab_test_*, ai_lab_chunk*, or ai_lab_isolated_*."
        )
    if expected_database is not None and configured != expected_database:
        raise UnsafeTestDatabaseError(
            f"POSTGRES_DB mismatch: expected {expected_database!r}, got {configured!r}."
        )
    return configured


def _current_database(executor: Any) -> str:
    in_transaction = getattr(executor, "in_transaction", None)
    had_transaction = bool(in_transaction()) if callable(in_transaction) else False
    actual = str(executor.execute(text("SELECT current_database()")).scalar_one())
    # SQLAlchemy autobegins even for SELECT. Do not leave that guard-only
    # transaction open, but never interfere with a transaction owned by a test.
    if not had_transaction and callable(in_transaction) and in_transaction():
        executor.rollback()
    return actual


def assert_isolated_database(
    target: Engine | Connection | Session | Any,
    expected_database: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Verify the connected PostgreSQL database, not merely configuration."""

    configured = require_test_database_environment(
        expected_database,
        environ=environ,
    )
    if isinstance(target, Engine):
        with target.connect() as connection:
            actual = _current_database(connection)
    else:
        actual = _current_database(target)
    if actual in PRODUCTION_DATABASES:
        raise UnsafeTestDatabaseError(
            "Refusing mutating test against production database 'ai_lab'. "
            "Set POSTGRES_DB to an explicitly created isolated test database."
        )
    if not _SAFE_TEST_DATABASE.fullmatch(actual):
        raise UnsafeTestDatabaseError(
            f"Connected database {actual!r} does not use an approved isolated-test name."
        )
    if actual != configured:
        raise UnsafeTestDatabaseError(
            f"Database isolation mismatch: POSTGRES_DB={configured!r}, "
            f"but SELECT current_database() returned {actual!r}."
        )
    return actual
