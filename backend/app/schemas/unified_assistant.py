from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UnifiedConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return " ".join(value.split())


class UnifiedAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=2000)
    client_id: int | None = Field(default=None, gt=0)
    candidate_id: int | None = Field(default=None, gt=0)
    document_id: int | None = Field(default=None, gt=0)
    mail_source_id: int | None = Field(default=None, gt=0)
    inspection_id: int | None = Field(default=None, gt=0)
    attempt_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    conversation: list[UnifiedConversationMessage] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def bound_context(self):
        if sum(len(item.content) for item in self.conversation) > 6000:
            raise ValueError("Conversation history is too large")
        return self


class UnifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    claim_class: Literal["FACT", "ESTIMATE", "HYPOTHESIS", "MISSING"]
    text: str
    source_refs: list[str] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)
    estimate_status: Literal["ESTIMABLE", "NOT_ESTIMABLE"] | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    assumptions: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    confirm_or_refute: str | None = None


class UnifiedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_ref: str
    source_type: str
    source_id: int | None = None
    title: str
    excerpt: str
    why_used: str
    supports_claim_ids: list[str]
    route: str | None = None
    external_analysis: bool = False


class UnifiedAssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    answer: str
    status: Literal[
        "accepted_local", "advanced_queued", "advanced_processing",
        "accepted_advanced", "review_required", "failed", "timed_out", "cancelled",
        "document_preparation_queued", "document_preparation_running", "resume_queued",
    ]
    progress: Literal[
        "collecting", "preparing_document", "analyzing", "advanced_analysis", "validating", "complete"
    ]
    target_scope: str
    claims: list[UnifiedClaim]
    sources: list[UnifiedSource]
    used_tools: list[str]
    model: str | None = None
    external_analysis_used: bool = False
    error_message: str | None = None
    current_stage: str | None = None
    last_progress_at: str | None = None
    can_cancel: bool = False
    delayed: bool = False
