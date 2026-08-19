from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.client_candidates.router import accept_client_candidate
from app.database.engine import engine
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.services.client_candidate_promotion_service import (
    CandidateDuplicateClientError,
    CandidateNotPendingError,
    ClientCandidatePromotionService,
)
from app.services.forward_client_contact_service import (
    ForwardClientContactService,
)
from app.services.forward_source_ingestion_service import CONTACT_METADATA_KEY


class FollowupChunk08CandidateDiagnosisTests(unittest.TestCase):
    """Synthetic-only characterization of the current promotion contract."""

    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.token = uuid4().hex
        self.service = ClientCandidatePromotionService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def _client(self, **overrides) -> Client:
        values = {
            "client_type": "company",
            "name": f"Synthetic Client {self.token}",
            "legal_name": None,
            "tax_id": None,
            "primary_email": None,
            "primary_phone": None,
            "city": None,
            "country_code": "PL",
        }
        values.update(overrides)
        client = Client(**values)
        self.db.add(client)
        self.db.flush()
        return client

    def _candidate(self, **overrides) -> ClientCandidate:
        values = {
            "client_type": "company",
            "name": f"Synthetic Candidate {self.token}",
            "legal_name": None,
            "tax_id": None,
            "primary_email": None,
            "primary_phone": None,
            "city": None,
            "country_code": "PL",
            "status": "pending",
            "confidence": 0.9,
            "matched_client_id": None,
            "raw_payload": {"synthetic": True},
        }
        values.update(overrides)
        candidate = ClientCandidate(**values)
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def _match(self, candidate: ClientCandidate) -> tuple[int | None, str | None]:
        client, matched_by = self.service.find_existing_client(candidate)
        return (client.id if client else None, matched_by)

    def test_01_unique_candidate_promotes_to_new_client(self) -> None:
        candidate = self._candidate(
            primary_email=f"unique-{self.token}@example.invalid"
        )
        client = self.service.promote(candidate.id)
        self.assertEqual(candidate.status, "accepted")
        self.assertEqual(candidate.matched_client_id, client.id)

    def test_02_exact_normalized_email_is_duplicate(self) -> None:
        client = self._client(primary_email=f"MAIL-{self.token}@EXAMPLE.INVALID")
        candidate = self._candidate(
            primary_email=f"  mail-{self.token}@example.invalid  "
        )
        self.assertEqual(self._match(candidate), (client.id, "email"))

    def test_03_exact_normalized_phone_is_duplicate(self) -> None:
        suffix = str(int(self.token[:8], 16)).zfill(9)[-9:]
        client = self._client(
            primary_phone=(
                f"+48 {suffix[:3]} {suffix[3:6]} {suffix[6:]}"
            )
        )
        candidate = self._candidate(primary_phone=suffix)
        self.assertEqual(self._match(candidate), (client.id, "phone"))

    def test_04_exact_normalized_tax_id_is_duplicate(self) -> None:
        digits = str(int(self.token[:9], 16)).zfill(10)[-10:]
        client = self._client(tax_id=digits)
        candidate = self._candidate(
            tax_id=f"{digits[:3]}-{digits[3:6]}-{digits[6:8]}-{digits[8:]}"
        )
        self.assertEqual(self._match(candidate), (client.id, "tax_id"))

    def test_05_same_name_only_is_not_a_duplicate(self) -> None:
        name = f"Shared Name {self.token}"
        self._client(name=name)
        candidate = self._candidate(name=name)
        self.assertEqual(self._match(candidate), (None, None))

    def test_06_same_name_and_city_is_not_a_duplicate(self) -> None:
        name = f"Shared City Name {self.token}"
        self._client(name=name, city="Krakow")
        candidate = self._candidate(name=name, city="Krakow")
        self.assertEqual(self._match(candidate), (None, None))

    def test_07_source_identity_is_not_used_by_duplicate_matcher(self) -> None:
        self._client(name=f"Source Target {self.token}")
        candidate = self._candidate(
            raw_payload={"synthetic": True, "external_id": self.token}
        )
        self.assertEqual(self._match(candidate), (None, None))

    def test_08_multiple_matches_are_collapsed_by_priority(self) -> None:
        email_client = self._client(
            primary_email=f"multi-{self.token}@example.invalid"
        )
        suffix = str(int(self.token[:8], 16)).zfill(9)[-9:]
        self._client(name=f"Phone Client {self.token}", primary_phone=suffix)
        candidate = self._candidate(
            primary_email=f"multi-{self.token}@example.invalid",
            primary_phone=suffix,
        )
        self.assertEqual(self._match(candidate), (email_client.id, "email"))

    def test_09_already_promoted_candidate_is_not_idempotent_result(self) -> None:
        candidate = self._candidate(
            primary_email=f"repeat-{self.token}@example.invalid"
        )
        self.service.promote(candidate.id)
        with self.assertRaises(CandidateNotPendingError):
            self.service.promote(candidate.id)

    def test_10_conflicting_tax_id_and_email_are_not_reported_together(self) -> None:
        digits = str(int(self.token[:9], 16)).zfill(10)[-10:]
        tax_client = self._client(tax_id=digits)
        self._client(
            name=f"Email Conflict {self.token}",
            primary_email=f"conflict-{self.token}@example.invalid",
        )
        candidate = self._candidate(
            tax_id=digits,
            primary_email=f"conflict-{self.token}@example.invalid",
        )
        self.assertEqual(self._match(candidate), (tax_client.id, "tax_id"))

    def test_11_contact_union_deduplicates_normalized_values(self) -> None:
        client = Client(
            client_type="company",
            name=f"Contact Union {self.token}",
            country_code="PL",
            primary_email=f"contact-{self.token}@example.invalid",
        )
        payload = {
            CONTACT_METADATA_KEY: {
                "emails": [
                    f"CONTACT-{self.token}@EXAMPLE.INVALID",
                    f"other-{self.token}@example.invalid",
                ],
                "phones": [],
            }
        }
        added = ForwardClientContactService.add_from_payloads(
            client, [payload], source_type="gmail_message"
        )
        self.assertEqual(added, 1)
        self.assertEqual(len(client.contact_points), 2)

    def test_12_document_relation_is_preserved_on_unique_promotion(self) -> None:
        candidate = self._candidate(
            primary_email=f"document-{self.token}@example.invalid"
        )
        document = Document(
            filename=f"{self.token}.pdf",
            original_filename=f"{self.token}.pdf",
            content_type="application/pdf",
            file_size=1,
            source_type="manual_upload",
            external_id=f"chunk08-{self.token}",
            candidate_id=candidate.id,
            processing_status="processed",
            metadata_status="processed",
            match_status="matched",
            vision_auto_eligible=False,
        )
        self.db.add(document)
        self.db.flush()

        client = self.service.promote(candidate.id)

        self.assertEqual(document.candidate_id, candidate.id)
        self.assertEqual(document.client_id, client.id)
        self.assertEqual(document.match_status, "confirmed")
        self.assertEqual(document.match_method, "candidate_accept")

    def test_current_duplicate_http_contract_is_typed_409_not_406(self) -> None:
        with patch(
            "app.api.client_candidates.router."
            "ClientCandidateReviewService.accept_candidate",
            side_effect=CandidateDuplicateClientError(
                client_id=123,
                matched_by="email",
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                accept_client_candidate(456, db=self.db)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "candidate_matches_existing_client",
                "message": "Candidate matches an existing client.",
                "matched_client_id": 123,
                "matched_by": "email",
            },
        )


if __name__ == "__main__":
    unittest.main()
