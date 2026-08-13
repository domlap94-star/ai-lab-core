from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.services.client_candidate_promotion_service import (
    ClientCandidatePromotionService,
)


def main() -> None:
    db = SessionLocal()

    try:
        service = ClientCandidatePromotionService(db)

        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status == "pending",
                ClientCandidate.matched_client_id.is_(None),
            )
            .order_by(
                ClientCandidate.confidence.desc(),
                ClientCandidate.id.asc(),
            )
            .all()
        )

        candidate = None

        for candidate_item in candidates:
            existing_client, matched_by = (
                service.find_existing_client(
                    candidate_item
                )
            )

            if existing_client is None:
                candidate = candidate_item
                break

        if candidate is None:
            raise RuntimeError(
                "No non-duplicate pending candidate "
                "available for validation."
            )

        candidate_id = candidate.id

        sources = (
            db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.deleted_at.is_(None),
            )
            .all()
        )

        documents_before = (
            db.query(Document)
            .filter(
                Document.candidate_id == candidate_id,
            )
            .all()
        )

        client_count_before = (
            db.query(Client)
            .filter(Client.deleted_at.is_(None))
            .count()
        )

        source_counts = Counter(
            source.source_type
            for source in sources
        )

        print()
        print("=" * 110)
        print("SELECTED CANDIDATE")
        print("=" * 110)

        print("candidate_id:", candidate.id)
        print("name:", candidate.name)
        print("client_type:", candidate.client_type)
        print("email:", candidate.primary_email)
        print("phone:", candidate.primary_phone)
        print("tax_id:", candidate.tax_id)
        print("city:", candidate.city)
        print("status:", candidate.status)
        print("confidence:", candidate.confidence)
        print("matched_client_id:", candidate.matched_client_id)
        print("source_counts:", dict(source_counts))
        print("documents:", len(documents_before))

        client = service.promote(candidate_id)

        db.flush()

        refreshed_candidate = (
            db.query(ClientCandidate)
            .filter(ClientCandidate.id == candidate_id)
            .one()
        )

        documents_after = (
            db.query(Document)
            .filter(
                Document.candidate_id == candidate_id,
            )
            .all()
        )

        print()
        print("=" * 110)
        print("PROMOTION RESULT BEFORE ROLLBACK")
        print("=" * 110)

        print("new_client_id:", client.id)
        print("new_client_name:", client.name)
        print(
            "candidate_status:",
            refreshed_candidate.status,
        )
        print(
            "candidate_matched_client_id:",
            refreshed_candidate.matched_client_id,
        )

        assigned_documents = [
            document
            for document in documents_after
            if document.client_id == client.id
        ]

        print(
            "documents_assigned_to_client:",
            len(assigned_documents),
        )

        if refreshed_candidate.status != "accepted":
            raise RuntimeError(
                "Candidate was not marked accepted."
            )

        if refreshed_candidate.matched_client_id != client.id:
            raise RuntimeError(
                "Candidate matched_client_id was not assigned."
            )

        if len(assigned_documents) != len(documents_after):
            raise RuntimeError(
                "Not all candidate documents were assigned."
            )

        for document in documents_after:
            if document.candidate_id != candidate_id:
                raise RuntimeError(
                    "Document candidate provenance was lost."
                )

        print()
        print("PROMOTION IN-TRANSACTION VALIDATION: OK")

        print()
        print("=" * 110)
        print("ROLLBACK")
        print("=" * 110)

        db.rollback()

        candidate_after_rollback = (
            db.query(ClientCandidate)
            .filter(ClientCandidate.id == candidate_id)
            .one()
        )

        client_count_after = (
            db.query(Client)
            .filter(Client.deleted_at.is_(None))
            .count()
        )

        documents_after_rollback = (
            db.query(Document)
            .filter(
                Document.candidate_id == candidate_id,
            )
            .all()
        )

        print(
            "candidate_status_after_rollback:",
            candidate_after_rollback.status,
        )
        print(
            "candidate_matched_client_id_after_rollback:",
            candidate_after_rollback.matched_client_id,
        )
        print(
            "client_count_before:",
            client_count_before,
        )
        print(
            "client_count_after:",
            client_count_after,
        )

        if candidate_after_rollback.status != "pending":
            raise RuntimeError(
                "Rollback did not restore candidate status."
            )

        if candidate_after_rollback.matched_client_id is not None:
            raise RuntimeError(
                "Rollback did not restore matched_client_id."
            )

        if client_count_after != client_count_before:
            raise RuntimeError(
                "Rollback did not restore client count."
            )

        for document in documents_after_rollback:
            if document.client_id is not None:
                raise RuntimeError(
                    "Rollback did not restore document client_id."
                )

        print()
        print("ROLLBACK VALIDATION: OK")

        print()
        print("=" * 110)
        print("CLIENT CANDIDATE PROMOTION CORE: OK")
        print("=" * 110)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
