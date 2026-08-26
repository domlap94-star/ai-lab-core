from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


PARENT = "followup_backup_planner_retention_20260824"
REVISION = "followup_assistant_file_pipeline_20260826"


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

        with engine.begin() as connection:
            assert_isolated_database(connection, name)
            connection.execute(text("""
                INSERT INTO analysis_jobs (
                    id, analysis_type, source_domain, status, sensitivity,
                    input_fingerprint, reasoning_attempt_count,
                    format_retry_count
                ) VALUES (
                    '00000000-0000-0000-0000-000000000026',
                    'migration_control', 'synthetic', 'accepted_local',
                    'public_reference', :fingerprint, 0, 0
                )
                ON CONFLICT (id) DO NOTHING
            """), {"fingerprint": "a" * 64})

        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(schema.has_table("document_preparation_jobs"), "preparation table missing")
            require(
                connection.execute(text("SELECT count(*) FROM document_preparation_jobs")).scalar_one() == 0,
                "migration backfilled preparation jobs",
            )
            columns = {row["name"] for row in schema.get_columns("analysis_jobs")}
            required_columns = {
                "attempt_id", "request_payload", "result_payload",
                "waiting_document_preparation_job_id", "resume_generation",
                "last_progress_at", "cancel_requested_at",
            }
            require(required_columns <= columns, "Assistant wait columns missing")
            preserved = connection.execute(text("""
                SELECT status, resume_generation, request_payload, result_payload
                FROM analysis_jobs
                WHERE id = '00000000-0000-0000-0000-000000000026'
            """)).one()
            require(preserved[0] == "accepted_local", "existing AnalysisJob status changed")
            require(preserved[1] == 0, "existing AnalysisJob resume baseline is unsafe")
            require(preserved[2] is None and preserved[3] is None,
                    "migration inferred request/result payload")
            indexes = {row["name"] for row in schema.get_indexes("document_preparation_jobs")}
            require("ix_document_preparation_jobs_queue" in indexes, "queue index missing")
            require("uq_document_preparation_generation" in {
                row["name"] for row in schema.get_unique_constraints("document_preparation_jobs")
            }, "generation idempotency missing")

        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(not schema.has_table("document_preparation_jobs"), "downgrade retained job table")
            columns = {row["name"] for row in schema.get_columns("analysis_jobs")}
            require("request_payload" not in columns, "downgrade retained wait columns")
            require(
                connection.execute(text("""
                    SELECT count(*) FROM analysis_jobs
                    WHERE id = '00000000-0000-0000-0000-000000000026'
                      AND status = 'accepted_local'
                """)).scalar_one() == 1,
                "downgrade lost or changed existing AnalysisJob",
            )

        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            require(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION,
                "wrong final isolated head",
            )
    finally:
        engine.dispose()

    print("FOLLOWUP_ASSISTANT_FILE_PIPELINE_MIGRATION_ROUNDTRIP=PASS")
    print("HISTORICAL_DOCUMENT_BACKFILL=0")
    print("ASSISTANT_PAYLOAD_BACKFILL=0")


if __name__ == "__main__":
    main()
