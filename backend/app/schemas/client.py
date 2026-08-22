from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.industry import IndustryRead
from app.schemas.client_bulk import ClientWorkflowState

ClientType = Literal[
    "company",
    "person",
    "institution",
    "other",
]

ClientPageSortOrder = Literal["newest", "oldest"]
CLIENT_ADDED_DATE_MIN = date(1900, 1, 1)
CLIENT_BUSINESS_TIMEZONE = ZoneInfo("Europe/Warsaw")


def _validate_client_added_at(value: date | None) -> date | None:
    if value is None:
        return None
    if value < CLIENT_ADDED_DATE_MIN:
        raise ValueError("Client added date must be on or after 1900-01-01")
    if value > datetime.now(CLIENT_BUSINESS_TIMEZONE).date():
        raise ValueError("Client added date cannot be in the future")
    return value


class ClientContactInput(BaseModel):
    value: str = Field(min_length=1, max_length=255)
    is_primary: bool = False

    @field_validator("value", mode="before")
    @classmethod
    def strip_value(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ClientContactRead(ClientContactInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    origin: Literal["manual", "gmail", "sheets", "migration", "other"]
    source_type: str | None = None
    source_id: int | None = None
    contact_person_id: int | None = None


class ContactPersonBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=150)
    is_preferred: bool = False
    is_decision_maker: bool = False
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Contact person display name is required")
        return normalized

    @field_validator("role", "notes", mode="before")
    @classmethod
    def strip_optional_person_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None


class ContactPersonCreate(ContactPersonBase):
    contact_point_ids: list[int] = Field(default_factory=list, max_length=50)
    emails: list[ClientContactInput] = Field(default_factory=list, max_length=20)
    phones: list[ClientContactInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_new_coordinates(self):
        self.emails = _validate_contacts(self.emails, kind="email", ensure_primary=False) or []
        self.phones = _validate_contacts(self.phones, kind="phone", ensure_primary=False) or []
        if len(set(self.contact_point_ids)) != len(self.contact_point_ids):
            raise ValueError("Duplicate contact point ID")
        return self


class ContactPersonUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=150)
    is_preferred: bool | None = None
    is_decision_maker: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)
    contact_point_ids: list[int] | None = Field(default=None, max_length=50)
    emails: list[ClientContactInput] | None = Field(default=None, max_length=20)
    phones: list[ClientContactInput] | None = Field(default=None, max_length=20)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Contact person display name is required")
        return normalized

    @field_validator("role", "notes", mode="before")
    @classmethod
    def strip_optional_person_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_coordinates(self):
        if self.contact_point_ids is not None and len(set(self.contact_point_ids)) != len(self.contact_point_ids):
            raise ValueError("Duplicate contact point ID")
        if self.emails is not None:
            self.emails = _validate_contacts(self.emails, kind="email", ensure_primary=False) or []
        if self.phones is not None:
            self.phones = _validate_contacts(self.phones, kind="phone", ensure_primary=False) or []
        return self


class ContactPersonRead(ContactPersonBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    position: int
    origin: Literal["manual", "gmail", "sheets", "migration", "other"]
    source_type: str | None = None
    source_id: int | None = None
    contact_points: list[ClientContactRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ContactPointPersonAssignment(BaseModel):
    contact_person_id: int | None = Field(default=None, ge=1)


class ClientAddressInput(BaseModel):
    label: str = Field(default="Adres", min_length=1, max_length=100)
    street: str | None = Field(default=None, max_length=255)
    building_number: str | None = Field(default=None, max_length=50)
    unit_number: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=150)
    country_code: str = Field(default="PL", min_length=2, max_length=2)
    is_primary: bool = False

    @field_validator(
        "label", "street", "building_number", "unit_number", "postal_code", "city",
        mode="before",
    )
    @classmethod
    def strip_address_values(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("country_code")
    @classmethod
    def normalize_address_country(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def require_address_content(self):
        if not any((self.street, self.building_number, self.unit_number, self.postal_code, self.city)):
            raise ValueError("Address must contain at least one address field")
        return self


class ClientAddressRead(ClientAddressInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    origin: Literal["manual", "gmail", "sheets", "migration", "other"]
    source_type: str | None = None
    source_id: int | None = None


def _validate_contacts(
    contacts: list[ClientContactInput] | None,
    *,
    kind: str,
    ensure_primary: bool = True,
):
    if contacts is None:
        return None
    seen: set[str] = set()
    primary_count = 0
    for contact in contacts:
        value = contact.value.strip()
        if kind == "email":
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                raise ValueError("Invalid email address")
            key = value.casefold()
        else:
            key = re.sub(r"[^0-9+]", "", value)
            if len(re.sub(r"\D", "", key)) < 6 or not re.fullmatch(r"\+?[0-9]+", key):
                raise ValueError("Invalid phone number")
        if key in seen:
            raise ValueError(f"Duplicate {kind} contact")
        seen.add(key)
        primary_count += int(contact.is_primary)
    if primary_count > 1:
        raise ValueError(f"At most one primary {kind} is allowed")
    if contacts and primary_count == 0 and ensure_primary:
        contacts[0].is_primary = True
    return contacts


def _validate_addresses(addresses: list[ClientAddressInput] | None):
    if addresses is None:
        return None
    seen: set[tuple[str, ...]] = set()
    primary_count = 0
    for address in addresses:
        key = tuple(
            (value or "").casefold().strip()
            for value in (
                address.street,
                address.building_number,
                address.unit_number,
                address.postal_code,
                address.city,
                address.country_code,
            )
        )
        if key in seen:
            raise ValueError("Duplicate client address")
        seen.add(key)
        primary_count += int(address.is_primary)
    if primary_count > 1:
        raise ValueError("At most one primary address is allowed")
    if addresses and primary_count == 0:
        addresses[0].is_primary = True
    return addresses


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
    client_added_at: date | None = None

    @field_validator("client_added_at")
    @classmethod
    def validate_client_added_at(cls, value: date | None) -> date | None:
        return _validate_client_added_at(value)

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
    emails: list[ClientContactInput] | None = None
    phones: list[ClientContactInput] | None = None
    addresses: list[ClientAddressInput] | None = None

    @model_validator(mode="after")
    def validate_contact_lists(self):
        self.emails = _validate_contacts(self.emails, kind="email")
        self.phones = _validate_contacts(self.phones, kind="phone")
        self.addresses = _validate_addresses(self.addresses)
        return self


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
    client_added_at: date | None = None
    emails: list[ClientContactInput] | None = None
    phones: list[ClientContactInput] | None = None
    addresses: list[ClientAddressInput] | None = None

    @field_validator("client_added_at")
    @classmethod
    def validate_client_added_at(cls, value: date | None) -> date | None:
        return _validate_client_added_at(value)

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

    @model_validator(mode="after")
    def validate_contact_lists(self):
        if "emails" in self.model_fields_set:
            self.emails = _validate_contacts(self.emails or [], kind="email")
        if "phones" in self.model_fields_set:
            self.phones = _validate_contacts(self.phones or [], kind="phone")
        if "addresses" in self.model_fields_set:
            self.addresses = _validate_addresses(self.addresses or [])
        return self


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    industry: IndustryRead | None
    source_record_date: date | None = None
    effective_added_date: date
    workflow_status: ClientWorkflowState = "untouched"
    workflow_status_label: str = "Brak modyfikacji"
    workflow_effective_date: date | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    emails: list[ClientContactRead] = Field(default_factory=list)
    phones: list[ClientContactRead] = Field(default_factory=list)
    addresses: list[ClientAddressRead] = Field(default_factory=list)
    contact_persons: list[ContactPersonRead] = Field(
        default_factory=list,
        validation_alias="active_contact_persons",
    )


class ClientPage(BaseModel):
    items: list[ClientRead]
    total: int
    skip: int
    limit: int
