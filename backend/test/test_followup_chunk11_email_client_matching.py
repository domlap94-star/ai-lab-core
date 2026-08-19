from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.session import SessionLocal, engine
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.candidate_source import CandidateSource
from app.models.document import Document
from app.models.import_source import ImportSource
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
)
from app.services.email_client_matching_service import (
    EMAIL_MATCH_METADATA_KEY,
    EmailClientMatchingService,
)
from app.services.email_attachment_reconciliation_service import (
    EmailAttachmentReconciliationService,
)
from app.services.forward_client_contact_service import ForwardClientContactService
from app.services.forward_source_ingestion_service import (
    ForwardSourceIngestionService,
)
from app.services.import_ingest_service import ImportIngestService


class FakeRepository:
    def __init__(self) -> None:
        self.clients = {index: SimpleNamespace(id=index) for index in range(1, 8)}
        self.emails: dict[str, list[int]] = {}
        self.phones: dict[str, list[int]] = {}
        self.taxes: dict[str, list[int]] = {}
        self.references: dict[str, list[int]] = {}
        self.threads: dict[str, list[int]] = {}
        self.names: dict[tuple[str, str], list[int]] = {}

    def _rows(self, mapping, value, limit):
        return [self.clients[item] for item in mapping.get(value, [])][:limit]

    def find_clients_by_email(self, value, *, limit=11):
        return self._rows(self.emails, value.casefold(), limit)

    def find_clients_by_phone(self, value, *, limit=11):
        value = ForwardSourceIngestionService.normalize_phone(value)
        return self._rows(self.phones, value, limit)

    def find_clients_by_tax_id(self, value, *, limit=11):
        value = ForwardSourceIngestionService.normalize_tax_id(value)
        return self._rows(self.taxes, value, limit)

    def find_clients_by_registration_number(self, value, *, limit=11):
        return self._rows(self.references, value.casefold(), limit)

    def find_thread_client_ids(
        self,
        *,
        import_source_id,
        external_parent_id,
        exclude_external_id=None,
        limit=11,
    ):
        del import_source_id
        del exclude_external_id
        return self.threads.get(external_parent_id, [])[:limit]

    def get_clients_by_ids(self, values):
        return [self.clients[value] for value in values if value in self.clients]

    def find_clients_by_name_city(self, *, name, city, limit=11):
        key = (" ".join(name.split()).casefold(), " ".join((city or "").split()).casefold())
        return self._rows(self.names, key, limit)


def request(
    *,
    sender="sender@example.test",
    text="",
    name="Synthetic Sender",
    city=None,
    tax_id=None,
    registration_number=None,
    thread=None,
    attachments=None,
):
    payload = {
        "text": text,
        "from": {"value": [{"address": sender, "name": name}]},
    }
    if attachments is not None:
        payload["attachments"] = attachments
    value = ImportIngestRequest(
        import_source_id=1,
        candidate=CandidateDataInput(
            name=name,
            primary_email=sender,
            city=city,
            tax_id=tax_id,
            registration_number=registration_number,
        ),
        source=CandidateSourceInput(
            source_type="gmail_message",
            external_id="synthetic-message",
            external_parent_id=thread,
            extracted_text=text,
            raw_payload=payload,
        ),
    )
    return ForwardSourceIngestionService().prepare(value)


def decide(repo, **kwargs):
    return EmailClientMatchingService(repo).match(request(**kwargs))


def test_20_case_matching_matrix():
    # 1 exact primary email; 2 additional contact uses the same canonical map.
    repo = FakeRepository()
    repo.emails["sender@example.test"] = [1]
    assert decide(repo).confidence == "certain"
    assert decide(repo).client.id == 1

    # 3 case variation.
    assert decide(repo, sender="SENDER@EXAMPLE.TEST").client.id == 1

    # 4 exact phone in current body.
    repo = FakeRepository()
    repo.phones["501502503"] = [2]
    assert decide(repo, text="Kontakt: +48 501 502 503").client.id == 2

    # 5 exact NIP in current body.
    repo = FakeRepository()
    repo.taxes["1234567890"] = [2]
    assert decide(repo, text="NIP: 123-456-78-90").client.id == 2

    # 6 NIP in already extracted attachment text.
    result = decide(
        repo,
        attachments=[{"content_type": "application/pdf", "extracted_text": "NIP 1234567890"}],
    )
    assert result.client.id == 2

    # 7 independent exact email and NIP point to the same Client.
    repo.emails["sender@example.test"] = [2]
    assert decide(repo, text="NIP 1234567890").client.id == 2

    # 8 contradictory email and NIP never auto-link.
    repo.emails["sender@example.test"] = [1]
    result = decide(repo, text="NIP 1234567890")
    assert result.confidence == "ambiguous" and result.client is None

    # 9 name only and 10 name+city are review proposals, never certain.
    repo = FakeRepository()
    repo.names[("synthetic sender", "")] = [1]
    assert decide(repo, sender="kontakt@podnoszenieposadzek.pl").confidence == "high"
    repo.names[("synthetic sender", "warszawa")] = [1]
    assert decide(repo, sender="kontakt@podnoszenieposadzek.pl", city="Warszawa").confidence == "high"

    # 11 generic mailbox and 14 shared contact yield multiple exact targets.
    repo = FakeRepository()
    repo.emails["biuro@example.test"] = [1, 2]
    assert decide(repo, sender="biuro@example.test").confidence == "ambiguous"
    repo.phones["501502503"] = [1, 2]
    assert decide(repo, sender="none@example.test", text="tel. 501 502 503").confidence == "ambiguous"

    # 12 forwarded/first-party sender: body email is evidence for review only.
    repo = FakeRepository()
    repo.emails["customer@example.test"] = [3]
    result = decide(
        repo,
        sender="kontakt@podnoszenieposadzek.pl",
        text="Przekazuję kontakt customer@example.test",
    )
    assert result.confidence == "high" and result.client is None

    repo.phones["501502503"] = [3]
    result = decide(
        repo,
        sender="kontakt@podnoszenieposadzek.pl",
        text="Przekazuję numer 501 502 503",
    )
    assert result.confidence == "high" and result.client is None

    # 13 a known thread is supporting evidence only.
    repo = FakeRepository()
    repo.threads["thread-1"] = [3]
    result = decide(
        repo, sender="kontakt@podnoszenieposadzek.pl", thread="thread-1"
    )
    assert result.confidence == "high" and result.client is None

    # 15 attachment filename alone is never identity evidence.
    repo = FakeRepository()
    result = decide(
        repo,
        attachments=[{"content_type": "application/pdf", "filename": "client-1.pdf"}],
    )
    assert result.confidence == "unresolved"

    # 16 OCR exact identifier can be certain.
    repo.taxes["1234567890"] = [4]
    result = decide(
        repo,
        attachments=[{"content_type": "image/png", "ocr_text": "NIP 1234567890"}],
    )
    assert result.client.id == 4 and not result.vision_required

    # 17 image without OCR/text requests review/visual evidence; no job is run.
    result = decide(
        FakeRepository(),
        attachments=[{"content_type": "image/png", "filename": "scan.png"}],
    )
    assert result.confidence == "unresolved" and result.vision_required

    # 18 no evidence remains unresolved.
    assert decide(FakeRepository()).confidence == "unresolved"

    # 19 re-evaluation is deterministic and side-effect free.
    repo = FakeRepository()
    repo.emails["sender@example.test"] = [5]
    first = decide(repo).metadata()
    second = decide(repo).metadata()
    assert first == second

    # 20 an existing-link style exact conflict remains ambiguous.
    repo.taxes["1234567890"] = [6]
    result = decide(repo, text="NIP 1234567890")
    assert result.confidence == "ambiguous"
    assert result.candidate_client_ids == (5, 6)


def test_body_contacts_are_not_added_to_matched_client():
    prepared = request(
        text="Kontakt dodatkowy: other@example.test, tel. 501 502 503"
    )
    client = SimpleNamespace(
        name="Synthetic",
        primary_email=None,
        primary_phone=None,
        contact_points=[],
    )
    added = ForwardClientContactService.add_from_payloads(
        client,
        [prepared.source.raw_payload],
        source_type="gmail_message",
    )
    assert added == 1
    assert [item.normalized_value for item in client.contact_points] == [
        "sender@example.test"
    ]
    own_identity = request(
        sender="kontakt@podnoszenieposadzek.pl",
        text="NIP 821-269-75-53, kontakt@podnoszenieposadzek.pl",
    )
    own_metadata = own_identity.source.raw_payload[
        "_next_stabil_forward_contacts_v1"
    ]
    assert own_metadata["body_tax_ids"] == []
    assert own_metadata["body_emails"] == []


def test_decision_metadata_is_bounded_and_contains_no_body():
    repo = FakeRepository()
    repo.emails["sender@example.test"] = [1]
    metadata = decide(repo, text="customer secret body").metadata()
    serialized = repr(metadata).casefold()
    assert "customer secret body" not in serialized
    assert set(metadata) == {
        "version",
        "confidence",
        "matched_client_id",
        "candidate_client_ids",
        "reasons",
        "contradictory",
        "vision_required",
        "evidence",
    }


def test_ingest_integration_is_idempotent_and_rolls_back():
    marker = uuid4().hex
    email = f"chunk11-{marker}@example.invalid"
    tax_a = "1111111111"
    tax_b = "2222222222"
    connection = engine.connect()
    outer = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    candidate_ids: list[int] = []
    try:
        import_source = (
            db.query(ImportSource)
            .filter(
                ImportSource.is_enabled.is_(True),
                ImportSource.deleted_at.is_(None),
            )
            .order_by(ImportSource.id.asc())
            .first()
        )
        assert import_source is not None
        client_a = Client(
            client_type="company",
            name=f"Chunk11 A {marker}",
            country_code="PL",
            primary_email=email,
            tax_id=tax_a,
        )
        client_b = Client(
            client_type="company",
            name=f"Chunk11 B {marker}",
            country_code="PL",
            tax_id=tax_b,
        )
        db.add_all([client_a, client_b])
        db.flush()

        exact = request(sender=email, text="Bieżąca wiadomość")
        exact = exact.model_copy(
            update={
                "import_source_id": import_source.id,
                "source": exact.source.model_copy(
                    update={"external_id": f"chunk11-exact-{marker}"}
                ),
            }
        )
        result = ImportIngestService(db).ingest(exact)
        candidate_ids.append(result.candidate_id)
        assert result.match_confidence == "certain"
        assert result.matched_client_id == client_a.id
        assert result.candidate_status == "duplicate"

        replay = ImportIngestService(db).ingest(exact)
        assert replay.candidate_id == result.candidate_id
        assert replay.matched_client_id == client_a.id
        assert replay.match_confidence == "certain"
        assert not replay.created_source

        conflict = request(sender=email, text=f"NIP: {tax_b}")
        conflict = conflict.model_copy(
            update={
                "import_source_id": import_source.id,
                "source": conflict.source.model_copy(
                    update={"external_id": f"chunk11-conflict-{marker}"}
                ),
            }
        )
        result = ImportIngestService(db).ingest(conflict)
        candidate_ids.append(result.candidate_id)
        assert result.match_confidence == "ambiguous"
        assert result.matched_client_id is None
        assert result.candidate_status == "pending"
        assert set(result.candidate_client_ids) == {client_a.id, client_b.id}
        stored = db.get(ClientCandidate, result.candidate_id)
        decision = stored.raw_payload["source"]["raw_payload"][
            EMAIL_MATCH_METADATA_KEY
        ]
        assert decision["confidence"] == "ambiguous"
        assert "Bieżąca wiadomość" not in repr(decision)
    finally:
        db.close()
        if outer.is_active:
            outer.rollback()
        connection.close()

    verification = SessionLocal()
    try:
        assert (
            verification.query(ClientCandidate)
            .filter(ClientCandidate.id.in_(candidate_ids))
            .count()
            == 0
        )
        assert (
            verification.query(Client)
            .filter(Client.name.like(f"Chunk11 % {marker}"))
            .count()
            == 0
        )
    finally:
        verification.close()


def test_future_attachment_reconciliation_is_certain_and_rolls_back():
    marker = uuid4().hex
    tax_id = "3333333333"
    connection = engine.connect()
    outer = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids: dict[str, int] = {}
    try:
        import_source = (
            db.query(ImportSource)
            .filter(
                ImportSource.is_enabled.is_(True),
                ImportSource.deleted_at.is_(None),
            )
            .order_by(ImportSource.id.asc())
            .first()
        )
        assert import_source is not None
        client = Client(
            client_type="company",
            name=f"Chunk11 Attachment {marker}",
            country_code="PL",
            tax_id=tax_id,
        )
        conflicting_client = Client(
            client_type="company",
            name=f"Chunk11 Conflict {marker}",
            country_code="PL",
            tax_id="4444444444",
        )
        candidate = ClientCandidate(
            client_type="company",
            name=f"Chunk11 Pending {marker}",
            country_code="PL",
            status="pending",
            confidence=0.0,
        )
        db.add_all([client, conflicting_client, candidate])
        db.flush()
        message_id = f"chunk11-attachment-{marker}"
        source = CandidateSource(
            candidate_id=candidate.id,
            import_source_id=import_source.id,
            source_type="gmail_message",
            external_id=message_id,
            raw_payload={
                "from": {
                    "value": [
                        {
                            "address": "kontakt@podnoszenieposadzek.pl",
                            "name": "NEXT Stabil",
                        }
                    ]
                },
                "text": "Załącznik zawiera dane identyfikacyjne.",
                EMAIL_MATCH_METADATA_KEY: {
                    "version": "NEXT_STABIL_EMAIL_CLIENT_MATCH_V2",
                    "confidence": "unresolved",
                    "matched_client_id": None,
                    "candidate_client_ids": [],
                    "reasons": [],
                    "contradictory": False,
                    "vision_required": False,
                    "evidence": [],
                },
            },
        )
        db.add(source)
        db.flush()
        document = Document(
            filename=f"{marker}.pdf",
            original_filename=f"{marker}.pdf",
            content_type="application/pdf",
            file_size=1,
            source_type="gmail_attachment",
            external_id=f"chunk11-document-{marker}",
            gmail_message_id=message_id,
            candidate_id=candidate.id,
            extracted_text=f"NIP: {tax_id}",
            processing_status="processed",
            metadata_status="processed",
            match_status="matched",
            vision_auto_eligible=True,
            vision_status="not_needed",
        )
        db.add(document)
        db.flush()
        ids = {"client": client.id, "candidate": candidate.id, "document": document.id}

        result = EmailAttachmentReconciliationService(db).reconcile(document.id)
        assert result.status == "linked_certain"
        assert result.client_id == client.id
        assert candidate.status == "duplicate"
        assert candidate.matched_client_id == client.id
        assert document.client_id == client.id
        assert document.match_method == "email_matching_v2_attachment"
        assert source.raw_payload[EMAIL_MATCH_METADATA_KEY]["confidence"] == "certain"

        repeated = EmailAttachmentReconciliationService(db).reconcile(document.id)
        assert repeated.status == "already_linked"
        assert repeated.client_id == client.id

        document.extracted_text = "NIP: 4444444444"
        db.add(document)
        db.flush()
        conflict = EmailAttachmentReconciliationService(db).reconcile(document.id)
        assert conflict.status == "review_existing_link_conflict"
        assert candidate.matched_client_id == client.id
        assert document.client_id == client.id
        assert document.match_status == "suggested"
        assert document.match_method == "email_matching_v2_conflict"
        assert source.raw_payload[EMAIL_MATCH_METADATA_KEY][
            "existing_link_conflict"
        ] is True
    finally:
        db.close()
        if outer.is_active:
            outer.rollback()
        connection.close()

    verification = SessionLocal()
    try:
        assert verification.get(ClientCandidate, ids["candidate"]) is None
        assert verification.get(Document, ids["document"]) is None
        assert verification.get(Client, ids["client"]) is None
    finally:
        verification.close()


if __name__ == "__main__":
    test_20_case_matching_matrix()
    test_body_contacts_are_not_added_to_matched_client()
    test_decision_metadata_is_bounded_and_contains_no_body()
    test_ingest_integration_is_idempotent_and_rolls_back()
    test_future_attachment_reconciliation_is_certain_and_rolls_back()
    print("follow-up chunk 11 email/client matching: 24/24 PASS")
