from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CallInitiatedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    contact_id: int | None = None


class CallActivityMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: int | None
    contact_kind: Literal["phone"]
    contact_reference: Literal["contact_point", "primary_phone"]


class StatusActivityMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_status: str
    new_status: str
    effective_date: date | None = None


class CallInitiatedResponse(BaseModel):
    event_id: int
    operation_id: UUID
    replayed: bool
    occurred_at: datetime
