from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from test.support.database_safety import assert_isolated_database, require_test_database_environment


PARENT = "followup_admin_knowledge_base_20260821"
REVISION = "followup_contact_person_20260822"


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
            client_a = connection.execute(text(
                "INSERT INTO clients (client_type,name,country_code) VALUES ('company','Chunk26 A','PL') RETURNING id"
            )).scalar_one()
            client_b = connection.execute(text(
                "INSERT INTO clients (client_type,name,country_code) VALUES ('company','Chunk26 B','PL') RETURNING id"
            )).scalar_one()
            historical = connection.execute(text(
                "INSERT INTO client_contact_points "
                "(client_id,kind,value,normalized_value,is_primary,position,origin) "
                "VALUES (:client,'email','legacy@example.invalid','legacy@example.invalid',true,0,'manual') RETURNING id"
            ), {"client": client_a}).scalar_one()

        command.upgrade(config, REVISION)
        with engine.begin() as connection:
            assert_isolated_database(connection, name)
            schema = inspect(connection)
            require(schema.has_table("contact_persons"), "contact_persons missing")
            require(connection.execute(text(
                "SELECT contact_person_id FROM client_contact_points WHERE id=:id"
            ), {"id": historical}).scalar_one() is None, "historical coordinate was inferred")
            require(connection.execute(text("SELECT count(*) FROM contact_persons")).scalar_one() == 0,
                    "migration backfilled people")
            preferred = connection.execute(text(
                "INSERT INTO contact_persons (client_id,display_name,is_preferred,is_decision_maker,position,origin) "
                "VALUES (:client,'Jan Testowy',true,true,0,'manual') RETURNING id"
            ), {"client": client_a}).scalar_one()
            second = connection.execute(text(
                "INSERT INTO contact_persons (client_id,display_name,is_preferred,is_decision_maker,position,origin) "
                "VALUES (:client,'Anna Testowa',false,true,1,'manual') RETURNING id"
            ), {"client": client_a}).scalar_one()
            other = connection.execute(text(
                "INSERT INTO contact_persons (client_id,display_name,is_preferred,is_decision_maker,position,origin) "
                "VALUES (:client,'Inny Klient',false,false,0,'manual') RETURNING id"
            ), {"client": client_b}).scalar_one()
            require(preferred and second and other, "person fixtures missing")
            connection.execute(text(
                "UPDATE client_contact_points SET contact_person_id=:person WHERE id=:point"
            ), {"person": preferred, "point": historical})
            generic = connection.execute(text(
                "INSERT INTO client_contact_points "
                "(client_id,kind,value,normalized_value,is_primary,position,origin,contact_person_id) "
                "VALUES (:client,'phone','500000000','500000000',true,0,'manual',NULL) RETURNING contact_person_id"
            ), {"client": client_a}).scalar_one()
            require(generic is None, "generic coordinate was rejected")

        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO contact_persons (client_id,display_name,is_preferred,is_decision_maker,position,origin) "
                    "VALUES (:client,'Drugi preferowany',true,false,2,'manual')"
                ), {"client": client_a})
            raise AssertionError("second active preferred person was accepted")
        except IntegrityError:
            pass

        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "UPDATE client_contact_points SET contact_person_id=:person WHERE id=:point"
                ), {"person": other, "point": historical})
            raise AssertionError("cross-client ownership was accepted")
        except IntegrityError:
            pass

        command.downgrade(config, PARENT)
        with engine.connect() as connection:
            assert_isolated_database(connection, name)
            require(not inspect(connection).has_table("contact_persons"), "downgrade retained ContactPerson")
            require(connection.execute(text(
                "SELECT count(*) FROM client_contact_points WHERE id=:id"
            ), {"id": historical}).scalar_one() == 1, "downgrade lost historical coordinate")
        command.upgrade(config, REVISION)
        with engine.connect() as connection:
            require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION,
                    "wrong final revision")
            require(connection.execute(text("SELECT count(*) FROM contact_persons")).scalar_one() == 0,
                    "re-upgrade backfilled people")
            require(connection.execute(text(
                "SELECT contact_person_id FROM client_contact_points WHERE id=:id"
            ), {"id": historical}).scalar_one() is None, "re-upgrade inferred ownership")
    finally:
        engine.dispose()
    print("FOLLOWUP_CHUNK26_CONTACT_PERSON_MIGRATION=PASS")
    print("ZERO_BACKFILL=PASS")
    print("CROSS_CLIENT_OWNERSHIP=REJECTED")
    print("SECOND_PREFERRED=REJECTED")
    print("MULTIPLE_DECISION_MAKERS=ALLOWED")


if __name__ == "__main__":
    main()
