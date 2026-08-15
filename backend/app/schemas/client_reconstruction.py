from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReconstructionEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: int | str
    field: str


class ClientReconstructionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: int
    entity_type: Literal["person", "company", "institution", "unknown"]
    canonical_name: str | None
    canonical_legal_name: str | None
    canonical_email: str | None
    canonical_phone: str | None
    current_name_class: Literal[
        "valid_identity", "email_artifact", "phone_artifact",
        "filename_artifact", "address_artifact", "prefix_artifact",
        "garbage_artifact", "status_or_note_artifact",
        "abbreviated_identity", "unknown",
    ]
    proposed_name_transformation: Literal[
        "none", "exact_source_value", "compose_person_name",
        "strip_artifact_prefix", "normalize_formatting",
        "extract_identity_from_signature", "other",
    ]
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[ReconstructionEvidenceRef]
    conflict_detected: bool
    duplicate_risk: bool
    recommended_disposition: Literal[
        "KEEP_AS_IS", "PROPOSE_REPAIR", "INSUFFICIENT_EVIDENCE",
        "CONFLICT", "POSSIBLE_DUPLICATE",
    ]


class ValidatedClientReconstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: ClientReconstructionProposal | None
    classification: Literal[
        "KEEP", "ELIGIBLE_FOR_HUMAN_REVIEW",
        "HIGH_CONFIDENCE_REPAIR_CANDIDATE", "INSUFFICIENT_EVIDENCE",
        "CONFLICT", "POSSIBLE_DUPLICATE", "MODEL_INVALID",
        "POLICY_REJECTED",
    ]
    validation_errors: list[str] = Field(default_factory=list)
    duplicate_client_ids: list[int] = Field(default_factory=list)
