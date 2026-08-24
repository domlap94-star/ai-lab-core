from __future__ import annotations

from datetime import date
from statistics import median
from time import perf_counter
import unittest
import uuid

from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.database.engine import engine
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.services.client_service import ClientService
from app.services.global_search_service import GlobalSearchService


class _SemanticDisabled:
    def search(self, **kwargs):
        raise AssertionError("Client-only equivalence must not use semantic search")


class ClientSearchEquivalenceTests(unittest.TestCase):
    def setUp(self) -> None:
        assert_isolated_database(engine, TEST_DATABASE_NAME)
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        suffix = uuid.uuid4().hex[:10].translate(
            str.maketrans("0123456789", "abcdefghij")
        )
        self.term = f"Żuraw{suffix}"
        self.postal_code = f"98-{int(uuid.uuid4().hex[:3], 16) % 1000:03d}"
        self.client = Client(
            client_type="company",
            name=f"{self.term} Główny",
            legal_name=f"{self.term} Legalna Nazwa",
            tax_id="521-123-45-67",
            primary_email=f"biuro-{self.term}@example.test",
            primary_phone="+48 512 345 678",
            street=f"Ulica {self.term}",
            building_number="17A",
            postal_code=self.postal_code,
            city=f"Miasto {self.term}",
            country_code="PL",
            notes=f"Notatka {self.term} kontrolowana",
            client_added_at=date(2025, 1, 2),
        )
        self.second = Client(
            client_type="person",
            name=f"{self.term} Oddział",
            primary_email=f"oddzial-{self.term}@example.test",
            country_code="PL",
            client_added_at=date(2020, 1, 2),
        )
        self.db.add_all([self.client, self.second])
        self.db.flush()
        self.db.add_all(
            [
                ClientContactPoint(
                    client_id=self.client.id,
                    kind="email",
                    value=f"kontakt-{self.term}@example.test",
                    normalized_value=f"kontakt-{self.term.casefold()}@example.test",
                    origin="manual",
                ),
                ClientContactPoint(
                    client_id=self.client.id,
                    kind="phone",
                    value="+48 501 602 703",
                    normalized_value="48501602703",
                    origin="manual",
                ),
                ClientAddress(
                    client_id=self.client.id,
                    label="Oddział testowy",
                    street=f"Aleja {self.term}",
                    building_number="21",
                    postal_code=self.postal_code,
                    city=f"Osada {self.term}",
                    country_code="PL",
                    origin="manual",
                ),
            ]
        )
        self.db.flush()
        self.clients = ClientService(self.db)
        self.global_search = GlobalSearchService(
            self.db,
            semantic_service=_SemanticDisabled(),
        )

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def _client_ids(self, query: str, *, sort_order: str = "newest") -> list[int]:
        return [
            item.id
            for item in self.clients.get_clients(
                search=query,
                sort_order=sort_order,
                skip=0,
                limit=100,
            ).items
        ]

    def _global_ids(self, query: str) -> list[int]:
        return [
            item.id
            for item in self.global_search.search(
                query=query,
                types=("client",),
                skip=0,
                limit=100,
                semantic=False,
            ).items
        ]

    def test_controlled_matching_matrix_is_equivalent(self) -> None:
        no_match = f"Brak{uuid.uuid4().hex}"
        cases = {
            "exact_name": self.client.name,
            "partial_name": f"{self.term} Gł",
            "legal_name": self.client.legal_name,
            "email": self.client.primary_email,
            "email_case": self.client.primary_email.upper(),
            "contact_email": f"kontakt-{self.term}@EXAMPLE.TEST",
            "phone_formatted": "+48 501 602 703",
            "phone_country_digits": "48501602703",
            "phone_local_digits": "501602703",
            "city": self.client.city,
            "street": f"Aleja {self.term}",
            "postal_code": self.postal_code,
            "multiple_matches": self.term,
            "normalized_whitespace": f"{self.term}   Główny",
            "normalized_tax_id": "5211234567",
            "notes": f"Notatka {self.term}",
            "no_match": no_match,
        }
        mismatches: dict[str, tuple[list[int], list[int]]] = {}
        for label, query in cases.items():
            clients = sorted(self._client_ids(query))
            global_search = sorted(self._global_ids(query))
            if clients != global_search:
                mismatches[label] = (clients, global_search)
        self.assertEqual(mismatches, {})
        self.assertIn(self.client.id, self._client_ids(self.client.name))
        self.assertEqual(
            {self.client.id, self.second.id},
            set(self._client_ids(self.term)),
        )

    def test_filters_sorting_and_pagination_remain_client_specific(self) -> None:
        page_one = self.clients.get_clients(
            search=self.term,
            sort_order="newest",
            skip=0,
            limit=1,
        )
        page_two = self.clients.get_clients(
            search=self.term,
            sort_order="newest",
            skip=1,
            limit=1,
        )
        oldest = self.clients.get_clients(
            search=self.term,
            sort_order="oldest",
            skip=0,
            limit=2,
        )
        companies = self.clients.get_clients(
            search=self.term,
            client_type="company",
            sort_order="newest",
            skip=0,
            limit=10,
        )

        self.assertEqual(page_one.total, 2)
        self.assertEqual(page_one.items[0].id, self.client.id)
        self.assertEqual(page_two.items[0].id, self.second.id)
        self.assertNotEqual(page_one.items[0].id, page_two.items[0].id)
        self.assertEqual(
            [item.id for item in oldest.items],
            [self.second.id, self.client.id],
        )
        self.assertEqual([item.id for item in companies.items], [self.client.id])
        for item in [*page_one.items, *page_two.items]:
            self.assertTrue(item.workflow_status)
            self.assertTrue(item.workflow_status_label)
            self.assertIsNotNone(item.effective_added_date)

    def test_empty_query_is_the_normal_bounded_client_list(self) -> None:
        page = self.clients.get_clients(search="  ", skip=0, limit=5)
        self.assertGreaterEqual(page.total, 2)
        self.assertEqual(len(page.items), min(5, page.total))

    def test_controlled_search_performance_is_bounded(self) -> None:
        queries = {
            "name": self.client.name,
            "email": self.client.primary_email,
            "phone": "501602703",
            "address": f"Aleja {self.term}",
            "pathological": "x" * 255,
        }
        timings: dict[str, list[float]] = {name: [] for name in queries}
        for _ in range(5):
            for name, query in queries.items():
                started = perf_counter()
                self._client_ids(query)
                timings[name].append((perf_counter() - started) * 1000)

        summary = {
            name: {
                "median_ms": round(median(values), 3),
                "max_ms": round(max(values), 3),
            }
            for name, values in timings.items()
        }
        print(f"CHUNK04_PERFORMANCE={summary}")
        self.assertTrue(all(values["max_ms"] < 5000 for values in summary.values()))


if __name__ == "__main__":
    unittest.main()
