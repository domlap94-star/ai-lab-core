from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProjectStatus = Literal["planned", "active", "completed", "cancelled"]


class ProjectBase(BaseModel):
    client_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus = "planned"
    start_date: date | None = None
    end_date: date | None = None
    street: str | None = Field(default=None, max_length=255)
    building_number: str | None = Field(default=None, max_length=50)
    unit_number: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=150)
    country_code: str = Field(default="PL", min_length=2, max_length=2)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("name", "description", "street", "building_number", "unit_number", "postal_code", "city", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_dates_and_coordinates(self):
        if self.end_date is not None and self.start_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    client_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    street: str | None = Field(default=None, max_length=255)
    building_number: str | None = Field(default=None, max_length=50)
    unit_number: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=150)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProjectPage(BaseModel):
    items: list[ProjectRead]
    total: int
    skip: int
    limit: int
