from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.client import Client
from app.models.client_contact_point import ClientContactPoint
from app.models.contact_person import ContactPerson
from app.schemas.client import ContactPersonCreate, ContactPersonUpdate
from app.services.change_history_service import ChangeHistoryService
from app.services.client_service import ClientService


class ContactPersonNotFoundError(Exception):
    pass


class ContactPersonValidationError(Exception):
    pass


class ContactPersonConflictError(Exception):
    pass


class ContactPersonService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, client_id: int) -> list[ContactPerson]:
        self._active_client(client_id)
        return (
            self.db.query(ContactPerson)
            .options(selectinload(ContactPerson.contact_points))
            .filter(
                ContactPerson.client_id == client_id,
                ContactPerson.deleted_at.is_(None),
            )
            .order_by(ContactPerson.position, ContactPerson.id)
            .all()
        )

    def create(
        self,
        client_id: int,
        data: ContactPersonCreate,
        *,
        actor_user_id: int,
    ) -> ContactPerson:
        client = self._active_client(client_id, lock=True)
        self._ensure_preferred_available(client_id, data.is_preferred)
        person = ContactPerson(
            client_id=client_id,
            display_name=data.display_name,
            role=data.role,
            is_preferred=data.is_preferred,
            is_decision_maker=data.is_decision_maker,
            notes=data.notes,
            position=self._next_position(client_id),
            origin="manual",
        )
        operation = str(uuid4())
        history = ChangeHistoryService(self.db)
        try:
            self.db.add(person)
            self.db.flush()
            touched = self._set_ownership(
                client,
                person,
                data.contact_point_ids,
                replace=False,
            )
            touched += self._create_coordinates(client, person, "email", data.emails)
            touched += self._create_coordinates(client, person, "phone", data.phones)
            self.db.flush()
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="contact_person",
                entity_id=person.id,
                action="created",
                before={},
                after=history.contact_person_snapshot(person),
                operation_id=operation,
                source_key=f"contact-person:{operation}:{person.id}:created",
            )
            self._history_coordinates(history, touched, actor_user_id, operation)
            self.db.commit()
            return self.get(client_id, person.id)
        except IntegrityError as error:
            self.db.rollback()
            raise ContactPersonConflictError("Preferred person or contact coordinate conflicts") from error
        except Exception:
            self.db.rollback()
            raise

    def get(self, client_id: int, person_id: int, *, include_deleted: bool = False) -> ContactPerson:
        query = (
            self.db.query(ContactPerson)
            .options(selectinload(ContactPerson.contact_points))
            .filter(ContactPerson.id == person_id, ContactPerson.client_id == client_id)
        )
        if not include_deleted:
            query = query.filter(ContactPerson.deleted_at.is_(None))
        person = query.one_or_none()
        if person is None:
            raise ContactPersonNotFoundError("Contact person not found")
        return person

    def update(
        self,
        client_id: int,
        person_id: int,
        data: ContactPersonUpdate,
        *,
        actor_user_id: int,
    ) -> ContactPerson:
        client = self._active_client(client_id, lock=True)
        person = self._active_person(client_id, person_id, lock=True)
        payload = data.model_dump(
            exclude_unset=True,
            exclude={"contact_point_ids", "emails", "phones"},
        )
        if payload.get("is_preferred") is True and not person.is_preferred:
            self._ensure_preferred_available(client_id, True, excluded_person_id=person.id)
        history = ChangeHistoryService(self.db)
        before = history.contact_person_snapshot(person)
        operation = str(uuid4())
        try:
            for key, value in payload.items():
                setattr(person, key, value)
            touched: list[tuple[ClientContactPoint, dict]] = []
            if data.contact_point_ids is not None:
                touched += self._set_ownership(client, person, data.contact_point_ids, replace=True)
            if data.emails is not None:
                touched += self._create_coordinates(client, person, "email", data.emails)
            if data.phones is not None:
                touched += self._create_coordinates(client, person, "phone", data.phones)
            self.db.flush()
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="contact_person",
                entity_id=person.id,
                action="updated",
                before=before,
                after=history.contact_person_snapshot(person),
                operation_id=operation,
                source_key=f"contact-person:{operation}:{person.id}:updated",
            )
            self._history_coordinates(history, touched, actor_user_id, operation)
            self.db.commit()
            return self.get(client_id, person.id)
        except IntegrityError as error:
            self.db.rollback()
            raise ContactPersonConflictError("Preferred person or contact coordinate conflicts") from error
        except Exception:
            self.db.rollback()
            raise

    def archive(self, client_id: int, person_id: int, *, actor_user_id: int) -> None:
        self._active_client(client_id, lock=True)
        person = self._active_person(client_id, person_id, lock=True)
        history = ChangeHistoryService(self.db)
        before = history.contact_person_snapshot(person)
        operation = str(uuid4())
        touched = []
        try:
            for point in list(person.contact_points):
                if point.deleted_at is None:
                    point_before = history.contact_snapshot(point)
                    point.contact_person_id = None
                    touched.append((point, point_before))
            person.deleted_at = datetime.now(timezone.utc)
            self.db.flush()
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="contact_person",
                entity_id=person.id,
                action="deleted",
                before=before,
                after=history.contact_person_snapshot(person),
                operation_id=operation,
                source_key=f"contact-person:{operation}:{person.id}:deleted",
            )
            self._history_coordinates(history, touched, actor_user_id, operation)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def restore(self, client_id: int, person_id: int, *, actor_user_id: int) -> ContactPerson:
        self._active_client(client_id, lock=True)
        person = self.get(client_id, person_id, include_deleted=True)
        if person.deleted_at is None:
            return person
        self._ensure_preferred_available(client_id, person.is_preferred, excluded_person_id=person.id)
        history = ChangeHistoryService(self.db)
        before = history.contact_person_snapshot(person)
        operation = str(uuid4())
        try:
            person.deleted_at = None
            self.db.flush()
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="contact_person",
                entity_id=person.id,
                action="restored",
                before=before,
                after=history.contact_person_snapshot(person),
                operation_id=operation,
                source_key=f"contact-person:{operation}:{person.id}:restored",
            )
            self.db.commit()
            return self.get(client_id, person.id)
        except IntegrityError as error:
            self.db.rollback()
            raise ContactPersonConflictError("Another active preferred person exists") from error

    def assign_coordinate(
        self,
        client_id: int,
        contact_point_id: int,
        person_id: int | None,
        *,
        actor_user_id: int,
    ) -> ClientContactPoint:
        self._active_client(client_id, lock=True)
        point = (
            self.db.query(ClientContactPoint)
            .filter(
                ClientContactPoint.id == contact_point_id,
                ClientContactPoint.client_id == client_id,
                ClientContactPoint.deleted_at.is_(None),
            )
            .with_for_update()
            .one_or_none()
        )
        if point is None:
            raise ContactPersonNotFoundError("Contact point not found")
        if person_id is not None:
            self._active_person(client_id, person_id, lock=True)
        history = ChangeHistoryService(self.db)
        before = history.contact_snapshot(point)
        operation = str(uuid4())
        point.contact_person_id = person_id
        try:
            self.db.flush()
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="client_contact",
                entity_id=point.id,
                action="updated",
                before=before,
                after=history.contact_snapshot(point),
                operation_id=operation,
                source_key=f"contact-person:{operation}:contact:{point.id}:updated",
            )
            self.db.commit()
            self.db.refresh(point)
            return point
        except IntegrityError as error:
            self.db.rollback()
            raise ContactPersonValidationError("Contact point and person must belong to the same Client") from error

    def _active_client(self, client_id: int, *, lock: bool = False) -> Client:
        query = self.db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        client = query.one_or_none()
        if client is None:
            raise ContactPersonNotFoundError("Client not found")
        return client

    def _active_person(self, client_id: int, person_id: int, *, lock: bool = False) -> ContactPerson:
        query = self.db.query(ContactPerson).filter(
            ContactPerson.id == person_id,
            ContactPerson.client_id == client_id,
            ContactPerson.deleted_at.is_(None),
        )
        if lock:
            query = query.with_for_update()
        person = query.one_or_none()
        if person is None:
            raise ContactPersonNotFoundError("Contact person not found")
        return person

    def _ensure_preferred_available(self, client_id: int, preferred: bool, *, excluded_person_id: int | None = None) -> None:
        if not preferred:
            return
        query = self.db.query(ContactPerson.id).filter(
            ContactPerson.client_id == client_id,
            ContactPerson.deleted_at.is_(None),
            ContactPerson.is_preferred.is_(True),
        )
        if excluded_person_id is not None:
            query = query.filter(ContactPerson.id != excluded_person_id)
        if query.first() is not None:
            raise ContactPersonConflictError("Only one active preferred person is allowed")

    def _next_position(self, client_id: int) -> int:
        values = [row[0] for row in self.db.query(ContactPerson.position).filter(ContactPerson.client_id == client_id).all()]
        return max(values, default=-1) + 1

    def _set_ownership(self, client: Client, person: ContactPerson, point_ids: list[int], *, replace: bool) -> list[tuple[ClientContactPoint, dict]]:
        requested = set(point_ids)
        points = []
        if requested:
            points = self.db.query(ClientContactPoint).filter(
                ClientContactPoint.id.in_(requested),
                ClientContactPoint.client_id == client.id,
                ClientContactPoint.deleted_at.is_(None),
            ).with_for_update().all()
            if {point.id for point in points} != requested:
                raise ContactPersonValidationError("Contact point does not belong to this Client")
        if replace:
            points += [point for point in person.contact_points if point.deleted_at is None and point.id not in requested]
        touched = []
        seen = set()
        history = ChangeHistoryService(self.db)
        for point in points:
            if point.id in seen:
                continue
            seen.add(point.id)
            target = person.id if point.id in requested else None
            if point.contact_person_id != target:
                touched.append((point, history.contact_snapshot(point)))
                point.contact_person_id = target
        return touched

    def _create_coordinates(self, client: Client, person: ContactPerson, kind: str, contacts: list) -> list[tuple[ClientContactPoint, dict]]:
        touched = []
        for raw in contacts:
            normalized = ClientService._normalize_contact(kind, raw.value)
            existing = next(
                (point for point in client.contact_points if point.deleted_at is None and point.kind == kind and point.normalized_value == normalized),
                None,
            )
            if existing is not None:
                raise ContactPersonConflictError("Duplicate normalized Client contact coordinate")
            has_primary = any(point.deleted_at is None and point.kind == kind and point.is_primary for point in client.contact_points)
            make_primary = bool(raw.is_primary or not has_primary)
            if make_primary:
                for point in client.contact_points:
                    if point.deleted_at is None and point.kind == kind and point.is_primary:
                        touched.append((point, ChangeHistoryService(self.db).contact_snapshot(point)))
                        point.is_primary = False
                setattr(client, "primary_email" if kind == "email" else "primary_phone", raw.value.strip())
            point = ClientContactPoint(
                client_id=client.id,
                contact_person_id=person.id,
                kind=kind,
                value=raw.value.strip(),
                normalized_value=normalized,
                is_primary=make_primary,
                position=len([p for p in client.contact_points if p.kind == kind]),
                origin="manual",
            )
            client.contact_points.append(point)
            touched.append((point, {}))
        return touched

    @staticmethod
    def _history_coordinates(history, touched, actor_user_id, operation) -> None:
        for point, before in touched:
            action = "created" if not before else "updated"
            history.persist(
                actor_user_id=actor_user_id,
                entity_type="client_contact",
                entity_id=point.id,
                action=action,
                before=before,
                after=history.contact_snapshot(point),
                operation_id=operation,
                source_key=f"contact-person:{operation}:contact:{point.id}:{action}",
            )
