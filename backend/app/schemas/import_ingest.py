from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ClientType = Literal[
    "company",
    "person",
    "institution",
    "other",
]

CandidateSourceType = Literal[
    "gmail_message",
    "gmail_thread",
    "google_sheets_row",
]


class CandidateDataInput(BaseModel):
    client_type: ClientType = "other"

    name: str | None = Field(
        default=None,
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

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

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
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value

    @field_validator("primary_email")
    @classmethod
    def normalize_email(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip().lower()

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def require_identifying_data(self) -> "CandidateDataInput":
        identifying_values = (
            self.name,
            self.legal_name,
            self.tax_id,
            self.primary_email,
            self.primary_phone,
            self.website,
        )

        if not any(identifying_values):
            raise ValueError(
                "At least one identifying field is required: "
                "name, legal_name, tax_id, primary_email, "
                "primary_phone or website"
            )

        return self


class CandidateSourceInput(BaseModel):
    source_type: CandidateSourceType

    external_id: str = Field(
        min_length=1,
        max_length=1000,
    )

    external_parent_id: str | None = Field(
        default=None,
        max_length=1000,
    )

    source_label: str | None = Field(
        default=None,
        max_length=500,
    )

    source_url: str | None = Field(
        default=None,
        max_length=2000,
    )

    extracted_text: str | None = None

    raw_payload: dict[str, Any] | None = None

    @field_validator(
        "external_id",
        "external_parent_id",
        "source_label",
        "source_url",
        "extracted_text",
        mode="before",
    )
    @classmethod
    def normalize_strings(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value


class ImportIngestRequest(BaseModel):
    import_source_id: int = Field(
        gt=0,
    )

    import_run_id: int | None = Field(
        default=None,
        gt=0,
    )

    candidate: CandidateDataInput
    source: CandidateSourceInput


class ImportIngestResponse(BaseModel):
    candidate_id: int
    candidate_status: str
    source_id: int

    created_candidate: bool
    created_source: bool

    matched_by: str | None = None
    matched_client_id: int | None = None
    match_confidence: Literal[
        "certain", "high", "ambiguous", "unresolved"
    ] | None = None
    match_reasons: list[str] = Field(default_factory=list, max_length=32)
    candidate_client_ids: list[int] = Field(default_factory=list, max_length=10)


class ImportBatchRequest(BaseModel):
    records: list[ImportIngestRequest] = Field(
        min_length=1,
        max_length=1000,
    )


class ImportBatchItemError(BaseModel):
    index: int
    external_id: str | None = None
    error: str


class ImportBatchResponse(BaseModel):
    received: int
    processed: int
    candidates_created: int
    sources_created: int
    existing_sources: int
    duplicates_detected: int
    failed: int
    results: list[ImportIngestResponse]
    errors: list[ImportBatchItemError]
