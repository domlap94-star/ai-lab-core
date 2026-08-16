from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.client_contact_point import ClientContactPoint
from app.models.document import Document
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.user import User
from app.schemas.document import (
    DocumentClientLinkRequest,
    DocumentClientMatchRead,
    DocumentClientSuggestion,
    DocumentMatchEvidence,
)
from app.services.client_identity_name_quality_service import ClientIdentityNameQualityService


class DocumentMatchNotFoundError(Exception):
    pass


class DocumentMatchConflictError(Exception):
    pass


class DocumentMatchInvalidOperationError(Exception):
    pass


class DocumentClientMatchingService:
    """Deterministic, single-document matching with transactional audit."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.quality = ClientIdentityNameQualityService()

    def get_match(self, document_id: int) -> DocumentClientMatchRead:
        document = self._document(document_id)
        suggestions, evidence, conflict = self._suggest(document)
        current = self._active_client(document.client_id) if document.client_id else None
        status = (
            "CONFLICT" if conflict else "ASSIGNED" if current else
            "CANDIDATE" if document.candidate_id else "UNMATCHED"
        )
        confidence = "CONFLICT" if conflict else (suggestions[0].confidence if suggestions else "NONE")
        history = (
            self.db.query(DocumentClientLinkEvent)
            .filter(DocumentClientLinkEvent.document_id == document.id)
            .order_by(DocumentClientLinkEvent.created_at.desc(), DocumentClientLinkEvent.id.desc())
            .all()
        )
        return DocumentClientMatchRead(
            document_id=document.id,
            current_client_id=current.id if current else None,
            current_client_name=current.name if current else None,
            candidate_id=document.candidate_id,
            status=status,
            confidence=confidence,
            suggestions=suggestions,
            evidence=evidence,
            conflict=conflict,
            history=history,
        )

    def link(self, document_id: int, actor: User, request: DocumentClientLinkRequest):
        document = self._document(document_id, lock=True)
        target = self._required_active_client(request.client_id)
        if document.client_id == target.id:
            raise DocumentMatchInvalidOperationError("Document is already linked to this client")
        match = self.get_match(document_id)
        conflicts = {item.client_id for item in match.suggestions if item.client_id != target.id}
        if (match.conflict or conflicts) and not request.confirm_conflict:
            raise DocumentMatchConflictError("Conflicting evidence requires explicit confirmation")
        old_client_id = document.client_id
        action = "MOVE" if old_client_id is not None else "LINK"
        document.client_id = target.id
        document.match_status = "confirmed"
        document.match_method = "manual"
        document.match_confidence = 1.0
        document.matched_at = datetime.now(UTC)
        event = self._event(
            document=document, actor=actor, action=action,
            old_client_id=old_client_id, new_client_id=target.id,
            reason=request.reason, match=match,
        )
        self.db.flush()
        self.db.refresh(document)
        return document, event

    def unlink(self, document_id: int, actor: User, reason: str, *, confirm: bool):
        if not confirm:
            raise DocumentMatchInvalidOperationError("Unlink requires explicit confirmation")
        document = self._document(document_id, lock=True)
        if document.client_id is None:
            raise DocumentMatchInvalidOperationError("Document is not linked")
        old_client_id = document.client_id
        match = self.get_match(document_id)
        document.client_id = None
        document.match_status = "suggested" if document.candidate_id else "unmatched"
        document.match_method = None
        document.match_confidence = None
        document.matched_at = None
        event = self._event(
            document=document, actor=actor, action="UNLINK",
            old_client_id=old_client_id, new_client_id=None,
            reason=reason, match=match,
        )
        self.db.flush()
        self.db.refresh(document)
        return document, event

    def undo(self, document_id: int, actor: User):
        document = self._document(document_id, lock=True)
        latest = (
            self.db.query(DocumentClientLinkEvent)
            .filter(DocumentClientLinkEvent.document_id == document.id)
            .order_by(DocumentClientLinkEvent.created_at.desc(), DocumentClientLinkEvent.id.desc())
            .first()
        )
        if (
            latest is None
            or latest.reversal_of_event_id is not None
            or document.client_id != latest.new_client_id
            or self.db.query(DocumentClientLinkEvent.id).filter(
                DocumentClientLinkEvent.reversal_of_event_id == latest.id
            ).first() is not None
        ):
            raise DocumentMatchInvalidOperationError("No reversible latest operation")
        if latest.old_client_id is not None:
            self._required_active_client(latest.old_client_id)
        target = latest.old_client_id
        action = "UNLINK" if target is None else "LINK" if latest.new_client_id is None else "MOVE"
        document.client_id = target
        document.match_status = "confirmed" if target else ("suggested" if document.candidate_id else "unmatched")
        document.match_method = "manual_undo" if target else None
        document.match_confidence = 1.0 if target else None
        document.matched_at = datetime.now(UTC) if target else None
        match = self.get_match(document_id)
        event = self._event(
            document=document, actor=actor, action=action,
            old_client_id=latest.new_client_id, new_client_id=target,
            reason=f"undo event {latest.id}", match=match,
            reversal_of_event_id=latest.id,
        )
        self.db.flush()
        self.db.refresh(document)
        return document, event

    def _suggest(self, document: Document):
        evidence_by_client: dict[int, list[DocumentMatchEvidence]] = {}
        candidate = None
        if document.candidate_id:
            candidate = self.db.query(ClientCandidate).filter(ClientCandidate.id == document.candidate_id).first()
        if candidate and candidate.matched_client_id and self._active_client(candidate.matched_client_id):
            evidence_by_client.setdefault(candidate.matched_client_id, []).append(
                DocumentMatchEvidence(
                    kind="candidate_match",
                    description=f"Kandydat #{candidate.id} jest przypisany do klienta #{candidate.matched_client_id}",
                    client_id=candidate.matched_client_id,
                )
            )
        if candidate:
            values: list[tuple[str, str]] = []
            email = self.quality.normalize_email(candidate.primary_email)
            phone = self.quality.normalize_phone(candidate.primary_phone)
            if email:
                values.append(("email", email))
            if phone:
                values.append(("phone", phone))
            for kind, value in values:
                rows = (
                    self.db.query(ClientContactPoint)
                    .join(Client, Client.id == ClientContactPoint.client_id)
                    .filter(
                        ClientContactPoint.kind == kind,
                        ClientContactPoint.normalized_value == value,
                        ClientContactPoint.deleted_at.is_(None),
                        Client.deleted_at.is_(None),
                    ).all()
                )
                for row in rows:
                    evidence_by_client.setdefault(row.client_id, []).append(
                        DocumentMatchEvidence(
                            kind=f"exact_{kind}",
                            description=f"Dokładna zgodność kontaktu {kind} z kandydatem #{candidate.id}",
                            client_id=row.client_id,
                        )
                    )
        if document.checksum_sha256:
            linked_duplicates = (
                self.db.query(Document.client_id)
                .join(Client, Client.id == Document.client_id)
                .filter(
                    Document.id != document.id,
                    Document.checksum_sha256 == document.checksum_sha256,
                    Document.client_id.is_not(None),
                    Client.deleted_at.is_(None),
                )
                .distinct()
                .all()
            )
            for (client_id,) in linked_duplicates:
                evidence_by_client.setdefault(client_id, []).append(
                    DocumentMatchEvidence(
                        kind="checksum_client",
                        description="Identyczny checksum występuje przy dokumencie przypisanym do tego klienta",
                        client_id=client_id,
                    )
                )
        conflict = len(evidence_by_client) > 1 or (
            document.client_id is not None
            and bool(evidence_by_client)
            and document.client_id not in evidence_by_client
        )
        suggestions: list[DocumentClientSuggestion] = []
        for client_id, items in evidence_by_client.items():
            client = self._active_client(client_id)
            if client is None:
                continue
            confidence = "CONFLICT" if conflict else (
                "HIGH" if any(item.kind in {"candidate_match", "checksum_client"} for item in items) else "MEDIUM"
            )
            suggestions.append(DocumentClientSuggestion(
                client_id=client.id, client_name=client.name,
                confidence=confidence, evidence=items,
            ))
        suggestions.sort(key=lambda item: item.client_id)
        evidence = [item for suggestion in suggestions for item in suggestion.evidence]
        return suggestions, evidence, conflict

    def _event(self, *, document, actor, action, old_client_id, new_client_id, reason, match, reversal_of_event_id=None):
        event = DocumentClientLinkEvent(
            document_id=document.id, actor_user_id=actor.id, action=action,
            old_client_id=old_client_id, new_client_id=new_client_id,
            previous_candidate_id=document.candidate_id, reason=reason.strip(),
            evidence_snapshot={
                "confidence": match.confidence,
                "suggested_client_ids": [item.client_id for item in match.suggestions],
                "evidence_kinds": sorted({item.kind for item in match.evidence}),
            },
            reversal_of_event_id=reversal_of_event_id,
        )
        self.db.add(document)
        self.db.add(event)
        return event

    def _document(self, document_id: int, *, lock: bool = False) -> Document:
        query = self.db.query(Document).filter(Document.id == document_id)
        document = (query.with_for_update().first() if lock else query.first())
        if document is None:
            raise DocumentMatchNotFoundError("Document not found")
        return document

    def _active_client(self, client_id: int | None) -> Client | None:
        if client_id is None:
            return None
        return self.db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).first()

    def _required_active_client(self, client_id: int) -> Client:
        client = self._active_client(client_id)
        if client is None:
            raise DocumentMatchNotFoundError("Active client not found")
        return client
