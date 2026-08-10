from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        document: Document,
    ) -> Document:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)

        return document

    def get(
        self,
        document_id: int,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )

    def get_by_external_id(
        self,
        *,
        source_type: str,
        external_id: str,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.source_type == source_type,
                Document.external_id == external_id,
            )
            .first()
        )

    def get_by_checksum(
        self,
        checksum_sha256: str,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.checksum_sha256 == checksum_sha256,
            )
            .first()
        )

    def find_candidate_by_gmail_message_id(
        self,
        gmail_message_id: str,
    ) -> ClientCandidate | None:
        return (
            self.db.query(ClientCandidate)
            .join(
                CandidateSource,
                CandidateSource.candidate_id
                == ClientCandidate.id,
            )
            .filter(
                CandidateSource.source_type
                == "gmail_message",
                CandidateSource.external_id
                == gmail_message_id,
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
            )
            .first()
        )

    def update(
        self,
        document: Document,
    ) -> Document:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)

        return document

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()