from types import SimpleNamespace
from uuid import uuid4

from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_contact_point import ClientContactPoint
from app.repositories.import_repository import ImportRepository
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
)
from app.services.forward_client_contact_service import ForwardClientContactService
from app.services.forward_source_ingestion_service import (
    CONTACT_METADATA_KEY,
    ForwardSourceIngestionService,
)
from app.services.import_ingest_service import ImportIngestService


def make_request(
    *,
    source_type="gmail_message",
    name=None,
    email=None,
    phone=None,
    notes=None,
    text="",
    sender_name="",
):
    return ImportIngestRequest(
        import_source_id=1,
        candidate=CandidateDataInput(
            name=name,
            primary_email=email,
            primary_phone=phone,
            notes=notes,
        ),
        source=CandidateSourceInput(
            source_type=source_type,
            external_id="synthetic-new-source",
            extracted_text=text,
            raw_payload={
                "text": text,
                "from": {
                    "value": [{"address": email, "name": sender_name}]
                },
            },
        ),
    )


def metadata(prepared):
    return prepared.source.raw_payload[CONTACT_METADATA_KEY]


def test_signature_current_author_and_gmail_notes_boundary():
    body = (
        "Dzień dobry Panie Dominiku...\n\n"
        "Pozdrawiam serdecznie,\n"
        "Przemysław Strzelec\n"
        "Wicedyrektor Oddziału\n"
        "Oddział ARP S.A."
        "\ntel. +48 501 502 503"
    )
    prepared = ForwardSourceIngestionService().prepare(
        make_request(
            email="przemyslaw@example.com",
            notes=body,
            text=body,
        )
    )
    assert prepared.candidate.name == "Przemysław Strzelec"
    assert prepared.candidate.notes is None
    assert prepared.source.raw_payload["text"] == body
    assert metadata(prepared)["phones"] == ["501502503"]


def test_quoted_previous_sender_is_not_current_identity_or_contact():
    prepared = ForwardSourceIngestionService().prepare(
        make_request(
            email="jan@example.com",
            sender_name="Jan Kowalski",
            text=(
                "Aktualna wiadomość\n\n"
                "W dniu 10.08.2026 Anna Nowak <anna@example.com> napisała:\n"
                "> Anna Nowak"
            ),
        )
    )
    assert prepared.candidate.name == "Jan Kowalski"
    assert metadata(prepared)["emails"] == ["jan@example.com"]


def test_identity_artifacts_are_unresolved_not_names():
    service = ForwardSourceIngestionService()
    artifacts = (
        ("jan@example.com", "jan@example.com", None),
        ("510 295 235", None, "510 295 235"),
        ("??? >>>", None, None),
        ("Oględziny 04.08.2025", None, None),
        ("Piaskowa 12b", None, None),
        ("[2.PNG]", None, None),
        ("[1] Nazwa firmy", None, None),
    )
    for name, email, phone in artifacts:
        prepared = service.prepare(
            make_request(name=name, email=email, phone=phone)
        )
        assert prepared.candidate.name is None, name
        assert ImportIngestService._resolve_candidate_name(prepared.candidate) == "Nieznany klient"


def test_sheet_multi_email_and_phone_are_separate():
    prepared = ForwardSourceIngestionService().prepare(
        make_request(
            source_type="google_sheets_row",
            name="Jan i Anna Kowalscy",
            email=" jan@example.com; anna@example.com ",
            phone="739 557 562 793 411 699",
        )
    )
    assert metadata(prepared)["emails"] == [
        "jan@example.com",
        "anna@example.com",
    ]
    assert metadata(prepared)["phones"] == ["739557562", "793411699"]
    assert prepared.candidate.primary_email == "jan@example.com"
    assert prepared.candidate.primary_phone == "739557562"


def test_ambiguous_phone_is_not_guessed():
    prepared = ForwardSourceIngestionService().prepare(
        make_request(
            source_type="google_sheets_row",
            name="Jan Kowalski",
            phone="12345 67890",
        )
    )
    assert metadata(prepared)["phones"] == []
    assert metadata(prepared)["warnings"] == ["AMBIGUOUS_PHONE"]
    assert prepared.candidate.primary_phone is None


def test_existing_primary_and_identity_are_preserved_while_contacts_append():
    client = SimpleNamespace(
        name="Prawidłowy Klient",
        primary_email="primary@example.com",
        primary_phone="500000001",
        contact_points=[],
    )
    payload = {
        CONTACT_METADATA_KEY: {
            "emails": ["primary@example.com", "new@example.com", "new@example.com"],
            "phones": ["500000001", "500000002", "500000002"],
            "warnings": [],
        }
    }
    added = ForwardClientContactService.add_from_payloads(client, [payload])
    assert added == 2
    assert client.name == "Prawidłowy Klient"
    assert client.primary_email == "primary@example.com"
    assert client.primary_phone == "500000001"
    assert [item.value for item in client.contact_points if item.kind == "email"] == [
        "primary@example.com",
        "new@example.com",
    ]
    assert [item.value for item in client.contact_points if item.kind == "phone"] == [
        "500000001",
        "500000002",
    ]
    assert sum(item.is_primary for item in client.contact_points if item.kind == "email") == 1
    assert sum(item.is_primary for item in client.contact_points if item.kind == "phone") == 1


def test_duplicate_matching_includes_non_primary_contact_points_with_rollback():
    db = SessionLocal()
    try:
        client = (
            db.query(Client)
            .filter(Client.deleted_at.is_(None))
            .order_by(Client.id.asc())
            .first()
        )
        assert client is not None
        marker = uuid4().hex[:12]
        email = f"forward-{marker}@example.test"
        phone = "7" + marker.translate(str.maketrans("abcdef", "123456"))[:8]
        client.contact_points.extend(
            [
                ClientContactPoint(
                    kind="email",
                    value=email,
                    normalized_value=email,
                    is_primary=False,
                    position=9001,
                ),
                ClientContactPoint(
                    kind="phone",
                    value=phone,
                    normalized_value=phone,
                    is_primary=False,
                    position=9002,
                ),
            ]
        )
        db.flush()
        repository = ImportRepository(db)
        assert repository.find_client_by_email(email).id == client.id
        assert repository.find_client_by_phone(phone).id == client.id
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_signature_current_author_and_gmail_notes_boundary()
    test_quoted_previous_sender_is_not_current_identity_or_contact()
    test_identity_artifacts_are_unresolved_not_names()
    test_sheet_multi_email_and_phone_are_separate()
    test_ambiguous_phone_is_not_guessed()
    test_existing_primary_and_identity_are_preserved_while_contacts_append()
    test_duplicate_matching_includes_non_primary_contact_points_with_rollback()
    print("forward source ingestion tests: PASS")
