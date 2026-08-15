from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_semantic_projection_service import (
    ClientEntitySemanticProjectionService,
)
from app.services.client_identity_name_quality_service import (
    ClientIdentityNameQualityService,
)


LINKED_CANDIDATE_STATUSES = frozenset(
    {"accepted", "merged", "duplicate"}
)
ACTION_NAMES = (
    "SAFE_RENAME_CANDIDATE",
    "REVIEW_REQUIRED",
    "INSUFFICIENT_EVIDENCE",
    "POTENTIAL_DUPLICATE_OR_MERGE",
    "FIRST_PARTY_OR_RELAY_REVIEW",
    "NO_CHANGE",
)


@dataclass(frozen=True)
class CleanupEvidence:
    candidate_id: int
    source_id: int
    source_type: str
    method: str
    value: str
    confidence: float


@dataclass
class CandidateCleanupProjection:
    candidate_id: int
    candidate_status: str
    proposed_name: str | None
    proposed_client_type: str | None
    legal_name: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    tax_id: str | None
    status: str
    reason: str
    confidence: float
    evidence: list[CleanupEvidence] = field(default_factory=list)


@dataclass
class ClientIdentityCleanupProposal:
    client_id: int
    suspicion_types: list[str]
    current_name: str
    current_client_type: str
    proposed_name: str | None
    proposed_client_type: str | None
    legal_name: str | None
    action: str
    confidence: float
    safety_reason: str
    duplicate_risk: str
    potential_duplicate_client_ids: list[int]
    candidate_ids: list[int]
    conflicts: list[str]
    evidence: list[CleanupEvidence]
    candidate_projections: list[CandidateCleanupProjection]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClientIdentityCleanupDryRunService:
    """Builds source-backed cleanup proposals without database writes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.semantic_service = ClientEntitySemanticProjectionService(db)
        self.quality = ClientIdentityNameQualityService

    def run(self) -> tuple[list[ClientIdentityCleanupProposal], dict[str, Any]]:
        clients = (
            self.db.query(Client)
            .filter(Client.deleted_at.is_(None))
            .order_by(Client.id.asc())
            .all()
        )
        suspicious = [
            client
            for client in clients
            if self.quality.is_suspicious(client.name)
        ]

        client_ids = [client.id for client in suspicious]
        candidates = (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.matched_client_id.in_(client_ids),
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
            )
            .order_by(
                ClientCandidate.matched_client_id.asc(),
                ClientCandidate.id.asc(),
            )
            .all()
            if client_ids
            else []
        )
        candidates_by_client: dict[int, list[ClientCandidate]] = defaultdict(list)
        for candidate in candidates:
            candidates_by_client[candidate.matched_client_id].append(candidate)

        source_ids_by_candidate = self._source_types_by_candidate(candidates)
        indexes = self._build_duplicate_indexes(clients)

        proposals = [
            self._build_proposal(
                client=client,
                candidates=candidates_by_client.get(client.id, []),
                source_types=source_ids_by_candidate,
                duplicate_indexes=indexes,
            )
            for client in suspicious
        ]
        summary = self._build_summary(clients, proposals)
        return proposals, summary

    def _build_proposal(
        self,
        *,
        client: Client,
        candidates: list[ClientCandidate],
        source_types: dict[int, dict[int, str]],
        duplicate_indexes: dict[str, dict[str, set[int]]],
    ) -> ClientIdentityCleanupProposal:
        projections = [
            self._project_candidate(candidate, source_types.get(candidate.id, {}))
            for candidate in candidates
        ]
        usable = [
            projection
            for projection in projections
            if projection.proposed_name
            and not self.quality.is_suspicious(projection.proposed_name)
            and not self.quality.additional_findings(projection.proposed_name)
            and projection.status not in {"first_party_internal", "relay_container"}
        ]

        grouped: dict[str, list[CandidateCleanupProjection]] = defaultdict(list)
        for projection in usable:
            grouped[self.quality.normalize_identity(projection.proposed_name)].append(
                projection
            )

        conflicts: list[str] = []
        if len(grouped) > 1:
            conflicts.append(
                "Linked candidate projections disagree on normalized identity."
            )

        winning: CandidateCleanupProjection | None = None
        if grouped:
            ranked_groups = sorted(
                grouped.values(),
                key=lambda group: (
                    -len(group),
                    -max(item.confidence for item in group),
                    self.quality.normalize_identity(group[0].proposed_name),
                ),
            )
            winning = sorted(
                ranked_groups[0],
                key=lambda item: (-item.confidence, item.candidate_id),
            )[0]

        proposed_name = winning.proposed_name if winning else None
        proposed_type = winning.proposed_client_type if winning else None
        legal_name = winning.legal_name if winning else None
        confidence = winning.confidence if winning else 0.0
        all_evidence = self._dedupe_evidence(
            item for projection in projections for item in projection.evidence
        )

        duplicate_risk, duplicate_ids = self._duplicate_risk(
            client=client,
            proposed_name=proposed_name,
            legal_name=legal_name,
            proposed_tax_id=(winning.tax_id if winning else None),
            proposed_email=(winning.contact_email if winning else None),
            proposed_phone=(winning.contact_phone if winning else None),
            duplicate_indexes=duplicate_indexes,
        )
        boundary_only = bool(projections) and all(
            projection.status in {"first_party_internal", "relay_container"}
            for projection in projections
        )
        strong_evidence = bool(winning) and any(
            evidence.source_id > 0
            and evidence.confidence >= 0.90
            and evidence.method not in {
                "base_fallback",
                "candidate_name_entity",
                "candidate_name_combined_entity_contact",
            }
            for evidence in winning.evidence
        )

        if boundary_only:
            action = "FIRST_PARTY_OR_RELAY_REVIEW"
            reason = "All linked projections are first-party or relay containers."
        elif proposed_name is None:
            action = "INSUFFICIENT_EVIDENCE"
            reason = "No safe source-backed identity survived projection policy."
        elif self.quality.normalize_identity(proposed_name) == self.quality.normalize_identity(
            client.name
        ):
            action = "NO_CHANGE"
            reason = "The normalized source-backed identity equals the current name."
        elif duplicate_risk == "STRONG":
            action = "POTENTIAL_DUPLICATE_OR_MERGE"
            reason = "A strong deterministic identifier matches another active client."
        elif conflicts:
            action = "REVIEW_REQUIRED"
            reason = conflicts[0]
        elif duplicate_risk == "POSSIBLE":
            action = "REVIEW_REQUIRED"
            reason = "The proposed normalized name already exists on another client."
        elif not strong_evidence:
            action = "REVIEW_REQUIRED"
            reason = "The proposal lacks strong source-ranked identity evidence."
        else:
            action = "SAFE_RENAME_CANDIDATE"
            reason = (
                "Strong source-backed identity, no candidate conflict, and no "
                "deterministic duplicate risk."
            )

        return ClientIdentityCleanupProposal(
            client_id=client.id,
            suspicion_types=list(self.quality.suspicion_types(client.name)),
            current_name=client.name,
            current_client_type=client.client_type,
            proposed_name=proposed_name,
            proposed_client_type=proposed_type,
            legal_name=legal_name,
            action=action,
            confidence=round(confidence, 4),
            safety_reason=reason,
            duplicate_risk=duplicate_risk,
            potential_duplicate_client_ids=duplicate_ids,
            candidate_ids=[candidate.id for candidate in candidates],
            conflicts=conflicts,
            evidence=all_evidence,
            candidate_projections=projections,
        )

    def _project_candidate(
        self,
        candidate: ClientCandidate,
        source_types: dict[int, str],
    ) -> CandidateCleanupProjection:
        projection = self.semantic_service.project(
            candidate,
            include_candidate_name_evidence=False,
        )
        evidence: list[CleanupEvidence] = []

        for item in projection.entity_evidence:
            if item.source_id <= 0:
                continue
            evidence.append(
                CleanupEvidence(
                    candidate_id=candidate.id,
                    source_id=item.source_id,
                    source_type=source_types.get(item.source_id, "unknown"),
                    method=item.method,
                    value=item.name,
                    confidence=item.confidence,
                )
            )

        for contact in projection.contacts:
            for source_id in contact.source_ids:
                evidence.append(
                    CleanupEvidence(
                        candidate_id=candidate.id,
                        source_id=source_id,
                        source_type=source_types.get(source_id, "unknown"),
                        method="semantic_contact",
                        value=contact.name,
                        confidence=contact.confidence,
                    )
                )

        evidence = self._dedupe_evidence(evidence)
        confidence = max((item.confidence for item in evidence), default=0.0)

        return CandidateCleanupProjection(
            candidate_id=candidate.id,
            candidate_status=candidate.status,
            proposed_name=projection.entity_name,
            proposed_client_type=(projection.entity_type if projection.entity_name else None),
            legal_name=projection.legal_name,
            contact_name=projection.contact_name,
            contact_email=projection.contact_email,
            contact_phone=projection.contact_phone,
            tax_id=projection.tax_id,
            status=projection.status,
            reason=projection.reason,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    def _duplicate_risk(
        self,
        *,
        client: Client,
        proposed_name: str | None,
        legal_name: str | None,
        proposed_tax_id: str | None,
        proposed_email: str | None,
        proposed_phone: str | None,
        duplicate_indexes: dict[str, dict[str, set[int]]],
    ) -> tuple[str, list[int]]:
        strong: set[int] = set()
        possible: set[int] = set()

        identifiers = {
            "tax": {
                self.quality.normalize_tax_id(client.tax_id),
                self.quality.normalize_tax_id(proposed_tax_id),
            },
            "email": {
                self.quality.normalize_email(client.primary_email),
                self.quality.normalize_email(proposed_email),
            },
            "phone": {
                self.quality.normalize_phone(client.primary_phone),
                self.quality.normalize_phone(proposed_phone),
            },
        }
        for kind, values in identifiers.items():
            for value in values:
                if not value or (kind == "phone" and len(value) < 9):
                    continue
                strong.update(duplicate_indexes[kind].get(value, set()))

        for value in (proposed_name, legal_name):
            normalized = self.quality.normalize_identity(value)
            if normalized:
                possible.update(duplicate_indexes["name"].get(normalized, set()))

        strong.discard(client.id)
        possible.discard(client.id)
        possible.difference_update(strong)
        if strong:
            return "STRONG", sorted(strong | possible)
        if possible:
            return "POSSIBLE", sorted(possible)
        return "NONE", []

    def _build_duplicate_indexes(
        self, clients: list[Client]
    ) -> dict[str, dict[str, set[int]]]:
        indexes: dict[str, dict[str, set[int]]] = {
            key: defaultdict(set) for key in ("name", "tax", "email", "phone")
        }
        for client in clients:
            names = {client.name, client.legal_name}
            for name in names:
                normalized = self.quality.normalize_identity(name)
                if normalized:
                    indexes["name"][normalized].add(client.id)
            values = {
                "tax": self.quality.normalize_tax_id(client.tax_id),
                "email": self.quality.normalize_email(client.primary_email),
                "phone": self.quality.normalize_phone(client.primary_phone),
            }
            for kind, value in values.items():
                if value and (kind != "phone" or len(value) >= 9):
                    indexes[kind][value].add(client.id)
        return indexes

    def _source_types_by_candidate(
        self, candidates: list[ClientCandidate]
    ) -> dict[int, dict[int, str]]:
        candidate_ids = [candidate.id for candidate in candidates]
        result: dict[int, dict[int, str]] = defaultdict(dict)
        if not candidate_ids:
            return result
        rows = (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.deleted_at.is_(None),
                CandidateSource.candidate_id.in_(candidate_ids),
            )
            .all()
        )
        for source in rows:
            result[source.candidate_id][source.id] = source.source_type
        return result

    def _build_summary(
        self,
        clients: list[Client],
        proposals: list[ClientIdentityCleanupProposal],
    ) -> dict[str, Any]:
        suspicion = Counter(
            item for proposal in proposals for item in proposal.suspicion_types
        )
        overlap = Counter(
            "+".join(proposal.suspicion_types)
            for proposal in proposals
            if len(proposal.suspicion_types) > 1
        )
        actions = Counter(proposal.action for proposal in proposals)
        evidence_sets = [
            {evidence.source_type for evidence in proposal.evidence}
            for proposal in proposals
        ]
        additional = Counter(
            finding
            for client in clients
            for finding in self.quality.additional_findings(client.name)
        )

        return {
            "active_clients_total": len(clients),
            "suspicious": {
                "email_as_name": suspicion["EMAIL_AS_NAME"],
                "phone_as_name": suspicion["PHONE_AS_NAME"],
                "file_as_name": suspicion["FILE_AS_NAME"],
                "unique_total": len(proposals),
                "overlaps": dict(sorted(overlap.items())),
            },
            "additional_quality_findings": dict(sorted(additional.items())),
            "linkage": {
                "with_matched_candidate": sum(bool(p.candidate_ids) for p in proposals),
                "without_matched_candidate": sum(not p.candidate_ids for p in proposals),
                "with_multiple_matched_candidates": sum(
                    len(p.candidate_ids) > 1 for p in proposals
                ),
            },
            "actions": {name: actions[name] for name in ACTION_NAMES},
            "evidence": {
                "gmail_backed": sum("gmail_message" in item for item in evidence_sets),
                "sheets_backed": sum("google_sheets_row" in item for item in evidence_sets),
                "both": sum(
                    {"gmail_message", "google_sheets_row"}.issubset(item)
                    for item in evidence_sets
                ),
                "no_reliable_identity_evidence": sum(not item for item in evidence_sets),
            },
            "type": {
                "proposed_type_changes": sum(
                    bool(p.proposed_client_type)
                    and p.proposed_client_type != p.current_client_type
                    for p in proposals
                )
            },
            "duplicates": {
                "possible": sum(p.duplicate_risk == "POSSIBLE" for p in proposals),
                "strong": sum(p.duplicate_risk == "STRONG" for p in proposals),
            },
        }

    @staticmethod
    def _dedupe_evidence(items) -> list[CleanupEvidence]:
        result: list[CleanupEvidence] = []
        seen: set[tuple[Any, ...]] = set()
        for item in items:
            key = (
                item.candidate_id,
                item.source_id,
                item.source_type,
                item.method,
                item.value.casefold(),
            )
            if key not in seen:
                seen.add(key)
                result.append(item)
        return sorted(
            result,
            key=lambda item: (-item.confidence, item.candidate_id, item.source_id),
        )
