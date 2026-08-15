from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


EmailDirection = Literal["sent", "received", "unknown"]


class ClientEmailAttachmentRead(BaseModel):
    document_id: int
    original_filename: str | None
    content_type: str
    file_size: int


class ClientEmailRead(BaseModel):
    id: int
    external_id: str
    message_id: str
    thread_id: str | None
    direction: EmailDirection
    message_at: datetime | None
    from_name: str | None
    from_address: str | None
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str | None
    body_text: str | None
    source_url: str | None
    attachment_count: int
    attachments: list[ClientEmailAttachmentRead]
    created_at: datetime


class ClientEmailPage(BaseModel):
    items: list[ClientEmailRead]
    total: int
    skip: int
    limit: int
