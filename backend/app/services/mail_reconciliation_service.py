from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import getaddresses
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate_source import CandidateSource
from app.models.document import Document
from app.models.import_source import ImportSource
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
)
from app.schemas.mail_reconciliation import (
    MailReconciliationCandidatePrediction,
    MailReconciliationDryRunResponse,
    MailReconciliationResponse,
)
from app.services.document_service import DocumentService
from app.services.first_party_identity_registry import FirstPartyIdentityRegistry
from app.services.import_ingest_service import (
    EmailCandidateResolutionPreview,
    ImportIngestService,
)
from app.services.mail_reconciliation_provider import N8nMailReconciliationProvider


class MailReconciliationBusyError(Exception):
    pass


class MailReconciliationScopeError(Exception):
    pass


class MailReconciliationValidationError(Exception):
    pass


@dataclass(frozen=True)
class _MessagePlan:
    item: dict[str, Any]
    request: ImportIngestRequest
    resolution: EmailCandidateResolutionPreview
    expected_documents: int

    def token_projection(self) -> dict[str, object]:
        return {
            "provider_message_id": self.request.source.external_id,
            "classification": self.resolution.classification,
            "existing_candidate_id": self.resolution.existing_candidate_id,
            "existing_client_id": self.resolution.existing_client_id,
            "resolved_client_id": self.resolution.resolved_client_id,
            "resolution_confidence": self.resolution.email_match.confidence,
            "resolution_evidence": list(self.resolution.email_match.reasons),
            "candidate_source_delta": 1,
            "candidate_delta": self.resolution.expected_candidate_delta,
            "document_delta": self.expected_documents,
            "new_client_link_delta": (
                self.resolution.expected_new_client_link_delta
            ),
        }


@dataclass(frozen=True)
class _Plan:
    window_days: int
    examined: int
    present: int
    import_source_id: int
    messages: list[_MessagePlan]

    @property
    def ids(self) -> list[str]:
        return [message.request.source.external_id for message in self.messages]

    @property
    def expected_candidates(self) -> int:
        return sum(
            message.resolution.expected_candidate_delta
            for message in self.messages
        )

    @property
    def expected_documents(self) -> int:
        return sum(message.expected_documents for message in self.messages)

    @property
    def expected_client_links(self) -> int:
        return sum(
            message.resolution.expected_new_client_link_delta
            for message in self.messages
        )


_RECONCILIATION_LOCK = threading.Lock()


class MailReconciliationService:
    MAX_PROVIDER_MESSAGES = 1000
    MAX_MISSING_MESSAGES = 100
    MAX_ATTACHMENTS_PER_MESSAGE = 20
    MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
    TOKEN_TTL_SECONDS = 600

    def __init__(self, db: Session, provider: Any | None = None) -> None:
        self.db = db
        self.provider = provider or N8nMailReconciliationProvider()

    def dry_run(
        self, *, window_days: int, actor_user_id: int
    ) -> MailReconciliationDryRunResponse:
        with self._claim():
            started = datetime.now(timezone.utc)
            plan = self._plan(window_days)
            return MailReconciliationDryRunResponse(
                window_days=window_days,
                messages_examined=plan.examined,
                already_present=plan.present,
                missing_count=len(plan.ids),
                missing_provider_ids=plan.ids,
                expected_candidate_sources=len(plan.ids),
                expected_candidates=plan.expected_candidates,
                expected_documents=plan.expected_documents,
                expected_client_links=plan.expected_client_links,
                candidate_resolutions=[
                    MailReconciliationCandidatePrediction(
                        provider_message_id=message.request.source.external_id,
                        classification=message.resolution.classification,
                        existing_candidate_id=(
                            message.resolution.existing_candidate_id
                        ),
                        existing_client_id=(
                            message.resolution.existing_client_id
                        ),
                        resolved_client_id=(
                            message.resolution.resolved_client_id
                        ),
                        resolution_confidence=(
                            message.resolution.email_match.confidence
                        ),
                        resolution_evidence=list(
                            message.resolution.email_match.reasons
                        ),
                        expected_candidate_delta=(
                            message.resolution.expected_candidate_delta
                        ),
                        expected_document_delta=message.expected_documents,
                        expected_new_client_link_delta=(
                            message.resolution.expected_new_client_link_delta
                        ),
                    )
                    for message in plan.messages
                ],
                dry_run_token=self._token(plan, actor_user_id),
                started_at=started,
                completed_at=datetime.now(timezone.utc),
            )

    def apply(
        self,
        *,
        window_days: int,
        actor_user_id: int,
        dry_run_token: str,
    ) -> MailReconciliationResponse:
        with self._claim():
            started = datetime.now(timezone.utc)
            plan = self._plan(window_days)
            if not self._valid_token(plan, actor_user_id, dry_run_token):
                raise MailReconciliationValidationError(
                    "reconciliation_plan_drift"
                )
            created = linked = review = attachments = failed = 0
            ingest_service = ImportIngestService(self.db)
            for message in plan.messages:
                try:
                    result = ingest_service.ingest(
                        message.request,
                        email_resolution=message.resolution,
                    )
                    if result.created_source:
                        created += 1
                        linked += (
                            message.resolution.expected_new_client_link_delta
                        )
                        review += int(result.created_candidate and result.matched_client_id is None)
                    attachments += self._ingest_attachments(
                        message.item,
                        result.candidate_id,
                        result.matched_client_id,
                    )
                    self._mark_complete(result.source_id)
                except Exception:
                    self.db.rollback()
                    failed += 1
            return MailReconciliationResponse(
                status="complete" if failed == 0 else "partial",
                messages_examined=plan.examined,
                already_present=plan.present,
                new_messages_ingested=created,
                new_client_linked=linked,
                new_review_candidates=review,
                attachments_created=attachments,
                failed=failed,
                started_at=started,
                completed_at=datetime.now(timezone.utc),
            )

    def _plan(self, window_days: int) -> _Plan:
        if not 1 <= window_days <= 30:
            raise MailReconciliationValidationError("window_days_out_of_range")
        audit = self.provider.audit(window_days=window_days, limit=self.MAX_PROVIDER_MESSAGES)
        if audit.truncated or len(audit.message_ids) > self.MAX_PROVIDER_MESSAGES:
            raise MailReconciliationScopeError("provider_window_truncated")
        rows = (
            self.db.query(
                CandidateSource.external_id,
                CandidateSource.raw_payload,
            )
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                CandidateSource.external_id.in_(audit.message_ids),
            )
            .all()
        )
        present = {
            external_id for external_id, payload in rows
            if not self._reconciliation_incomplete(payload)
        }
        missing = [value for value in audit.message_ids if value not in present]
        if len(missing) > self.MAX_MISSING_MESSAGES:
            raise MailReconciliationScopeError("missing_set_too_large")
        messages = self.provider.fetch(missing) if missing else []
        messages = self._validate_provider_messages(missing, messages)
        source = self.db.query(ImportSource).filter(
            ImportSource.source_type == "gmail",
            ImportSource.deleted_at.is_(None),
        ).order_by(ImportSource.id).first()
        if source is None:
            raise MailReconciliationValidationError(
                "gmail_import_source_missing"
            )
        ingest_service = ImportIngestService(self.db)
        planned: list[_MessagePlan] = []
        for item in messages:
            request = self._request(item, import_source_id=source.id)
            if request is None:
                continue
            resolution = self._candidate_resolution(
                ingest_service,
                request,
            )
            planned.append(
                _MessagePlan(
                    item=item,
                    request=resolution.request,
                    resolution=resolution,
                    expected_documents=self._expected_documents([item]),
                )
            )
        return _Plan(
            window_days=window_days,
            examined=len(audit.message_ids),
            present=len(present),
            import_source_id=source.id,
            messages=planned,
        )

    @staticmethod
    def _candidate_resolution(
        ingest_service: ImportIngestService,
        request: ImportIngestRequest,
    ) -> EmailCandidateResolutionPreview:
        return ingest_service.preview_email_resolution(request)

    class _LockContext:
        def __enter__(self) -> None:
            if not _RECONCILIATION_LOCK.acquire(blocking=False):
                raise MailReconciliationBusyError

        def __exit__(self, *_: object) -> None:
            _RECONCILIATION_LOCK.release()

    @classmethod
    def _claim(cls) -> "MailReconciliationService._LockContext":
        return cls._LockContext()

    def _token(self, plan: _Plan, actor_user_id: int, issued_at: int | None = None) -> str:
        timestamp = issued_at if issued_at is not None else int(time.time())
        material = self._token_material(plan, actor_user_id, timestamp)
        digest = hmac.new(settings.secret_key.encode(), material, hashlib.sha256).hexdigest()
        return f"{timestamp}.{digest}"

    def _valid_token(self, plan: _Plan, actor_user_id: int, token: str) -> bool:
        try:
            timestamp = int(token.split(".", 1)[0])
        except (ValueError, TypeError):
            return False
        now = int(time.time())
        if timestamp > now + 30 or now - timestamp > self.TOKEN_TTL_SECONDS:
            return False
        return hmac.compare_digest(token, self._token(plan, actor_user_id, timestamp))

    @staticmethod
    def _token_material(plan: _Plan, actor_user_id: int, timestamp: int) -> bytes:
        material = {
            "actor_user_id": actor_user_id,
            "window_days": plan.window_days,
            "issued_at": timestamp,
            "messages": [
                message.token_projection() for message in plan.messages
            ],
            "expected_candidate_sources": len(plan.messages),
            "expected_candidates": plan.expected_candidates,
            "expected_documents": plan.expected_documents,
            "expected_new_client_links": plan.expected_client_links,
        }
        return json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def _expected_documents(self, messages: list[dict[str, Any]]) -> int:
        external_ids = [
            self._attachment_external_id(item, attachment, index)
            for item in messages
            for index, attachment in enumerate(item.get("attachments") or [])
            if isinstance(attachment, dict)
        ]
        existing = {
            value for (value,) in self.db.query(Document.external_id).filter(
                Document.source_type == "gmail_attachment",
                Document.external_id.in_(external_ids),
            ).all()
        }
        return sum(value not in existing for value in external_ids)

    @staticmethod
    def _validate_provider_messages(
        missing_ids: list[str], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        expected = set(missing_ids)
        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for item in messages:
            message_id = str(item.get("id") or "").strip()
            if not message_id or message_id not in expected or message_id in seen:
                raise MailReconciliationValidationError("provider_message_set_mismatch")
            seen.add(message_id)
            normalized.append(item)
        if seen != expected:
            raise MailReconciliationValidationError("provider_message_set_incomplete")
        return normalized

    def _request(
        self,
        item: dict[str, Any],
        *,
        import_source_id: int,
    ) -> ImportIngestRequest | None:
        contact, direction = self._contact(item)
        if contact is None:
            return None
        email, name = contact
        subject = self._text(item.get("subject") or item.get("Subject"), 500)
        if self._ignored_subject(subject):
            return None
        body = self._text(
            item.get("text") or item.get("textPlain") or item.get("snippet"),
            10_000,
        )
        message_id = str(item["id"])
        raw = dict(item)
        raw.pop("attachments", None)
        raw["direction"] = direction
        raw["_ai_lab_reconciliation"] = {"version": 1, "complete": False}
        return ImportIngestRequest(
            import_source_id=import_source_id,
            candidate=CandidateDataInput(
                client_type="person", name=(name or email)[:255],
                primary_email=email, country_code="PL", confidence=0.85,
            ),
            source=CandidateSourceInput(
                source_type="gmail_message", external_id=message_id,
                external_parent_id=self._text(
                    item.get("threadId") or item.get("thread_id"), 1000
                ),
                source_label=subject or f"Wiadomość Gmail {message_id}",
                extracted_text=body, raw_payload=raw,
            ),
        )

    def _contact(self, item: dict[str, Any]) -> tuple[tuple[str, str | None] | None, str]:
        labels = item.get("labelIds") or item.get("labels") or []
        sent = isinstance(labels, list) and any(
            str(value if isinstance(value, str) else value.get("id") or value.get("name") or "").upper() == "SENT"
            for value in labels
        )
        preferred = self._addresses(
            item.get("to") or item.get("To")
        ) if sent else self._addresses(item.get("from") or item.get("From"))
        # Match the canonical scheduled Gmail transform exactly: SENT uses
        # external TO recipients, received mail uses external FROM senders.
        # Falling back to the opposite side can manufacture a false contact.
        for email, name in preferred:
            if not FirstPartyIdentityRegistry.is_first_party_email(email) and not self._ignored(email):
                return (email, name), "outgoing" if sent else "incoming"
        return None, "outgoing" if sent else "incoming"

    @staticmethod
    def _addresses(value: Any) -> list[tuple[str, str | None]]:
        if isinstance(value, dict) and isinstance(value.get("value"), list):
            return [
                (str(row.get("address") or "").strip().lower(), str(row.get("name") or "").strip() or None)
                for row in value["value"] if isinstance(row, dict) and "@" in str(row.get("address") or "")
            ]
        parts = (
            [
                str(row.get("address") if isinstance(row, dict) else row or "")
                for row in value
            ]
            if isinstance(value, list)
            else [str(value or "")]
        )
        return [(address.lower(), name or None) for name, address in getaddresses(parts) if "@" in address]

    @staticmethod
    def _ignored(email: str) -> bool:
        local, _, domain = email.partition("@")
        return domain in {
            "google.com", "accounts.google.com", "mail.google.com", "notifications.google.com", "youtube.com", "youtube-nocookie.com",
        } or local in {"no-reply", "noreply", "do-not-reply", "donotreply", "mailer-daemon", "postmaster"}

    @staticmethod
    def _ignored_subject(subject: str | None) -> bool:
        normalized = (subject or "").casefold()
        return any(value in normalized for value in (
            "delivery status notification", "undelivered mail returned", "mail delivery failed",
            "security alert", "alert zabezpieczeń", "kod weryfikacyjny google", "google verification code",
        ))

    @staticmethod
    def _reconciliation_incomplete(payload: Any) -> bool:
        marker = payload.get("_ai_lab_reconciliation") if isinstance(payload, dict) else None
        return isinstance(marker, dict) and marker.get("complete") is False

    @staticmethod
    def _text(value: Any, limit: int) -> str | None:
        if value is None:
            return None
        text = re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()
        return text[:limit] or None

    def _attachment_external_id(
        self, item: dict[str, Any], attachment: dict[str, Any], index: int
    ) -> str:
        filename = (
            self._text(attachment.get("filename"), 255)
            or f"attachment-{index + 1}.bin"
        )
        return (
            self._text(attachment.get("external_id"), 1000)
            or f"{item['id']}|{filename}"
        )

    def _ingest_attachments(self, item: dict[str, Any], candidate_id: int, client_id: int | None) -> int:
        values = item.get("attachments") or []
        if not isinstance(values, list) or len(values) > self.MAX_ATTACHMENTS_PER_MESSAGE:
            raise MailReconciliationValidationError("attachment_count_invalid")
        decoded: list[tuple[dict[str, Any], bytes]] = []
        total = 0
        for attachment in values:
            if not isinstance(attachment, dict):
                raise MailReconciliationValidationError("attachment_invalid")
            try:
                content = base64.b64decode(str(attachment.get("content_base64") or ""), validate=True)
            except (ValueError, TypeError) as error:
                raise MailReconciliationValidationError("attachment_invalid") from error
            total += len(content)
            if total > self.MAX_ATTACHMENT_BYTES:
                raise MailReconciliationValidationError("attachments_too_large")
            decoded.append((attachment, content))
        created = 0
        for index, (attachment, content) in enumerate(decoded):
            filename = (
                self._text(attachment.get("filename"), 255)
                or f"attachment-{index + 1}.bin"
            )
            result = DocumentService(self.db).store_document(
                content=content,
                original_filename=filename,
                content_type=(
                    self._text(attachment.get("mime_type"), 255)
                    or "application/octet-stream"
                ),
                source_type="gmail_attachment",
                external_id=self._attachment_external_id(item, attachment, index),
                gmail_message_id=str(item["id"]),
                gmail_thread_id=self._text(
                    item.get("threadId") or item.get("thread_id"), 1000
                ),
                candidate_id=candidate_id,
                client_id=client_id,
            )
            created += int(result.created)
        return created

    def _mark_complete(self, source_id: int) -> None:
        source = self.db.query(CandidateSource).filter(CandidateSource.id == source_id).one()
        payload = dict(source.raw_payload or {})
        payload["_ai_lab_reconciliation"] = {"version": 1, "complete": True}
        source.raw_payload = payload
        self.db.commit()
