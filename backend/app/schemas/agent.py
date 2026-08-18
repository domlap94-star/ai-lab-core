from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def normalize(cls, value: str) -> str:
        return " ".join(value.split())


class AgentAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=1000)
    client_id: int | None = Field(default=None, gt=0)
    inspection_id: int | None = Field(default=None, gt=0)
    conversation: list[AgentConversationMessage] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def bound_history(self):
        if sum(len(item.content) for item in self.conversation) > 4000:
            raise ValueError("Conversation history is too large")
        return self


class AgentSource(BaseModel):
    source_type: str = Field(min_length=1, max_length=30)
    source_id: int | None = None
    title: str = Field(max_length=255)
    date: datetime | None = None
    route: str | None = Field(default=None, max_length=500)
    snippet: str = Field(default="", max_length=600)


class AgentToolTrace(BaseModel):
    name: str
    outcome: Literal["ok", "error", "blocked", "timeout", "cancelled"]


class AgentAskResponse(BaseModel):
    request_id: str
    answer: str
    sources: list[AgentSource]
    tool_trace: list[AgentToolTrace]
    coverage: dict[str, int] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    status: Literal["completed", "blocked"]
    model: str | None = None


class AgentPlannerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["tool", "answer"]
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = Field(default=None, max_length=5000)
    source_ids: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "tool" and not self.tool:
            raise ValueError("Tool action requires a tool name")
        if self.action == "answer" and not self.answer:
            raise ValueError("Answer action requires answer text")
        return self
