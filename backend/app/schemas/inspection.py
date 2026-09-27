from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

InspectionStatus = Literal["planned", "in_progress", "completed", "cancelled"]
WARSAW = ZoneInfo("Europe/Warsaw")


def inspection_local_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=WARSAW)
    return value.astimezone(WARSAW).date()


class InspectionBase(BaseModel):
    client_id: int = Field(gt=0)
    status: InspectionStatus = "planned"
    scheduled_date: date | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_m: float | None = Field(default=None, ge=0)

    @field_validator("scheduled_date", mode="before")
    @classmethod
    def reject_datetime_as_date(cls, value: object) -> object:
        if isinstance(value, datetime) or (isinstance(value, str) and "T" in value):
            raise ValueError("scheduled_date must use YYYY-MM-DD")
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_timing_and_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at cannot precede started_at")
        if self.status != "completed" and self.completed_at is not None:
            raise ValueError("completed_at is only valid for completed inspections")
        return self


class InspectionCreate(InspectionBase):
    @model_validator(mode="after")
    def require_canonical_date(self):
        legacy_dates = [
            inspection_local_date(value)
            for value in (self.scheduled_at, self.started_at)
            if value is not None
        ]
        if self.scheduled_date is None:
            if not legacy_dates:
                raise ValueError("scheduled_date is required")
            self.scheduled_date = legacy_dates[0]
        if any(value != self.scheduled_date for value in legacy_dates):
            raise ValueError("scheduled_date conflicts with legacy timestamp")
        return self


class InspectionUpdate(BaseModel):
    client_id: int | None = Field(default=None, gt=0)
    status: InspectionStatus | None = None
    scheduled_date: date | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_m: float | None = Field(default=None, ge=0)

    @field_validator("scheduled_date", mode="before")
    @classmethod
    def reject_datetime_as_date(cls, value: object) -> object:
        if isinstance(value, datetime) or (isinstance(value, str) and "T" in value):
            raise ValueError("scheduled_date must use YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def normalize_legacy_date(self):
        legacy_dates = [
            inspection_local_date(value)
            for value in (self.scheduled_at, self.started_at)
            if value is not None
        ]
        if self.scheduled_date is None and legacy_dates:
            self.scheduled_date = legacy_dates[0]
        if self.scheduled_date is not None and any(
            value != self.scheduled_date for value in legacy_dates
        ):
            raise ValueError("scheduled_date conflicts with legacy timestamp")
        return self


class InspectionRead(InspectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int | None
    project_name: str | None
    title: str
    client_name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class InspectionPage(BaseModel):
    items: list[InspectionRead]
    total: int
    skip: int
    limit: int
