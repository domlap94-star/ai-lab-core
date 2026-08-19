from __future__ import annotations

from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.client_candidate import ClientCandidate
from app.services.candidate_context_service import (
    CandidateContextNotFoundError,
    CandidateContextService,
)
from app.services.client_candidate_promotion_service import (
    CandidateAlreadyMatchedError,
    CandidateDuplicateClientError,
    CandidateNotFoundError,
    CandidateNotPendingError,
    CandidatePromotionError,
    ClientCandidatePromotionService,
)
from app.services.change_history_service import ChangeHistoryService


class CandidateReviewNotFoundError(Exception):
    pass


class CandidateReviewInvalidStateError(Exception):
    pass


class ClientCandidateReviewService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.context_service = (
            CandidateContextService(db)
        )

        self.promotion_service = (
            ClientCandidatePromotionService(db)
        )

    def get_candidates(
        self,
        *,
        status: str | None = "pending",
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ClientCandidate]:
        query = (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None)
            )
        )

        if status is not None:
            query = query.filter(
                ClientCandidate.status == status
            )

        if search:
            pattern = (
                f"%{search.strip()}%"
            )

            query = query.filter(
                or_(
                    ClientCandidate.name.ilike(
                        pattern
                    ),
                    ClientCandidate.legal_name.ilike(
                        pattern
                    ),
                    ClientCandidate.tax_id.ilike(
                        pattern
                    ),
                    ClientCandidate.primary_email.ilike(
                        pattern
                    ),
                    ClientCandidate.primary_phone.ilike(
                        pattern
                    ),
                    ClientCandidate.city.ilike(
                        pattern
                    ),
                )
            )

        return (
            query
            .order_by(
                ClientCandidate.confidence.desc(),
                ClientCandidate.id.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_candidate_context(
        self,
        candidate_id: int,
    ) -> dict:
        try:
            return (
                self.context_service.build_context(
                    candidate_id
                )
            )

        except CandidateContextNotFoundError as error:
            raise CandidateReviewNotFoundError(
                f"Candidate {candidate_id} not found."
            ) from error

    def accept_candidate(
        self,
        candidate_id: int,
        *,
        actor_user_id: int | None = None,
    ):
        try:
            candidate = self.promotion_service.get_candidate_for_update(candidate_id)
            before_candidate = ChangeHistoryService.candidate_snapshot(candidate)
            client = (
                self.promotion_service.promote(
                    candidate_id
                )
            )

            operation = str(uuid4())
            history = ChangeHistoryService(self.db)
            after_candidate = history.candidate_snapshot(candidate)
            after_candidate["resulting_client_id"] = client.id
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="client_candidate",
                entity_id=candidate.id,
                action="accepted",
                before=before_candidate,
                after=after_candidate,
                operation_id=operation,
                source_key=f"candidate:{operation}:accepted",
            )
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="client",
                entity_id=client.id,
                action="created",
                before={},
                after=history.client_snapshot(client, include_nulls=False),
                operation_id=operation,
                source_key=f"candidate:{operation}:client-created",
            )

            self.db.commit()
            self.db.refresh(client)

            return client

        except (
            CandidateNotFoundError,
            CandidateNotPendingError,
            CandidateAlreadyMatchedError,
            CandidateDuplicateClientError,
            CandidatePromotionError,
        ):
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def reject_candidate(
        self,
        candidate_id: int,
        *,
        actor_user_id: int | None = None,
    ) -> ClientCandidate:
        try:
            candidate = (
                self.db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == candidate_id,
                    ClientCandidate.deleted_at.is_(None),
                )
                .with_for_update()
                .first()
            )

            if candidate is None:
                raise CandidateReviewNotFoundError(
                    f"Candidate {candidate_id} not found."
                )

            if candidate.status != "pending":
                raise CandidateReviewInvalidStateError(
                    "Candidate "
                    f"{candidate.id} has status "
                    f"{candidate.status!r}; "
                    "expected 'pending'."
                )

            if candidate.matched_client_id is not None:
                raise CandidateReviewInvalidStateError(
                    "Candidate "
                    f"{candidate.id} is already linked "
                    f"to client "
                    f"{candidate.matched_client_id}."
                )

            before = ChangeHistoryService.candidate_snapshot(candidate)
            candidate.status = "rejected"

            self.db.flush()
            operation = str(uuid4())
            ChangeHistoryService(self.db).persist(
                actor_user_id=actor_user_id,
                entity_type="client_candidate",
                entity_id=candidate.id,
                action="rejected",
                before=before,
                after=ChangeHistoryService.candidate_snapshot(candidate),
                operation_id=operation,
                source_key=f"candidate:{operation}:rejected",
            )
            self.db.commit()
            self.db.refresh(candidate)

            return candidate

        except (
            CandidateReviewNotFoundError,
            CandidateReviewInvalidStateError,
        ):
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise
