from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.core.config import Settings
from app.database import init_db as init_db_module
from app.services import backup_plan_reconciler as reconciler_module


EXPECTED_REVISION = "followup_assistant_chat_history_20260829"


def _settings_values() -> dict[str, object]:
    return {
        "postgres_db": "synthetic",
        "postgres_user": "synthetic",
        "postgres_password": "synthetic-not-a-secret",
        "secret_key": "synthetic-not-a-secret",
        "admin_username": "synthetic-admin",
        "admin_email": "synthetic-admin@example.invalid",
        "admin_password": "synthetic-not-a-secret",
        "n8n_ingest_api_key": "synthetic-not-a-secret",
    }


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class _ReadOnlySession:
    def __init__(
        self,
        *,
        revision: str | None = EXPECTED_REVISION,
        role_id: int | None = 7,
        administrator: int | None = 1,
    ) -> None:
        self.revision = revision
        self.role_id = role_id
        self.administrator = administrator
        self.statements: list[tuple[str, dict[str, object] | None]] = []
        self.rollback_count = 0
        self.close_count = 0
        self.commit_count = 0
        self.add_count = 0
        self.flush_count = 0

    def execute(
        self,
        statement: object,
        parameters: dict[str, object] | None = None,
    ) -> _ScalarResult:
        sql = " ".join(str(statement).split())
        self.statements.append((sql, parameters))
        if "FROM alembic_version" in sql:
            return _ScalarResult(self.revision)
        if "FROM roles" in sql:
            return _ScalarResult(self.role_id)
        if "FROM users" in sql:
            return _ScalarResult(self.administrator)
        return _ScalarResult(None)

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1

    def commit(self) -> None:
        self.commit_count += 1
        raise AssertionError("read-only readiness must not commit")

    def add(self, _value: object) -> None:
        self.add_count += 1
        raise AssertionError("read-only readiness must not add ORM objects")

    def flush(self) -> None:
        self.flush_count += 1
        raise AssertionError("read-only readiness must not flush")


def _install_session(
    monkeypatch: pytest.MonkeyPatch,
    session: _ReadOnlySession,
) -> None:
    monkeypatch.setattr(init_db_module, "SessionLocal", lambda: session)


def test_startup_guard_settings_default_true_and_reject_invalid_values() -> None:
    current = Settings(_env_file=None, **_settings_values())

    assert current.database_startup_seed_enabled is True
    assert current.backup_plan_reconciler_enabled is True

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **_settings_values(),
            database_startup_seed_enabled="not-a-boolean",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **_settings_values(),
            backup_plan_reconciler_enabled="not-a-boolean",
        )


def test_existing_bootstrap_path_still_calls_seed_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _ReadOnlySession()
    calls = {"seed": 0}
    _install_session(monkeypatch, session)

    def seed(_session: object) -> None:
        calls["seed"] += 1

    monkeypatch.setattr(init_db_module, "seed_admin", seed)

    init_db_module.init_database()

    assert calls == {"seed": 1}
    assert session.close_count == 1


def test_read_only_ready_database_passes_without_orm_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _ReadOnlySession()
    _install_session(monkeypatch, session)

    init_db_module.verify_database_ready_read_only(
        expected_schema_revision=EXPECTED_REVISION,
        expected_admin_username="synthetic-admin",
    )

    assert [item[0] for item in session.statements] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '5000ms'",
        "SELECT version_num FROM alembic_version",
        "SELECT id FROM roles WHERE name = :role_name LIMIT 1",
        (
            "SELECT 1 FROM users WHERE username = :username "
            "AND role_id = :role_id AND is_active IS TRUE "
            "AND trashed_at IS NULL LIMIT 1"
        ),
    ]
    assert session.statements[-1][1] == {
        "username": "synthetic-admin",
        "role_id": 7,
    }
    assert session.rollback_count == 1
    assert session.close_count == 1
    assert session.commit_count == 0
    assert session.add_count == 0
    assert session.flush_count == 0


@pytest.mark.parametrize(
    ("session", "expected_error"),
    [
        (
            _ReadOnlySession(revision="wrong-revision"),
            "database_schema_revision_mismatch",
        ),
        (
            _ReadOnlySession(role_id=None),
            "database_administrator_role_missing",
        ),
        (
            _ReadOnlySession(administrator=None),
            "database_administrator_user_missing",
        ),
    ],
)
def test_read_only_database_guard_fails_closed_without_repair(
    monkeypatch: pytest.MonkeyPatch,
    session: _ReadOnlySession,
    expected_error: str,
) -> None:
    _install_session(monkeypatch, session)

    with pytest.raises(RuntimeError, match=f"^{expected_error}$"):
        init_db_module.verify_database_ready_read_only(
            expected_schema_revision=EXPECTED_REVISION,
            expected_admin_username="synthetic-admin",
        )

    assert session.rollback_count == 1
    assert session.close_count == 1
    assert session.commit_count == 0
    assert session.add_count == 0
    assert session.flush_count == 0


def test_read_only_database_guard_requires_an_expected_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = 0

    def forbidden_session() -> object:
        nonlocal opened
        opened += 1
        raise AssertionError("session must not open without expected revision")

    monkeypatch.setattr(init_db_module, "SessionLocal", forbidden_session)

    with pytest.raises(RuntimeError, match="^database_schema_revision_required$"):
        init_db_module.verify_database_ready_read_only(
            expected_schema_revision=None,
            expected_admin_username="synthetic-admin",
        )

    assert opened == 0


def test_disabled_backup_reconciler_creates_no_task_or_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"session": 0, "task": 0}

    def forbidden_session() -> object:
        calls["session"] += 1
        raise AssertionError("disabled reconciler opened a database session")

    def forbidden_task(*_args: object, **_kwargs: object) -> object:
        calls["task"] += 1
        raise AssertionError("disabled reconciler created a task")

    monkeypatch.setattr(reconciler_module, "SessionLocal", forbidden_session)
    monkeypatch.setattr(reconciler_module.asyncio, "create_task", forbidden_task)

    assert reconciler_module.start_backup_plan_reconciler(enabled=False) is None
    assert calls == {"session": 0, "task": 0}


@pytest.mark.asyncio
async def test_enabled_backup_reconciler_runs_once_and_closes_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"reconcile": 0, "wait": 0}
    wait_forever = asyncio.Event()

    def reconcile_once() -> None:
        calls["reconcile"] += 1

    async def controlled_to_thread(
        function: Callable[..., object],
        *args: object,
    ) -> object:
        if function is reconcile_once:
            function(*args)
            return None
        calls["wait"] += 1
        await wait_forever.wait()
        return None

    monkeypatch.setattr(reconciler_module, "_reconcile_once", reconcile_once)
    monkeypatch.setattr(reconciler_module.asyncio, "to_thread", controlled_to_thread)

    task = reconciler_module.start_backup_plan_reconciler()
    assert task is not None
    await asyncio.sleep(0)
    assert calls == {"reconcile": 1, "wait": 1}

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()


@pytest.mark.asyncio
async def test_all_automation_off_lifespan_reaches_yield_twice_without_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    calls = {
        "verify": 0,
        "seed": 0,
        "reconciler_start": 0,
        "task": 0,
        "yield": 0,
    }

    def verify(**kwargs: object) -> None:
        calls["verify"] += 1
        assert kwargs == {
            "expected_schema_revision": EXPECTED_REVISION,
            "expected_admin_username": "synthetic-admin",
        }

    def forbidden_seed() -> None:
        calls["seed"] += 1
        raise AssertionError("disabled bootstrap called init_database")

    original_reconciler_start = main_module.start_backup_plan_reconciler

    def reconcile_start(*, enabled: bool = True) -> asyncio.Task[Any] | None:
        calls["reconciler_start"] += 1
        return original_reconciler_start(enabled=enabled)

    def forbidden_task(*_args: object, **_kwargs: object) -> object:
        calls["task"] += 1
        raise AssertionError("all-automation-off profile created a task")

    for name in (
        "vision_automation_enabled",
        "visual_v2_enabled",
        "advanced_analysis_enabled",
        "knowledge_base_processing_enabled",
        "knowledge_base_vector_writes_enabled",
        "document_preparation_enabled",
        "assistant_pipeline_v2_enabled",
    ):
        monkeypatch.setattr(main_module.settings, name, False)
    monkeypatch.setattr(main_module.settings, "database_startup_seed_enabled", False)
    monkeypatch.setattr(main_module.settings, "backup_plan_reconciler_enabled", False)
    monkeypatch.setattr(
        main_module.settings,
        "database_schema_revision",
        EXPECTED_REVISION,
    )
    monkeypatch.setattr(main_module.settings, "admin_username", "synthetic-admin")
    monkeypatch.setattr(main_module, "verify_database_ready_read_only", verify)
    monkeypatch.setattr(main_module, "init_database", forbidden_seed)
    monkeypatch.setattr(main_module, "start_backup_plan_reconciler", reconcile_start)
    monkeypatch.setattr(main_module.asyncio, "create_task", forbidden_task)

    for _ in range(2):
        async with main_module.lifespan(FastAPI()):
            calls["yield"] += 1

    assert calls == {
        "verify": 2,
        "seed": 0,
        "reconciler_start": 2,
        "task": 0,
        "yield": 2,
    }


@pytest.mark.asyncio
async def test_failed_read_only_readiness_starts_no_automation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    starts = 0

    def fail_readiness(**_kwargs: object) -> None:
        raise RuntimeError("database_schema_revision_mismatch")

    def forbidden_start(*_args: object, **_kwargs: object) -> None:
        nonlocal starts
        starts += 1
        raise AssertionError("automation started after readiness failure")

    monkeypatch.setattr(main_module.settings, "database_startup_seed_enabled", False)
    monkeypatch.setattr(
        main_module.settings,
        "database_schema_revision",
        EXPECTED_REVISION,
    )
    monkeypatch.setattr(main_module, "verify_database_ready_read_only", fail_readiness)
    for name in (
        "start_vision_dispatcher",
        "start_knowledge_base_dispatcher",
        "start_backup_plan_reconciler",
        "start_document_preparation_dispatcher",
        "start_assistant_run_dispatcher",
        "start_visual_v2_dispatcher",
    ):
        monkeypatch.setattr(main_module, name, forbidden_start)

    with pytest.raises(RuntimeError, match="^database_schema_revision_mismatch$"):
        async with main_module.lifespan(FastAPI()):
            raise AssertionError("lifespan yielded after readiness failure")

    assert starts == 0
