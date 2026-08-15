from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
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
    identity_confidence: float
    evidence: list[CleanupEvidence] = field(default_factory=list)
    identity_support_evidence: list[CleanupEvidence] = field(default_factory=list)
    gmail_quoted_boundaries: int = 0
    gmail_relay_messages: int = 0


@dataclass
class ClientIdentityCleanupProposal:
    client_id: int
    suspicion_types: list[str]
    current_name: str
    current_client_type: str
    primary_email: str | None
    primary_phone: str | None
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
    identity_support_evidence: list[CleanupEvidence]
    candidate_projections: list[CandidateCleanupProjection]
    diagnostics: dict[str, Any]

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
        document_counts = self._document_counts_by_candidate(candidates)
        indexes = self._build_duplicate_indexes(clients)

        proposals = [
            self._build_proposal(
                client=client,
                candidates=candidates_by_client.get(client.id, []),
                source_types=source_ids_by_candidate,
                document_counts=document_counts,
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
        document_counts: dict[int, int],
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
                    -max(item.identity_confidence for item in group),
                    self.quality.normalize_identity(group[0].proposed_name),
                ),
            )
            winning = sorted(
                ranked_groups[0],
                key=lambda item: (-item.identity_confidence, item.candidate_id),
            )[0]
            winning_group = ranked_groups[0]
        else:
            winning_group = []

        proposed_name = winning.proposed_name if winning else None
        proposed_type = winning.proposed_client_type if winning else None
        legal_name = winning.legal_name if winning else None
        identity_support_evidence = self._dedupe_evidence(
            evidence
            for projection in winning_group
            for evidence in projection.identity_support_evidence
        )
        confidence = max(
            (item.confidence for item in identity_support_evidence),
            default=0.0,
        )
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
            for evidence in identity_support_evidence
        )
        abbreviated_person_fallback = bool(
            winning
            and proposed_type == "person"
            and proposed_name
            and re.search(r"(?<!\w)[^\W\d_]\.(?!\w)", proposed_name)
            and identity_support_evidence
            and all(
                evidence.method == "person_contact_fallback"
                for evidence in identity_support_evidence
            )
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
        elif abbreviated_person_fallback:
            action = "REVIEW_REQUIRED"
            reason = (
                "The person identity is supported only by an abbreviated "
                "person-contact fallback and requires human confirmation."
            )
        elif not strong_evidence:
            action = "REVIEW_REQUIRED"
            reason = "The proposal lacks strong source-ranked identity evidence."
        else:
            action = "SAFE_RENAME_CANDIDATE"
            reason = (
                "Strong source-backed identity, no candidate conflict, and no "
                "deterministic duplicate risk."
            )

        diagnostics = self._build_diagnostics(
            candidates=candidates,
            projections=projections,
            source_types=source_types,
            document_counts=document_counts,
            action=action,
            identity_support_evidence=identity_support_evidence,
            conflicts=conflicts,
        )

        return ClientIdentityCleanupProposal(
            client_id=client.id,
            suspicion_types=list(self.quality.suspicion_types(client.name)),
            current_name=client.name,
            current_client_type=client.client_type,
            primary_email=client.primary_email,
            primary_phone=client.primary_phone,
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
            identity_support_evidence=identity_support_evidence,
            candidate_projections=projections,
            diagnostics=diagnostics,
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
        identity_support = self._identity_support_evidence(
            projection.entity_name,
            evidence,
        )
        identity_confidence = max(
            (item.confidence for item in identity_support),
            default=0.0,
        )
        base_projection = projection.base_projection

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
            identity_confidence=round(identity_confidence, 4),
            evidence=evidence,
            identity_support_evidence=identity_support,
            gmail_quoted_boundaries=(
                base_projection.gmail_quoted_boundaries
                if base_projection is not None
                else 0
            ),
            gmail_relay_messages=(
                base_projection.gmail_relay_messages
                if base_projection is not None
                else 0
            ),
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

    def _document_counts_by_candidate(
        self,
        candidates: list[ClientCandidate],
    ) -> dict[int, int]:
        candidate_ids = [candidate.id for candidate in candidates]
        if not candidate_ids:
            return {}
        rows = (
            self.db.query(Document.candidate_id, func.count(Document.id))
            .filter(Document.candidate_id.in_(candidate_ids))
            .group_by(Document.candidate_id)
            .all()
        )
        return {candidate_id: count for candidate_id, count in rows}

    def _build_diagnostics(
        self,
        *,
        candidates: list[ClientCandidate],
        projections: list[CandidateCleanupProjection],
        source_types: dict[int, dict[int, str]],
        document_counts: dict[int, int],
        action: str,
        identity_support_evidence: list[CleanupEvidence],
        conflicts: list[str],
    ) -> dict[str, Any]:
        candidate_ids = [candidate.id for candidate in candidates]
        all_source_types = [
            source_type
            for candidate_id in candidate_ids
            for source_type in source_types.get(candidate_id, {}).values()
        ]
        source_type_set = set(all_source_types)
        has_gmail = "gmail_message" in source_type_set
        has_sheets = "google_sheets_row" in source_type_set
        all_evidence = [
            evidence
            for projection in projections
            for evidence in projection.evidence
        ]
        reasons: list[str] = []

        if action == "INSUFFICIENT_EVIDENCE":
            if not all_source_types:
                reasons.append("no_candidate_source")
            if has_gmail:
                reasons.append("gmail_sources_no_usable_identity_evidence")
            if has_sheets:
                reasons.append("sheets_sources_no_usable_identity_evidence")
            if has_gmail and has_sheets:
                reasons.append("gmail_and_sheets_no_usable_identity_evidence")
            if not all_evidence and any(candidate.name.strip() for candidate in candidates):
                reasons.append("only_candidate_self_identity_existed")
            if any(
                projection.status == "first_party_internal"
                for projection in projections
            ):
                reasons.append("rejected_by_first_party_policy")
            if any(
                projection.status == "relay_container"
                or projection.gmail_relay_messages > 0
                for projection in projections
            ):
                reasons.append("rejected_as_relay")
            if any(
                projection.gmail_quoted_boundaries > 0
                for projection in projections
            ):
                reasons.append("quoted_history_excluded_by_boundary")
            if all_evidence and (
                not identity_support_evidence
                or max(
                    evidence.confidence
                    for evidence in identity_support_evidence
                )
                < 0.90
            ):
                reasons.append("weak_or_unrelated_evidence")
            if conflicts:
                reasons.append("ambiguous_or_conflicting_identity")
            if not reasons:
                reasons.append("other_deterministic_no_identity")

        return {
            "source_types": sorted(source_type_set),
            "source_count": len(all_source_types),
            "has_gmail_source": has_gmail,
            "has_sheets_source": has_sheets,
            "candidate_has_primary_email": any(
                bool(candidate.primary_email) for candidate in candidates
            ),
            "candidate_has_primary_phone": any(
                bool(candidate.primary_phone) for candidate in candidates
            ),
            "candidate_has_tax_id": any(bool(candidate.tax_id) for candidate in candidates),
            "document_count": sum(
                document_counts.get(candidate_id, 0)
                for candidate_id in candidate_ids
            ),
            "why_insufficient": reasons,
        }

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
            {
                evidence.source_type
                for evidence in proposal.identity_support_evidence
            }
            for proposal in proposals
        ]
        additional = Counter(
            finding
            for client in clients
            for finding in self.quality.additional_findings(client.name)
        )

        insufficient = [
            proposal
            for proposal in proposals
            if proposal.action == "INSUFFICIENT_EVIDENCE"
        ]
        reason_counts = Counter(
            reason
            for proposal in insufficient
            for reason in proposal.diagnostics["why_insufficient"]
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
            "insufficient_diagnostics": {
                "categories_overlap": True,
                "no_candidate_source": reason_counts["no_candidate_source"],
                "gmail_no_usable_identity": reason_counts[
                    "gmail_sources_no_usable_identity_evidence"
                ],
                "sheets_no_usable_identity": reason_counts[
                    "sheets_sources_no_usable_identity_evidence"
                ],
                "both_no_usable_identity": reason_counts[
                    "gmail_and_sheets_no_usable_identity_evidence"
                ],
                "only_candidate_self_identity": reason_counts[
                    "only_candidate_self_identity_existed"
                ],
                "rejected_first_party": reason_counts[
                    "rejected_by_first_party_policy"
                ],
                "rejected_relay": reason_counts["rejected_as_relay"],
                "quoted_history_excluded": reason_counts[
                    "quoted_history_excluded_by_boundary"
                ],
                "weak_or_unrelated_evidence": reason_counts[
                    "weak_or_unrelated_evidence"
                ],
                "ambiguous_or_conflicting": reason_counts[
                    "ambiguous_or_conflicting_identity"
                ],
                "other_deterministic_reason": reason_counts[
                    "other_deterministic_no_identity"
                ],
                "candidate_has_primary_email": sum(
                    p.diagnostics["candidate_has_primary_email"]
                    for p in insufficient
                ),
                "candidate_has_primary_phone": sum(
                    p.diagnostics["candidate_has_primary_phone"]
                    for p in insufficient
                ),
                "candidate_has_tax_id": sum(
                    p.diagnostics["candidate_has_tax_id"]
                    for p in insufficient
                ),
                "candidate_has_documents": sum(
                    p.diagnostics["document_count"] > 0
                    for p in insufficient
                ),
                "documents_total": sum(
                    p.diagnostics["document_count"]
                    for p in insufficient
                ),
            },
            "future_evidence_opportunities": {
                "gmail_header_or_display_name_review": sum(
                    p.diagnostics["has_gmail_source"] for p in insufficient
                ),
                "sheets_structure_review": sum(
                    p.diagnostics["has_sheets_source"] for p in insufficient
                ),
                "document_metadata_or_ocr_review": sum(
                    p.diagnostics["document_count"] > 0
                    for p in insufficient
                ),
                "contact_or_address_model_review": sum(
                    p.diagnostics["candidate_has_primary_email"]
                    or p.diagnostics["candidate_has_primary_phone"]
                    for p in insufficient
                ),
                "manual_review": len(insufficient),
            },
        }

    def _identity_support_evidence(
        self,
        proposed_name: str | None,
        evidence: list[CleanupEvidence],
    ) -> list[CleanupEvidence]:
        normalized_proposed = self.quality.normalize_identity(proposed_name)
        if not normalized_proposed:
            return []
        return self._dedupe_evidence(
            item
            for item in evidence
            if self.quality.normalize_identity(item.value)
            == normalized_proposed
        )

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
