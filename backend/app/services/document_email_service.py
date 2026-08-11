from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser
from html import unescape
from pathlib import Path
from typing import Any

import re


@dataclass(frozen=True)
class EmailDocumentResult:
    status: str

    text: str | None

    raw_metadata: dict[str, Any] | None
    normalized_metadata: dict[str, Any] | None

    attachment_count: int

    error: str | None = None


class DocumentEmailService:
    def extract(
        self,
        *,
        path: Path,
    ) -> EmailDocumentResult:
        if not path.exists():
            return EmailDocumentResult(
                status="failed",
                text=None,
                raw_metadata=None,
                normalized_metadata=None,
                attachment_count=0,
                error=f"File does not exist: {path}",
            )

        try:
            raw_bytes = path.read_bytes()

            message = BytesParser(
                policy=policy.default
            ).parsebytes(
                raw_bytes
            )

            text = self._extract_message_text(
                message
            )

            attachments = (
                self._extract_attachment_metadata(
                    message
                )
            )

            raw_metadata = {
                "from": self._header(
                    message,
                    "From",
                ),
                "to": self._header(
                    message,
                    "To",
                ),
                "cc": self._header(
                    message,
                    "Cc",
                ),
                "bcc": self._header(
                    message,
                    "Bcc",
                ),
                "subject": self._header(
                    message,
                    "Subject",
                ),
                "date": self._header(
                    message,
                    "Date",
                ),
                "message_id": self._header(
                    message,
                    "Message-ID",
                ),
                "in_reply_to": self._header(
                    message,
                    "In-Reply-To",
                ),
                "references": self._header(
                    message,
                    "References",
                ),
                "reply_to": self._header(
                    message,
                    "Reply-To",
                ),
                "return_path": self._header(
                    message,
                    "Return-Path",
                ),
                "mime_version": self._header(
                    message,
                    "MIME-Version",
                ),
                "content_type": (
                    message.get_content_type()
                ),
                "attachment_count": len(
                    attachments
                ),
                "attachments": attachments,
            }

            normalized_metadata = {
                "format": "rfc822",
                "subject": self._header(
                    message,
                    "Subject",
                ),
                "from": self._header(
                    message,
                    "From",
                ),
                "to": self._header(
                    message,
                    "To",
                ),
                "cc": self._header(
                    message,
                    "Cc",
                ),
                "date": self._header(
                    message,
                    "Date",
                ),
                "message_id": self._header(
                    message,
                    "Message-ID",
                ),
                "in_reply_to": self._header(
                    message,
                    "In-Reply-To",
                ),
                "references": self._header(
                    message,
                    "References",
                ),
                "attachment_count": len(
                    attachments
                ),
                "attachment_names": [
                    attachment["filename"]
                    for attachment
                    in attachments
                    if attachment.get(
                        "filename"
                    )
                ],
            }

            return EmailDocumentResult(
                status="processed",
                text=(
                    text
                    if text
                    else None
                ),
                raw_metadata=raw_metadata,
                normalized_metadata=(
                    normalized_metadata
                ),
                attachment_count=len(
                    attachments
                ),
                error=None,
            )

        except Exception as error:
            return EmailDocumentResult(
                status="failed",
                text=None,
                raw_metadata=None,
                normalized_metadata=None,
                attachment_count=0,
                error=str(error),
            )

    def _extract_message_text(
        self,
        message: Message,
    ) -> str:
        plain_parts: list[str] = []
        html_parts: list[str] = []

        if message.is_multipart():
            for part in message.walk():
                if (
                    part.get_content_disposition()
                    == "attachment"
                ):
                    continue

                content_type = (
                    part.get_content_type()
                )

                if content_type == "text/plain":
                    value = self._decode_part(
                        part
                    )

                    if value:
                        plain_parts.append(
                            value
                        )

                elif content_type == "text/html":
                    value = self._decode_part(
                        part
                    )

                    if value:
                        html_parts.append(
                            self._html_to_text(
                                value
                            )
                        )

        else:
            content_type = (
                message.get_content_type()
            )

            value = self._decode_part(
                message
            )

            if content_type == "text/html":
                value = self._html_to_text(
                    value
                )

            if value:
                plain_parts.append(
                    value
                )

        selected_parts = (
            plain_parts
            if plain_parts
            else html_parts
        )

        return self._normalize_text(
            "\n\n".join(
                selected_parts
            )
        )

    def _extract_attachment_metadata(
        self,
        message: Message,
    ) -> list[dict[str, Any]]:
        attachments: list[
            dict[str, Any]
        ] = []

        for part in message.walk():
            disposition = (
                part.get_content_disposition()
            )

            filename = (
                part.get_filename()
            )

            if (
                disposition != "attachment"
                and not filename
            ):
                continue

            payload = part.get_payload(
                decode=True
            )

            attachments.append(
                {
                    "filename": filename,
                    "content_type": (
                        part.get_content_type()
                    ),
                    "content_disposition": (
                        disposition
                    ),
                    "content_id": (
                        part.get(
                            "Content-ID"
                        )
                    ),
                    "size": (
                        len(payload)
                        if payload
                        else 0
                    ),
                }
            )

        return attachments

    @staticmethod
    def _decode_part(
        part: Message,
    ) -> str:
        try:
            content = part.get_content()

            if isinstance(
                content,
                str,
            ):
                return content

        except Exception:
            pass

        try:
            payload = part.get_payload(
                decode=True
            )

            if not payload:
                return ""

            charset = (
                part.get_content_charset()
                or "utf-8"
            )

            return payload.decode(
                charset,
                errors="replace",
            )

        except Exception:
            return ""

    @staticmethod
    def _header(
        message: Message,
        name: str,
    ) -> str | None:
        value = message.get(
            name
        )

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None

    @staticmethod
    def _html_to_text(
        value: str,
    ) -> str:
        value = re.sub(
            r"(?is)<(script|style).*?>.*?</\1>",
            " ",
            value,
        )

        value = re.sub(
            r"(?i)<br\s*/?>",
            "\n",
            value,
        )

        value = re.sub(
            r"(?i)</p>",
            "\n",
            value,
        )

        value = re.sub(
            r"(?s)<[^>]+>",
            " ",
            value,
        )

        return unescape(
            value
        )

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        lines = [
            " ".join(
                line.split()
            ).strip()
            for line
            in value
            .replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
            .split(
                "\n"
            )
        ]

        return "\n".join(
            line
            for line in lines
            if line
        ).strip()