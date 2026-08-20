from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document


class CandidateContextRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_candidate(
        self,
        candidate_id: int,
    ) -> ClientCandidate | None:
        return (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.id == candidate_id,
                ClientCandidate.deleted_at.is_(None),
            )
            .first()
        )

    def get_sources(
        self,
        candidate_id: int,
    ) -> list[CandidateSource]:
        return (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.deleted_at.is_(None),
            )
            .order_by(
                CandidateSource.created_at.asc(),
                CandidateSource.id.asc(),
            )
            .all()
        )

    def get_documents(
        self,
        candidate_id: int,
    ) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(
                Document.candidate_id == candidate_id,
                Document.trashed_at.is_(None),
                Document.purged_at.is_(None),
            )
            .order_by(
                Document.created_at.asc(),
                Document.id.asc(),
            )
            .all()
        )

    def get_unmatched_documents(
        self,
    ) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(
                Document.candidate_id.is_(None),
                Document.client_id.is_(None),
                Document.match_status == "unmatched",
                Document.trashed_at.is_(None),
                Document.purged_at.is_(None),
            )
            .order_by(
                Document.created_at.asc(),
                Document.id.asc(),
            )
            .all()
        )
