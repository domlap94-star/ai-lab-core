from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from test.support.database_safety import assert_isolated_database, require_test_database_environment


PARENT = "followup_work_item_realization_link_20260821"
REVISION = "followup_admin_backup_restore_ui_20260821"


def database_url(name: str) -> str:
    return (
        "postgresql+psycopg://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@"
        f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{name}"
    )


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    name = require_test_database_environment()
    engine = create_engine(database_url(name))
    config = Config("/app/alembic.ini")
    try:
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            before = {
                table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in ("clients", "documents", "users", "work_items", "projects")
            }
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        require(current in {PARENT, REVISION}, f"unexpected head: {current}")
        if current == REVISION:
            command.downgrade(config, PARENT)
        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            for table in ("backup_schedules", "backup_runs", "restore_runs"):
                require(schema.has_table(table), f"missing {table}")
                require(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0, f"unexpected {table} backfill")
        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(not schema.has_table("backup_schedules"), "downgrade retained schedules")
            after = {
                table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in before
            }
            require(after == before, "migration changed business rows")
        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION, "wrong final head")
    finally:
        engine.dispose()
    print("FOLLOWUP_CHUNK15_MIGRATION_ROUNDTRIP=PASS")
    print("backfill=0")


if __name__ == "__main__":
    main()
