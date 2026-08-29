from __future__ import annotations

import hashlib
import json
import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


PARENT = "followup_assistant_pipeline_v2_20260826"
REVISION = "followup_assistant_chat_history_20260829"
NEW_INDEXES = {
    "ix_conversations_history_active",
    "ix_assistant_runs_conversation_created",
    "ix_messages_conversation_created",
    "uq_messages_assistant_run_role",
}
NEW_CONSTRAINTS = {
    "ck_conversations_kind",
    "ck_messages_role",
    "fk_assistant_runs_conversation_id_conversations",
    "fk_messages_assistant_run_id_assistant_runs",
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


def rows_hash(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_rows(connection, statement: str) -> list[dict]:
    return [dict(row) for row in connection.execute(text(statement)).mappings()]


def columns(schema, table: str) -> dict[str, dict]:
    return {row["name"]: row for row in schema.get_columns(table)}


def indexes(schema, table: str) -> dict[str, dict]:
    return {row["name"]: row for row in schema.get_indexes(table)}


def foreign_keys(schema, table: str) -> dict[str, dict]:
    return {row["name"]: row for row in schema.get_foreign_keys(table)}


def checks(schema, table: str) -> dict[str, dict]:
    return {row["name"]: row for row in schema.get_check_constraints(table)}


def normalized_sql(value: object) -> str:
    return "".join(str(value or "").lower().split()).replace("(", "").replace(")", "")


def insert_run(connection, *, run_id: str, user_id: int, attempt: str,
               fingerprint: str, conversation_id: int | None, upgraded: bool) -> None:
    columns_sql = ""
    values_sql = ""
    parameters: dict[str, object] = {
        "id": run_id,
        "user_id": user_id,
        "attempt": attempt,
        "fingerprint": fingerprint,
    }
    if upgraded:
        columns_sql = ", conversation_id"
        values_sql = ", :conversation_id"
        parameters["conversation_id"] = conversation_id
    connection.execute(
        text(
            f"""
            INSERT INTO assistant_runs (
                id, created_by_user_id, attempt_id, orchestrator_version,
                evidence_contract_version, policy_generation, input_fingerprint,
                request_payload, target_scope, complexity, status, sensitivity
                {columns_sql}
            ) VALUES (
                :id, :user_id, :attempt, 'isolated-v2', 'isolated-evidence-v2',
                'isolated-policy', :fingerprint, '{{}}'::json, '{{}}'::json,
                'standard', 'created', 'public_reference'
                {values_sql}
            )
            """
        ),
        parameters,
    )


def expect_integrity_error(connection, statement: str, parameters: dict) -> None:
    savepoint = connection.begin_nested()
    try:
        connection.execute(text(statement), parameters)
    except IntegrityError:
        savepoint.rollback()
    else:
        savepoint.rollback()
        raise AssertionError("expected integrity error")


def current_revision(engine) -> str:
    with engine.connect() as connection:
        return str(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def main() -> None:
    name = require_test_database_environment()
    engine = create_engine(database_url(name))
    config = Config("/app/alembic.ini")

    legacy_conversation_ids: list[int] = []
    legacy_message_ids: list[int] = []
    legacy_run_ids = [str(uuid4()), str(uuid4())]
    post_upgrade_legacy_conversation_id: int | None = None
    assistant_chat_ids: list[int] = []
    assistant_run_ids: list[str] = []

    try:
        with engine.connect() as connection:
            actual = assert_isolated_database(connection, name)
            require(actual == name, "SELECT current_database() isolation mismatch")
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            require(current == PARENT, f"isolated baseline must be {PARENT}, got {current}")

        with engine.begin() as connection:
            assert_isolated_database(connection, name)
            role_id = connection.execute(
                text(
                    "INSERT INTO roles (name, description) "
                    "VALUES ('ChatHistoryMigrationRole','isolated fixture') RETURNING id"
                )
            ).scalar_one()
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO users (
                        username, email, password_hash, is_active,
                        must_change_password, password_reset_requested,
                        auth_version, role_id
                    ) VALUES (
                        'chat_history_migration_user',
                        'chat-history-migration@example.invalid',
                        'isolated-not-a-real-password', true, false, false, 0, :role_id
                    ) RETURNING id
                    """
                ),
                {"role_id": role_id},
            ).scalar_one()

            for index in range(4):
                conversation_id = connection.execute(
                    text(
                        """
                        INSERT INTO conversations (user_id, title, model)
                        VALUES (:user_id, :title, 'llama3.2') RETURNING id
                        """
                    ),
                    {"user_id": user_id, "title": f"Legacy chat {index + 1}"},
                ).scalar_one()
                legacy_conversation_ids.append(conversation_id)
                for role in ("user", "assistant"):
                    message_id = connection.execute(
                        text(
                            """
                            INSERT INTO messages (conversation_id, role, content)
                            VALUES (:conversation_id, :role, :content) RETURNING id
                            """
                        ),
                        {
                            "conversation_id": conversation_id,
                            "role": role,
                            "content": f"Synthetic {role} content {index + 1}",
                        },
                    ).scalar_one()
                    legacy_message_ids.append(message_id)

            for index, run_id in enumerate(legacy_run_ids, start=1):
                insert_run(
                    connection,
                    run_id=run_id,
                    user_id=user_id,
                    attempt=f"chatlegacy{index:04d}",
                    fingerprint=(f"{index:x}" * 64)[:64],
                    conversation_id=None,
                    upgraded=False,
                )

        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            legacy_conversations = read_rows(
                connection,
                "SELECT id,user_id,title,model,created_at,updated_at "
                "FROM conversations ORDER BY id",
            )
            legacy_messages = read_rows(
                connection,
                "SELECT id,conversation_id,role,content,created_at "
                "FROM messages ORDER BY id",
            )
            legacy_runs = read_rows(
                connection,
                "SELECT * FROM assistant_runs ORDER BY id",
            )
            baseline_hashes = {
                "conversations": rows_hash(legacy_conversations),
                "messages": rows_hash(legacy_messages),
                "assistant_runs": rows_hash(legacy_runs),
            }
            require(len(legacy_conversations) == 4, "legacy conversation seed mismatch")
            require(len(legacy_messages) == 8, "legacy message seed mismatch")
            require(len(legacy_runs) == 2, "legacy AssistantRun seed mismatch")

        command.upgrade(config, REVISION)
        require(current_revision(engine) == REVISION, "wrong upgraded Alembic head")

        with engine.begin() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            conversation_columns = columns(schema, "conversations")
            run_columns = columns(schema, "assistant_runs")
            message_columns = columns(schema, "messages")

            require(conversation_columns["kind"]["nullable"] is False, "kind must be NOT NULL")
            require("legacy_chat" in str(conversation_columns["kind"].get("default")),
                    "kind server default missing")
            require(conversation_columns["last_activity_at"]["nullable"] is True,
                    "last_activity_at must be nullable")
            require(conversation_columns["deleted_at"]["nullable"] is True,
                    "deleted_at must be nullable")
            require(run_columns["conversation_id"]["nullable"] is True,
                    "AssistantRun conversation_id must be nullable")
            require(message_columns["assistant_run_id"]["nullable"] is True,
                    "message assistant_run_id must be nullable")

            conversation_checks = checks(schema, "conversations")
            message_checks = checks(schema, "messages")
            require("ck_conversations_kind" in conversation_checks, "conversation kind CHECK missing")
            require("legacy_chat" in str(conversation_checks["ck_conversations_kind"]["sqltext"])
                    and "assistant_v2" in str(conversation_checks["ck_conversations_kind"]["sqltext"]),
                    "conversation kind CHECK values incorrect")
            require("ck_messages_role" in message_checks, "message role CHECK missing")
            require("user" in str(message_checks["ck_messages_role"]["sqltext"])
                    and "assistant" in str(message_checks["ck_messages_role"]["sqltext"]),
                    "message role CHECK values incorrect")

            run_fk = foreign_keys(schema, "assistant_runs")[
                "fk_assistant_runs_conversation_id_conversations"
            ]
            require(run_fk["constrained_columns"] == ["conversation_id"], "run FK column mismatch")
            require(run_fk["referred_table"] == "conversations", "run FK target mismatch")
            require(str(run_fk.get("options", {}).get("ondelete")).upper() == "SET NULL",
                    "run FK must use ON DELETE SET NULL")
            message_fk = foreign_keys(schema, "messages")[
                "fk_messages_assistant_run_id_assistant_runs"
            ]
            require(message_fk["constrained_columns"] == ["assistant_run_id"],
                    "message FK column mismatch")
            require(message_fk["referred_table"] == "assistant_runs", "message FK target mismatch")
            require(str(message_fk.get("options", {}).get("ondelete")).upper() == "SET NULL",
                    "message FK must use ON DELETE SET NULL")

            conversation_indexes = indexes(schema, "conversations")
            run_indexes = indexes(schema, "assistant_runs")
            message_indexes = indexes(schema, "messages")
            history_index = conversation_indexes["ix_conversations_history_active"]
            require(history_index["column_names"] == ["user_id", "kind", "last_activity_at", "id"],
                    "history ordering index columns incorrect")
            history_where = normalized_sql(
                history_index.get("dialect_options", {}).get("postgresql_where")
            )
            require("deleted_atisnull" in history_where, "history partial predicate missing")
            require(
                run_indexes["ix_assistant_runs_conversation_created"]["column_names"]
                == ["conversation_id", "created_at", "id"],
                "run conversation index incorrect",
            )
            require(
                message_indexes["ix_messages_conversation_created"]["column_names"]
                == ["conversation_id", "created_at", "id"],
                "message order index incorrect",
            )
            run_role_index = message_indexes["uq_messages_assistant_run_role"]
            require(run_role_index["unique"] is True, "run/role index must be unique")
            require(run_role_index["column_names"] == ["assistant_run_id", "role"],
                    "run/role unique index columns incorrect")
            require(
                "assistant_run_idisnotnull" in normalized_sql(
                    run_role_index.get("dialect_options", {}).get("postgresql_where")
                ),
                "run/role partial predicate missing",
            )

            require(
                connection.execute(text("SELECT count(*) FROM conversations WHERE kind='legacy_chat'")).scalar_one()
                == 4,
                "legacy conversations not classified as legacy_chat",
            )
            require(
                connection.execute(text("SELECT count(*) FROM assistant_runs WHERE conversation_id IS NULL")).scalar_one()
                == 2,
                "migration backfilled existing AssistantRuns",
            )
            require(
                connection.execute(text("SELECT count(*) FROM messages WHERE assistant_run_id IS NULL")).scalar_one()
                == 8,
                "migration backfilled existing messages",
            )
            require(
                rows_hash(read_rows(connection, "SELECT id,user_id,title,model,created_at,updated_at FROM conversations ORDER BY id"))
                == baseline_hashes["conversations"],
                "upgrade changed legacy conversation values",
            )
            require(
                rows_hash(read_rows(connection, "SELECT id,conversation_id,role,content,created_at FROM messages ORDER BY id"))
                == baseline_hashes["messages"],
                "upgrade changed legacy message values",
            )

            post_upgrade_legacy_conversation_id = connection.execute(
                text(
                    "INSERT INTO conversations (user_id,title,model) "
                    "VALUES (:user_id,'Post-upgrade legacy','llama3.2') RETURNING id"
                ),
                {"user_id": user_id},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO messages (conversation_id,role,content) "
                    "VALUES (:conversation_id,'user','Synthetic legacy-compatible message')"
                ),
                {"conversation_id": post_upgrade_legacy_conversation_id},
            )
            require(
                connection.execute(
                    text("SELECT kind FROM conversations WHERE id=:id"),
                    {"id": post_upgrade_legacy_conversation_id},
                ).scalar_one() == "legacy_chat",
                "legacy insert did not receive server default",
            )

            for title in ("Chat A", "Chat B"):
                chat_id = connection.execute(
                    text(
                        """
                        INSERT INTO conversations (
                            user_id,title,model,kind,last_activity_at
                        ) VALUES (
                            :user_id,:title,'assistant_v2','assistant_v2',now()
                        ) RETURNING id
                        """
                    ),
                    {"user_id": user_id, "title": title},
                ).scalar_one()
                assistant_chat_ids.append(chat_id)

            for index, chat_id in enumerate(
                [assistant_chat_ids[0], assistant_chat_ids[0], assistant_chat_ids[1], None],
                start=1,
            ):
                run_id = str(uuid4())
                assistant_run_ids.append(run_id)
                insert_run(
                    connection,
                    run_id=run_id,
                    user_id=user_id,
                    attempt=f"chatv2run{index:04d}",
                    fingerprint=(f"{index + 2:x}" * 64)[:64],
                    conversation_id=chat_id,
                    upgraded=True,
                )
                if chat_id is not None:
                    for role in ("user", "assistant"):
                        connection.execute(
                            text(
                                """
                                INSERT INTO messages (
                                    conversation_id,assistant_run_id,role,content
                                ) VALUES (:conversation_id,:run_id,:role,:content)
                                """
                            ),
                            {
                                "conversation_id": chat_id,
                                "run_id": run_id,
                                "role": role,
                                "content": f"Synthetic V2 {role} {index}",
                            },
                        )

            require(
                connection.execute(
                    text("SELECT count(*) FROM assistant_runs WHERE conversation_id=:id"),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == 2,
                "one conversation to many runs failed",
            )
            require(
                connection.execute(
                    text("SELECT count(*) FROM messages WHERE conversation_id=:id"),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == 4,
                "one conversation to many messages failed",
            )
            require(
                connection.execute(
                    text(
                        "SELECT array_agg(role ORDER BY created_at,id) "
                        "FROM messages WHERE conversation_id=:id"
                    ),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == ["user", "assistant", "user", "assistant"],
                "conversation message ordering is not deterministic",
            )
            require(
                connection.execute(
                    text("SELECT count(*) FROM assistant_runs WHERE id=:id AND conversation_id IS NULL"),
                    {"id": assistant_run_ids[3]},
                ).scalar_one() == 1,
                "unbound AssistantRun must remain legal",
            )

            duplicate_sql = (
                "INSERT INTO messages (conversation_id,assistant_run_id,role,content) "
                "VALUES (:conversation_id,:run_id,:role,'duplicate')"
            )
            for role in ("user", "assistant"):
                expect_integrity_error(
                    connection,
                    duplicate_sql,
                    {
                        "conversation_id": assistant_chat_ids[0],
                        "run_id": assistant_run_ids[0],
                        "role": role,
                    },
                )
            expect_integrity_error(
                connection,
                "INSERT INTO messages (conversation_id,role,content) "
                "VALUES (:conversation_id,'system','invalid role')",
                {"conversation_id": assistant_chat_ids[0]},
            )
            expect_integrity_error(
                connection,
                "UPDATE assistant_runs SET conversation_id=-1 WHERE id=:run_id",
                {"run_id": assistant_run_ids[0]},
            )
            expect_integrity_error(
                connection,
                "UPDATE messages SET assistant_run_id=:missing "
                "WHERE conversation_id=:conversation_id AND role='user'",
                {
                    "missing": str(uuid4()),
                    "conversation_id": assistant_chat_ids[0],
                },
            )

            physical_chat_id = connection.execute(
                text(
                    "INSERT INTO conversations (user_id,title,model,kind) "
                    "VALUES (:user_id,'Physical FK test','assistant_v2','assistant_v2') RETURNING id"
                ),
                {"user_id": user_id},
            ).scalar_one()
            physical_run_id = str(uuid4())
            assistant_run_ids.append(physical_run_id)
            insert_run(
                connection,
                run_id=physical_run_id,
                user_id=user_id,
                attempt="chatphysical0001",
                fingerprint="a" * 64,
                conversation_id=physical_chat_id,
                upgraded=True,
            )
            connection.execute(
                text("DELETE FROM conversations WHERE id=:id"),
                {"id": physical_chat_id},
            )
            require(
                connection.execute(
                    text("SELECT conversation_id FROM assistant_runs WHERE id=:id"),
                    {"id": physical_run_id},
                ).scalar_one() is None,
                "conversation physical delete did not SET NULL on AssistantRun",
            )

            run_delete_chat_id = connection.execute(
                text(
                    "INSERT INTO conversations (user_id,title,model,kind) "
                    "VALUES (:user_id,'Run FK test','assistant_v2','assistant_v2') RETURNING id"
                ),
                {"user_id": user_id},
            ).scalar_one()
            assistant_chat_ids.append(run_delete_chat_id)
            run_delete_id = str(uuid4())
            insert_run(
                connection,
                run_id=run_delete_id,
                user_id=user_id,
                attempt="chatphysical0002",
                fingerprint="b" * 64,
                conversation_id=run_delete_chat_id,
                upgraded=True,
            )
            run_delete_message_id = connection.execute(
                text(
                    """
                    INSERT INTO messages (conversation_id,assistant_run_id,role,content)
                    VALUES (:conversation_id,:run_id,'user','Synthetic FK message') RETURNING id
                    """
                ),
                {"conversation_id": run_delete_chat_id, "run_id": run_delete_id},
            ).scalar_one()
            connection.execute(text("DELETE FROM assistant_runs WHERE id=:id"), {"id": run_delete_id})
            require(
                connection.execute(
                    text("SELECT assistant_run_id FROM messages WHERE id=:id"),
                    {"id": run_delete_message_id},
                ).scalar_one() is None,
                "AssistantRun physical delete did not SET NULL on message",
            )

            deleted_at = connection.execute(
                text(
                    "UPDATE conversations SET deleted_at=now() "
                    "WHERE id=:id RETURNING deleted_at"
                ),
                {"id": assistant_chat_ids[0]},
            ).scalar_one()
            run_count_before = connection.execute(
                text("SELECT count(*) FROM assistant_runs WHERE conversation_id=:id"),
                {"id": assistant_chat_ids[0]},
            ).scalar_one()
            message_count_before = connection.execute(
                text("SELECT count(*) FROM messages WHERE conversation_id=:id"),
                {"id": assistant_chat_ids[0]},
            ).scalar_one()
            require(
                connection.execute(
                    text("SELECT count(*) FROM conversations WHERE id=:id AND deleted_at IS NULL"),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == 0,
                "soft-deleted chat remained in active-history predicate",
            )
            connection.execute(
                text("UPDATE assistant_runs SET status='queued' WHERE id=:id"),
                {"id": assistant_run_ids[0]},
            )
            require(
                connection.execute(
                    text("SELECT deleted_at FROM conversations WHERE id=:id"),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == deleted_at,
                "run update resurrected soft-deleted chat",
            )
            require(
                connection.execute(
                    text("SELECT count(*) FROM assistant_runs WHERE conversation_id=:id"),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == run_count_before,
                "soft delete changed AssistantRuns",
            )
            require(
                connection.execute(
                    text("SELECT count(*) FROM messages WHERE conversation_id=:id"),
                    {"id": assistant_chat_ids[0]},
                ).scalar_one() == message_count_before,
                "soft delete changed messages",
            )

        downgrade_error = None
        try:
            command.downgrade(config, PARENT)
        except Exception as error:  # Alembic preserves the deterministic migration error.
            downgrade_error = str(error)
        require(downgrade_error is not None, "downgrade accepted Assistant V2 history")
        require("assistant_chat_history_downgrade_refused" in downgrade_error,
                f"unexpected downgrade error: {downgrade_error}")
        require(current_revision(engine) == REVISION, "refused downgrade changed Alembic head")

        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require("conversation_id" in columns(schema, "assistant_runs"),
                    "refused downgrade changed schema")
            require(
                connection.execute(
                    text("SELECT count(*) FROM conversations WHERE kind='assistant_v2'")
                ).scalar_one() >= 2,
                "refused downgrade changed Assistant V2 data",
            )

        with engine.begin() as connection:
            assert_isolated_database(connection, name)
            connection.execute(
                text("DELETE FROM messages WHERE conversation_id = ANY(:ids)"),
                {"ids": assistant_chat_ids},
            )
            connection.execute(
                text("DELETE FROM assistant_runs WHERE id = ANY(:ids)"),
                {"ids": assistant_run_ids},
            )
            connection.execute(
                text("DELETE FROM conversations WHERE id = ANY(:ids)"),
                {"ids": assistant_chat_ids},
            )
            connection.execute(
                text("DELETE FROM conversations WHERE id=:id"),
                {"id": post_upgrade_legacy_conversation_id},
            )
            require(
                connection.execute(text("SELECT count(*) FROM conversations WHERE kind <> 'legacy_chat'")).scalar_one()
                == 0,
                "Assistant V2 conversation cleanup incomplete",
            )
            for query in (
                "SELECT count(*) FROM conversations WHERE deleted_at IS NOT NULL",
                "SELECT count(*) FROM conversations WHERE last_activity_at IS NOT NULL",
                "SELECT count(*) FROM assistant_runs WHERE conversation_id IS NOT NULL",
                "SELECT count(*) FROM messages WHERE assistant_run_id IS NOT NULL",
            ):
                require(connection.execute(text(query)).scalar_one() == 0,
                        f"downgrade precondition cleanup incomplete: {query}")

        command.downgrade(config, PARENT)
        require(current_revision(engine) == PARENT, "clean downgrade did not reach parent")

        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require("kind" not in columns(schema, "conversations"), "parent retained conversation.kind")
            require("last_activity_at" not in columns(schema, "conversations"),
                    "parent retained last_activity_at")
            require("deleted_at" not in columns(schema, "conversations"),
                    "parent retained deleted_at")
            require("conversation_id" not in columns(schema, "assistant_runs"),
                    "parent retained AssistantRun conversation_id")
            require("assistant_run_id" not in columns(schema, "messages"),
                    "parent retained message assistant_run_id")
            require("ck_messages_role" not in checks(schema, "messages"),
                    "parent retained message role CHECK")
            require(
                rows_hash(read_rows(connection, "SELECT id,user_id,title,model,created_at,updated_at FROM conversations ORDER BY id"))
                == baseline_hashes["conversations"],
                "downgrade changed original legacy conversations",
            )
            require(
                rows_hash(read_rows(connection, "SELECT id,conversation_id,role,content,created_at FROM messages ORDER BY id"))
                == baseline_hashes["messages"],
                "downgrade changed original legacy messages",
            )
            require(
                rows_hash(read_rows(connection, "SELECT * FROM assistant_runs ORDER BY id"))
                == baseline_hashes["assistant_runs"],
                "downgrade changed original AssistantRuns",
            )

        command.upgrade(config, REVISION)
        require(current_revision(engine) == REVISION, "re-upgrade did not reach revision")

        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1,
                    "migration graph produced multiple heads")
            require(
                connection.execute(
                    text("SELECT count(*) FROM conversations WHERE kind='legacy_chat'")
                ).scalar_one() == 4,
                "re-upgrade changed legacy conversation classification",
            )
            require(
                connection.execute(
                    text("SELECT count(*) FROM assistant_runs WHERE conversation_id IS NULL")
                ).scalar_one() == 2,
                "re-upgrade bound historical AssistantRuns",
            )
            require(
                connection.execute(
                    text("SELECT count(*) FROM messages WHERE assistant_run_id IS NULL")
                ).scalar_one() == 8,
                "re-upgrade bound historical messages",
            )
            require(
                rows_hash(read_rows(connection, "SELECT id,user_id,title,model,created_at,updated_at FROM conversations ORDER BY id"))
                == baseline_hashes["conversations"],
                "re-upgrade changed legacy conversations",
            )
            require(
                rows_hash(read_rows(connection, "SELECT id,conversation_id,role,content,created_at FROM messages ORDER BY id"))
                == baseline_hashes["messages"],
                "re-upgrade changed legacy messages",
            )
            for table in ("conversations", "assistant_runs", "messages"):
                table_indexes = indexes(schema, table)
                require(len(table_indexes) == len(set(table_indexes)),
                        f"duplicate reflected index names on {table}")
            reflected_indexes = {
                **indexes(schema, "conversations"),
                **indexes(schema, "assistant_runs"),
                **indexes(schema, "messages"),
            }
            require(NEW_INDEXES <= set(reflected_indexes), "re-upgrade indexes missing")
            reflected_constraints = (
                set(checks(schema, "conversations"))
                | set(checks(schema, "messages"))
                | set(foreign_keys(schema, "assistant_runs"))
                | set(foreign_keys(schema, "messages"))
            )
            require(NEW_CONSTRAINTS <= reflected_constraints,
                    "re-upgrade constraints missing")

        print(f"ISOLATED_DATABASE={name}")
        print(f"PARENT={PARENT}")
        print(f"REVISION={REVISION}")
        print("LEGACY_CONVERSATIONS_PRESERVED=4")
        print("LEGACY_MESSAGES_PRESERVED=8")
        print("ASSISTANT_RUN_BACKFILL=0")
        print("MESSAGE_RUN_BACKFILL=0")
        print("DOWNGRADE_WITH_V2_DATA=REFUSED")
        print("CLEAN_DOWNGRADE=PASS")
        print("REUPGRADE=PASS")
        print("FOLLOWUP_ASSISTANT_CHAT_HISTORY_MIGRATION_ROUNDTRIP=PASS")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
