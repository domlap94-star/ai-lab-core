from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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