from __future__ import annotations

from datetime import date
import unittest
import uuid

from sqlalchemy.orm import Session

from app.database.engine import engine
from app.models.client import Client
from app.models.client_workflow_status import ClientWorkflowStatus
from app.schemas.client import ClientRead
from app.schemas.client_bulk import ClientWorkflowBatchRequest
from app.services.client_bulk_service import ClientBulkService
from app.services.client_service import ClientService
from app.services.global_search_service import GlobalSearchService


class _SemanticStub:
    def search(self, **_kwargs):
        return []


class FollowupChunk02ClientStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        suffix = uuid.uuid4().hex[:12]
        self.client = Client(
            client_type="company",
            name=f"Status projection {suffix}",
            country_code="PL",
        )
        self.default_client = Client(
            client_type="company",
            name=f"Status default {suffix}",
            country_code="PL",
        )
        self.db.add_all([self.client, self.default_client])
        self.db.flush()
        self.db.add(
            ClientWorkflowStatus(
                client_id=self.client.id,
                status="inspection",
                effective_date=date(2026, 8, 19),
            )
        )
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_list_detail_workflow_endpoint_and_search_share_projection(self) -> None:
        service = ClientService(self.db)
        detail = service.get_client(self.client.id)
        listed = next(
            item
            for item in service.get_clients(search=self.client.name, limit=10).items
            if item.id == self.client.id
        )
        status = ClientBulkService(self.db).workflow_statuses([self.client.id])[0]
        search = GlobalSearchService(
            self.db,
            semantic_service=_SemanticStub(),
        ).search(query=self.client.name, types=("client",), semantic=False)
        hit = next(item for item in search.items if item.id == self.client.id)

        self.assertEqual(detail.workflow_status, "inspection")
        self.assertEqual(listed.workflow_status, detail.workflow_status)
        self.assertEqual(status.status, detail.workflow_status)
        self.assertEqual(hit.client_workflow_status, detail.workflow_status)
        self.assertEqual(detail.workflow_status_label, "Oględziny")
        self.assertEqual(hit.client_workflow_status_label, "Oględziny")
        self.assertEqual(detail.workflow_effective_date, date(2026, 8, 19))

        payload = ClientRead.model_validate(detail).model_dump(mode="json")
        self.assertEqual(payload["workflow_status"], "inspection")
        self.assertEqual(payload["workflow_status_label"], "Oględziny")
        self.assertEqual(payload["workflow_effective_date"], "2026-08-19")

    def test_missing_status_has_one_canonical_default(self) -> None:
        detail = ClientService(self.db).get_client(self.default_client.id)
        self.assertEqual(detail.workflow_status, "untouched")
        self.assertEqual(detail.workflow_status_label, "Brak modyfikacji")
        self.assertIsNone(detail.workflow_effective_date)

    def test_supported_status_write_is_visible_in_every_projection(self) -> None:
        result = ClientBulkService(self.db).set_workflow_status(
            ClientWorkflowBatchRequest(
                client_ids=[self.client.id],
                status="phone_contact",
                effective_date=date(2026, 8, 20),
            )
        )
        self.assertEqual(result.succeeded, 1)

        detail = ClientService(self.db).get_client(self.client.id)
        listed = next(
            item
            for item in ClientService(self.db).get_clients(
                search=self.client.name,
                limit=10,
            ).items
            if item.id == self.client.id
        )
        hit = next(
            item
            for item in GlobalSearchService(
                self.db,
                semantic_service=_SemanticStub(),
            ).search(query=self.client.name, types=("client",), semantic=False).items
            if item.id == self.client.id
        )
        self.assertEqual(detail.workflow_status, "phone_contact")
        self.assertEqual(listed.workflow_status, "phone_contact")
        self.assertEqual(hit.client_workflow_status, "phone_contact")
        self.assertEqual(detail.workflow_status_label, "Kontakt telefoniczny")
        self.assertEqual(detail.workflow_effective_date, date(2026, 8, 20))


if __name__ == "__main__":
    unittest.main()
