from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BusinessConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return " ".join(value.split())


class BusinessAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation: list[BusinessConversationMessage] = Field(
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


class BusinessSource(BaseModel):
    source_type: Literal[
        "client", "candidate", "email", "document", "inspection",
        "project", "timeline", "analytics"
    ]
    source_id: int | None = None
    title: str
    date: datetime | None = None
    route: str | None = None
    snippet: str = Field(max_length=600)


class BusinessCoverage(BaseModel):
    clients_considered: int = 0
    candidates_considered: int = 0
    emails_searched: int = 0
    documents_searched: int = 0
    inspections_considered: int = 0
    projects_considered: int = 0
    timeline_events_considered: int = 0


class BusinessAskResponse(BaseModel):
    answer: str
    sources: list[BusinessSource]
    coverage: BusinessCoverage
    limitations: list[str]
    intent: Literal[
        "analytics", "client_lookup", "recent_activity", "communications",
        "documents", "inspections", "projects", "general_summary"
    ]
    direct_answer: bool = False
    semantic_status: Literal["available", "unavailable", "not_used", "limited"]
    model: str | None = None
