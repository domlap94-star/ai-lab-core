from __future__ import annotations

from pydantic import BaseModel, Field


class RagRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=4000,
    )

    model: str = Field(
        default="llama3.2",
        min_length=1,
        max_length=255,
    )

    retrieval_limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    client_id: int | None = Field(
        default=None,
        ge=1,
    )

    document_id: int | None = Field(
        default=None,
        ge=1,
    )

    content_type: str | None = Field(
        default=None,
        max_length=255,
    )

    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
