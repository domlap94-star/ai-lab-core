from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CandidateStatus = Literal[
    "pending",
    "accepted",
    "rejected",
    "merged",
    "duplicate",
]


class ClientCandidateListItem(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    client_type: str
    name: str
    legal_name: str | None
    tax_id: str | None
    primary_email: str | None
    primary_phone: str | None
    city: str | None
    country_code: str
    status: CandidateStatus
    confidence: float
    matched_client_id: int | None
    source_summary: str | None
    created_at: datetime
    updated_at: datetime


class ClientCandidateContextResponse(BaseModel):
    candidate: dict[str, Any]
    gmail_messages: list[dict[str, Any]]
    sheets_rows: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    other_sources: list[dict[str, Any]]
    metadata: dict[str, Any]


class CandidateAcceptResponse(BaseModel):
    candidate_id: int
    candidate_status: str
    client_id: int
    client_name: str


class CandidateDuplicateMatch(BaseModel):
    client_id: int
    client_name: str
    workflow_status: str
    workflow_status_label: str
    confidence: Literal["certain", "ambiguous"]
    reasons: list[
        Literal[
            "exact_tax_id",
            "exact_email",
            "exact_phone",
            "verified_source_identity",
        ]
    ] = Field(min_length=1, max_length=4)


class CandidateMergeIdentity(BaseModel):
    id: int
    name: str
    legal_name: str | None
    tax_id: str | None
    emails: list[str] = Field(max_length=20)
    phones: list[str] = Field(max_length=20)
    addresses: list[dict[str, Any]] = Field(max_length=20)
    workflow_status: str | None = None
    workflow_status_label: str | None = None


class CandidateMergeFieldProposal(BaseModel):
    field: str
    candidate_value: str | None
    target_value: str | None
    proposed_action: Literal[
        "keep_existing", "take_candidate", "add", "manual_conflict"
    ]
    required_resolution: bool = False


class CandidateMergePreviewResponse(BaseModel):
    candidate: CandidateMergeIdentity
    target: CandidateMergeIdentity
    match: CandidateDuplicateMatch
    field_proposals: list[CandidateMergeFieldProposal] = Field(max_length=20)
    relation_counts: dict[str, int]
    expected_candidate_version: str
    blocked_reasons: list[str] = Field(max_length=10)


class CandidateMergeRequest(BaseModel):
    operation_id: str = Field(min_length=36, max_length=36)
    target_client_id: int = Field(gt=0)
    field_decisions: dict[
        Literal[
            "name",
            "legal_name",
            "tax_id",
            "primary_email",
            "primary_phone",
            "address",
        ],
        Literal["keep_existing", "take_candidate", "add"],
    ] = Field(default_factory=dict, max_length=6)
    expected_candidate_version: str = Field(min_length=1, max_length=64)

    @field_validator("operation_id")
    @classmethod
    def valid_operation_id(cls, value: str) -> str:
        parsed = UUID(value)
        if str(parsed) != value.lower():
            raise ValueError("operation_id must use canonical UUID format")
        return str(parsed)

    @field_validator("expected_candidate_version")
    @classmethod
    def valid_candidate_version(cls, value: str) -> str:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


class CandidateMergeResponse(BaseModel):
    operation_id: str
    candidate_id: int
    candidate_status: Literal["merged"]
    client_id: int
    client_name: str
    changed_fields: list[str]
    relation_counts: dict[str, int]
    idempotent_replay: bool = False


class CandidateMergeRelationCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contacts_added: int = Field(ge=0)
    addresses_added: int = Field(ge=0)
    documents_relinked: int = Field(ge=0)
    emails_relinked: int = Field(ge=0)
    sources_preserved: int = Field(ge=0)


class CandidateMergeAuditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed_fields: list[
        Literal[
            "name",
            "legal_name",
            "tax_id",
            "primary_email",
            "primary_phone",
            "contacts",
            "addresses",
            "documents",
            "emails",
            "candidate_status",
            "matched_client_id",
        ]
    ] = Field(max_length=11)
    relation_counts: CandidateMergeRelationCounts

    @field_validator("changed_fields")
    @classmethod
    def unique_changed_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("changed_fields must be unique")
        return value


class CandidateRejectResponse(BaseModel):
    candidate_id: int
    candidate_status: str


class CandidateBulkAcceptRequest(BaseModel):
    candidate_ids: list[int] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_positive_ids(self):
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("candidate_ids must be unique")
        if any(value <= 0 for value in self.candidate_ids):
            raise ValueError("candidate_ids must be positive")
        return self


class CandidateBulkAcceptItem(BaseModel):
    candidate_id: int
    result: Literal["promoted", "duplicate", "conflict", "not_found", "failed"]
    client_id: int | None = None
    message: str | None = None


class CandidateBulkAcceptResponse(BaseModel):
    requested: int
    promoted: int
    failed: int
    results: list[CandidateBulkAcceptItem]
