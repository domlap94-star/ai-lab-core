from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


TechnicalIntent = Literal[
    "case_summary", "document_analysis", "inspection_preparation",
    "soil_ground", "foundation_settlement", "floor_settlement",
    "geopolymer", "measurements", "comparison", "missing_information",
    "general_technical",
]


class TechnicalConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return " ".join(value.split())


class TechnicalAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    client_id: int | None = Field(default=None, gt=0)
    inspection_id: int | None = Field(default=None, gt=0)
    conversation: list[TechnicalConversationMessage] = Field(
        default_factory=list, max_length=8
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def bound_history(self):
        if sum(len(item.content) for item in self.conversation) > 4000:
            raise ValueError("Conversation history is too large")
        return self


class TechnicalSource(BaseModel):
    source_type: Literal[
        "client", "inspection", "document", "email", "timeline",
        "project", "analytics",
    ]
    source_id: int | None = None
    title: str
    date: datetime | None = None
    route: str | None = None
    snippet: str = Field(max_length=600)


class TechnicalCoverage(BaseModel):
    structured_fields_used: int = 0
    documents_considered: int = 0
    document_chunks_used: int = 0
    inspections_considered: int = 0
    emails_considered: int = 0
    timeline_events_considered: int = 0


class TechnicalAskResponse(BaseModel):
    answer: str
    facts: list[str] = Field(default_factory=list, max_length=12)
    inferences: list[str] = Field(default_factory=list, max_length=12)
    missing_information: list[str] = Field(default_factory=list, max_length=12)
    sources: list[TechnicalSource]
    coverage: TechnicalCoverage
    limitations: list[str]
    intent: TechnicalIntent
    semantic_status: Literal["available", "unavailable", "not_used", "limited"]
    model: str | None = None
