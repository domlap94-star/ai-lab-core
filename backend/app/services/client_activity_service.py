from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_activity_event import ClientActivityEvent
from app.models.client_contact_point import ClientContactPoint
from app.schemas.client_activity import CallActivityMetadata, CallInitiatedResponse, StatusActivityMetadata


class ActivityNotFoundError(Exception):
    pass


class ActivityValidationError(Exception):
    pass


class ActivityConflictError(Exception):
    pass


class ClientActivityService:
    WRITABLE_EVENT_TYPES = frozenset({"call_initiated", "client_status_changed"})

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_call(
        self,
        *,
        client_id: int,
        actor_user_id: int,
        operation_id: UUID,
        contact_id: int | None,
    ) -> CallInitiatedResponse:
        client = self.db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).one_or_none()
        if client is None:
            raise ActivityNotFoundError("Client not found")

        if contact_id is None:
            if not (client.primary_phone or "").strip():
                raise ActivityValidationError("Client has no active phone contact")
            metadata = CallActivityMetadata(contact_id=None, contact_kind="phone", contact_reference="primary_phone")
            entity_type, entity_id = "client", client_id
        else:
            contact = self.db.query(ClientContactPoint).filter(
                ClientContactPoint.id == contact_id,
                ClientContactPoint.client_id == client_id,
                ClientContactPoint.kind == "phone",
                ClientContactPoint.deleted_at.is_(None),
            ).one_or_none()
            if contact is None:
                raise ActivityValidationError("Phone contact does not belong to this Client")
            metadata = CallActivityMetadata(contact_id=contact.id, contact_kind="phone", contact_reference="contact_point")
            entity_type, entity_id = "client_contact_point", contact.id

        source_key = f"call:{operation_id}"
        existing = self.db.query(ClientActivityEvent).filter(ClientActivityEvent.source_key == source_key).one_or_none()
        if existing is not None:
            expected = metadata.model_dump(mode="json")
            if existing.client_id != client_id or existing.actor_user_id != actor_user_id or existing.event_metadata != expected:
                raise ActivityConflictError("Operation ID is already bound to another call action")
            return CallInitiatedResponse(event_id=existing.id, operation_id=operation_id, replayed=True, occurred_at=existing.occurred_at)

        now = datetime.now(UTC)
        event = ClientActivityEvent(
            client_id=client_id,
            actor_user_id=actor_user_id,
            event_type="call_initiated",
            direction="outgoing",
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_at=now,
            summary=None,
            event_metadata=metadata.model_dump(mode="json"),
            source_key=source_key,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return CallInitiatedResponse(event_id=event.id, operation_id=operation_id, replayed=False, occurred_at=event.occurred_at)

    def add_status_change(
        self,
        *,
        client_id: int,
        actor_user_id: int,
        old_status: str,
        new_status: str,
        effective_date: date | None,
        source_key: str,
    ) -> ClientActivityEvent:
        metadata = StatusActivityMetadata(old_status=old_status, new_status=new_status, effective_date=effective_date)
        event = ClientActivityEvent(
            client_id=client_id,
            actor_user_id=actor_user_id,
            event_type="client_status_changed",
            direction=None,
            entity_type="client",
            entity_id=client_id,
            occurred_at=datetime.now(UTC),
            summary=None,
            event_metadata=metadata.model_dump(mode="json"),
            source_key=source_key,
        )
        self.db.add(event)
        return event
