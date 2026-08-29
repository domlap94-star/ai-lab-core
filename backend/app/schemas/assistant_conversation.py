from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.unified_assistant import UnifiedAssistantResponse


class AssistantConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def normalize_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Conversation title must not be empty")
        return normalized


class AssistantConversationRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Conversation title must not be empty")
        return normalized


class AssistantConversationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    created_at: datetime
    last_activity_at: datetime
    last_message_preview: str | None = None
    latest_run_id: str | None = None
    latest_run_status: str | None = None
    active: bool = False


class AssistantConversationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AssistantConversationSummary]


class AssistantConversationMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    role: str
    content: str
    assistant_run_id: str | None = None
    created_at: datetime
    run_status: str | None = None
    run_current_stage: str | None = None
    run_result: UnifiedAssistantResponse | None = None


class AssistantConversationDetail(AssistantConversationSummary):
    messages: list[AssistantConversationMessageResponse]
    has_older: bool = False


class AssistantConversationDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    deleted_at: datetime
    active_run_id: str | None = None
    message: str = "Usunięcie rozmowy nie anuluje trwającej analizy."
