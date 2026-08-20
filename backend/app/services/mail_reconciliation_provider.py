from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class MailReconciliationProviderError(Exception):
    pass


@dataclass(frozen=True)
class ReconciliationAudit:
    message_ids: list[str]
    truncated: bool


class N8nMailReconciliationProvider:
    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not (
            settings.mail_reconcile_webhook_url
            and settings.mail_reconcile_webhook_secret
        ):
            raise MailReconciliationProviderError("provider_not_configured")
        try:
            response = httpx.post(
                settings.mail_reconcile_webhook_url,
                json=payload,
                headers={
                    "X-AI-Lab-Mail-Reconcile-Secret": (
                        settings.mail_reconcile_webhook_secret
                    ),
                },
                timeout=settings.mail_reconcile_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise MailReconciliationProviderError("provider_unavailable") from error
        if not isinstance(data, dict):
            raise MailReconciliationProviderError("provider_invalid_response")
        return data

    def audit(self, *, window_days: int, limit: int) -> ReconciliationAudit:
        data = self._call(
            {"action": "audit", "window_days": window_days, "limit": limit}
        )
        values = data.get("message_ids")
        if not isinstance(values, list):
            raise MailReconciliationProviderError("provider_invalid_response")
        message_ids = [str(value).strip() for value in values if str(value).strip()]
        unique_ids = list(dict.fromkeys(message_ids))
        return ReconciliationAudit(
            message_ids=unique_ids[: limit + 1],
            truncated=bool(data.get("truncated")) or len(unique_ids) > limit,
        )

    def fetch(self, message_ids: list[str]) -> list[dict[str, Any]]:
        data = self._call(
            {"action": "fetch", "provider_message_ids": message_ids}
        )
        messages = data.get("messages")
        if not isinstance(messages, list):
            raise MailReconciliationProviderError("provider_invalid_response")
        return [item for item in messages if isinstance(item, dict)]
