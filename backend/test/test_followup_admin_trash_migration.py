from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


PARENT = "followup_calendar_tasks_20260820"
REVISION = "followup_admin_trash_retention_20260820"


def database_url(database_name: str) -> str:
    return (
        "postgresql+psycopg://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@"
        f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{database_name}"
    )


def row_counts(connection) -> dict[str, int]:
    return {
        table: int(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in ("clients", "documents", "users", "change_history_events")
    }


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    database_name = require_test_database_environment()
    engine = create_engine(database_url(database_name))
    config = Config("/app/alembic.ini")
    try:
        with engine.connect() as connection:
            assert_isolated_database(connection, database_name)
            before = row_counts(connection)
            current = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        require(current in {PARENT, REVISION}, f"unexpected isolated head: {current}")
        if current == REVISION:
            command.downgrade(config, PARENT)

        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, database_name)
            inspector = inspect(connection)
            require(inspector.has_table("trash_entries"), "Trash table missing")
            require(
                connection.execute(text("SELECT count(*) FROM trash_entries")).scalar_one()
                == 0,
                "migration created Trash entries",
            )
            require(row_counts(connection) == before, "upgrade rewrote business rows")

        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert_isolated_database(connection, database_name)
            inspector = inspect(connection)
            require(not inspector.has_table("trash_entries"), "downgrade retained Trash table")
            require(row_counts(connection) == before, "downgrade rewrote business rows")

        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, database_name)
            require(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == REVISION,
                "wrong final isolated head",
            )
            require(row_counts(connection) == before, "re-upgrade rewrote business rows")
    finally:
        engine.dispose()

    print("FOLLOWUP_ADMIN_TRASH_MIGRATION_ROUNDTRIP=PASS")
    print(f"isolated_database={database_name}")
    print("business_rows_rewritten=0")


if __name__ == "__main__":
    main()
