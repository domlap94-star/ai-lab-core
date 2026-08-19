from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChangeHistoryRead(BaseModel):
    stable_key: str
    source_type: str
    created_at: datetime
    actor_user_id: int | None
    actor_display_name: str | None
    entity_type: str
    entity_id: int
    entity_label: str
    action: str
    changed_fields: list[str] = Field(max_length=40)
    before_values: dict[str, Any]
    after_values: dict[str, Any]
    deep_link: str | None


class ChangeHistoryPage(BaseModel):
    items: list[ChangeHistoryRead]
    total: int
    skip: int
    limit: int
