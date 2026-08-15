from __future__ import annotations

import html
import re
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import getaddresses
from html.parser import HTMLParser
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.client_email_repository import ClientEmailRepository
from app.repositories.client_repository import ClientRepository
from app.schemas.client_email import (
    ClientEmailAttachmentRead,
    ClientEmailPage,
    ClientEmailRead,
    EmailDirection,
)
from app.services.client_service import ClientNotFoundError
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


MAX_BODY_CHARACTERS = 100_000


class _SafeHtmlTextExtractor(HTMLParser):
    BLOCK_TAGS = frozenset(
        {
            "br",
            "div",
            "p",
            "li",
            "tr",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        del attrs
        if tag in {"script", "style"}:
            self.ignored_depth += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if not self.ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


class ClientEmailService:
    def __init__(self, db: Session) -> None:
        self.client_repository = ClientRepository(db)
        self.email_repository = ClientEmailRepository(db)
        self.boundary = GmailMessageBoundaryService()

    def get_emails(
        self,
        *,
        client_id: int,
        skip: int,
        limit: int,
    ) -> ClientEmailPage:
        if self.client_repository.get(client_id) is None:
            raise ClientNotFoundError

        rows, total = self.email_repository.get_page(
            client_id=client_id,
            skip=skip,
            limit=limit,
        )
        message_ids = [row.external_id for row in rows]
        attachments_by_message: dict[str, list[Any]] = defaultdict(list)
        for document in self.email_repository.get_attachments(message_ids):
            attachments_by_message[document.gmail_message_id].append(document)

        items = [
            self._to_public_email(
                row,
                attachments_by_message.get(row.external_id, []),
            )
            for row in rows
        ]
        return ClientEmailPage(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    def _to_public_email(
        self,
        row: Any,
        documents: list[Any],
    ) -> ClientEmailRead:
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        sender = self._addresses(payload.get("from") or payload.get("From"))
        recipients = self._addresses(payload.get("to") or payload.get("To"))
        copies = self._addresses(payload.get("cc") or payload.get("Cc"))
        attachment_models = [
            ClientEmailAttachmentRead(
                document_id=document.id,
                original_filename=(
                    document.original_filename or document.filename or None
                ),
                content_type=document.content_type,
                file_size=document.file_size,
            )
            for document in documents
        ]

        return ClientEmailRead(
            id=row.source_id,
            external_id=row.external_id,
            message_id=row.external_id,
            thread_id=(
                self._clean_string(payload.get("threadId"))
                or row.external_parent_id
            ),
            direction=self._direction(payload),
            message_at=(
                row.message_at or self._parse_message_at(payload)
            ),
            from_name=sender[0][0] if sender else None,
            from_address=sender[0][1] if sender else None,
            to_addresses=[address for _, address in recipients],
            cc_addresses=[address for _, address in copies],
            subject=self._clean_string(
                payload.get("subject") or payload.get("Subject")
            ),
            body_text=self._body_text(payload, row.extracted_text),
            source_url=self._safe_source_url(row.source_url),
            attachment_count=len(attachment_models),
            attachments=attachment_models,
            created_at=row.created_at,
        )

    @classmethod
    def _addresses(cls, value: Any) -> list[tuple[str | None, str]]:
        candidates: list[tuple[str, str]] = []
        if isinstance(value, dict):
            entries = value.get("value")
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    candidates.append(
                        (
                            str(entry.get("name") or ""),
                            str(entry.get("address") or ""),
                        )
                    )
            elif value.get("text"):
                candidates.extend(getaddresses([str(value["text"])]))
        elif isinstance(value, list):
            for entry in value:
                candidates.extend(cls._addresses(entry))
        elif value:
            candidates.extend(getaddresses([str(value)]))

        result: list[tuple[str | None, str]] = []
        seen: set[str] = set()
        for raw_name, raw_address in candidates:
            address = raw_address.strip().casefold()
            if not address or "@" not in address or address in seen:
                continue
            seen.add(address)
            result.append((cls._clean_string(raw_name), address))
        return result

    @staticmethod
    def _labels(payload: dict[str, Any]) -> set[str]:
        result: set[str] = set()
        raw_labels = payload.get("labelIds") or payload.get("labels") or []
        if not isinstance(raw_labels, list):
            return result
        for label in raw_labels:
            if isinstance(label, str):
                value = label
            elif isinstance(label, dict):
                value = label.get("id") or label.get("name") or ""
            else:
                value = ""
            if value:
                result.add(str(value).strip().upper())
        return result

    @classmethod
    def _direction(cls, payload: dict[str, Any]) -> EmailDirection:
        explicit = str(payload.get("direction") or "").strip().casefold()
        if explicit in {"sent", "outgoing", "wyslana", "wysłana"}:
            return "sent"
        if explicit in {"received", "incoming", "odebrana"}:
            return "received"

        labels = cls._labels(payload)
        if "SENT" in labels:
            return "sent"
        if "INBOX" in labels:
            return "received"
        return "unknown"

    def _body_text(
        self,
        payload: dict[str, Any],
        extracted_text: str | None,
    ) -> str | None:
        text = self._first_text(payload, ("text", "textPlain"))
        if text is None:
            html_body = self._first_text(payload, ("html", "textAsHtml"))
            if html_body is not None:
                text = self._html_to_text(html_body)
        if text is None:
            text = self._first_text(payload, ("snippet",))
        if text is None:
            text = extracted_text
        if not text:
            return None

        current = self.boundary.parse(self._normalize_text(text)).current_content
        normalized = self._normalize_text(current)
        if not normalized:
            return None
        return normalized[:MAX_BODY_CHARACTERS]

    @staticmethod
    def _first_text(
        payload: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _html_to_text(value: str) -> str:
        parser = _SafeHtmlTextExtractor()
        parser.feed(value)
        parser.close()
        return parser.text()

    @staticmethod
    def _normalize_text(value: str) -> str:
        text = html.unescape(str(value)).replace("\xa0", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        if value is None:
            return None
        normalized = html.unescape(str(value)).replace("\xa0", " ").strip()
        return normalized or None

    @staticmethod
    def _parse_message_at(payload: dict[str, Any]) -> datetime | None:
        value = payload.get("date")
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        internal = payload.get("internalDate")
        if internal is None:
            return None
        try:
            return datetime.fromtimestamp(int(str(internal)) / 1000, timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _safe_source_url(value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip()
        if normalized.startswith(("https://", "http://")):
            return normalized
        return None
