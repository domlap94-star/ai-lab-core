from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.document import Document
from app.models.import_source import ImportSource
from app.models.client_candidate import ClientCandidate
from app.models.mail_send_operation import MailSendOperation
from app.models.user import User
from app.schemas.import_ingest import CandidateDataInput, CandidateSourceInput, ImportIngestRequest
from app.schemas.mail_send import MailForwardRequest, MailReplyRequest, MailSendRequest, MailSendResponse
from app.services.document_service import resolve_document_storage_path
from app.services.import_ingest_service import ImportIngestService
from app.services.mail_provider_adapter import (
    MailProviderDefinitiveError,
    MailProviderUnknownError,
    N8nMailProviderAdapter,
)


MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("application/", "image/", "text/")


class MailSendConflictError(Exception): pass
class MailSendNotFoundError(Exception): pass
class MailSendValidationError(Exception): pass


class MailSendService:
    def __init__(self, db: Session, provider: Any | None = None) -> None:
        self.db = db
        self.provider = provider or N8nMailProviderAdapter()

    def compose(self, actor: User, request: MailSendRequest) -> MailSendResponse:
        return self._execute("compose", actor, request)

    def reply(self, source_id: int, actor: User, request: MailReplyRequest) -> MailSendResponse:
        source = self._source(source_id)
        payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
        sender = self._address(payload.get("replyTo") or payload.get("from") or payload.get("From"))
        if not sender:
            raise MailSendValidationError("reply_recipient_missing")
        composed = MailSendRequest(
            operation_id=request.operation_id,
            to=[sender],
            subject=self._prefixed("Re:", str(payload.get("subject") or payload.get("Subject") or "(bez tematu)")),
            body=request.body,
            attachment_document_ids=request.attachment_document_ids,
            client_id=self._client_id(source),
        )
        return self._execute("reply", actor, composed, source=source)

    def forward(self, source_id: int, actor: User, request: MailForwardRequest) -> MailSendResponse:
        source = self._source(source_id)
        payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
        composed = request.model_copy(update={
            "subject": self._prefixed("Fwd:", request.subject or str(payload.get("subject") or "(bez tematu)")),
        })
        return self._execute("forward", actor, composed, source=source)

    def _execute(self, action: str, actor: User, request: MailSendRequest, *, source: CandidateSource | None = None) -> MailSendResponse:
        documents, encoded = self._attachments(request.attachment_document_ids, request.client_id)
        digest = self._payload_hash(action, request, source.id if source else None)
        operation, replayed, claimed = self._claim(
            action=action, actor=actor, request=request, source=source,
            digest=digest, attachment_count=len(documents),
        )
        if replayed or not claimed:
            if operation.payload_sha256 != digest:
                raise MailSendConflictError("operation_payload_conflict")
            if operation.status == "provider_accepted":
                return self._resume_ingest(operation, request, documents)
            return self._response(operation, replayed=True)

        provider_payload = {
            "operation_id": str(request.operation_id), "action": action,
            "to": request.to, "cc": request.cc, "bcc": request.bcc,
            "subject": request.subject, "body": request.body,
            "source_provider_message_id": source.external_id if source else None,
            "source_provider_thread_id": source.external_parent_id if source else None,
            "attachments": encoded,
        }
        try:
            operation.attempt_count = 1
            result = self.provider.send(provider_payload)
        except MailProviderDefinitiveError as exc:
            operation.status = "failed"; operation.error_code = exc.code[:64]
            self.db.commit()
            return self._response(operation)
        except MailProviderUnknownError:
            operation.status = "unknown"; operation.error_code = "provider_outcome_unknown"
            self.db.commit()
            return self._response(operation)

        operation.status = "provider_accepted"
        operation.provider_message_id = result.message_id
        operation.provider_thread_id = result.thread_id
        operation.provider_execution_ref = result.execution_ref
        operation.provider_accepted_at = datetime.now(timezone.utc)
        operation.error_code = None
        self.db.commit()
        return self._resume_ingest(operation, request, documents)

    def _claim(self, *, action: str, actor: User, request: MailSendRequest, source: CandidateSource | None, digest: str, attachment_count: int):
        existing = self.db.query(MailSendOperation).filter(MailSendOperation.operation_id == request.operation_id).one_or_none()
        if existing:
            return existing, True, False
        operation = MailSendOperation(
            operation_id=request.operation_id, actor_user_id=actor.id, action=action,
            payload_sha256=digest, status="pending", source_message_id=source.id if source else None,
            client_id=request.client_id, recipient_count=len(set(request.to + request.cc + request.bcc)),
            attachment_count=attachment_count, attempt_count=0,
        )
        self.db.add(operation)
        try:
            self.db.commit(); self.db.refresh(operation)
            return operation, False, True
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(MailSendOperation).filter(MailSendOperation.operation_id == request.operation_id).one()
            return existing, True, False

    def _resume_ingest(self, operation: MailSendOperation, request: MailSendRequest, documents: list[Document]) -> MailSendResponse:
        if operation.canonical_source_id:
            operation.status = "canonical_synced"; self.db.commit()
            return self._response(operation, replayed=True)
        try:
            source_id = self._canonical_ingest(operation, request, documents)
        except Exception:
            self.db.rollback()
            return self._response(operation)
        operation = self.db.query(MailSendOperation).filter(MailSendOperation.id == operation.id).one()
        operation.canonical_source_id = source_id; operation.status = "canonical_synced"
        self.db.commit()
        return self._response(operation)

    def _canonical_ingest(self, operation: MailSendOperation, request: MailSendRequest, documents: list[Document]) -> int:
        import_source = self.db.query(ImportSource).filter(ImportSource.source_type == "gmail", ImportSource.deleted_at.is_(None)).order_by(ImportSource.id).first()
        if import_source is None:
            raise MailSendValidationError("gmail_import_source_missing")
        client = self.db.query(Client).filter(Client.id == request.client_id, Client.deleted_at.is_(None)).one_or_none() if request.client_id else None
        primary = (client.primary_email if client and client.primary_email else request.to[0])
        now = datetime.now(timezone.utc)
        raw = {
            "id": operation.provider_message_id, "threadId": operation.provider_thread_id,
            "labelIds": ["SENT"], "direction": "sent", "to": request.to,
            "cc": request.cc, "bcc": request.bcc, "subject": request.subject,
            "text": request.body, "date": now.isoformat(),
            "internalDate": str(int(now.timestamp() * 1000)),
            "attachment_document_ids": [document.id for document in documents],
        }
        result = ImportIngestService(self.db).ingest(ImportIngestRequest(
            import_source_id=import_source.id,
            candidate=CandidateDataInput(
                client_type=client.client_type if client else "other",
                name=client.name if client else primary,
                legal_name=client.legal_name if client else None,
                tax_id=client.tax_id if client else None,
                primary_email=primary,
                primary_phone=client.primary_phone if client else None,
                country_code=client.country_code if client else "PL",
                confidence=1.0 if client else 0.0,
            ),
            source=CandidateSourceInput(
                source_type="gmail_message", external_id=operation.provider_message_id,
                external_parent_id=operation.provider_thread_id,
                source_label=f"Sent Gmail {operation.provider_message_id}",
                extracted_text=request.body, raw_payload=raw,
            ),
        ))
        return result.source_id

    def _attachments(self, ids: list[int], client_id: int | None):
        if not ids: return [], []
        docs = self.db.query(Document).filter(
            Document.id.in_(ids),
            Document.trashed_at.is_(None),
            Document.purged_at.is_(None),
        ).order_by(Document.id).all()
        if len(docs) != len(ids): raise MailSendValidationError("attachment_not_found")
        total = 0; encoded = []
        for document in docs:
            if client_id and document.client_id not in (None, client_id): raise MailSendValidationError("attachment_forbidden")
            if not document.content_type.startswith(ALLOWED_MIME_PREFIXES): raise MailSendValidationError("attachment_mime_forbidden")
            path = resolve_document_storage_path(storage_path=document.storage_path or "", data_root=Path(settings.data_dir))
            data = path.read_bytes(); total += len(data)
            if total > MAX_ATTACHMENT_BYTES: raise MailSendValidationError("attachments_too_large")
            encoded.append({"document_id": document.id, "filename": document.original_filename or document.filename, "mime_type": document.content_type, "content_base64": base64.b64encode(data).decode("ascii")})
        return docs, encoded

    @staticmethod
    def _payload_hash(action: str, request: MailSendRequest, source_id: int | None) -> str:
        body_digest = hashlib.sha256(request.body.encode()).hexdigest()
        value = {"action": action, "to": request.to, "cc": request.cc, "bcc": request.bcc, "subject": request.subject, "body_sha256": body_digest, "documents": sorted(request.attachment_document_ids), "source_message_id": source_id, "client_id": request.client_id}
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _source(self, source_id: int) -> CandidateSource:
        source = self.db.query(CandidateSource).filter(CandidateSource.id == source_id, CandidateSource.source_type == "gmail_message", CandidateSource.deleted_at.is_(None)).one_or_none()
        if source is None: raise MailSendNotFoundError
        return source

    def _client_id(self, source: CandidateSource) -> int | None:
        return self.db.query(ClientCandidate.matched_client_id).filter(ClientCandidate.id == source.candidate_id).scalar()

    @staticmethod
    def _address(value: Any) -> str | None:
        if isinstance(value, str) and "@" in value:
            candidate = value.rsplit("<", 1)[-1].rstrip(">").strip().lower()
            return candidate if "@" in candidate else None
        if isinstance(value, dict) and isinstance(value.get("value"), list) and value["value"]:
            return str(value["value"][0].get("address") or "").lower() or None
        return None

    @staticmethod
    def _prefixed(prefix: str, subject: str) -> str:
        lowered = subject.lower()
        while lowered.startswith(prefix.lower()):
            subject = subject[len(prefix):].lstrip(); lowered = subject.lower()
        return f"{prefix} {subject}"[:500]

    @staticmethod
    def _response(operation: MailSendOperation, replayed: bool = False) -> MailSendResponse:
        return MailSendResponse(operation_id=operation.operation_id, action=operation.action, status=operation.status, provider_message_id=operation.provider_message_id, provider_thread_id=operation.provider_thread_id, canonical_source_id=operation.canonical_source_id, replayed=replayed, error_code=operation.error_code, provider_accepted_at=operation.provider_accepted_at)
