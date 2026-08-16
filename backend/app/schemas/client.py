from datetime import date, datetime
from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.industry import IndustryRead

ClientType = Literal[
    "company",
    "person",
    "institution",
    "other",
]

ClientPageSortOrder = Literal["newest", "oldest"]


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


def _validate_contacts(contacts: list[ClientContactInput] | None, *, kind: str):
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
    if contacts and primary_count == 0:
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
    emails: list[ClientContactInput] | None = None
    phones: list[ClientContactInput] | None = None
    addresses: list[ClientAddressInput] | None = None

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
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    emails: list[ClientContactRead] = Field(default_factory=list)
    phones: list[ClientContactRead] = Field(default_factory=list)
    addresses: list[ClientAddressRead] = Field(default_factory=list)


class ClientPage(BaseModel):
    items: list[ClientRead]
    total: int
    skip: int
    limit: int
