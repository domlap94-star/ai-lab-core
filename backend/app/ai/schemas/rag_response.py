from __future__ import annotations

from pydantic import BaseModel


class RagSourceResponse(BaseModel):
    source_number: int
    score: float

    document_id: int
    chunk_id: int
    chunk_index: int

    filename: str | None

    page_from: int | None
    page_to: int | None

    client_id: int | None

    content_source: str | None

    fragment: str


class RagEvidenceResponse(BaseModel):
    evidence_id: int
    source_number: int
    text: str


class RagClaimResponse(BaseModel):
    evidence_id: int
    source_number: int
    quote: str


class RagApiResponse(BaseModel):
    question: str
    answer: str
    model: str

    sources: list[RagSourceResponse]
    evidence: list[RagEvidenceResponse]
    claims: list[RagClaimResponse]

    cited_source_numbers: list[int]

    generation_attempts: int
