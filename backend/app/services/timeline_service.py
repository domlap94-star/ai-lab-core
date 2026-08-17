from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.document import Document
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.inspection import Inspection
from app.models.project import Project
from app.repositories.client_email_repository import ClientEmailRepository
from app.schemas.timeline import TimelineEvent, TimelineEventType, TimelinePage
from app.services.client_email_service import ClientEmailService
from app.services.client_service import ClientNotFoundError
from app.services.project_service import ProjectNotFoundError


class TimelineService:
    """Bounded, read-only projection over existing business records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_client_timeline(
        self,
        *,
        client_id: int,
        skip: int,
        limit: int,
        event_type: TimelineEventType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        project_id: int | None = None,
    ) -> TimelinePage:
        client = self._active_client(client_id)
        if project_id is not None:
            project = self._active_project(project_id)
            if project.client_id != client_id:
                raise ProjectNotFoundError

        window = skip + limit
        events: list[TimelineEvent] = []
        totals: list[int] = []

        if project_id is None and self._enabled(event_type, "client_created"):
            if self._within(client.created_at, date_from, date_to):
                events.append(
                    TimelineEvent(
                        stable_key=f"client:{client.id}:created",
                        event_type="client_created",
                        occurred_at=client.created_at,
                        title="Dodano klienta",
                        summary=client.name,
                        client_id=client.id,
                        source_type="client",
                        source_id=client.id,
                    )
                )
                totals.append(1)

        project_query = self.db.query(Project).filter(
            Project.client_id == client_id,
            Project.deleted_at.is_(None),
        )
        if project_id is not None:
            project_query = project_query.filter(Project.id == project_id)
        self._append_model_events(
            events,
            totals,
            query=project_query,
            date_column=Project.created_at,
            event_type="project_created",
            date_from=date_from,
            date_to=date_to,
            window=window,
            mapper=self._project_created,
            enabled=self._enabled(event_type, "project_created"),
        )

        inspection_query = self.db.query(Inspection).filter(
            Inspection.client_id == client_id,
            Inspection.deleted_at.is_(None),
        )
        if project_id is not None:
            inspection_query = inspection_query.filter(
                Inspection.project_id == project_id
            )
        self._inspection_events(
            events,
            totals,
            inspection_query,
            event_type,
            date_from,
            date_to,
            window,
        )

        document_query = self.db.query(Document).filter(
            Document.client_id == client_id
        )
        if project_id is not None:
            document_query = document_query.filter(
                Document.project_id == project_id
            )
        self._document_events(
            events,
            totals,
            document_query,
            event_type,
            date_from,
            date_to,
            window,
        )

        if project_id is None:
            self._email_events(
                events,
                totals,
                client_id,
                event_type,
                date_from,
                date_to,
                window,
            )

        link_query = self.db.query(DocumentClientLinkEvent).filter(
            or_(
                DocumentClientLinkEvent.old_client_id == client_id,
                DocumentClientLinkEvent.new_client_id == client_id,
            )
        )
        if project_id is not None:
            link_query = link_query.join(
                Document, Document.id == DocumentClientLinkEvent.document_id
            ).filter(Document.project_id == project_id)
        self._link_events(
            events,
            totals,
            link_query,
            client_id,
            project_id,
            event_type,
            date_from,
            date_to,
            window,
        )
        return self._page(events, sum(totals), skip, limit)

    def get_project_timeline(
        self,
        *,
        project_id: int,
        skip: int,
        limit: int,
        event_type: TimelineEventType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> TimelinePage:
        project = self._active_project(project_id)
        return self.get_client_timeline(
            client_id=project.client_id,
            project_id=project.id,
            skip=skip,
            limit=limit,
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
        )

    def _inspection_events(
        self,
        events: list[TimelineEvent],
        totals: list[int],
        base_query: Any,
        requested: TimelineEventType | None,
        date_from: datetime | None,
        date_to: datetime | None,
        window: int,
    ) -> None:
        specifications = (
            ("inspection_created", Inspection.created_at, self._inspection_created),
            ("inspection_scheduled", Inspection.scheduled_at, self._inspection_scheduled),
            ("inspection_started", Inspection.started_at, self._inspection_started),
            ("inspection_completed", Inspection.completed_at, self._inspection_completed),
        )
        for event_type, column, mapper in specifications:
            query = base_query.filter(column.isnot(None))
            self._append_model_events(
                events,
                totals,
                query=query,
                date_column=column,
                event_type=event_type,
                date_from=date_from,
                date_to=date_to,
                window=window,
                mapper=mapper,
                enabled=self._enabled(requested, event_type),
            )

    def _document_events(
        self,
        events: list[TimelineEvent],
        totals: list[int],
        base_query: Any,
        requested: TimelineEventType | None,
        date_from: datetime | None,
        date_to: datetime | None,
        window: int,
    ) -> None:
        photo_sources = ("camera_photo", "camera_video")
        for event_type, predicate in (
            ("photo_captured", Document.source_type.in_(photo_sources)),
            ("document_added", ~Document.source_type.in_(photo_sources)),
        ):
            if not self._enabled(requested, event_type):
                continue
            query = base_query.filter(predicate)
            date_column = (
                func.coalesce(Document.captured_at, Document.created_at)
                if event_type == "photo_captured"
                else Document.created_at
            )
            self._append_model_events(
                events,
                totals,
                query=query,
                date_column=date_column,
                event_type=event_type,
                date_from=date_from,
                date_to=date_to,
                window=window,
                mapper=(self._photo_event if event_type == "photo_captured" else self._document_event),
                enabled=True,
            )

    def _email_events(
        self,
        events: list[TimelineEvent],
        totals: list[int],
        client_id: int,
        requested: TimelineEventType | None,
        date_from: datetime | None,
        date_to: datetime | None,
        window: int,
    ) -> None:
        if requested not in (None, "email_received", "email_sent"):
            return
        repository = ClientEmailRepository(self.db)
        sources = repository._deduplicated_sources(client_id)
        query = self.db.query(sources).filter(sources.c.duplicate_rank == 1)
        occurred = func.coalesce(sources.c.message_at, sources.c.created_at)
        query = self._date_filter(query, occurred, date_from, date_to)
        direction = func.lower(
            func.coalesce(sources.c.raw_payload.op("->>")("direction"), "")
        )
        labels = cast(sources.c.raw_payload.op("->")("labelIds"), String)
        sent = or_(
            direction.in_(("sent", "outgoing", "wyslana", "wysłana")),
            labels.ilike('%"SENT"%'),
        )
        received = or_(
            direction.in_(("received", "incoming", "odebrana")),
            labels.ilike('%"INBOX"%'),
        )
        if requested == "email_sent":
            query = query.filter(sent)
        elif requested == "email_received":
            query = query.filter(received)
        else:
            query = query.filter(or_(sent, received))
        totals.append(query.count())
        rows = (
            query.order_by(
                occurred.desc().nulls_last(), sources.c.source_id.desc()
            )
            .limit(window)
            .all()
        )
        for row in rows:
            payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
            direction = ClientEmailService._direction(payload)
            event_kind = "email_sent" if direction == "sent" else "email_received"
            if requested is not None and requested != event_kind:
                continue
            occurred_at = row.message_at or row.created_at
            if not self._within(occurred_at, date_from, date_to):
                continue
            sender = ClientEmailService._addresses(payload.get("from") or payload.get("From"))
            subject = ClientEmailService._clean_string(payload.get("subject") or payload.get("Subject"))
            summary = subject or "(bez tematu)"
            events.append(
                TimelineEvent(
                    stable_key=f"email:{row.source_id}",
                    event_type=event_kind,
                    occurred_at=occurred_at,
                    title="Wysłano wiadomość" if event_kind == "email_sent" else "Odebrano wiadomość",
                    summary=summary[:500],
                    client_id=client_id,
                    source_type="candidate_source",
                    source_id=row.source_id,
                    metadata={
                        "direction": direction,
                        "from_name": sender[0][0] if sender else None,
                        "from_address": sender[0][1] if sender else None,
                    },
                )
            )

    def _link_events(
        self,
        events: list[TimelineEvent],
        totals: list[int],
        base_query: Any,
        scope_client_id: int,
        scope_project_id: int | None,
        requested: TimelineEventType | None,
        date_from: datetime | None,
        date_to: datetime | None,
        window: int,
    ) -> None:
        mapping = {
            "LINK": "document_client_linked",
            "MOVE": "document_client_moved",
            "UNLINK": "document_client_unlinked",
        }
        allowed_actions = [action for action, kind in mapping.items() if requested in (None, kind)]
        if not allowed_actions:
            return
        query = base_query.filter(DocumentClientLinkEvent.action.in_(allowed_actions))
        query = self._date_filter(query, DocumentClientLinkEvent.created_at, date_from, date_to)
        totals.append(query.count())
        rows = query.order_by(DocumentClientLinkEvent.created_at.desc(), DocumentClientLinkEvent.id.desc()).limit(window).all()
        for row in rows:
            kind = mapping[row.action]
            events.append(
                TimelineEvent(
                    stable_key=f"document-link:{row.id}",
                    event_type=kind,
                    occurred_at=row.created_at,
                    title={
                        "LINK": "Przypisano dokument do klienta",
                        "MOVE": "Przeniesiono dokument między klientami",
                        "UNLINK": "Odpięto dokument od klienta",
                    }[row.action],
                    summary="Cofnięcie wcześniejszej operacji" if row.reversal_of_event_id else row.reason[:500],
                    client_id=scope_client_id,
                    project_id=scope_project_id,
                    document_id=row.document_id,
                    source_type="document_client_link_event",
                    source_id=row.id,
                    actor_user_id=row.actor_user_id,
                    metadata={
                        "old_client_id": row.old_client_id,
                        "new_client_id": row.new_client_id,
                        "reversal_of_event_id": row.reversal_of_event_id,
                    },
                )
            )

    def _append_model_events(
        self,
        events: list[TimelineEvent],
        totals: list[int],
        *,
        query: Any,
        date_column: Any,
        event_type: str,
        date_from: datetime | None,
        date_to: datetime | None,
        window: int,
        mapper: Any,
        enabled: bool,
    ) -> None:
        if not enabled:
            return
        query = self._date_filter(query, date_column, date_from, date_to)
        totals.append(query.count())
        for row in query.order_by(date_column.desc(), row_id_column(query).desc()).limit(window).all():
            events.append(mapper(row))

    @staticmethod
    def _date_filter(query: Any, column: Any, date_from: datetime | None, date_to: datetime | None) -> Any:
        if date_from is not None:
            query = query.filter(column >= date_from)
        if date_to is not None:
            query = query.filter(column <= date_to)
        return query

    @staticmethod
    def _enabled(requested: TimelineEventType | None, event_type: str) -> bool:
        return requested is None or requested == event_type

    @staticmethod
    def _within(value: datetime, date_from: datetime | None, date_to: datetime | None) -> bool:
        return (date_from is None or value >= date_from) and (date_to is None or value <= date_to)

    @staticmethod
    def _page(events: Iterable[TimelineEvent], total: int, skip: int, limit: int) -> TimelinePage:
        ordered = sorted(events, key=lambda item: (item.occurred_at, item.stable_key), reverse=True)
        return TimelinePage(items=ordered[skip : skip + limit], total=total, skip=skip, limit=limit)

    def _active_client(self, client_id: int) -> Client:
        client = self.db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).one_or_none()
        if client is None:
            raise ClientNotFoundError
        return client

    def _active_project(self, project_id: int) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).one_or_none()
        if project is None:
            raise ProjectNotFoundError
        return project

    @staticmethod
    def _project_created(row: Project) -> TimelineEvent:
        return TimelineEvent(stable_key=f"project:{row.id}:created", event_type="project_created", occurred_at=row.created_at, title="Utworzono realizację", summary=row.name, client_id=row.client_id, project_id=row.id, source_type="project", source_id=row.id, actor_user_id=row.created_by_user_id)

    @staticmethod
    def _inspection_created(row: Inspection) -> TimelineEvent:
        return TimelineEvent(stable_key=f"inspection:{row.id}:created", event_type="inspection_created", occurred_at=row.created_at, title="Utworzono wizję lokalną", summary=row.title, client_id=row.client_id, project_id=row.project_id, inspection_id=row.id, source_type="inspection", source_id=row.id, actor_user_id=row.created_by_user_id)

    @staticmethod
    def _inspection_started(row: Inspection) -> TimelineEvent:
        return TimelineEvent(stable_key=f"inspection:{row.id}:started", event_type="inspection_started", occurred_at=row.started_at, title="Rozpoczęto wizję lokalną", summary=row.title, client_id=row.client_id, project_id=row.project_id, inspection_id=row.id, source_type="inspection", source_id=row.id, actor_user_id=row.updated_by_user_id)

    @staticmethod
    def _inspection_scheduled(row: Inspection) -> TimelineEvent:
        return TimelineEvent(stable_key=f"inspection:{row.id}:scheduled", event_type="inspection_scheduled", occurred_at=row.scheduled_at, title="Zaplanowano wizję lokalną", summary=row.title, client_id=row.client_id, project_id=row.project_id, inspection_id=row.id, source_type="inspection", source_id=row.id, actor_user_id=row.created_by_user_id)

    @staticmethod
    def _inspection_completed(row: Inspection) -> TimelineEvent:
        return TimelineEvent(stable_key=f"inspection:{row.id}:completed", event_type="inspection_completed", occurred_at=row.completed_at, title="Zakończono wizję lokalną", summary=row.title, client_id=row.client_id, project_id=row.project_id, inspection_id=row.id, source_type="inspection", source_id=row.id, actor_user_id=row.updated_by_user_id)

    @staticmethod
    def _document_event(row: Document) -> TimelineEvent:
        name = row.original_filename or row.filename
        return TimelineEvent(stable_key=f"document:{row.id}:added", event_type="document_added", occurred_at=row.created_at, title="Dodano dokument", summary=name[:500], client_id=row.client_id, project_id=row.project_id, inspection_id=row.inspection_id, document_id=row.id, source_type="document", source_id=row.id, metadata={"content_type": row.content_type, "filename": name[:255]})

    @staticmethod
    def _photo_event(row: Document) -> TimelineEvent:
        name = row.original_filename or row.filename
        return TimelineEvent(stable_key=f"document:{row.id}:captured", event_type="photo_captured", occurred_at=row.captured_at or row.created_at, title="Wykonano zdjęcie" if row.source_type == "camera_photo" else "Nagrano materiał", summary=name[:500], client_id=row.client_id, project_id=row.project_id, inspection_id=row.inspection_id, document_id=row.id, source_type="document", source_id=row.id, metadata={"content_type": row.content_type, "filename": name[:255]})


def row_id_column(query: Any) -> Any:
    """Return the primary id column of the single ORM entity in a query."""
    entity = query.column_descriptions[0]["entity"]
    return entity.id
