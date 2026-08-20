from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RecentActivityItem(BaseModel):
    stable_key: str = Field(max_length=220)
    timestamp: datetime
    actor_user_id: int | None
    actor_display: str = Field(max_length=80)
    action: str = Field(max_length=40)
    entity_type: str = Field(max_length=64)
    entity_id: int
    summary: str = Field(max_length=200)
    deep_link: str | None = Field(default=None, max_length=500)
    client_id: int | None = None
    client_name: str | None = Field(default=None, max_length=255)


class RecentActivityPage(BaseModel):
    items: list[RecentActivityItem]
    skip: int
    limit: int
    has_more: bool
