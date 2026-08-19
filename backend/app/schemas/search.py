from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


SearchEntityType = Literal[
    "client",
    "project",
    "inspection",
    "document",
    "email",
    "candidate",
]


class GlobalSearchResult(BaseModel):
    type: SearchEntityType
    id: int
    title: str
    subtitle: str | None = None
    snippet: str | None = None
    score: float
    match_reason: str
    match_reasons: list[str]
    occurred_at: datetime | None = None
    client_id: int | None = None
    project_id: int | None = None
    inspection_id: int | None = None
    client_workflow_status: str | None = None
    client_workflow_status_label: str | None = None
    client_workflow_effective_date: date | None = None
    route: str


class GlobalSearchPage(BaseModel):
    items: list[GlobalSearchResult]
    skip: int
    limit: int
    has_more: bool
    semantic_status: Literal[
        "available",
        "unavailable",
        "not_requested",
    ]
