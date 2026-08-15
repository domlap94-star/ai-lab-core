from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.industry import IndustryRead

ClientType = Literal[
    "company",
    "person",
    "institution",
    "other",
]


class ClientBase(BaseModel):
    client_type: ClientType
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    legal_name: str | None = Field(
        default=None,
        max_length=255,
    )
    tax_id: str | None = Field(
        default=None,
        max_length=32,
    )
    registration_number: str | None = Field(
        default=None,
        max_length=64,
    )
    industry_id: int | None = None
    website: str | None = Field(
        default=None,
        max_length=500,
    )
    primary_email: str | None = Field(
        default=None,
        max_length=255,
    )
    primary_phone: str | None = Field(
        default=None,
        max_length=50,
    )
    street: str | None = Field(
        default=None,
        max_length=255,
    )
    building_number: str | None = Field(
        default=None,
        max_length=50,
    )
    unit_number: str | None = Field(
        default=None,
        max_length=50,
    )
    postal_code: str | None = Field(
        default=None,
        max_length=20,
    )
    city: str | None = Field(
        default=None,
        max_length=150,
    )
    country_code: str = Field(
        default="PL",
        min_length=2,
        max_length=2,
    )
    notes: str | None = None

    @field_validator(
        "name",
        "legal_name",
        "tax_id",
        "registration_number",
        "website",
        "primary_email",
        "primary_phone",
        "street",
        "building_number",
        "unit_number",
        "postal_code",
        "city",
        mode="before",
    )
    @classmethod
    def strip_string_values(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None

        return value

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str | None,
    ) -> str:
        if not value:
            raise ValueError("Client name must not be empty")

        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    client_type: ClientType | None = None
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    legal_name: str | None = Field(
        default=None,
        max_length=255,
    )
    tax_id: str | None = Field(
        default=None,
        max_length=32,
    )
    registration_number: str | None = Field(
        default=None,
        max_length=64,
    )
    industry_id: int | None = None
    website: str | None = Field(
        default=None,
        max_length=500,
    )
    primary_email: str | None = Field(
        default=None,
        max_length=255,
    )
    primary_phone: str | None = Field(
        default=None,
        max_length=50,
    )
    street: str | None = Field(
        default=None,
        max_length=255,
    )
    building_number: str | None = Field(
        default=None,
        max_length=50,
    )
    unit_number: str | None = Field(
        default=None,
        max_length=50,
    )
    postal_code: str | None = Field(
        default=None,
        max_length=20,
    )
    city: str | None = Field(
        default=None,
        max_length=150,
    )
    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
    )
    notes: str | None = None

    @field_validator(
        "name",
        "legal_name",
        "tax_id",
        "registration_number",
        "website",
        "primary_email",
        "primary_phone",
        "street",
        "building_number",
        "unit_number",
        "postal_code",
        "city",
        mode="before",
    )
    @classmethod
    def strip_string_values(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None

        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip().upper()


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    industry: IndustryRead | None
    source_record_date: date | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ClientPage(BaseModel):
    items: list[ClientRead]
    total: int
    skip: int
    limit: int
