from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.candidate_source import CandidateSource
from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.import_source import ImportSource
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.user import User
from app.services.timeline_service import TimelineService


class TimelineReadModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.actor = self.db.query(User).filter(User.is_active.is_(True)).first()
        self.assertIsNotNone(self.actor)
        self.now = datetime.now(UTC).replace(microsecond=0)
        suffix = uuid.uuid4().hex
        self.client = Client(
            client_type="company",
            name=f"Timeline {suffix}",
            country_code="PL",
            created_at=self.now - timedelta(days=5),
        )
        self.other_client = Client(
            client_type="company", name=f"Other {suffix}", country_code="PL"
        )
        self.db.add_all([self.client, self.other_client])
        self.db.flush()
        self.project = Project(
            client_id=self.client.id,
            name="Realizacja osi czasu",
            status="active",
            created_by_user_id=self.actor.id,
            created_at=self.now - timedelta(days=4),
        )
        self.db.add(self.project)
        self.db.flush()
        self.inspection = Inspection(
            client_id=self.client.id,
            project_id=self.project.id,
            title="Wizja osi czasu",
            status="completed",
            scheduled_at=self.now - timedelta(days=2, hours=1),
            started_at=self.now - timedelta(days=2),
            completed_at=self.now - timedelta(days=1),
            created_by_user_id=self.actor.id,
            updated_by_user_id=self.actor.id,
            created_at=self.now - timedelta(days=3),
        )
        self.db.add(self.inspection)
        self.db.flush()
        self.document = Document(
            filename="timeline.pdf",
            original_filename="Raport timeline.pdf",
            content_type="application/pdf",
            file_size=10,
            source_type="manual_upload",
            client_id=self.client.id,
            project_id=self.project.id,
            inspection_id=self.inspection.id,
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
            created_at=self.now - timedelta(hours=12),
        )
        self.photo = Document(
            filename="timeline.jpg",
            original_filename="Zdjęcie timeline.jpg",
            content_type="image/jpeg",
            file_size=10,
            source_type="camera_photo",
            client_id=self.client.id,
            project_id=self.project.id,
            inspection_id=self.inspection.id,
            captured_at=self.now - timedelta(hours=6),
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.unrelated = Document(
            filename="unrelated.pdf",
            content_type="application/pdf",
            file_size=10,
            source_type="manual_upload",
            client_id=self.client.id,
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.db.add_all([self.document, self.photo, self.unrelated])
        self.db.flush()
        source = ImportSource(
            source_type="gmail",
            display_name=f"Timeline Gmail {suffix}",
            status="active",
        )
        candidate = ClientCandidate(
            client_type="company",
            name="Timeline mail candidate",
            status="accepted",
            confidence=1,
            matched_client_id=self.client.id,
        )
        self.db.add_all([source, candidate])
        self.db.flush()
        self.email = CandidateSource(
            candidate_id=candidate.id,
            import_source_id=source.id,
            source_type="gmail_message",
            external_id=f"timeline-{suffix}",
            extracted_text="SECRET RAW BODY MUST NOT APPEAR",
            raw_payload={
                "direction": "received",
                "date": (self.now - timedelta(hours=3)).isoformat(),
                "from": "Sender <sender@example.com>",
                "subject": "Bezpieczny temat",
                "text": "SECRET RAW BODY MUST NOT APPEAR",
            },
        )
        self.db.add(self.email)
        self.db.flush()
        self.link = DocumentClientLinkEvent(
            document_id=self.document.id,
            actor_user_id=self.actor.id,
            action="LINK",
            new_client_id=self.client.id,
            reason="manual",
        )
        self.db.add(self.link)
        self.db.flush()
        self.merge = CandidateMergeEvent(
            operation_id=str(uuid.uuid4()),
            actor_user_id=self.actor.id,
            candidate_id=candidate.id,
            target_client_id=self.client.id,
            action="candidate_merged",
            changed_fields=[],
            relation_counts={
                "contacts_added": 0,
                "addresses_added": 0,
                "documents_relinked": 0,
                "emails_relinked": 0,
                "sources_preserved": 1,
            },
        )
        self.db.add(self.merge)
        self.db.flush()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_client_timeline_sources_filters_pagination_and_safe_payload(self) -> None:
        service = TimelineService(self.db)
        page = service.get_client_timeline(
            client_id=self.client.id, skip=0, limit=100
        )
        kinds = {item.event_type for item in page.items}
        self.assertTrue(
            {
                "client_created",
                "project_created",
                "inspection_created",
                "inspection_scheduled",
                "inspection_started",
                "inspection_completed",
                "document_added",
                "photo_captured",
                "email_received",
                "document_client_linked",
                "candidate_merged",
            }.issubset(kinds)
        )
        serialized = json.dumps(
            page.model_dump(mode="json"), ensure_ascii=False
        )
        self.assertNotIn("SECRET RAW BODY", serialized)
        self.assertNotIn("extracted_text", serialized)
        self.assertNotIn("raw_payload", serialized)
        ordering = [(item.occurred_at, item.stable_key) for item in page.items]
        self.assertEqual(ordering, sorted(ordering, reverse=True))

        first = service.get_client_timeline(
            client_id=self.client.id, skip=0, limit=2
        )
        second = service.get_client_timeline(
            client_id=self.client.id, skip=2, limit=2
        )
        self.assertTrue({item.stable_key for item in first.items}.isdisjoint(
            {item.stable_key for item in second.items}
        ))
        filtered = service.get_client_timeline(
            client_id=self.client.id,
            skip=0,
            limit=20,
            event_type="document_added",
            date_from=self.now - timedelta(days=1),
            date_to=self.now,
        )
        self.assertGreaterEqual(filtered.total, 1)
        self.assertTrue(all(item.event_type == "document_added" for item in filtered.items))

    def test_project_scope_excludes_unrelated_document_and_email(self) -> None:
        page = TimelineService(self.db).get_project_timeline(
            project_id=self.project.id, skip=0, limit=100
        )
        self.assertNotIn(self.unrelated.id, {item.document_id for item in page.items})
        self.assertFalse(any(item.event_type.startswith("email_") for item in page.items))
        self.assertTrue(all(item.project_id == self.project.id for item in page.items))

    def test_empty_client_and_bounded_query_count(self) -> None:
        empty = Client(client_type="person", name="Empty timeline", country_code="PL")
        self.db.add(empty)
        self.db.flush()
        statements: list[str] = []

        def capture(*args) -> None:
            statements.append(str(args[2]))

        event.listen(self.connection, "before_cursor_execute", capture)
        try:
            page = TimelineService(self.db).get_client_timeline(
                client_id=empty.id, skip=0, limit=20
            )
        finally:
            event.remove(self.connection, "before_cursor_execute", capture)
        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].event_type, "client_created")
        self.assertLessEqual(len(statements), 25)

    def test_routes_require_auth_and_return_source_references(self) -> None:
        def override_db():
            yield self.db

        client = TestClient(app)
        self.assertIn(
            client.get(f"/api/v1/clients/{self.client.id}/timeline").status_code,
            (401, 403),
        )
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.actor
        response = client.get(
            f"/api/v1/clients/{self.client.id}/timeline?limit=100"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(all(item["source_id"] is not None for item in response.json()["items"]))
        project = client.get(
            f"/api/v1/projects/{self.project.id}/timeline?limit=100"
        )
        self.assertEqual(project.status_code, 200, project.text)
        document = client.get(
            f"/api/v1/documents?document_id={self.document.id}"
        )
        self.assertEqual(document.status_code, 200, document.text)
        self.assertEqual(document.json()["total"], 1)
        self.assertEqual(document.json()["items"][0]["id"], self.document.id)
        document = client.get(
            f"/api/v1/documents?document_id={self.document.id}"
        )
        self.assertEqual(document.status_code, 200, document.text)
        self.assertEqual(document.json()["total"], 1)
        self.assertEqual(document.json()["items"][0]["id"], self.document.id)


if __name__ == "__main__":
    unittest.main()
