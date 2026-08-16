from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class DocumentRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    filename: str
    original_filename: str | None

    content_type: str
    file_size: int

    storage_path: str | None
    checksum_sha256: str | None

    source_type: str
    external_id: str | None

    gmail_message_id: str | None
    gmail_thread_id: str | None

    candidate_id: int | None
    client_id: int | None

    captured_at: datetime | None
    latitude: float | None
    longitude: float | None
    location_accuracy_m: float | None
    location_source: str | None
    inspection_session_id: str | None

    processing_status: str
    processing_error: str | None

    match_status: str
    match_confidence: float | None
    match_method: str | None
    matched_at: datetime | None

    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    created: bool
    matched_by: str | None = None


DocumentLinkState = Literal[
    "ALL",
    "LINKED",
    "CANDIDATE_ONLY",
    "UNLINKED",
]


class DocumentPublicRead(BaseModel):
    id: int
    original_filename: str | None
    content_type: str
    file_size: int
    source_type: str
    client_id: int | None
    client_name: str | None
    candidate_id: int | None
    candidate_name: str | None
    processing_status: str
    metadata_status: str
    match_status: str
    match_confidence: float | None
    captured_at: datetime | None
    parent_document_id: int | None
    archive_member_path: str | None
    archive_depth: int
    created_at: datetime
    updated_at: datetime


class DocumentPublicPage(BaseModel):
    items: list[DocumentPublicRead]
    total: int
    skip: int
    limit: int


DocumentMatchConfidence = Literal["HIGH", "MEDIUM", "LOW", "CONFLICT", "NONE"]


class DocumentMatchEvidence(BaseModel):
    kind: str
    description: str
    client_id: int | None = None


class DocumentClientSuggestion(BaseModel):
    client_id: int
    client_name: str
    confidence: DocumentMatchConfidence
    evidence: list[DocumentMatchEvidence]


class DocumentClientLinkEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    actor_user_id: int
    action: Literal["LINK", "UNLINK", "MOVE"]
    old_client_id: int | None
    new_client_id: int | None
    previous_candidate_id: int | None
    reason: str
    reversal_of_event_id: int | None
    created_at: datetime


class DocumentClientMatchRead(BaseModel):
    document_id: int
    current_client_id: int | None
    current_client_name: str | None
    candidate_id: int | None
    status: Literal["ASSIGNED", "CANDIDATE", "UNMATCHED", "CONFLICT"]
    confidence: DocumentMatchConfidence
    suggestions: list[DocumentClientSuggestion]
    evidence: list[DocumentMatchEvidence]
    conflict: bool
    history: list[DocumentClientLinkEventRead]


class DocumentClientLinkRequest(BaseModel):
    client_id: int = Field(ge=1)
    reason: str = Field(default="manual", min_length=1, max_length=500)
    confirm_conflict: bool = False


class DocumentClientUnlinkRequest(BaseModel):
    reason: str = Field(default="manual", min_length=1, max_length=500)
    confirm: bool = False


class DocumentClientLinkResult(BaseModel):
    document: DocumentPublicRead
    event: DocumentClientLinkEventRead
