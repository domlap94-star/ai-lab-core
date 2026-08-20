from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers complete metadata
from app.database.base import Base
from app.database.engine import engine
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.import_source import ImportSource
from app.services.mail_reconciliation_provider import ReconciliationAudit
from app.services.mail_reconciliation_service import (
    MailReconciliationService,
    MailReconciliationValidationError,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@contextmanager
def isolated_database():
    schema = f"mail_reconciliation_parity_{uuid4().hex}"
    connection = engine.connect()
    outer = connection.begin()
    try:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        Base.metadata.create_all(bind=connection)
        db = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield db
        finally:
            db.close()
    finally:
        outer.rollback()
        connection.close()


class Provider:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self.messages = {str(item["id"]): item for item in messages}

    def audit(self, *, window_days: int, limit: int) -> ReconciliationAudit:
        return ReconciliationAudit(list(self.messages)[:limit], False)

    def fetch(self, message_ids: list[str]) -> list[dict[str, object]]:
        return [self.messages[value] for value in message_ids]


class ParityService(MailReconciliationService):
    """Keeps attachment parity inside the isolated schema, without files."""

    def _ingest_attachments(
        self,
        item: dict[str, object],
        candidate_id: int,
        client_id: int | None,
    ) -> int:
        created = 0
        for index, attachment in enumerate(item.get("attachments") or []):
            external_id = self._attachment_external_id(item, attachment, index)
            exists = self.db.query(Document).filter(
                Document.source_type == "gmail_attachment",
                Document.external_id == external_id,
            ).first()
            if exists is not None:
                continue
            self.db.add(
                Document(
                    filename=str(attachment["filename"]),
                    original_filename=str(attachment["filename"]),
                    content_type=str(attachment["mime_type"]),
                    file_size=1,
                    source_type="gmail_attachment",
                    external_id=external_id,
                    gmail_message_id=str(item["id"]),
                    candidate_id=candidate_id,
                    client_id=client_id,
                    processing_status="stored",
                    metadata_status="pending",
                    match_status="unmatched",
                )
            )
            self.db.commit()
            created += 1
        return created


def message(message_id: str, email: str, *, attachment: bool = False) -> dict[str, object]:
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "labelIds": ["INBOX"],
        "from": {"value": [{"address": email, "name": "Synthetic Person"}]},
        "to": {"value": [{"address": "app@example.invalid"}]},
        "subject": "Synthetic parity fixture",
        "text": "Synthetic parity body",
        "attachments": (
            [{
                "filename": "fixture.txt",
                "mime_type": "text/plain",
                "external_id": f"attachment-{message_id}",
                "content_base64": "eA==",
            }]
            if attachment
            else []
        ),
    }


def candidate(email: str, *, client_id: int | None = None) -> ClientCandidate:
    return ClientCandidate(
        client_type="person",
        name="Synthetic Candidate",
        primary_email=email,
        country_code="PL",
        status="duplicate" if client_id else "pending",
        confidence=0.8,
        matched_client_id=client_id,
    )


def main() -> None:
    messages = [
        message("new-unresolved", "new@example.invalid"),
        message("reuse-unlinked", "reuse-unlinked@example.invalid"),
        message("reuse-linked", "reuse-linked@example.invalid"),
        message("deterministic-client", "client-only@example.invalid"),
        message("with-attachment", "attachment@example.invalid", attachment=True),
        message("already-present", "present@example.invalid"),
    ]
    with isolated_database() as db:
        source = ImportSource(
            source_type="gmail",
            display_name="Synthetic Gmail",
            status="active",
            is_enabled=True,
        )
        unlinked_client = Client(
            client_type="person",
            name="Synthetic Unlinked Client",
            primary_email="reuse-unlinked@example.invalid",
            country_code="PL",
        )
        linked_client = Client(
            client_type="person",
            name="Synthetic Linked Client",
            primary_email="reuse-linked@example.invalid",
            country_code="PL",
        )
        client_only = Client(
            client_type="person",
            name="Synthetic Client Only",
            primary_email="client-only@example.invalid",
            country_code="PL",
        )
        db.add_all([source, unlinked_client, linked_client, client_only])
        db.flush()
        reuse_unlinked = candidate("reuse-unlinked@example.invalid")
        reuse_linked = candidate(
            "reuse-linked@example.invalid",
            client_id=linked_client.id,
        )
        existing = candidate("present@example.invalid")
        db.add_all([reuse_unlinked, reuse_linked, existing])
        db.flush()
        db.add(
            CandidateSource(
                candidate_id=existing.id,
                import_source_id=source.id,
                source_type="gmail_message",
                external_id="already-present",
                external_parent_id="thread-already-present",
                raw_payload={},
            )
        )
        db.commit()

        service = ParityService(db, Provider(messages))
        dry = service.dry_run(window_days=7, actor_user_id=77)
        predictions = {
            item.provider_message_id: item for item in dry.candidate_resolutions
        }
        require(dry.missing_count == 5, "Existing provider ID was not skipped")
        require(dry.expected_candidate_sources == 5, "Source delta mismatch")
        require(dry.expected_candidates == 3, "Candidate delta mismatch")
        require(dry.expected_documents == 1, "Document delta mismatch")
        require(dry.expected_client_links == 2, "New-link delta mismatch")
        require(
            predictions["new-unresolved"].classification == "new_candidate",
            "New unresolved classification mismatch",
        )
        require(
            predictions["reuse-unlinked"].classification
            == "reuse_existing_candidate_unlinked",
            "Unlinked Candidate reuse was not predicted",
        )
        require(
            predictions["reuse-linked"].classification
            == "reuse_existing_candidate_client_linked",
            "Client-linked Candidate reuse was not predicted",
        )
        require(
            predictions["reuse-linked"].expected_new_client_link_delta == 0,
            "Existing Candidate/Client relation was counted as a new link",
        )
        require(
            predictions["reuse-linked"].resolved_client_id == linked_client.id,
            "Resolved Client was not included in the rich plan",
        )
        require(
            predictions["deterministic-client"].resolved_client_id
            == client_only.id,
            "New Candidate target Client was not bound to the rich plan",
        )
        require(
            predictions["deterministic-client"].resolution_confidence
            == "certain",
            "Deterministic confidence was not exposed",
        )

        before = {
            "sources": db.query(CandidateSource).count(),
            "candidates": db.query(ClientCandidate).count(),
            "documents": db.query(Document).count(),
            "links": db.query(ClientCandidate).filter(
                ClientCandidate.matched_client_id.is_not(None)
            ).count(),
        }
        applied = service.apply(
            window_days=7,
            actor_user_id=77,
            dry_run_token=dry.dry_run_token,
        )
        after = {
            "sources": db.query(CandidateSource).count(),
            "candidates": db.query(ClientCandidate).count(),
            "documents": db.query(Document).count(),
            "links": db.query(ClientCandidate).filter(
                ClientCandidate.matched_client_id.is_not(None)
            ).count(),
        }
        actual = {key: after[key] - before[key] for key in before}
        require(actual == {
            "sources": dry.expected_candidate_sources,
            "candidates": dry.expected_candidates,
            "documents": dry.expected_documents,
            "links": dry.expected_client_links,
        }, f"Prediction/apply delta mismatch: {actual}")
        require(applied.new_messages_ingested == 5, "Apply source count mismatch")
        require(applied.new_client_linked == 2, "Apply new-link count mismatch")
        require(
            db.query(CandidateSource).filter(
                CandidateSource.external_id == "reuse-linked",
                CandidateSource.candidate_id == reuse_linked.id,
            ).count() == 1,
            "Canonical apply did not reuse the linked Candidate",
        )
        second = service.dry_run(window_days=7, actor_user_id=77)
        require(second.missing_count == 0, "Second dry-run was not idempotent")

    with isolated_database() as db:
        source = ImportSource(
            source_type="gmail",
            display_name="Synthetic Gmail",
            status="active",
            is_enabled=True,
        )
        client = Client(
            client_type="person",
            name="Drift Client",
            primary_email="drift@example.invalid",
            country_code="PL",
        )
        db.add_all([source, client])
        db.commit()
        drift_service = ParityService(
            db,
            Provider([message("drift", "drift@example.invalid")]),
        )
        signed = drift_service.dry_run(window_days=7, actor_user_id=88)
        db.add(candidate("drift@example.invalid", client_id=client.id))
        db.commit()
        try:
            drift_service.apply(
                window_days=7,
                actor_user_id=88,
                dry_run_token=signed.dry_run_token,
            )
        except MailReconciliationValidationError as error:
            require(
                str(error) == "reconciliation_plan_drift",
                "Plan drift returned the wrong typed conflict",
            )
        else:
            raise AssertionError("Material Candidate-resolution drift was accepted")
        require(
            db.query(CandidateSource).count() == 0,
            "Plan drift was detected only after a canonical write",
        )

    print("FOLLOW-UP CHUNK 10 RECONCILIATION PARITY: 8/8 PASS")
    print("isolated_schema_rolled_back=True production_writes=0")


if __name__ == "__main__":
    main()
