from __future__ import annotations

import os
from time import perf_counter

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

DATABASE_NAME = "ai_lab_chunk13_20260820"
PARENT = "followup_change_history_entity_types_20260820"
REVISION = "followup_calendar_tasks_20260820"
TABLES = ("work_items", "work_item_notes", "work_item_documents", "absence_requests")


def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def main() -> None:
    os.environ["POSTGRES_DB"] = DATABASE_NAME
    url = f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ.get('POSTGRES_HOST','postgres')}:{os.environ.get('POSTGRES_PORT','5432')}/{DATABASE_NAME}"
    engine = create_engine(url)
    config = Config("/app/alembic.ini")
    with engine.connect() as connection:
        require(connection.execute(text("select current_database()")).scalar_one() == DATABASE_NAME, "migration target is not isolated")
        current = connection.execute(text("select version_num from alembic_version")).scalar_one()
    if current == REVISION: command.downgrade(config, PARENT)
    require(current in {PARENT, REVISION}, f"unexpected isolated head: {current}")
    started = perf_counter(); command.upgrade(config, REVISION); elapsed = perf_counter() - started
    with engine.connect() as connection:
        inspector = inspect(connection)
        for table in TABLES:
            require(inspector.has_table(table), f"missing {table}")
            require(connection.execute(text(f"select count(*) from {table}")).scalar_one() == 0, f"{table} is not empty")
        require(connection.execute(text("select count(*) from change_history_events")).scalar_one() == 0, "history changed")
    command.downgrade(config, PARENT)
    with engine.connect() as connection:
        for table in TABLES: require(not inspect(connection).has_table(table), f"downgrade retained {table}")
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        transaction = connection.begin()
        role_id = connection.execute(text("insert into roles (name,description) values ('Chunk13TestRole','isolated migration fixture') returning id")).scalar_one()
        actor_id = connection.execute(text("insert into users (username,email,password_hash,is_active,must_change_password,password_reset_requested,role_id) values ('chunk13migration','chunk13@example.invalid','x',true,false,false,:role) returning id"), {"role": role_id}).scalar_one()
        accepted = ("client", "ignored_mail_source", "user", "work_item", "work_item_note", "work_item_document", "absence_request")
        for index, entity in enumerate(accepted, 1):
            connection.execute(text("insert into change_history_events (actor_user_id,entity_type,entity_id,action,changed_fields,before_values,after_values,source_key) values (:actor,:entity,:id,'updated','[]','{}','{}',:key)"), {"actor": actor_id, "entity": entity, "id": index, "key": f"chunk13-check-{index}"})
        transaction.rollback()
    with engine.connect() as connection:
        transaction = connection.begin()
        role_id = connection.execute(text("insert into roles (name,description) values ('Chunk13InvalidRole','isolated invalid fixture') returning id")).scalar_one()
        actor_id = connection.execute(text("insert into users (username,email,password_hash,is_active,must_change_password,password_reset_requested,role_id) values ('chunk13invalid','chunk13-invalid@example.invalid','x',true,false,false,:role) returning id"), {"role": role_id}).scalar_one()
        try:
            connection.execute(text("insert into change_history_events (actor_user_id,entity_type,entity_id,action,changed_fields,before_values,after_values,source_key) values (:actor,'invalid',99,'updated','[]','{}','{}','chunk13-invalid')"), {"actor": actor_id})
        except Exception:
            pass
        else:
            transaction.rollback()
            raise AssertionError("invalid Change History entity type accepted")
        transaction.rollback()
    with engine.connect() as connection:
        require(connection.execute(text("select version_num from alembic_version")).scalar_one() == REVISION, "wrong final isolated head")
    engine.dispose()
    print(f"CHUNK 13 migration round-trip: PASS ({elapsed:.3f}s)")


if __name__ == "__main__": main()
