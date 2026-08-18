from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ClientAiConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return " ".join(value.split())


class ClientAiAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation: list[ClientAiConversationMessage] = Field(
        default_factory=list,
        max_length=8,
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def bound_conversation(self):
        if sum(len(item.content) for item in self.conversation) > 4000:
            raise ValueError("Conversation history is too large")
        return self


class ClientAiSource(BaseModel):
    source_type: Literal[
        "client", "email", "document", "project", "inspection", "timeline"
    ]
    source_id: int
    title: str
    date: datetime | None = None
    route: str
    snippet: str = Field(max_length=600)


class ClientAiCoverage(BaseModel):
    structured_fields: int = 0
    projects_considered: int = 0
    inspections_considered: int = 0
    emails_searched: int = 0
    documents_lexical_searched: int = 0
    document_vectors_used: int = 0
    timeline_events_considered: int = 0


class ClientAiAskResponse(BaseModel):
    answer: str
    sources: list[ClientAiSource]
    coverage: ClientAiCoverage
    semantic_status: Literal["available", "unavailable", "not_used", "limited"]
    limitations: list[str]
    direct_answer: bool = False
    model: str | None = None
