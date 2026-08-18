from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentToolAuditMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    outcome: Literal["ok", "error", "blocked", "timeout", "cancelled"]
    duration_ms: int = Field(ge=0, le=300_000)


class AgentExecutionMetadata(BaseModel):
    """Strict metadata only; customer content and model payloads are forbidden."""

    model_config = ConfigDict(extra="forbid")

    tools: list[AgentToolAuditMetadata] = Field(default_factory=list, max_length=8)
    rounds: int = Field(default=0, ge=0, le=5)
    final_status: Literal["started", "completed", "failed", "cancelled", "blocked"]
