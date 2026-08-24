from __future__ import annotations

import unittest
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


ISOLATED_DB_NAME = "ai_lab_chunk08_isolated"
require_test_database_environment(ISOLATED_DB_NAME)

from app.database.engine import engine
from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.import_source import ImportSource
from app.models.user import User
from app.schemas.client_candidate_review import CandidateMergeRequest
from app.services.candidate_merge_service import (
    CandidateMergeConflictError,
    CandidateMergeService,
    CandidateMergeValidationError,
)
from app.services.client_candidate_promotion_service import (
    ClientCandidatePromotionService,
)
from app.services.forward_source_ingestion_service import CONTACT_METADATA_KEY


class CandidateMergeIsolatedTests(unittest.TestCase):
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
        self.token = uuid4().hex
        actor = self.db.query(User.id).order_by(User.id).first()
        self.actor_id = actor[0] if actor is not None else None
        self.assertIsNotNone(self.actor_id)

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def _client(self, **overrides) -> Client:
        values = {
            "client_type": "company",
            "name": f"Merge Target {self.token}",
            "country_code": "PL",
            "primary_email": f"match-{self.token}@example.invalid",
        }
        values.update(overrides)
        client = Client(**values)
        self.db.add(client)
        self.db.flush()
        return client

    def _candidate(self, **overrides) -> ClientCandidate:
        values = {
            "client_type": "company",
            "name": f"Merge Candidate {self.token}",
            "country_code": "PL",
            "primary_email": f"match-{self.token}@example.invalid",
            "status": "pending",
            "confidence": 0.9,
            "raw_payload": {"synthetic": True},
        }
        values.update(overrides)
        candidate = ClientCandidate(**values)
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def _source(self, candidate: ClientCandidate, *, email: str) -> CandidateSource:
        import_source = ImportSource(
            source_type="gmail",
            display_name=f"CHUNK08 {self.token}",
            status="inactive",
            is_enabled=False,
        )
        self.db.add(import_source)
        self.db.flush()
        source = CandidateSource(
            candidate_id=candidate.id,
            import_source_id=import_source.id,
            source_type="gmail_message",
            external_id=f"chunk08-{self.token}",
            source_label="Synthetic message",
            raw_payload={
                CONTACT_METADATA_KEY: {
                    "verified_emails": [email],
                    "verified_phones": [],
                }
            },
        )
        self.db.add(source)
        self.db.flush()
        return source

    def _request(self, preview, target_id: int, *, operation_id: str | None = None):
        decisions = {
            item.field: "keep_existing"
            for item in preview.field_proposals
            if item.required_resolution
        }
        return CandidateMergeRequest(
            operation_id=operation_id or str(uuid4()),
            target_client_id=target_id,
            field_decisions=decisions,
            expected_candidate_version=preview.expected_candidate_version,
        )

    def test_preview_is_read_only_and_bounded(self) -> None:
        target = self._client()
        candidate = self._candidate()
        before = self.db.query(CandidateMergeEvent).count()
        preview = CandidateMergeService(self.db).preview(
            candidate_id=candidate.id, target_client_id=target.id
        )
        self.assertEqual(self.db.query(CandidateMergeEvent).count(), before)
        self.assertEqual(candidate.status, "pending")
        self.assertEqual(preview.match.client_id, target.id)
        self.assertEqual(preview.match.reasons, ["exact_email"])

    def test_multiple_exact_matches_are_all_returned(self) -> None:
        email_target = self._client()
        phone_target = self._client(
            name=f"Phone Target {self.token}",
            primary_email=None,
            primary_phone="+48 123 456 789",
        )
        candidate = self._candidate(primary_phone="123456789")
        matches = ClientCandidatePromotionService(self.db).find_existing_clients(
            candidate
        )
        self.assertEqual([item.client.id for item in matches], [email_target.id, phone_target.id])

    def test_conflicting_tax_and_email_return_two_clients(self) -> None:
        digits = str(int(self.token[:9], 16)).zfill(10)[-10:]
        tax_target = self._client(
            primary_email=None,
            tax_id=f"{digits[:3]}-{digits[3:6]}-{digits[6:8]}-{digits[8:]}",
        )
        email_target = self._client(name=f"Email Target {self.token}")
        candidate = self._candidate(tax_id=digits)
        matches = ClientCandidatePromotionService(self.db).find_existing_clients(
            candidate
        )
        self.assertEqual([item.client.id for item in matches], [tax_target.id, email_target.id])

    def test_nip_conflict_requires_explicit_resolution(self) -> None:
        target = self._client(tax_id="111-222-33-44")
        candidate = self._candidate(tax_id="9998887766")
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        tax_proposal = next(
            item for item in preview.field_proposals if item.field == "tax_id"
        )
        self.assertTrue(tax_proposal.required_resolution)
        self.assertIn("tax_id:manual_resolution_required", preview.blocked_reasons)
        request = CandidateMergeRequest(
            operation_id=str(uuid4()),
            target_client_id=target.id,
            field_decisions={},
            expected_candidate_version=preview.expected_candidate_version,
        )
        with self.assertRaises(CandidateMergeValidationError):
            service.merge(
                candidate_id=candidate.id,
                actor_user_id=self.actor_id,
                request=request,
            )
        self.assertEqual(self.db.query(CandidateMergeEvent).count(), 0)

    def test_contact_union_is_deduplicated_and_audited(self) -> None:
        target = self._client()
        candidate = self._candidate()
        secondary = f"secondary-{self.token}@example.invalid"
        self._source(candidate, email=secondary)
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        result = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=self._request(preview, target.id),
        )
        self.assertEqual(result.relation_counts["contacts_added"], 1)
        normalized = [item.normalized_value for item in target.emails]
        self.assertEqual(normalized.count(secondary), 1)

    def test_address_union_does_not_replace_primary(self) -> None:
        target = self._client()
        candidate = self._candidate(street="Testowa", building_number="8", city="Warszawa")
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        request = self._request(preview, target.id)
        request.field_decisions["address"] = "add"
        result = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=request,
        )
        self.assertEqual(result.relation_counts["addresses_added"], 1)
        self.assertFalse(target.addresses[0].is_primary)

    def test_country_only_candidate_does_not_create_empty_address(self) -> None:
        target = self._client()
        candidate = self._candidate()
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        address = next(
            item for item in preview.field_proposals if item.field == "address"
        )
        self.assertEqual(address.proposed_action, "keep_existing")
        result = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=self._request(preview, target.id),
        )
        self.assertEqual(result.relation_counts["addresses_added"], 0)
        self.assertEqual(target.address_records, [])

    def test_document_relink_preserves_document_identity(self) -> None:
        target = self._client()
        candidate = self._candidate()
        document = Document(
            filename=f"{self.token}.pdf",
            original_filename=f"{self.token}.pdf",
            content_type="application/pdf",
            file_size=1,
            source_type="manual_upload",
            external_id=f"merge-{self.token}",
            candidate_id=candidate.id,
            processing_status="processed",
            metadata_status="processed",
            match_status="matched",
            checksum_sha256="a" * 64,
            vision_auto_eligible=False,
        )
        self.db.add(document)
        self.db.flush()
        document_id = document.id
        checksum = document.checksum_sha256
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        result = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=self._request(preview, target.id),
        )
        self.assertEqual(result.relation_counts["documents_relinked"], 1)
        self.assertEqual(document.id, document_id)
        self.assertEqual(document.checksum_sha256, checksum)
        self.assertEqual(document.client_id, target.id)
        self.assertEqual(document.match_method, "candidate_merge")

    def test_email_source_is_preserved_without_copy(self) -> None:
        target = self._client()
        candidate = self._candidate()
        source = self._source(candidate, email=f"mail-{self.token}@example.invalid")
        source_id = source.id
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        result = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=self._request(preview, target.id),
        )
        self.assertEqual(result.relation_counts["emails_relinked"], 1)
        self.assertEqual(self.db.get(CandidateSource, source_id).candidate_id, candidate.id)
        self.assertEqual(candidate.matched_client_id, target.id)

    def test_same_operation_is_idempotent_with_one_audit_row(self) -> None:
        target = self._client()
        candidate = self._candidate()
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        operation_id = str(uuid4())
        request = self._request(preview, target.id, operation_id=operation_id)
        first = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=request,
        )
        second = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=request,
        )
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(second.idempotent_replay)
        self.assertEqual(
            self.db.query(CandidateMergeEvent)
            .filter(CandidateMergeEvent.operation_id == operation_id)
            .count(),
            1,
        )

    def test_stale_preview_is_rejected_without_audit(self) -> None:
        target = self._client()
        candidate = self._candidate()
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        request = self._request(preview, target.id)
        request.expected_candidate_version = "2000-01-01T00:00:00+00:00"
        with self.assertRaises(CandidateMergeConflictError) as raised:
            service.merge(
                candidate_id=candidate.id,
                actor_user_id=self.actor_id,
                request=request,
            )
        self.assertEqual(raised.exception.code, "CANDIDATE_VERSION_CONFLICT")
        self.assertEqual(self.db.query(CandidateMergeEvent).count(), 0)

    def test_apply_rejects_decision_that_does_not_match_preview(self) -> None:
        target = self._client(primary_email=f"target-{self.token}@example.invalid")
        candidate = self._candidate(tax_id="521-123-45-67")
        target.tax_id = "5211234567"
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        request = self._request(preview, target.id)
        request.field_decisions["primary_email"] = "keep_existing"
        with self.assertRaises(CandidateMergeValidationError):
            service.merge(
                candidate_id=candidate.id,
                actor_user_id=self.actor_id,
                request=request,
            )
        self.assertEqual(self.db.query(CandidateMergeEvent).count(), 0)

    def test_audit_contains_metadata_only(self) -> None:
        target = self._client()
        candidate = self._candidate()
        service = CandidateMergeService(self.db)
        preview = service.preview(candidate_id=candidate.id, target_client_id=target.id)
        result = service.merge(
            candidate_id=candidate.id,
            actor_user_id=self.actor_id,
            request=self._request(preview, target.id),
        )
        event = self.db.query(CandidateMergeEvent).filter(
            CandidateMergeEvent.operation_id == result.operation_id
        ).one()
        serialized = str(event.changed_fields) + str(event.relation_counts)
        for forbidden in ("raw_payload", "email_body", "document_text", "token", "sql"):
            self.assertNotIn(forbidden, serialized.casefold())
        self.assertEqual(event.actor_user_id, self.actor_id)
        self.assertEqual(event.action, "candidate_merged")

    def test_isolated_schema_has_no_historical_audit_rows(self) -> None:
        self.assertEqual(
            self.db.execute(text("select count(1) from candidate_merge_events")).scalar(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
