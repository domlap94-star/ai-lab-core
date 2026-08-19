from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class MailSendRequest(BaseModel):
    operation_id: UUID
    to: list[str] = Field(default_factory=list, max_length=50)
    cc: list[str] = Field(default_factory=list, max_length=50)
    bcc: list[str] = Field(default_factory=list, max_length=50)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=100_000)
    attachment_document_ids: list[int] = Field(default_factory=list, max_length=10)
    client_id: int | None = Field(default=None, gt=0)

    @field_validator("to", "cc", "bcc")
    @classmethod
    def normalize_addresses(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for raw in values:
            value = raw.strip().lower()
            if not value or len(value) > 254 or value.count("@") != 1:
                raise ValueError("Nieprawidłowy adres email")
            local, domain = value.split("@", 1)
            if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
                raise ValueError("Nieprawidłowy adres email")
            if value not in result:
                result.append(value)
        return result

    @field_validator("attachment_document_ids")
    @classmethod
    def unique_documents(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("Nieprawidłowy dokument")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_recipients(self):
        if not self.to and not self.cc and not self.bcc:
            raise ValueError("Wymagany jest co najmniej jeden odbiorca")
        if len(set(self.to + self.cc + self.bcc)) > 50:
            raise ValueError("Maksymalnie 50 odbiorców")
        return self


class MailReplyRequest(BaseModel):
    operation_id: UUID
    body: str = Field(min_length=1, max_length=100_000)
    attachment_document_ids: list[int] = Field(default_factory=list, max_length=10)


class MailForwardRequest(MailSendRequest):
    client_id: int | None = None


class MailSendResponse(BaseModel):
    operation_id: UUID
    action: Literal["compose", "reply", "forward"]
    status: Literal["pending", "provider_accepted", "canonical_synced", "failed", "unknown"]
    provider_message_id: str | None = None
    provider_thread_id: str | None = None
    canonical_source_id: int | None = None
    replayed: bool = False
    error_code: str | None = None
    provider_accepted_at: datetime | None = None
