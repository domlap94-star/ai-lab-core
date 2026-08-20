from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WorkItemType = Literal["task", "order", "realization", "reminder", "event"]
WorkItemStatus = Literal["todo", "in_progress", "completed", "cancelled"]
WorkItemPriority = Literal["low", "normal", "high", "urgent"]
CandidateResolution = Literal["new_candidate"]
AbsenceStatus = Literal["requested", "approved", "rejected", "cancelled"]


class WorkItemCreate(BaseModel):
    item_type: WorkItemType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    start_at: datetime | None = None
    due_at: datetime | None = None
    all_day: bool = False
    timezone_name: str | None = Field(default=None, max_length=64)
    status: WorkItemStatus = "todo"
    priority: WorkItemPriority = "normal"
    assignee_user_id: int | None = Field(default=None, gt=0)
    client_id: int | None = Field(default=None, gt=0)
    party_name: str | None = Field(default=None, max_length=255)

    @field_validator("title", "description", "timezone_name", "party_name", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("start_at", "due_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("date-time values must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_semantics(self):
        if self.due_at and self.start_at and self.due_at < self.start_at:
            raise ValueError("due_at cannot precede start_at")
        if self.item_type == "event" and self.start_at is None:
            raise ValueError("event requires start_at")
        if self.item_type == "reminder" and self.due_at is None:
            raise ValueError("reminder requires due_at")
        if self.all_day and (self.start_at is None or self.due_at is None or not self.timezone_name):
            raise ValueError("all_day requires start_at, due_at and timezone_name")
        if self.timezone_name:
            try:
                ZoneInfo(self.timezone_name)
            except ZoneInfoNotFoundError as error:
                raise ValueError("timezone_name must be a valid IANA timezone") from error
        return self


class WorkItemUpdate(BaseModel):
    expected_version: int = Field(gt=0)
    item_type: WorkItemType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    start_at: datetime | None = None
    due_at: datetime | None = None
    all_day: bool | None = None
    timezone_name: str | None = Field(default=None, max_length=64)
    status: WorkItemStatus | None = None
    priority: WorkItemPriority | None = None
    assignee_user_id: int | None = Field(default=None, gt=0)
    client_id: int | None = Field(default=None, gt=0)
    party_name: str | None = Field(default=None, max_length=255)

    @field_validator("start_at", "due_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("date-time values must include a timezone offset")
        return value


class WorkItemStatusUpdate(BaseModel):
    status: WorkItemStatus
    expected_version: int = Field(gt=0)


class VersionRequest(BaseModel):
    expected_version: int = Field(gt=0)


class WorkItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_type: WorkItemType
    title: str
    description: str | None
    start_at: datetime | None
    due_at: datetime | None
    all_day: bool
    timezone_name: str | None
    status: WorkItemStatus
    priority: WorkItemPriority
    assignee_user_id: int | None
    assignee_display: str | None = None
    client_id: int | None
    client_name: str | None = None
    party_name: str | None
    created_by_user_id: int
    updated_by_user_id: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    deleted_at: datetime | None
    version: int


class WorkItemPage(BaseModel):
    items: list[WorkItemRead]
    total: int
    skip: int
    limit: int


class WorkItemNoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=10000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("note text is required")
        return value


class WorkItemNoteUpdate(WorkItemNoteCreate):
    expected_version: int = Field(gt=0)


class WorkItemNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    work_item_id: int
    text: str
    created_by_user_id: int
    updated_by_user_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int


class WorkItemDocumentLink(BaseModel):
    document_id: int = Field(gt=0)
    note_id: int | None = Field(default=None, gt=0)


class WorkItemDocumentRead(BaseModel):
    id: int
    work_item_id: int
    note_id: int | None
    document_id: int
    filename: str
    content_type: str
    file_size: int
    source_type: str
    captured_at: datetime | None
    created_at: datetime


class AbsenceCreate(BaseModel):
    absence_type: Literal["vacation", "day_off", "sick_leave", "other"]
    start_date: date
    end_date: date
    note: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AbsenceUpdate(AbsenceCreate):
    expected_version: int = Field(gt=0)


class AbsenceReview(BaseModel):
    expected_version: int = Field(gt=0)
    review_note: str | None = Field(default=None, max_length=2000)


class AbsenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requester_user_id: int
    requester_display: str | None = None
    absence_type: Literal["vacation", "day_off", "sick_leave", "other"]
    start_date: date
    end_date: date
    status: AbsenceStatus
    note: str | None
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    review_note: str | None
    cancelled_by_user_id: int | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class AbsencePage(BaseModel):
    items: list[AbsenceRead]
    total: int
    skip: int
    limit: int


class CalendarEntry(BaseModel):
    entity_id: int
    entity_kind: Literal["work_item", "absence"]
    item_type: str
    title: str
    start: datetime | date
    end: datetime | date
    status: str
    priority: str | None = None
    assignee_display: str | None = None
    client_id: int | None = None
    client_name: str | None = None
    all_day: bool


class CalendarMonth(BaseModel):
    year: int
    month: int
    items: list[CalendarEntry]
    total: int
    day_counts: dict[str, int]
    truncated: bool


class AssigneeRead(BaseModel):
    id: int
    username: str
