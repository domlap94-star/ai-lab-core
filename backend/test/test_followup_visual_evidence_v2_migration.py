from __future__ import annotations

import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


PARENT = "followup_assistant_chat_history_20260829"
REVISION = "followup_visual_evidence_v2_20260831"

NEW_TABLES = {
    "document_material_generations",
    "document_material_sources",
    "source_privacy_assessments",
    "visual_analysis_requests",
    "visual_analysis_runs",
    "visual_analysis_stages",
    "visual_source_requirements",
    "visual_analysis_sources",
    "visual_requirement_source_bindings",
    "visual_comparison_groups",
    "visual_comparison_group_members",
    "visual_source_authorizations",
    "visual_analysis_consumers",
    "visual_external_batches",
    "visual_external_batch_sources",
    "visual_external_batch_source_requirements",
    "validated_visual_batch_results",
    "visual_evidence_artifacts",
    "visual_evidence_artifact_batches",
    "visual_evidence_atoms",
    "visual_evidence_atom_sources",
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


def revision(engine) -> str:
    with engine.connect() as connection:
        assert_isolated_database(connection)
        return str(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def names(rows: list[dict]) -> set[str]:
    return {str(row["name"]) for row in rows}


def normalized(value: object) -> str:
    return "".join(str(value or "").lower().split()).replace('"', "").replace("::charactervarying", "")


def require_fk(schema, table: str, name: str, ondelete: str) -> None:
    foreign_keys = {row["name"]: row for row in schema.get_foreign_keys(table)}
    require(name in foreign_keys, f"missing FK {table}.{name}")
    actual = str(foreign_keys[name].get("options", {}).get("ondelete", "")).upper()
    require(actual == ondelete, f"{name} ON DELETE must be {ondelete}, got {actual}")


def assert_upgraded_schema(connection) -> None:
    schema = inspect(connection)
    tables = set(schema.get_table_names())
    require(NEW_TABLES <= tables, f"missing V2 tables: {sorted(NEW_TABLES - tables)}")

    prep_columns = {row["name"]: row for row in schema.get_columns("document_preparation_jobs")}
    require(prep_columns["heartbeat_at"]["nullable"], "heartbeat_at must be nullable")
    require(prep_columns["last_progress_at"]["nullable"], "last_progress_at must be nullable")
    require("next_retry_at" not in prep_columns, "duplicate retry clock must not exist")
    require("material_generation_id" not in prep_columns, "preparation job must not point to product")

    stage_columns = {row["name"]: row for row in schema.get_columns("assistant_run_stages")}
    require(stage_columns["visual_consumer_id"]["nullable"], "visual_consumer_id must be nullable")
    require("visual_evidence_artifact_id" not in stage_columns, "Assistant stage must not duplicate artifact ownership")

    request_columns = {row["name"]: row for row in schema.get_columns("visual_analysis_requests")}
    for column in ("source_plan_fingerprint", "work_fingerprint", "visual_run_id"):
        require(request_columns[column]["nullable"], f"pre-plan {column} must be nullable")

    source_checks = {row["name"]: normalized(row["sqltext"]) for row in schema.get_check_constraints("document_material_sources")}
    source_kind = source_checks["ck_mat_sources_kind"]
    for literal in (
        "document_file", "document_text", "page_text", "page_ocr_text", "page_render",
        "asset_original", "asset_ocr_text", "asset_render", "table_structure",
    ):
        require(literal in source_kind, f"missing material source kind {literal}")
    for stale in ("'page_ocr'", "'asset_text'", "'asset_ocr'", "'normalized_image'"):
        require(stale not in source_kind, f"stale material source literal {stale}")
    reference_shape = source_checks["ck_mat_sources_reference"]
    require("table_structure" in reference_shape and "page_idisnotnull" in reference_shape,
            "table_structure must be page-scoped")

    privacy_checks = {row["name"]: normalized(row["sqltext"]) for row in schema.get_check_constraints("source_privacy_assessments")}
    require("restricted_never_external" in privacy_checks["ck_privacy_restricted"],
            "restricted source externalization barrier missing")

    result_columns = {row["name"]: row for row in schema.get_columns("validated_visual_batch_results")}
    require(result_columns["raw_response_sha256"]["nullable"] is False,
            "raw response provenance must be mandatory")
    require(result_columns["validated_payload"]["nullable"] is True,
            "non-accepted validation must have no payload")
    require(result_columns["validated_payload_sha256"]["nullable"] is True,
            "non-accepted validation must have no fabricated payload hash")
    result_checks = {row["name"]: normalized(row["sqltext"]) for row in schema.get_check_constraints("validated_visual_batch_results")}
    payload_state = result_checks["ck_validated_visual_payload_state"]
    require("'accepted'" in payload_state and "validated_payloadisnotnull" in payload_state,
            "accepted payload contract missing")
    require("<>" in payload_state and "validated_payloadisnull" in payload_state,
            "non-accepted payload-nullability contract missing")

    require_fk(schema, "document_material_generations", "fk_mat_gen_prep_checksum", "RESTRICT")
    require_fk(schema, "document_material_sources", "fk_mat_source_page_document", "RESTRICT")
    require_fk(schema, "visual_analysis_sources", "fk_visual_source_material_exact", "RESTRICT")
    require_fk(schema, "visual_external_batches", "fk_visual_batch_stage_run", "RESTRICT")
    require_fk(schema, "visual_evidence_atom_sources", "fk_visual_atom_source_artifact_result", "RESTRICT")
    require_fk(schema, "assistant_run_stages", "fk_assistant_stage_visual_consumer", "RESTRICT")

    require("analysis_job_id" not in {row["name"] for row in schema.get_columns("visual_external_batches")},
            "Visual transport must not depend on AnalysisJob")
    require("visual_evidence_artifact_sources" not in tables,
            "non-canonical artifact source table must not exist")

    request_indexes = names(schema.get_indexes("visual_analysis_requests"))
    run_indexes = names(schema.get_indexes("visual_analysis_runs"))
    artifact_indexes = names(schema.get_indexes("visual_evidence_artifacts"))
    require("uq_visual_request_active_fp" in request_indexes, "active request election index missing")
    require("uq_visual_run_active_work" in run_indexes, "active work election index missing")
    require("uq_visual_artifact_current_work" in artifact_indexes, "current artifact index missing")

    trigger_names = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT tgname FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgname LIKE 'ct_visual_%'"
            )
        )
    }
    require(
        {"ct_visual_cmp_group_members", "ct_visual_cmp_group_row", "ct_visual_artifact_acceptance"}
        <= trigger_names,
        "deferred Visual integrity triggers missing",
    )


def main() -> None:
    name = require_test_database_environment()
    engine = create_engine(database_url(name))
    config = Config("/app/alembic.ini")
    script = ScriptDirectory.from_config(config)
    require(script.get_heads() == [REVISION], "migration graph must have one exact head")
    require(script.get_revision(REVISION).down_revision == PARENT, "migration parent mismatch")

    with engine.connect() as connection:
        actual = assert_isolated_database(connection, name)
        require(actual == name, "SELECT current_database() isolation mismatch")
        require(revision(engine) == PARENT, f"isolated DB must start at {PARENT}")
        baseline = {
            table: int(connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one())
            for table in (
                "document_preparation_jobs",
                "document_intelligence_artifacts",
                "document_intelligence_sources",
                "assistant_run_stages",
            )
        }

    command.upgrade(config, REVISION)
    require(revision(engine) == REVISION, "upgrade did not reach exact Visual V2 revision")

    with engine.connect() as connection:
        assert_isolated_database(connection, name)
        assert_upgraded_schema(connection)
        for table, expected in baseline.items():
            actual = int(connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one())
            require(actual == expected, f"upgrade backfilled or changed {table}")
        for table in NEW_TABLES:
            require(int(connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()) == 0,
                    f"upgrade populated {table}")

    request_id = str(uuid4())
    with engine.begin() as connection:
        assert_isolated_database(connection, name)
        connection.execute(
            text(
                """
                INSERT INTO visual_analysis_requests (
                    id, initiating_service, request_idempotency_key,
                    request_fingerprint, authorization_scope_fingerprint,
                    request_manifest, request_manifest_sha256,
                    source_planner_generation, privacy_policy_generation,
                    detector_generation, sanitizer_generation,
                    external_prompt_generation, result_contract_generation,
                    transport_generation, validator_generation,
                    artifact_assembler_generation, status
                ) VALUES (
                    :id, 'isolated-migration-test', 'downgrade-guard',
                    :hash_a, :hash_b, '{}'::jsonb, :hash_c,
                    'planner-v1', 'privacy-v1', 'detector-v1', 'sanitizer-v1',
                    'prompt-v1', 'contract-v1', 'transport-v1', 'validator-v1',
                    'assembler-v1', 'failed'
                )
                """
            ),
            {"id": request_id, "hash_a": "a" * 64, "hash_b": "b" * 64, "hash_c": "c" * 64},
        )

    refused = False
    try:
        command.downgrade(config, PARENT)
    except RuntimeError as error:
        refused = "visual_evidence_v2_downgrade_refused" in str(error)
    require(refused, "downgrade must refuse while Visual V2 data exists")
    require(revision(engine) == REVISION, "refused downgrade changed Alembic head")
    with engine.connect() as connection:
        assert_isolated_database(connection, name)
        require(
            connection.execute(
                text("SELECT count(*) FROM visual_analysis_requests WHERE id = :id"),
                {"id": request_id},
            ).scalar_one() == 1,
            "refused downgrade lost Visual V2 data",
        )

    with engine.begin() as connection:
        assert_isolated_database(connection, name)
        connection.execute(text("DELETE FROM visual_analysis_requests WHERE id = :id"), {"id": request_id})

    command.downgrade(config, PARENT)
    require(revision(engine) == PARENT, "clean downgrade did not restore parent revision")
    with engine.connect() as connection:
        assert_isolated_database(connection, name)
        schema = inspect(connection)
        require(not (NEW_TABLES & set(schema.get_table_names())), "clean downgrade left Visual V2 tables")
        prep_columns = {row["name"] for row in schema.get_columns("document_preparation_jobs")}
        require("heartbeat_at" not in prep_columns and "last_progress_at" not in prep_columns,
                "clean downgrade left Material V3 columns")
        require("visual_consumer_id" not in {row["name"] for row in schema.get_columns("assistant_run_stages")},
                "clean downgrade left Assistant Visual binding")

    command.upgrade(config, REVISION)
    require(revision(engine) == REVISION, "re-upgrade did not reach exact revision")
    with engine.connect() as connection:
        assert_isolated_database(connection, name)
        assert_upgraded_schema(connection)
        for table, expected in baseline.items():
            actual = int(connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one())
            require(actual == expected, f"roundtrip changed {table}")

    print(
        "VISUAL_EVIDENCE_V2_MIGRATION_ROUNDTRIP_PASS "
        f"database={name} parent={PARENT} revision={REVISION} tables={len(NEW_TABLES)}"
    )


if __name__ == "__main__":
    main()
