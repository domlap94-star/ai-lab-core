from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.unified_assistant import UnifiedAssistantResponse, UnifiedConversationMessage


MAX_JSON_BYTES = 64 * 1024
MAX_JSON_DEPTH = 7
MAX_JSON_COLLECTION = 100
MAX_JSON_STRING = 8_000


def validate_bounded_json(value: Any, *, field_name: str) -> Any:
    """Reject unbounded orchestration JSON before it reaches PostgreSQL."""

    def walk(item: Any, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"{field_name} exceeds maximum depth")
        if isinstance(item, dict):
            if len(item) > MAX_JSON_COLLECTION:
                raise ValueError(f"{field_name} has too many keys")
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 100:
                    raise ValueError(f"{field_name} contains an invalid key")
                walk(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > MAX_JSON_COLLECTION:
                raise ValueError(f"{field_name} has too many items")
            for child in item:
                walk(child, depth + 1)
        elif isinstance(item, str) and len(item) > MAX_JSON_STRING:
            raise ValueError(f"{field_name} contains an oversized string")
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"{field_name} contains an unsupported value")

    walk(value, 0)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError(f"{field_name} exceeds maximum encoded size")
    return value


class AssistantRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=2000)
    attempt_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    client_id: int | None = Field(default=None, gt=0)
    candidate_id: int | None = Field(default=None, gt=0)
    document_id: int | None = Field(default=None, gt=0)
    mail_source_id: int | None = Field(default=None, gt=0)
    inspection_id: int | None = Field(default=None, gt=0)
    conversation_id: int | None = Field(default=None, gt=0)
    conversation: list[UnifiedConversationMessage] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_contract_bounds(self):
        if sum(len(item.content) for item in self.conversation) > 6000:
            raise ValueError("Conversation history is too large")
        validate_bounded_json(self.model_dump(mode="json"), field_name="request_payload")
        return self


class AssistantRunProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=24)
    message: str

    @model_validator(mode="after")
    def progress_is_ordered(self):
        if self.current is not None and self.total is not None and self.current > self.total:
            raise ValueError("Progress exceeds total")
        return self


class AssistantRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    attempt_id: str
    conversation_id: int | None = None
    conversation_deleted: bool = False
    status: Literal[
        "created", "queued", "running", "waiting", "completed",
        "review_required", "failed", "cancelled",
    ]
    current_stage: str | None = None
    complexity: Literal["fast", "standard", "deep", "visual", "external_candidate"]
    progress: AssistantRunProgress
    can_cancel: bool
    poll_after_ms: int = Field(default=2000, ge=500, le=30_000)
    recovery_generation: int = Field(ge=0)
    result: UnifiedAssistantResponse | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class AssistantRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AssistantRunResponse]
