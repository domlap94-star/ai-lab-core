from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.schemas.client_reconstruction import (
    ClientReconstructionProposal,
    ValidatedClientReconstruction,
)
from app.services.client_identity_name_quality_service import ClientIdentityNameQualityService
from app.services.first_party_identity_registry import FirstPartyIdentityRegistry


PREFIX_RE = re.compile(r"^\s*\[\s*\d+\s*\]\s*")
GARBAGE_RE = re.compile(r"^[\W_]+$", re.UNICODE)
STATUS_VALUES = {"nie odbiera", "oferta wyslana", "ogledziny"}


class ClientReconstructionPolicyService:
    """Validates model output against provenance, then classifies it deterministically."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.quality = ClientIdentityNameQualityService

    def validate(self, packet: dict[str, Any], proposal: ClientReconstructionProposal) -> ValidatedClientReconstruction:
        errors: list[str] = []
        client_id = int(packet["client"]["id"])
        if proposal.client_id != client_id:
            errors.append("client_id mismatch")
        source_index = {(str(item["source_type"]), str(item["source_id"])): item
                        for item in packet.get("source_evidence", [])}
        for ref in proposal.evidence_refs:
            if (ref.source_type, str(ref.source_id)) not in source_index:
                errors.append(f"foreign evidence ref {ref.source_type}:{ref.source_id}")

        supported_values = self._supported_values(packet)
        for field, value in (("name", proposal.canonical_name),
                             ("email", proposal.canonical_email),
                             ("phone", proposal.canonical_phone)):
            if value and not self._supported(field, value, supported_values, proposal):
                errors.append(f"unsupported canonical_{field}")

        duplicate_ids = self._duplicates(client_id, proposal)
        hard_rejected = bool(proposal.canonical_name and self._hard_reject(proposal.canonical_name))
        if errors:
            return ValidatedClientReconstruction(
                proposal=proposal, classification="MODEL_INVALID",
                validation_errors=errors, duplicate_client_ids=duplicate_ids,
            )
        if hard_rejected:
            return ValidatedClientReconstruction(
                proposal=proposal, classification="POLICY_REJECTED",
                validation_errors=["canonical name violates identity quality policy"],
                duplicate_client_ids=duplicate_ids,
            )
        if duplicate_ids or proposal.duplicate_risk or proposal.recommended_disposition == "POSSIBLE_DUPLICATE":
            classification = "POSSIBLE_DUPLICATE"
        elif proposal.conflict_detected or proposal.recommended_disposition == "CONFLICT":
            classification = "CONFLICT"
        elif proposal.recommended_disposition == "KEEP_AS_IS":
            classification = "KEEP"
        elif proposal.recommended_disposition == "INSUFFICIENT_EVIDENCE" or not proposal.canonical_name:
            classification = "INSUFFICIENT_EVIDENCE"
        elif proposal.confidence >= 0.95 and proposal.proposed_name_transformation in {
            "exact_source_value", "compose_person_name", "strip_artifact_prefix",
            "normalize_formatting", "extract_identity_from_signature",
        }:
            classification = "HIGH_CONFIDENCE_REPAIR_CANDIDATE"
        else:
            classification = "ELIGIBLE_FOR_HUMAN_REVIEW"
        return ValidatedClientReconstruction(
            proposal=proposal, classification=classification,
            validation_errors=[], duplicate_client_ids=duplicate_ids,
        )

    def _supported_values(self, packet: dict[str, Any]) -> dict[str, set[str]]:
        result = {"name": set(), "email": set(), "phone": set()}
        for projection in packet.get("deterministic_projections", []):
            for key in ("entity_name", "legal_name", "contact_name"):
                if projection.get(key): result["name"].add(self.quality.normalize_identity(projection[key]))
            if projection.get("contact_email"): result["email"].add(self.quality.normalize_email(projection["contact_email"]))
            if projection.get("contact_phone"): result["phone"].add(self.quality.normalize_phone(projection["contact_phone"]))
            for evidence in projection.get("evidence", []):
                if evidence.get("value"):
                    result["name"].add(self.quality.normalize_identity(evidence["value"]))
                    result["name"].add(self.quality.normalize_identity(PREFIX_RE.sub("", evidence["value"])))
        for source in packet.get("source_evidence", []):
            for value in self._walk(source):
                result["name"].add(self.quality.normalize_identity(value))
                if self.quality.EMAIL_RE.fullmatch(value.strip()): result["email"].add(self.quality.normalize_email(value))
                if len(self.quality.normalize_phone(value)) >= 9: result["phone"].add(self.quality.normalize_phone(value))
        return result

    def _supported(self, field: str, value: str, values: dict[str, set[str]], proposal: ClientReconstructionProposal) -> bool:
        normalizer = {"name": self.quality.normalize_identity, "email": self.quality.normalize_email,
                      "phone": self.quality.normalize_phone}[field]
        normalized = normalizer(value)
        if normalized in values[field]: return True
        if field == "name" and proposal.proposed_name_transformation == "compose_person_name":
            parts = normalized.split()
            return len(parts) >= 2 and all(any(part in item.split() for item in values["name"]) for part in parts)
        return False

    def _hard_reject(self, value: str) -> bool:
        normalized = self.quality.normalize_identity(value)
        return bool(self.quality.suspicion_types(value) or self.quality.additional_findings(value)
                    or GARBAGE_RE.fullmatch(value.strip()) or normalized in STATUS_VALUES
                    or FirstPartyIdentityRegistry.is_first_party_person(value)
                    or FirstPartyIdentityRegistry.is_first_party_entity(value)
                    or FirstPartyIdentityRegistry.is_first_party_email(value))

    def _duplicates(self, client_id: int, proposal: ClientReconstructionProposal) -> list[int]:
        filters = []
        if proposal.canonical_email: filters.append(Client.primary_email.ilike(proposal.canonical_email.strip()))
        if proposal.canonical_phone:
            digits = self.quality.normalize_phone(proposal.canonical_phone)
            if digits: filters.append(Client.primary_phone.isnot(None))
        if proposal.canonical_legal_name: filters.append(Client.legal_name.ilike(proposal.canonical_legal_name.strip()))
        if not filters: return []
        candidates = self.db.query(Client).filter(Client.id != client_id, Client.deleted_at.is_(None), or_(*filters)).all()
        return sorted(item.id for item in candidates if
                      (proposal.canonical_email and self.quality.normalize_email(item.primary_email) == self.quality.normalize_email(proposal.canonical_email)) or
                      (proposal.canonical_phone and self.quality.normalize_phone(item.primary_phone) == self.quality.normalize_phone(proposal.canonical_phone)) or
                      (proposal.canonical_legal_name and self.quality.normalize_identity(item.legal_name) == self.quality.normalize_identity(proposal.canonical_legal_name)))

    @classmethod
    def _walk(cls, value: Any):
        if isinstance(value, str): yield value
        elif isinstance(value, dict):
            for item in value.values(): yield from cls._walk(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value: yield from cls._walk(item)
