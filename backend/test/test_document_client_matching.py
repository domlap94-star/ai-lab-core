import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.database.engine import engine
from app.database.session import SessionLocal
from app.main import app
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.client_contact_point import ClientContactPoint
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_chunk import DocumentChunk
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.document_page import DocumentPage
from app.models.user import User
from app.schemas.document import DocumentClientLinkRequest
from app.services.document_client_matching_service import (
    DocumentClientMatchingService,
    DocumentMatchConflictError,
    DocumentMatchInvalidOperationError,
    DocumentMatchNotFoundError,
)


class DocumentClientMatchingTests(unittest.TestCase):
    def setUp(self):
        if not inspect(engine).has_table("document_client_link_events"):
            self.skipTest("chunk8doclink_20260817 is not applied")
        self.db = SessionLocal()
        self.transaction = self.db.begin()
        self.actor = self.db.query(User).filter(User.is_active.is_(True)).first()
        self.assertIsNotNone(self.actor)
        suffix = uuid.uuid4().hex
        self.a = Client(client_type="company", name=f"Chunk8 A {suffix}", country_code="PL")
        self.b = Client(client_type="company", name=f"Chunk8 B {suffix}", country_code="PL")
        self.db.add_all([self.a, self.b])
        self.db.flush()
        self.candidate = ClientCandidate(
            client_type="company", name=f"Candidate {suffix}", status="pending",
            confidence=0.8, matched_client_id=self.a.id, primary_email=f"{suffix}@example.test",
        )
        self.db.add(self.candidate)
        self.db.flush()
        self.db.add(ClientContactPoint(
            client_id=self.a.id, kind="email", value=self.candidate.primary_email,
            normalized_value=self.candidate.primary_email, is_primary=True, position=0,
            origin="manual",
        ))
        self.document = Document(
            filename=f"{suffix}.pdf", original_filename="test.pdf",
            content_type="application/pdf", file_size=4, source_type="manual_upload",
            storage_path=f"synthetic/{suffix}.pdf",
            gmail_message_id=f"gmail-{suffix}",
            gmail_thread_id=f"thread-{suffix}",
            candidate_id=self.candidate.id, processing_status="stored", metadata_status="pending",
            match_status="suggested",
        )
        self.db.add(self.document)
        self.db.flush()
        self.db.add_all([
            DocumentPage(document_id=self.document.id, page_number=1),
            DocumentAsset(
                document_id=self.document.id,
                asset_index=1,
                storage_path=f"synthetic/{suffix}-asset.bin",
            ),
            DocumentChunk(
                document_id=self.document.id,
                chunk_index=0,
                content="synthetic",
                token_count=1,
                character_count=9,
            ),
        ])
        self.db.flush()
        self.service = DocumentClientMatchingService(self.db)

    def tearDown(self):
        self.transaction.rollback()
        self.db.close()

    def test_high_candidate_suggestion_and_none(self):
        match = self.service.get_match(self.document.id)
        self.assertEqual(match.confidence, "HIGH")
        self.assertEqual(match.suggestions[0].client_id, self.a.id)
        self.document.candidate_id = None
        self.document.checksum_sha256 = None
        match = self.service.get_match(self.document.id)
        self.assertEqual(match.confidence, "NONE")

    def test_name_only_candidate_does_not_create_low_suggestion(self):
        self.candidate.matched_client_id = None
        self.candidate.primary_email = None
        self.candidate.primary_phone = None
        self.db.flush()
        match = self.service.get_match(self.document.id)
        self.assertEqual(match.suggestions, [])
        self.assertEqual(match.confidence, "NONE")

    def test_medium_exact_contact_and_conflict(self):
        self.candidate.matched_client_id = None
        match = self.service.get_match(self.document.id)
        self.assertEqual(match.confidence, "MEDIUM")
        self.db.add(ClientContactPoint(
            client_id=self.b.id, kind="email", value=self.candidate.primary_email,
            normalized_value=self.candidate.primary_email, is_primary=True, position=0,
            origin="manual",
        ))
        self.db.flush()
        match = self.service.get_match(self.document.id)
        self.assertTrue(match.conflict)
        self.assertEqual(match.confidence, "CONFLICT")

    def test_link_move_unlink_undo_are_audited_and_document_is_preserved(self):
        _, link = self.service.link(
            self.document.id, self.actor,
            DocumentClientLinkRequest(client_id=self.a.id, confirm_conflict=True),
        )
        self.assertEqual(link.action, "LINK")
        _, move = self.service.link(
            self.document.id, self.actor,
            DocumentClientLinkRequest(client_id=self.b.id, confirm_conflict=True),
        )
        self.assertEqual((move.old_client_id, move.new_client_id), (self.a.id, self.b.id))
        _, unlink = self.service.unlink(self.document.id, self.actor, "test", confirm=True)
        self.assertEqual(unlink.action, "UNLINK")
        restored, undo = self.service.undo(self.document.id, self.actor)
        self.assertEqual(restored.client_id, self.b.id)
        self.assertEqual(undo.reversal_of_event_id, unlink.id)
        with self.assertRaises(DocumentMatchInvalidOperationError):
            self.service.undo(self.document.id, self.actor)
        self.assertIsNotNone(self.db.query(Document).filter(Document.id == self.document.id).first())
        self.assertEqual(
            self.db.query(DocumentClientLinkEvent).filter(
                DocumentClientLinkEvent.document_id == self.document.id
            ).count(), 4,
        )
        persisted = self.db.query(Document).filter(Document.id == self.document.id).one()
        self.assertEqual(persisted.storage_path, self.document.storage_path)
        self.assertEqual(persisted.candidate_id, self.candidate.id)
        self.assertEqual(persisted.gmail_message_id, self.document.gmail_message_id)
        self.assertEqual(persisted.gmail_thread_id, self.document.gmail_thread_id)
        self.assertEqual(self.db.query(DocumentPage).filter_by(document_id=self.document.id).count(), 1)
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=self.document.id).count(), 1)
        self.assertEqual(self.db.query(DocumentChunk).filter_by(document_id=self.document.id).count(), 1)
        events = (
            self.db.query(DocumentClientLinkEvent)
            .filter(DocumentClientLinkEvent.document_id == self.document.id)
            .order_by(DocumentClientLinkEvent.id)
            .all()
        )
        self.assertEqual([item.action for item in events], ["LINK", "MOVE", "UNLINK", "LINK"])
        self.assertEqual(events[-1].reversal_of_event_id, events[-2].id)

    def test_undo_link_and_move_restore_exact_previous_assignment(self):
        linked, link = self.service.link(
            self.document.id, self.actor,
            DocumentClientLinkRequest(client_id=self.a.id, confirm_conflict=True),
        )
        self.assertEqual(linked.client_id, self.a.id)
        restored, reverse_link = self.service.undo(self.document.id, self.actor)
        self.assertIsNone(restored.client_id)
        self.assertEqual(reverse_link.reversal_of_event_id, link.id)

        moved_from = Document(
            filename="move.pdf", original_filename="move.pdf",
            content_type="application/pdf", file_size=1,
            source_type="manual_upload", client_id=self.a.id,
            processing_status="stored", metadata_status="pending",
            match_status="confirmed",
        )
        self.db.add(moved_from)
        self.db.flush()
        moved, move = self.service.link(
            moved_from.id, self.actor,
            DocumentClientLinkRequest(client_id=self.b.id, confirm_conflict=True),
        )
        self.assertEqual(moved.client_id, self.b.id)
        restored_move, reverse_move = self.service.undo(moved_from.id, self.actor)
        self.assertEqual(restored_move.client_id, self.a.id)
        self.assertEqual(reverse_move.reversal_of_event_id, move.id)

    def test_audit_snapshot_is_bounded_and_preserves_candidate_reference(self):
        _, event = self.service.link(
            self.document.id, self.actor,
            DocumentClientLinkRequest(
                client_id=self.a.id,
                reason="operator confirmation",
                confirm_conflict=True,
            ),
        )
        self.assertEqual(event.actor_user_id, self.actor.id)
        self.assertEqual(event.previous_candidate_id, self.candidate.id)
        self.assertEqual(event.reason, "operator confirmation")
        self.assertEqual(
            set(event.evidence_snapshot),
            {"confidence", "suggested_client_ids", "evidence_kinds"},
        )
        self.assertNotIn("body", str(event.evidence_snapshot).lower())

    def test_invalid_deleted_client_and_confirmation_guards(self):
        self.b.deleted_at = self.document.created_at
        self.db.flush()
        with self.assertRaises(DocumentMatchNotFoundError):
            self.service.link(self.document.id, self.actor, DocumentClientLinkRequest(client_id=self.b.id))
        with self.assertRaises(DocumentMatchInvalidOperationError):
            self.service.unlink(self.document.id, self.actor, "test", confirm=False)

    def test_conflict_requires_explicit_confirmation(self):
        with self.assertRaises(DocumentMatchConflictError):
            self.service.link(
                self.document.id, self.actor,
                DocumentClientLinkRequest(client_id=self.b.id, confirm_conflict=False),
            )

    def test_mutation_endpoints_reject_unauthenticated_requests(self):
        http = TestClient(app)
        base = f"/api/v1/documents/{self.document.id}"
        self.assertEqual(http.get(f"{base}/client-match").status_code, 401)
        self.assertEqual(
            http.post(f"{base}/link-client", json={"client_id": self.a.id}).status_code,
            401,
        )
        self.assertEqual(
            http.post(f"{base}/unlink-client", json={"confirm": True}).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
