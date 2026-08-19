from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class MailProviderDefinitiveError(Exception):
    def __init__(self, code: str): self.code = code


class MailProviderUnknownError(Exception):
    pass


@dataclass(frozen=True)
class MailProviderResult:
    message_id: str
    thread_id: str | None
    execution_ref: str | None


class N8nMailProviderAdapter:
    def send(self, payload: dict[str, Any]) -> MailProviderResult:
        if not settings.mail_send_webhook_url or not settings.mail_send_webhook_secret:
            raise MailProviderDefinitiveError("provider_not_configured")
        try:
            response = httpx.post(
                settings.mail_send_webhook_url,
                json=payload,
                headers={"X-AI-Lab-Mail-Secret": settings.mail_send_webhook_secret},
                timeout=settings.mail_send_timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise MailProviderUnknownError from exc
        if 400 <= response.status_code < 500:
            raise MailProviderDefinitiveError("provider_rejected")
        if response.status_code >= 500:
            raise MailProviderUnknownError
        data = response.json()
        if data.get("accepted") is not True or not data.get("provider_message_id"):
            raise MailProviderUnknownError
        return MailProviderResult(
            message_id=str(data["provider_message_id"]),
            thread_id=str(data["provider_thread_id"]) if data.get("provider_thread_id") else None,
            execution_ref=str(data["provider_execution_ref"])[:255] if data.get("provider_execution_ref") else None,
        )
