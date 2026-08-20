from __future__ import annotations

import os
from time import perf_counter

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


DATABASE_NAME = "ai_lab_chunk05_20260820_a"
PARENT = "followup_ignored_mail_sources_20260820"
REVISION = "followup_change_history_entity_types_20260820"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    isolated_url = (
        "postgresql+psycopg://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@"
        f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{DATABASE_NAME}"
    )
    os.environ["POSTGRES_DB"] = DATABASE_NAME
    engine = create_engine(isolated_url)
    config = Config("/app/alembic.ini")

    with engine.connect() as connection:
        database = connection.execute(text("select current_database()" )).scalar_one()
        require(database == DATABASE_NAME, "migration target is not isolated")
        before = {
            "history": connection.execute(text("select count(*) from change_history_events")).scalar_one(),
            "ignored": connection.execute(text("select count(*) from ignored_mail_sources")).scalar_one(),
            "clients": connection.execute(text("select count(*) from clients")).scalar_one(),
            "candidates": connection.execute(text("select count(*) from client_candidates")).scalar_one(),
            "documents": connection.execute(text("select count(*) from documents")).scalar_one(),
        }
        current = connection.execute(text("select version_num from alembic_version")).scalar_one()
        require(current in {PARENT, REVISION}, f"unexpected isolated head: {current}")

    if current == REVISION:
        command.downgrade(config, PARENT)
    started = perf_counter()
    command.upgrade(config, REVISION)
    elapsed = perf_counter() - started
    command.downgrade(config, PARENT)
    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        after = {
            "history": connection.execute(text("select count(*) from change_history_events")).scalar_one(),
            "ignored": connection.execute(text("select count(*) from ignored_mail_sources")).scalar_one(),
            "clients": connection.execute(text("select count(*) from clients")).scalar_one(),
            "candidates": connection.execute(text("select count(*) from client_candidates")).scalar_one(),
            "documents": connection.execute(text("select count(*) from documents")).scalar_one(),
        }
        require(after == before, f"row counts changed: {before} -> {after}")
        require(
            connection.execute(text("select version_num from alembic_version")).scalar_one()
            == REVISION,
            "isolated database did not finish at new head",
        )
        connection.commit()

        actor_id = connection.execute(text("select id from users order by id limit 1")).scalar_one()
        connection.commit()
        accepted = (
            ("ignored_mail_source", "activated"),
            ("user", "deactivated"),
            ("client", "updated"),
        )
        transaction = connection.begin()
        try:
            for index, (entity_type, action) in enumerate(accepted, 1):
                connection.execute(
                    text(
                        "insert into change_history_events "
                        "(actor_user_id,entity_type,entity_id,action,changed_fields,"
                        "before_values,after_values,source_key) values "
                        "(:actor,:entity_type,:entity_id,:action,'[]','{}','{}',:source_key)"
                    ),
                    {
                        "actor": actor_id,
                        "entity_type": entity_type,
                        "entity_id": index,
                        "action": action,
                        "source_key": f"chunk05-migration-accepted-{index}",
                    },
                )
        finally:
            transaction.rollback()

        for column, value in (("entity_type", "random_invalid"), ("action", "random_invalid")):
            transaction = connection.begin()
            try:
                entity_type = value if column == "entity_type" else "client"
                action = value if column == "action" else "updated"
                try:
                    connection.execute(
                        text(
                            "insert into change_history_events "
                            "(actor_user_id,entity_type,entity_id,action,changed_fields,"
                            "before_values,after_values,source_key) values "
                            "(:actor,:entity_type,999,:action,'[]','{}','{}',:source_key)"
                        ),
                        {
                            "actor": actor_id,
                            "entity_type": entity_type,
                            "action": action,
                            "source_key": f"chunk05-migration-invalid-{column}",
                        },
                    )
                except Exception:
                    pass
                else:
                    raise AssertionError(f"invalid {column} was accepted")
            finally:
                transaction.rollback()

    engine.dispose()
    print(f"CHUNK 05 Change History migration round-trip: PASS ({elapsed:.3f}s)")


if __name__ == "__main__":
    main()
