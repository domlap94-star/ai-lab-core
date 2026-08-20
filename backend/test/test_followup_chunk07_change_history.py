from __future__ import annotations

from datetime import date, datetime, timezone
import json
from statistics import median
from time import perf_counter
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


ISOLATED_DB_NAME = "ai_lab_chunk07_isolated"
require_test_database_environment(ISOLATED_DB_NAME)

from app.api.admin_users import require_admin
from app.api.auth import get_current_user
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.change_history_event import ChangeHistoryEvent
from app.models.client import Client
from app.models.client_activity_event import ClientActivityEvent
from app.models.client_candidate import ClientCandidate
from app.models.role import Role
from app.models.user import User
from app.schemas.client import (
    ClientAddressInput,
    ClientContactInput,
    ClientCreate,
    ClientUpdate,
)
from app.schemas.client_bulk import ClientWorkflowBatchRequest
from app.services.change_history_query_service import ChangeHistoryQueryService
from app.services.change_history_service import (
    ChangeHistoryConflictError,
    ChangeHistoryService,
    ChangeHistoryValidationError,
)
from app.services.client_bulk_service import ClientBulkService
from app.services.client_candidate_review_service import ClientCandidateReviewService
from app.services.client_service import ClientService


class ChangeHistoryIsolatedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert_isolated_database(engine, ISOLATED_DB_NAME)

    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        token = uuid4().hex
        admin_role = Role(name=f"Administrator-{token}", description="isolated")
        user_role = Role(name=f"User-{token}", description="isolated")
        self.db.add_all([admin_role, user_role])
        self.db.flush()
        self.admin = User(
            username=f"admin-{token[:10]}",
            email=f"admin-{token}@example.invalid",
            password_hash="synthetic-hash",
            role_id=admin_role.id,
            is_active=True,
        )
        self.user = User(
            username=f"user-{token[:10]}",
            email=f"user-{token}@example.invalid",
            password_hash="synthetic-hash",
            role_id=user_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin, self.user])
        self.db.flush()
        self.client = Client(
            client_type="company",
            name=f"CHUNK07 {token}",
            country_code="PL",
            city="Warszawa",
        )
        self.db.add(self.client)
        self.db.flush()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def _persist(self, **overrides) -> ChangeHistoryEvent | None:
        values = {
            "actor_user_id": self.admin.id,
            "entity_type": "client",
            "entity_id": self.client.id,
            "action": "updated",
            "before": {"city": "Warszawa"},
            "after": {"city": "Kraków"},
            "operation_id": str(uuid4()),
            "source_key": f"test:{uuid4()}",
        }
        values.update(overrides)
        return ChangeHistoryService(self.db).persist(**values)

    def test_sanitizer_scalars_dates_null_enums_and_unchanged(self) -> None:
        row = self._persist(
            before={"city": "Warszawa", "client_added_at": None, "country_code": "PL"},
            after={"city": "Kraków", "client_added_at": date(2026, 8, 19), "country_code": "PL"},
        )
        self.assertEqual(row.changed_fields, ["city", "client_added_at"])
        self.assertEqual(row.after_values["client_added_at"], "2026-08-19")
        self.assertNotIn("country_code", row.after_values)

    def test_sensitive_identifiers_are_masked_and_notes_are_descriptors(self) -> None:
        row = self._persist(
            before={
                "primary_email": "old@example.invalid",
                "primary_phone": "+48 111 222 333",
                "tax_id": "123-456-78-90",
                "notes": "old note",
            },
            after={
                "primary_email": "new@example.invalid",
                "primary_phone": "+48 999 888 777",
                "tax_id": "999-888-77-66",
                "notes": "new note" * 200,
            },
        )
        encoded = json.dumps(row.after_values)
        for secret in ("new@example.invalid", "999888777", "9998887766", "new note"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(row.after_values["primary_email"]["masked"], "n***@example.invalid")
        self.assertEqual(row.after_values["notes"]["length"], 1600)

    def test_address_is_bounded_and_nested_or_forbidden_values_are_rejected(self) -> None:
        row = self._persist(
            entity_type="client_address",
            before={"street": "Krótka", "city": "Warszawa"},
            after={"street": "Długa", "city": "Kraków"},
        )
        self.assertEqual(row.changed_fields, ["city", "street"])
        with self.assertRaises(ChangeHistoryValidationError):
            self._persist(before={"password": "a"}, after={"password": "b"})
        with self.assertRaises(ChangeHistoryValidationError):
            self._persist(before={"city": "a"}, after={"city": {"raw": "b"}})
        with self.assertRaises(ChangeHistoryValidationError):
            self._persist(before={"city": "a"}, after={"city": "b" * 256})

    def test_limits_noop_and_source_key_idempotency(self) -> None:
        self.assertIsNone(self._persist(before={"city": "same"}, after={"city": "same"}))
        source_key = f"test:{uuid4()}"
        first = self._persist(source_key=source_key, operation_id="same")
        second = self._persist(source_key=source_key, operation_id="same")
        self.assertEqual(first.id, second.id)
        with self.assertRaises(ChangeHistoryConflictError):
            self._persist(
                source_key=source_key,
                operation_id="same",
                before={"city": "Warszawa"},
                after={"city": "Gdańsk"},
            )
        with self.assertRaises(ChangeHistoryValidationError):
            ChangeHistoryService._validate_payload_size({"city": "x" * 9000})

    def test_client_create_update_contacts_addresses_added_date_and_delete(self) -> None:
        service = ClientService(self.db)
        created = service.create_client(
            ClientCreate(
                client_type="company",
                name=f"Audited {uuid4().hex}",
                country_code="PL",
                emails=[ClientContactInput(value="audit@example.invalid", is_primary=True)],
                phones=[ClientContactInput(value="+48 123 456 789", is_primary=True)],
                addresses=[ClientAddressInput(street="Krótka", city="Łódź", is_primary=True)],
            ),
            actor_user_id=self.admin.id,
        )
        events = self.db.query(ChangeHistoryEvent).filter(
            ChangeHistoryEvent.operation_id.is_not(None),
            ChangeHistoryEvent.entity_id.in_([created.id, *[x.id for x in created.contact_points], *[x.id for x in created.address_records]]),
        ).all()
        self.assertTrue(any(x.entity_type == "client" and x.action == "created" for x in events))
        self.assertTrue(any(x.entity_type == "client_contact" for x in events))
        self.assertTrue(any(x.entity_type == "client_address" for x in events))

        original_created_at = created.created_at
        service.update_client(
            created.id,
            ClientUpdate(
                city="Poznań",
                client_added_at=date(2026, 8, 18),
                emails=[],
                phones=[],
                addresses=[],
            ),
            actor_user_id=self.admin.id,
        )
        self.db.expire_all()
        changed = self.db.query(ChangeHistoryEvent).filter_by(
            entity_type="client", entity_id=created.id, action="updated"
        ).one()
        self.assertIn("client_added_at", changed.changed_fields)
        self.assertEqual(self.db.get(Client, created.id).created_at, original_created_at)
        self.assertTrue(self.db.query(ChangeHistoryEvent).filter_by(entity_type="client_contact", action="deleted").count())
        self.assertTrue(self.db.query(ChangeHistoryEvent).filter_by(entity_type="client_address", action="deleted").count())
        service.delete_client(created.id, actor_user_id=self.admin.id)
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(entity_type="client", action="deleted").count(), 1)

    def test_client_noop_and_audit_failure_rolls_back_business_write(self) -> None:
        service = ClientService(self.db)
        before_count = self.db.query(ChangeHistoryEvent).count()
        service.update_client(
            self.client.id,
            ClientUpdate(name=self.client.name),
            actor_user_id=self.admin.id,
        )
        self.assertEqual(self.db.query(ChangeHistoryEvent).count(), before_count)
        with patch.object(ChangeHistoryService, "persist", side_effect=RuntimeError("synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                service.update_client(self.client.id, ClientUpdate(city="Gdańsk"), actor_user_id=self.admin.id)
        self.db.expire_all()
        self.assertEqual(self.db.get(Client, self.client.id).city, "Warszawa")

    def test_status_activity_and_history_are_atomic_and_noop_safe(self) -> None:
        operation = uuid4()
        request = ClientWorkflowBatchRequest(
            client_ids=[self.client.id],
            status="phone_contact",
            effective_date=date(2026, 8, 19),
            operation_id=operation,
        )
        ClientBulkService(self.db).set_workflow_status(request, actor_user_id=self.admin.id)
        self.assertEqual(self.db.query(ClientActivityEvent).count(), 1)
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(action="status_changed").count(), 1)
        ClientBulkService(self.db).set_workflow_status(
            request.model_copy(update={"operation_id": uuid4()}),
            actor_user_id=self.admin.id,
        )
        self.assertEqual(self.db.query(ClientActivityEvent).count(), 1)
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(action="status_changed").count(), 1)

        other = Client(client_type="company", name=f"atomic-{uuid4()}", country_code="PL")
        self.db.add(other)
        self.db.flush()
        failing = request.model_copy(update={"client_ids": [other.id], "operation_id": uuid4()})
        with patch.object(ChangeHistoryService, "persist", side_effect=RuntimeError("synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                ClientBulkService(self.db).set_workflow_status(failing, actor_user_id=self.admin.id)
        self.assertEqual(self.db.query(ClientActivityEvent).filter_by(client_id=other.id).count(), 0)

    def test_candidate_reject_and_accept_are_audited(self) -> None:
        rejected = ClientCandidate(
            client_type="company", name=f"reject-{uuid4()}", country_code="PL",
            status="pending", confidence=0.5, raw_payload={"synthetic": True},
        )
        accepted = ClientCandidate(
            client_type="company", name=f"accept-{uuid4()}", country_code="PL",
            primary_email=f"{uuid4().hex}@example.invalid",
            status="pending", confidence=0.5, raw_payload={"synthetic": True},
        )
        self.db.add_all([rejected, accepted])
        self.db.flush()
        service = ClientCandidateReviewService(self.db)
        service.reject_candidate(rejected.id, actor_user_id=self.admin.id)
        promoted = service.accept_candidate(accepted.id, actor_user_id=self.admin.id)
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(entity_type="client_candidate", action="rejected").count(), 1)
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(entity_type="client_candidate", action="accepted").count(), 1)
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(entity_type="client", entity_id=promoted.id, action="created").count(), 1)

    def test_candidate_merge_and_domain_audits_are_projected_not_copied(self) -> None:
        candidate = ClientCandidate(
            client_type="company", name=f"merge-{uuid4()}", country_code="PL",
            status="merged", confidence=1.0, matched_client_id=self.client.id,
            raw_payload={"synthetic": True},
        )
        self.db.add(candidate)
        self.db.flush()
        merge = CandidateMergeEvent(
            operation_id=str(uuid4()), actor_user_id=self.admin.id,
            candidate_id=candidate.id, target_client_id=self.client.id,
            action="candidate_merged", changed_fields=["contacts"],
            relation_counts={"contacts_added": 1},
        )
        self.db.add(merge)
        self.db.flush()
        page = ChangeHistoryQueryService(self.db).get_page(
            entity_type="candidate_merge", entity_id=candidate.id, limit=50
        )
        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].source_type, "candidate_merge")
        self.assertEqual(self.db.query(ChangeHistoryEvent).filter_by(entity_type="candidate_merge").count(), 0)
        document_page = ChangeHistoryQueryService(self.db).get_page(entity_type="document", limit=50)
        lifecycle_page = ChangeHistoryQueryService(self.db).get_page(entity_type="user", limit=50)
        self.assertGreaterEqual(document_page.total, 1)
        self.assertGreaterEqual(lifecycle_page.total, 1)

    def test_admin_api_auth_filters_pagination_and_actor_projection(self) -> None:
        self._persist()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        http = TestClient(app)
        self.assertEqual(http.get("/api/v1/admin/change-history").status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.assertEqual(http.get("/api/v1/admin/change-history").status_code, 403)
        app.dependency_overrides[require_admin] = lambda: self.admin
        response = http.get(
            "/api/v1/admin/change-history",
            params={
                "entity_type": "client",
                "entity_id": self.client.id,
                "actor_user_id": self.admin.id,
                "action": "updated",
                "date_from": "2020-01-01T00:00:00Z",
                "date_to": datetime.now(timezone.utc).isoformat(),
                "skip": 0,
                "limit": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["actor_user_id"], self.admin.id)
        self.assertEqual(body["items"][0]["actor_display_name"], self.admin.username)
        serialized = json.dumps(body).casefold()
        for forbidden in ("synthetic-hash", "password", "authorization", "email_body"):
            self.assertNotIn(forbidden, serialized)

    def test_bounded_query_performance_latest_entity_and_actor(self) -> None:
        service = ChangeHistoryService(self.db)
        for index in range(300):
            service.persist(
                actor_user_id=self.admin.id,
                entity_type="client",
                entity_id=self.client.id,
                action="updated",
                before={"city": f"City {index}"},
                after={"city": f"City {index + 1}"},
                operation_id=f"perf-{index}",
                source_key=f"test:performance:{uuid4()}",
            )
        measurements: dict[str, list[float]] = {
            "latest": [], "entity": [], "actor": [],
        }
        queries = {
            "latest": {},
            "entity": {"entity_type": "client", "entity_id": self.client.id},
            "actor": {"actor_user_id": self.admin.id},
        }
        for name, filters in queries.items():
            for _ in range(5):
                started = perf_counter()
                page = ChangeHistoryQueryService(self.db).get_page(
                    limit=50, **filters
                )
                measurements[name].append((perf_counter() - started) * 1000)
                self.assertEqual(len(page.items), 50)
        report = {
            name: {
                "median_ms": round(median(values), 3),
                "max_ms": round(max(values), 3),
            }
            for name, values in measurements.items()
        }
        print(f"CHUNK07_QUERY_PERFORMANCE={report}")
        self.assertLess(max(max(values) for values in measurements.values()), 500)


if __name__ == "__main__":
    unittest.main()
