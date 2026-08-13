from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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
