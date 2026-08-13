from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_secondary_resolver import (
    CandidateIdentitySecondaryResolver,
)


@dataclass(frozen=True)
class CandidateIdentityChange:
    candidate_id: int
    old_name: str
    new_name: str
    confidence: float
    reason: str


class CandidateIdentityEnrichmentService:
    """
    Applies only deterministic AUTO_SAFE identity resolutions.

    REVIEW / AMBIGUOUS / INSUFFICIENT candidates are never changed.
    Transaction ownership belongs to the caller.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.resolver = CandidateIdentitySecondaryResolver(db)

    def build_auto_safe_changes(
        self,
    ) -> list[CandidateIdentityChange]:
        candidates = (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status == "pending",
            )
            .order_by(
                ClientCandidate.id.asc(),
            )
            .all()
        )

        changes: list[CandidateIdentityChange] = []

        for candidate in candidates:
            resolution = self.resolver.resolve(candidate)

            if resolution.status != "auto_safe":
                continue

            proposed_name = (
                resolution.proposed_name or ""
            ).strip()

            current_name = (
                candidate.name or ""
            ).strip()

            if not proposed_name:
                continue

            if proposed_name == current_name:
                continue

            changes.append(
                CandidateIdentityChange(
                    candidate_id=candidate.id,
                    old_name=current_name,
                    new_name=proposed_name,
                    confidence=resolution.confidence,
                    reason=resolution.reason or "",
                )
            )

        return changes

    def apply_auto_safe(
        self,
    ) -> list[CandidateIdentityChange]:
        changes = self.build_auto_safe_changes()

        for change in changes:
            candidate = (
                self.db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id == change.candidate_id,
                    ClientCandidate.deleted_at.is_(None),
                    ClientCandidate.status == "pending",
                )
                .with_for_update()
                .first()
            )

            if candidate is None:
                continue

            resolution = self.resolver.resolve(candidate)

            if resolution.status != "auto_safe":
                continue

            proposed_name = (
                resolution.proposed_name or ""
            ).strip()

            if not proposed_name:
                continue

            candidate.name = proposed_name

        self.db.flush()

        return changes
