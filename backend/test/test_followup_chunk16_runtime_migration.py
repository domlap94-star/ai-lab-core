from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from test.support.database_safety import assert_isolated_database, require_test_database_environment


PARENT = "followup_admin_backup_restore_ui_20260821"
REVISION = "followup_admin_knowledge_base_20260821"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def database_url(name: str) -> str:
    return (
        "postgresql+psycopg://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@"
        f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{name}"
    )


def main() -> None:
    name = require_test_database_environment()
    engine = create_engine(database_url(name))
    config = Config("/app/alembic.ini")
    try:
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        require(current in {PARENT, REVISION}, f"unexpected head: {current}")
        if current == REVISION:
            command.downgrade(config, PARENT)
        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            for table in (
                "knowledge_base_items", "knowledge_base_pages", "analysis_jobs",
                "analysis_job_sources", "knowledge_base_processing_jobs",
                "knowledge_base_analysis_artifacts",
            ):
                require(schema.has_table(table), f"missing {table}")
                require(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0,
                        f"unexpected backfill in {table}")
            item_checks = {row["name"] for row in schema.get_check_constraints("knowledge_base_items")}
            require("ck_knowledge_base_items_analysis_status" in item_checks,
                    "analysis status constraint missing")
            require("ck_knowledge_base_items_indexing_status" in item_checks,
                    "indexing status constraint missing")
            analysis_indexes = {row["name"] for row in schema.get_indexes("analysis_jobs")}
            processing_indexes = {row["name"] for row in schema.get_indexes("knowledge_base_processing_jobs")}
            require("uq_analysis_jobs_active_fingerprint" in analysis_indexes,
                    "active fingerprint uniqueness missing")
            require("uq_kb_processing_active_item" in processing_indexes,
                    "single-item processing uniqueness missing")
        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(not schema.has_table("analysis_jobs"), "downgrade retained analysis jobs")
            require(not schema.has_table("knowledge_base_items"), "downgrade retained Knowledge Base")
        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION,
                    "wrong final head")
    finally:
        engine.dispose()
    print("FOLLOWUP_CHUNK16_RUNTIME_MIGRATION_ROUNDTRIP=PASS")
    print("BACKFILL=0")


if __name__ == "__main__":
    main()
