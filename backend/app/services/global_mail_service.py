from collections import defaultdict
from datetime import timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.global_mail_repository import GlobalMailRepository
from app.schemas.global_mail import (
    GlobalMailAttachment,
    GlobalMailDetail,
    GlobalMailListItem,
    GlobalMailPage,
    GlobalMailThread,
)
from app.services.client_email_service import ClientEmailService


class GlobalMailNotFoundError(Exception):
    pass


class GlobalMailService:
    def __init__(self, db: Session) -> None:
        self.repository = GlobalMailRepository(db)
        self.client_email = ClientEmailService(db)

    def get_page(self, **filters: Any) -> GlobalMailPage:
        limit = int(filters["limit"])
        rows, has_more = self.repository.get_page(**filters)
        return GlobalMailPage(
            items=[self._list_item(row) for row in rows],
            skip=int(filters["skip"]),
            limit=limit,
            has_more=has_more,
        )

    def get_detail(self, source_id: int) -> GlobalMailDetail:
        row = self.repository.get_one(source_id)
        if row is None:
            raise GlobalMailNotFoundError
        documents = self.repository.get_attachments([row["message_id"]])
        return self._detail(row, documents)

    def get_thread(self, thread_id: str, limit: int = 200) -> GlobalMailThread:
        rows = self.repository.get_thread(thread_id, limit)
        if not rows:
            raise GlobalMailNotFoundError
        documents = self.repository.get_attachments(
            [row["message_id"] for row in rows]
        )
        grouped: dict[str, list[Any]] = defaultdict(list)
        for document in documents:
            grouped[document.gmail_message_id].append(document)
        return GlobalMailThread(
            thread_id=thread_id,
            items=[self._detail(row, grouped[row["message_id"]]) for row in rows],
        )

    def _list_item(self, row: Any) -> GlobalMailListItem:
        payload = row["raw_payload"] if isinstance(row["raw_payload"], dict) else {}
        senders = self.client_email._addresses(payload.get("from") or payload.get("From"))
        recipients = self.client_email._addresses(payload.get("to") or payload.get("To"))
        occurred_at = row["occurred_at"]
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        return GlobalMailListItem(
            source_id=row["source_id"],
            message_id=row["message_id"],
            thread_id=row["thread_id"],
            direction=row["direction"],
            read_state=row["read_state"] or "unknown",
            sender=senders[0][1] if senders else None,
            recipients=[address for _, address in recipients],
            subject=self.client_email._clean_string(payload.get("subject") or payload.get("Subject")),
            occurred_at=occurred_at,
            client_id=row["client_id"],
            client_name=row["client_name"],
            review_state=row["review_state"],
            has_attachments=bool(row["attachment_count"]),
            attachment_count=int(row["attachment_count"]),
        )

    def _detail(self, row: Any, documents: list[Any]) -> GlobalMailDetail:
        item = self._list_item(row)
        payload = row["raw_payload"] if isinstance(row["raw_payload"], dict) else {}
        copies = self.client_email._addresses(payload.get("cc") or payload.get("Cc"))
        return GlobalMailDetail(
            **item.model_dump(),
            cc=[address for _, address in copies],
            body_text=self.client_email._body_text(payload, row["extracted_text"]),
            attachments=[
                GlobalMailAttachment(
                    document_id=document.id,
                    filename=document.original_filename or document.filename or None,
                    mime_type=document.content_type,
                    size=document.file_size,
                    processing_status=document.processing_status,
                )
                for document in documents
            ],
        )
