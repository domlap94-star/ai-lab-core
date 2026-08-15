from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.database.session import SessionLocal, get_db
from app.main import app
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.import_source import ImportSource


COLLISION_TEST_ID = "COLLISION_TEST_ID"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    db = SessionLocal()
    marker = f"email-scope-{uuid4().hex}"

    def override_db():
        yield db

    def override_user():
        return object()

    try:
        client_a = Client(
            client_type="company",
            name=f"{marker}-client-a",
            country_code="PL",
        )
        client_b = Client(
            client_type="company",
            name=f"{marker}-client-b",
            country_code="PL",
        )
        db.add_all([client_a, client_b])
        db.flush()

        import_a1 = ImportSource(
            source_type="gmail",
            display_name=f"{marker}-mailbox-a1",
            external_account_id=f"{marker}-account-a1",
            status="active",
            is_enabled=True,
        )
        import_a2 = ImportSource(
            source_type="gmail",
            display_name=f"{marker}-mailbox-a2",
            external_account_id=f"{marker}-account-a2",
            status="active",
            is_enabled=True,
        )
        import_b = ImportSource(
            source_type="gmail",
            display_name=f"{marker}-mailbox-b",
            external_account_id=f"{marker}-account-b",
            status="active",
            is_enabled=True,
        )
        db.add_all([import_a1, import_a2, import_b])
        db.flush()

        candidate_a = ClientCandidate(
            client_type="company",
            name=f"{marker}-candidate-a",
            country_code="PL",
            status="accepted",
            confidence=1.0,
            matched_client_id=client_a.id,
        )
        candidate_b = ClientCandidate(
            client_type="company",
            name=f"{marker}-candidate-b",
            country_code="PL",
            status="accepted",
            confidence=1.0,
            matched_client_id=client_b.id,
        )
        db.add_all([candidate_a, candidate_b])
        db.flush()

        def source(
            candidate_id: int,
            import_source_id: int,
            suffix: str,
        ) -> CandidateSource:
            return CandidateSource(
                candidate_id=candidate_id,
                import_source_id=import_source_id,
                source_type="gmail_message",
                external_id=COLLISION_TEST_ID,
                external_parent_id=f"{COLLISION_TEST_ID}-thread-{suffix}",
                source_label=f"Collision {suffix}",
                raw_payload={
                    "id": COLLISION_TEST_ID,
                    "threadId": f"{COLLISION_TEST_ID}-thread-{suffix}",
                    "date": "2026-08-15T12:00:00Z",
                    "from": {
                        "value": [
                            {
                                "name": "Test",
                                "address": "test@example.com",
                            }
                        ]
                    },
                    "to": {
                        "value": [
                            {
                                "name": "NEXT Stabil",
                                "address": "kontakt@podnoszenieposadzek.pl",
                            }
                        ]
                    },
                    "labelIds": ["INBOX"],
                    "subject": f"Collision {suffix}",
                    "text": f"Scoped message {suffix}",
                },
            )

        db.add_all(
            [
                source(candidate_a.id, import_a1.id, "a1"),
                source(candidate_a.id, import_a2.id, "a2"),
                source(candidate_b.id, import_b.id, "b"),
            ]
        )

        def attachment(
            suffix: str,
            *,
            client_id: int | None = None,
            candidate_id: int | None = None,
        ) -> Document:
            return Document(
                filename=f"{marker}-{suffix}.pdf",
                original_filename=f"{suffix}.pdf",
                content_type="application/pdf",
                file_size=100,
                source_type="gmail_attachment",
                external_id=f"{marker}-document-{suffix}",
                gmail_message_id=COLLISION_TEST_ID,
                client_id=client_id,
                candidate_id=candidate_id,
                processing_status="processed",
                metadata_status="processed",
                match_status="matched",
                archive_depth=0,
            )

        document_a = attachment("a-direct", client_id=client_a.id)
        document_a_candidate = attachment(
            "a-candidate",
            candidate_id=candidate_a.id,
        )
        document_b = attachment("b-direct", client_id=client_b.id)
        document_unscoped = attachment("unscoped")
        db.add_all(
            [
                document_a,
                document_a_candidate,
                document_b,
                document_unscoped,
            ]
        )
        db.flush()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        http = TestClient(app)

        response_a = http.get(f"/api/v1/clients/{client_a.id}/emails")
        require(response_a.status_code == 200, response_a.text)
        page_a = response_a.json()
        require(
            page_a["total"] == 2,
            "Cross-import dedupe must preserve provenance namespaces",
        )
        allowed_a = {document_a.id, document_a_candidate.id}
        returned_a = {
            attachment_item["document_id"]
            for item in page_a["items"]
            for attachment_item in item["attachments"]
        }
        require(
            returned_a == allowed_a,
            "Client A response contains unscoped or foreign attachments",
        )
        require(document_b.id not in returned_a, "Client B attachment leaked to A")
        require(
            document_unscoped.id not in returned_a,
            "Unscoped attachment leaked to Client A",
        )

        response_b = http.get(f"/api/v1/clients/{client_b.id}/emails")
        require(response_b.status_code == 200, response_b.text)
        returned_b = {
            attachment_item["document_id"]
            for item in response_b.json()["items"]
            for attachment_item in item["attachments"]
        }
        require(
            returned_b == {document_b.id},
            "Client B response contains Client A or unscoped attachments",
        )

        print("CLIENT EMAIL ATTACHMENT SCOPE: OK")
        print("client_a_messages=2")
        print("client_a_attachments=direct+candidate_only")
        print("client_b_attachment_excluded_from_a=OK")
        print("unscoped_attachment_excluded=OK")
        print("dedupe_namespace=import_source_id+external_id")
    finally:
        app.dependency_overrides.clear()
        db.rollback()
        remaining = (
            db.query(Client)
            .filter(Client.name.like(f"{marker}%"))
            .count()
        )
        require(remaining == 0, "Rollback left test clients in the database")
        db.rollback()
        db.close()
        print("database_modifications_after_rollback=0")


if __name__ == "__main__":
    main()
