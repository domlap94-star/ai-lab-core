from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TrashEntityType = Literal["document", "client", "user"]
TrashState = Literal["trashed", "purging", "blocked", "restored", "purged"]


class TrashEntryRead(BaseModel):
    id: int
    entity_type: TrashEntityType
    entity_id: int
    state: TrashState
    safe_display_label: str
    trashed_at: datetime
    purge_after: datetime
    trashed_by_user_id: int
    restored_at: datetime | None = None
    purged_at: datetime | None = None
    attempt_count: int
    last_error_code: str | None = None

    model_config = {"from_attributes": True}


class TrashPage(BaseModel):
    items: list[TrashEntryRead]
    total: int
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class TrashPurgeSummary(BaseModel):
    eligible: int
    processed: int
    purged: int
    blocked: int
    failed: int
    singleton_acquired: bool
