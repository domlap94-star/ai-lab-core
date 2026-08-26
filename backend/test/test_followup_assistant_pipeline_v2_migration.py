from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


PARENT = "followup_assistant_file_pipeline_20260826"
REVISION = "followup_assistant_pipeline_v2_20260826"
NEW_TABLES = {
    "document_intelligence_artifacts",
    "document_intelligence_sources",
    "assistant_runs",
    "assistant_run_stages",
    "assistant_run_materials",
}


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


def table_columns(schema, table: str) -> set[str]:
    return {row["name"] for row in schema.get_columns(table)}


def table_checks(schema, table: str) -> set[str]:
    return {row["name"] for row in schema.get_check_constraints(table)}


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

        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            before_analysis_jobs = connection.execute(
                text("SELECT count(*) FROM analysis_jobs")
            ).scalar_one()
            before_preparation_jobs = connection.execute(
                text("SELECT count(*) FROM document_preparation_jobs")
            ).scalar_one()

        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(NEW_TABLES <= set(schema.get_table_names()), "V2 tables missing")
            for table in NEW_TABLES:
                require(
                    connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0,
                    f"migration backfilled {table}",
                )
            require(
                connection.execute(text("SELECT count(*) FROM analysis_jobs")).scalar_one()
                == before_analysis_jobs,
                "migration changed existing AnalysisJobs",
            )
            require(
                connection.execute(text("SELECT count(*) FROM document_preparation_jobs")).scalar_one()
                == before_preparation_jobs,
                "migration changed existing preparation jobs",
            )

            require(
                {
                    "document_id", "input_checksum", "analyzer_generation", "kind",
                    "status", "validation_state", "payload", "payload_sha256",
                    "processor_id", "processor_version", "preparation_job_id",
                }
                <= table_columns(schema, "document_intelligence_artifacts"),
                "intelligence artifact contract incomplete",
            )
            require(
                {
                    "artifact_id", "source_ref", "source_kind", "source_entity_id",
                    "page_number", "source_checksum", "excerpt_sha256", "source_role",
                }
                <= table_columns(schema, "document_intelligence_sources"),
                "intelligence source binding incomplete",
            )
            require(
                {
                    "created_by_user_id", "attempt_id", "request_payload", "target_scope",
                    "complexity", "status", "current_stage", "plan", "result_payload",
                    "heartbeat_at", "cancel_requested_at", "recovery_generation",
                }
                <= table_columns(schema, "assistant_runs"),
                "AssistantRun durability contract incomplete",
            )
            require(
                {
                    "assistant_run_id", "stage_key", "stage_type", "status", "attempt",
                    "progress_current", "progress_total", "heartbeat_at", "lease_expires_at",
                    "inactivity_timeout_seconds", "absolute_cap_seconds", "analysis_job_id",
                    "document_preparation_job_id", "intelligence_artifact_id",
                }
                <= table_columns(schema, "assistant_run_stages"),
                "stage progress/recovery contract incomplete",
            )
            require(
                {
                    "assistant_run_id", "source_ref", "source_domain", "source_entity_id",
                    "source_role", "required", "readiness_level", "status",
                    "document_preparation_job_id", "intelligence_artifact_id",
                    "sensitivity", "source_manifest",
                }
                <= table_columns(schema, "assistant_run_materials"),
                "material dependency/source contract incomplete",
            )

            require(
                "ck_assistant_run_stages_time_bounds"
                in table_checks(schema, "assistant_run_stages"),
                "progress-aware stage time bounds missing",
            )
            require(
                "uq_document_intelligence_generation"
                in {
                    row["name"]
                    for row in schema.get_unique_constraints(
                        "document_intelligence_artifacts"
                    )
                },
                "intelligence generation idempotency missing",
            )
            require(
                "uq_assistant_runs_user_attempt"
                in {
                    row["name"]
                    for row in schema.get_unique_constraints("assistant_runs")
                },
                "AssistantRun create idempotency missing",
            )
            require(
                "uq_assistant_run_stage_attempt"
                in {
                    row["name"]
                    for row in schema.get_unique_constraints("assistant_run_stages")
                },
                "stage attempt audit boundary missing",
            )
            require(
                "uq_document_intelligence_current"
                in {row["name"] for row in schema.get_indexes("document_intelligence_artifacts")},
                "single current intelligence artifact gate missing",
            )

        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(
                not (NEW_TABLES & set(schema.get_table_names())),
                "downgrade retained V2 tables",
            )
            require(
                connection.execute(text("SELECT count(*) FROM analysis_jobs")).scalar_one()
                == before_analysis_jobs,
                "downgrade changed existing AnalysisJobs",
            )
            require(
                connection.execute(text("SELECT count(*) FROM document_preparation_jobs")).scalar_one()
                == before_preparation_jobs,
                "downgrade changed existing preparation jobs",
            )

        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            require(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == REVISION,
                "wrong final isolated head",
            )
            for table in NEW_TABLES:
                require(
                    connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0,
                    f"re-upgrade backfilled {table}",
                )
    finally:
        engine.dispose()

    print("FOLLOWUP_ASSISTANT_PIPELINE_V2_MIGRATION_ROUNDTRIP=PASS")
    print("ASSISTANT_RUN_BACKFILL=0")
    print("DOCUMENT_INTELLIGENCE_BACKFILL=0")
    print("EXISTING_JOB_MUTATIONS=0")


if __name__ == "__main__":
    main()
