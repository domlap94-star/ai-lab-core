from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MailDirection = Literal["received", "sent", "unknown"]
MailReadState = Literal["read", "unread", "unknown"]


class GlobalMailAttachment(BaseModel):
    document_id: int
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    processing_status: str


class GlobalMailListItem(BaseModel):
    source_id: int
    message_id: str
    thread_id: str | None = None
    direction: MailDirection
    read_state: MailReadState
    sender: str | None = None
    recipients: list[str] = Field(default_factory=list)
    subject: str | None = None
    occurred_at: datetime
    client_id: int | None = None
    client_name: str | None = None
    review_state: str | None = None
    has_attachments: bool
    attachment_count: int


class GlobalMailPage(BaseModel):
    items: list[GlobalMailListItem]
    skip: int
    limit: int
    has_more: bool


class GlobalMailDetail(GlobalMailListItem):
    cc: list[str] = Field(default_factory=list)
    body_text: str | None = None
    attachments: list[GlobalMailAttachment] = Field(default_factory=list)


class GlobalMailThread(BaseModel):
    thread_id: str
    items: list[GlobalMailDetail]
