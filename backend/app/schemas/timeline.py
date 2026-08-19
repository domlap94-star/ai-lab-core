from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TimelineEventType = Literal[
    "client_created",
    "project_created",
    "inspection_created",
    "inspection_scheduled",
    "inspection_started",
    "inspection_completed",
    "document_added",
    "photo_captured",
    "email_received",
    "email_sent",
    "document_client_linked",
    "document_client_moved",
    "document_client_unlinked",
    "call_initiated",
    "client_status_changed",
    "candidate_merged",
]


class TimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stable_key: str
    event_type: TimelineEventType
    occurred_at: datetime
    title: str
    summary: str | None = None
    client_id: int | None = None
    project_id: int | None = None
    inspection_id: int | None = None
    document_id: int | None = None
    source_type: str
    source_id: int | str
    actor_user_id: int | None = None
    actor_display_name: str | None = None
    direction: Literal["incoming", "outgoing"] | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    deep_link: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelinePage(BaseModel):
    items: list[TimelineEvent]
    total: int
    skip: int
    limit: int
