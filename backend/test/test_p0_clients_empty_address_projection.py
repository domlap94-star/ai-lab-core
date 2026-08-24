from __future__ import annotations

import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.database.engine import engine
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.services.client_service import ClientService


class EmptyAddressProjectionRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert_isolated_database(engine, TEST_DATABASE_NAME)

    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_clients_page_omits_legacy_country_only_address(self) -> None:
        unique_name = f"P0 empty address {uuid4().hex}"
        client = Client(
            client_type="company",
            name=unique_name,
            country_code="PL",
        )
        self.db.add(client)
        self.db.flush()
        self.db.add(
            ClientAddress(
                client_id=client.id,
                label="Adres kandydata",
                country_code="PL",
                origin="other",
                source_type="candidate_merge",
            )
        )
        self.db.flush()

        page = ClientService(self.db).get_clients(
            search=unique_name,
            sort_order="newest",
            skip=0,
            limit=10,
        )

        self.assertEqual(page.total, 1)
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].id, client.id)
        self.assertEqual(page.items[0].addresses, [])


if __name__ == "__main__":
    unittest.main()
