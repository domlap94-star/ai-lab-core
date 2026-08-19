from __future__ import annotations

from datetime import date
import json
import os
import unittest
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.engine import engine
from app.models.client import Client
from app.models.client_activity_event import ClientActivityEvent
from app.models.client_contact_point import ClientContactPoint
from app.models.role import Role
from app.models.user import User
from app.schemas.client_activity import CallActivityMetadata, CallInitiatedRequest, StatusActivityMetadata
from app.schemas.client_bulk import ClientWorkflowBatchRequest
from app.services.client_activity_service import ActivityConflictError, ActivityValidationError, ClientActivityService
from app.services.client_bulk_service import ClientBulkService
from app.services.timeline_service import TimelineService


ISOLATED_DB_NAME = "ai_lab_chunk06_isolated"


@unittest.skipUnless(os.getenv("POSTGRES_DB") == ISOLATED_DB_NAME, "requires isolated CHUNK 06 database")
class ClientActivityIsolatedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        role = Role(name=f"chunk06-{uuid4()}", description="isolated")
        self.db.add(role)
        self.db.flush()
        self.actor = User(username=f"chunk06-{uuid4().hex[:10]}", email=f"{uuid4().hex}@example.invalid", password_hash="not-a-secret", role_id=role.id, is_active=True)
        self.client = Client(client_type="company", name="CHUNK06 isolated", country_code="PL", primary_phone="+48 123 456 789")
        self.other = Client(client_type="company", name="CHUNK06 other", country_code="PL", primary_phone="123456789")
        self.db.add_all([self.actor, self.client, self.other])
        self.db.flush()
        self.contact = ClientContactPoint(client_id=self.client.id, kind="phone", value="+48 123 456 789", normalized_value="48123456789", is_primary=True, origin="manual")
        self.other_contact = ClientContactPoint(client_id=self.other.id, kind="phone", value="123456789", normalized_value="123456789", is_primary=True, origin="manual")
        self.db.add_all([self.contact, self.other_contact])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_call_create_actor_metadata_and_timeline(self) -> None:
        operation = uuid4()
        response = ClientActivityService(self.db).record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=operation, contact_id=self.contact.id)
        self.assertFalse(response.replayed)
        row = self.db.query(ClientActivityEvent).one()
        self.assertEqual(row.actor_user_id, self.actor.id)
        self.assertEqual(row.source_key, f"call:{operation}")
        self.assertEqual(row.event_metadata, {"contact_id": self.contact.id, "contact_kind": "phone", "contact_reference": "contact_point"})
        self.assertNotIn("123456789", json.dumps(row.event_metadata))
        item = TimelineService(self.db).get_client_timeline(client_id=self.client.id, skip=0, limit=20, event_type="call_initiated").items[0]
        self.assertEqual(item.stable_key, f"activity:{row.id}")
        self.assertEqual(item.actor_display_name, self.actor.username)

    def test_call_replay_and_conflicting_operation(self) -> None:
        operation = uuid4()
        first = ClientActivityService(self.db).record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=operation, contact_id=self.contact.id)
        second = ClientActivityService(self.db).record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=operation, contact_id=self.contact.id)
        self.assertTrue(second.replayed)
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(self.db.query(ClientActivityEvent).count(), 1)
        with self.assertRaises(ActivityConflictError):
            ClientActivityService(self.db).record_call(client_id=self.other.id, actor_user_id=self.actor.id, operation_id=operation, contact_id=self.other_contact.id)

    def test_cross_client_and_non_phone_contact_are_rejected(self) -> None:
        with self.assertRaises(ActivityValidationError):
            ClientActivityService(self.db).record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=uuid4(), contact_id=self.other_contact.id)
        email = ClientContactPoint(client_id=self.client.id, kind="email", value="safe@example.invalid", normalized_value="safe@example.invalid", is_primary=False, origin="manual")
        self.db.add(email)
        self.db.flush()
        with self.assertRaises(ActivityValidationError):
            ClientActivityService(self.db).record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=uuid4(), contact_id=email.id)

    def test_legacy_primary_phone_is_bounded(self) -> None:
        response = ClientActivityService(self.db).record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=uuid4(), contact_id=None)
        row = self.db.get(ClientActivityEvent, response.event_id)
        self.assertEqual(row.event_metadata["contact_reference"], "primary_phone")
        self.assertIsNone(row.event_metadata["contact_id"])

    def test_strict_request_and_metadata_reject_arbitrary_content(self) -> None:
        with self.assertRaises(ValidationError):
            CallInitiatedRequest(operation_id=uuid4(), contact_id=self.contact.id, actor_user_id=self.actor.id)
        with self.assertRaises(ValidationError):
            CallActivityMetadata(contact_id=self.contact.id, contact_kind="phone", contact_reference="contact_point", phone="123")
        with self.assertRaises(ValidationError):
            StatusActivityMetadata(old_status="untouched", new_status="completed", effective_date=None, raw_payload={})

    def test_status_change_is_persisted_once_and_noop_is_not(self) -> None:
        service = ClientBulkService(self.db)
        request = ClientWorkflowBatchRequest(client_ids=[self.client.id], status="phone_contact", effective_date=date(2026, 8, 19), operation_id=uuid4())
        service.set_workflow_status(request, actor_user_id=self.actor.id)
        self.assertEqual(self.db.query(ClientActivityEvent).filter_by(event_type="client_status_changed").count(), 1)
        service.set_workflow_status(ClientWorkflowBatchRequest(client_ids=[self.client.id], status="phone_contact", effective_date=date(2026, 8, 19), operation_id=uuid4()), actor_user_id=self.actor.id)
        self.assertEqual(self.db.query(ClientActivityEvent).filter_by(event_type="client_status_changed").count(), 1)
        item = TimelineService(self.db).get_client_timeline(client_id=self.client.id, skip=0, limit=20, event_type="client_status_changed").items[0]
        self.assertEqual(item.metadata["old_status"], "untouched")
        self.assertEqual(item.metadata["new_status"], "phone_contact")

    def test_sort_pagination_isolation_and_duplicate_keys(self) -> None:
        activity = ClientActivityService(self.db)
        for _ in range(3):
            activity.record_call(client_id=self.client.id, actor_user_id=self.actor.id, operation_id=uuid4(), contact_id=self.contact.id)
        first = TimelineService(self.db).get_client_timeline(client_id=self.client.id, skip=0, limit=2)
        second = TimelineService(self.db).get_client_timeline(client_id=self.client.id, skip=2, limit=2)
        self.assertTrue({x.stable_key for x in first.items}.isdisjoint({x.stable_key for x in second.items}))
        self.assertEqual(len({x.stable_key for x in first.items + second.items}), len(first.items + second.items))
        other = TimelineService(self.db).get_client_timeline(client_id=self.other.id, skip=0, limit=20, event_type="call_initiated")
        self.assertEqual(other.total, 0)


if __name__ == "__main__":
    unittest.main()
