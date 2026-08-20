from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MailReconciliationRequest(BaseModel):
    window_days: int = Field(default=7, ge=1, le=30)


class MailReconciliationCandidatePrediction(BaseModel):
    provider_message_id: str
    classification: Literal[
        "new_candidate",
        "reuse_existing_candidate_unlinked",
        "reuse_existing_candidate_client_linked",
    ]
    existing_candidate_id: int | None = None
    existing_client_id: int | None = None
    resolved_client_id: int | None = None
    resolution_confidence: str
    resolution_evidence: list[str]
    expected_candidate_source_delta: int = 1
    expected_candidate_delta: int
    expected_document_delta: int
    expected_new_client_link_delta: int


class MailReconciliationApplyRequest(MailReconciliationRequest):
    dry_run_token: str = Field(min_length=66, max_length=160)


class MailReconciliationDryRunResponse(BaseModel):
    status: str = "dry_run"
    window_days: int
    messages_examined: int
    already_present: int
    missing_count: int
    missing_provider_ids: list[str] = Field(max_length=100)
    expected_candidate_sources: int
    expected_candidates: int
    expected_documents: int
    expected_client_links: int
    candidate_resolutions: list[MailReconciliationCandidatePrediction]
    dry_run_token: str
    started_at: datetime
    completed_at: datetime


class MailReconciliationResponse(BaseModel):
    status: str
    messages_examined: int
    already_present: int
    new_messages_ingested: int
    new_client_linked: int
    new_review_candidates: int
    attachments_created: int
    failed: int
    started_at: datetime
    completed_at: datetime
