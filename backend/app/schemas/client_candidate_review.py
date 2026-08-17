from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
