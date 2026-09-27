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
from app.models.user import User
from app.services.client_scope_service import ClientScopeService


class GlobalMailNotFoundError(Exception):
    pass


class GlobalMailService:
    def __init__(self, db: Session) -> None:
        self.repository = GlobalMailRepository(db)
        self.client_email = ClientEmailService(db)

    def get_page(self, *, viewer: User | None = None, **filters: Any) -> GlobalMailPage:
        if viewer is not None and ClientScopeService.is_external(viewer):
            filters["external_user_id"] = viewer.id
        limit = int(filters["limit"])
        rows, has_more = self.repository.get_page(**filters)
        return GlobalMailPage(
            items=[self._list_item(row) for row in rows],
            skip=int(filters["skip"]),
            limit=limit,
            has_more=has_more,
        )

    def get_detail(self, source_id: int, viewer: User | None = None) -> GlobalMailDetail:
        external_user_id = viewer.id if viewer is not None and ClientScopeService.is_external(viewer) else None
        row = self.repository.get_one(source_id, external_user_id=external_user_id)
        if row is None:
            raise GlobalMailNotFoundError
        documents = self.repository.get_attachments([row["message_id"]])
        payload = row["raw_payload"] if isinstance(row["raw_payload"], dict) else {}
        selected = payload.get("attachment_document_ids")
        if isinstance(selected, list):
            documents = self._unique_documents(documents + self.repository.get_documents_by_ids([value for value in selected if isinstance(value, int)]))
        if viewer is not None and ClientScopeService.is_external(viewer):
            documents = [document for document in documents if document.client_id == row["client_id"]]
        return self._detail(row, documents)

    def get_thread(self, thread_id: str, limit: int = 200, viewer: User | None = None) -> GlobalMailThread:
        external_user_id = viewer.id if viewer is not None and ClientScopeService.is_external(viewer) else None
        rows = self.repository.get_thread(thread_id, limit, external_user_id=external_user_id)
        if not rows:
            raise GlobalMailNotFoundError
        documents = self.repository.get_attachments(
            [row["message_id"] for row in rows]
        )
        grouped: dict[str, list[Any]] = defaultdict(list)
        for document in documents:
            grouped[document.gmail_message_id].append(document)
        if viewer is not None and ClientScopeService.is_external(viewer):
            allowed_by_message = {row["message_id"]: row["client_id"] for row in rows}
            grouped = defaultdict(list, {
                message_id: [document for document in items if document.client_id == allowed_by_message.get(message_id)]
                for message_id, items in grouped.items()
            })
        return GlobalMailThread(
            thread_id=thread_id,
            items=[self._detail(row, grouped[row["message_id"]]) for row in rows],
        )

    @staticmethod
    def _unique_documents(documents: list[Any]) -> list[Any]:
        return list({document.id: document for document in documents}.values())

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
            ignored=bool(row["ignored"]),
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
