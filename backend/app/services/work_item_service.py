from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.models.absence_request import AbsenceRequest
from app.models.client import Client
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.models.work_item import WorkItem
from app.models.work_item_document import WorkItemDocument
from app.models.work_item_note import WorkItemNote
from app.schemas.work_item import (
    AbsenceCreate, AbsenceRead, AbsenceUpdate, CalendarEntry, CalendarMonth,
    WorkItemCreate, WorkItemDocumentRead, WorkItemNoteCreate,
    WorkItemNoteRead, WorkItemNoteUpdate, WorkItemRead, WorkItemUpdate,
)
from app.services.change_history_service import ChangeHistoryService


class WorkItemNotFoundError(LookupError): pass
class WorkItemConflictError(RuntimeError): pass
class WorkItemReferenceError(ValueError): pass
class AbsenceAuthorizationError(PermissionError): pass
class AbsenceOverlapError(RuntimeError): pass


def _is_admin(user: User) -> bool:
    return bool(user.role and user.role.name == "Administrator")


class WorkItemService:
    PROJECT_STATUS = {
        "todo": "planned",
        "in_progress": "active",
        "completed": "completed",
        "cancelled": "cancelled",
    }
    def __init__(self, db: Session):
        self.db = db
        self.history = ChangeHistoryService(db)

    def _active(self, item_id: int, *, include_archived: bool = False, lock: bool = False) -> WorkItem:
        query = self.db.query(WorkItem).filter(WorkItem.id == item_id)
        if not include_archived:
            query = query.filter(WorkItem.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        item = query.one_or_none()
        if item is None:
            raise WorkItemNotFoundError
        return item

    def _validate_references(self, *, assignee_user_id: int | None, client_id: int | None) -> None:
        if assignee_user_id is not None:
            user = self.db.query(User).filter(User.id == assignee_user_id, User.is_active.is_(True)).one_or_none()
            if user is None:
                raise WorkItemReferenceError("assignee_not_active")
        if client_id is not None:
            client = self.db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).one_or_none()
            if client is None:
                raise WorkItemReferenceError("client_not_found")

    @staticmethod
    def _snapshot(item: WorkItem) -> dict:
        return {name: getattr(item, name) for name in (
            "item_type", "title", "description", "start_at", "due_at", "all_day",
            "timezone_name", "status", "priority", "assignee_user_id", "client_id", "project_id",
            "party_name", "completed_at", "deleted_at", "version",
        )}

    def _read(
        self,
        item: WorkItem,
        *,
        assignee_display: str | None = None,
        client_name: str | None = None,
        prefetched: bool = False,
    ) -> WorkItemRead:
        assignee = assignee_display
        client = client_name
        if not prefetched:
            assignee = self.db.query(User.username).filter(User.id == item.assignee_user_id).scalar() if item.assignee_user_id else None
            client = self.db.query(Client.name).filter(Client.id == item.client_id).scalar() if item.client_id else None
        return WorkItemRead.model_validate(item).model_copy(update={"assignee_display": assignee, "client_name": client})

    @staticmethod
    def _project_date(value: datetime | None, timezone_name: str | None) -> date | None:
        if value is None:
            return None
        return value.astimezone(ZoneInfo(timezone_name or "Europe/Warsaw")).date()

    def _new_project(self, data: WorkItemCreate, actor: User) -> Project:
        if data.client_id is None:
            raise WorkItemReferenceError("realization_client_required")
        project = Project(
            client_id=data.client_id,
            name=data.title,
            description=data.description,
            status=self.PROJECT_STATUS[data.status],
            start_date=self._project_date(data.start_at, data.timezone_name),
            end_date=self._project_date(data.due_at, data.timezone_name),
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _sync_project(self, item: WorkItem, actor: User) -> None:
        project = item.project or self.db.query(Project).filter(Project.id == item.project_id).with_for_update().one()
        if project.client_id != item.client_id:
            raise WorkItemConflictError("realization_client_change_forbidden")
        project.name = item.title
        project.description = item.description
        project.status = self.PROJECT_STATUS[item.status]
        project.start_date = self._project_date(item.start_at, item.timezone_name)
        project.end_date = self._project_date(item.due_at, item.timezone_name)
        project.updated_by_user_id = actor.id

    def create(self, data: WorkItemCreate, actor: User) -> WorkItemRead:
        self._validate_references(assignee_user_id=data.assignee_user_id, client_id=data.client_id)
        values = data.model_dump()
        if values["status"] == "completed":
            values["completed_at"] = datetime.now(timezone.utc)
        if data.item_type == "realization":
            values["project_id"] = self._new_project(data, actor).id
        item = WorkItem(**values, created_by_user_id=actor.id, updated_by_user_id=actor.id)
        try:
            self.db.add(item)
            self.db.flush()
            self.history.persist(actor_user_id=actor.id, entity_type="work_item", entity_id=item.id, action="created", before={}, after=self._snapshot(item), source_key=f"work-item:{item.id}:created")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(item)
        return self._read(item)

    def repair_legacy_realization(
        self,
        item_id: int,
        actor: User,
        *,
        commit: bool = True,
    ) -> WorkItemRead:
        """Link one legacy realization to its canonical Project, idempotently.

        This is deliberately not a broad backfill. The caller must select the
        exact legacy WorkItem; this method then locks it, detects an exact
        existing Project, and creates at most one Project in the same database
        transaction.
        """
        if not _is_admin(actor):
            raise WorkItemConflictError("administrator_required")
        item = self._active(item_id, lock=True)
        if item.item_type != "realization":
            raise WorkItemConflictError("legacy_realization_required")
        if item.client_id is None:
            raise WorkItemReferenceError("realization_client_required")
        if item.project_id is not None:
            return self._read(item)

        start_date = self._project_date(item.start_at, item.timezone_name)
        end_date = self._project_date(item.due_at, item.timezone_name)
        projects = (
            self.db.query(Project)
            .filter(
                Project.client_id == item.client_id,
                Project.name == item.title,
                Project.start_date == start_date,
                Project.end_date == end_date,
                Project.deleted_at.is_(None),
            )
            .order_by(Project.id)
            .with_for_update()
            .all()
        )
        if len(projects) > 1:
            raise WorkItemConflictError("legacy_realization_project_ambiguous")
        before = self._snapshot(item)
        try:
            if projects:
                project = projects[0]
                linked_item_id = self.db.query(WorkItem.id).filter(
                    WorkItem.project_id == project.id,
                    WorkItem.id != item.id,
                ).scalar()
                if linked_item_id is not None:
                    raise WorkItemConflictError("legacy_realization_project_already_linked")
            else:
                project = Project(
                    client_id=item.client_id,
                    name=item.title,
                    description=item.description,
                    status=self.PROJECT_STATUS[item.status],
                    start_date=start_date,
                    end_date=end_date,
                    created_by_user_id=actor.id,
                    updated_by_user_id=actor.id,
                )
                self.db.add(project)
                self.db.flush()
            item.project_id = project.id
            item.updated_by_user_id = actor.id
            item.version += 1
            self.db.flush()
            self.history.persist(
                actor_user_id=actor.id,
                entity_type="work_item",
                entity_id=item.id,
                action="updated",
                before=before,
                after=self._snapshot(item),
                source_key=f"work-item:{item.id}:v{item.version}",
            )
            if commit:
                self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        if commit:
            self.db.refresh(item)
        return self._read(item)

    def get(self, item_id: int, *, include_archived: bool = False) -> WorkItemRead:
        return self._read(self._active(item_id, include_archived=include_archived))

    def list(self, *, item_type=None, status=None, priority=None, assignee_user_id=None, client_id=None, date_from=None, date_to=None, search=None, archived=False, skip=0, limit=50):
        query = self.db.query(WorkItem, User.username, Client.name).outerjoin(
            User, User.id == WorkItem.assignee_user_id
        ).outerjoin(Client, Client.id == WorkItem.client_id)
        query = query.filter(WorkItem.deleted_at.isnot(None) if archived else WorkItem.deleted_at.is_(None))
        for column, value in ((WorkItem.item_type, item_type), (WorkItem.status, status), (WorkItem.priority, priority), (WorkItem.assignee_user_id, assignee_user_id), (WorkItem.client_id, client_id)):
            if value is not None:
                query = query.filter(column == value)
        if date_from is not None:
            query = query.filter(or_(WorkItem.start_at >= date_from, WorkItem.due_at >= date_from))
        if date_to is not None:
            query = query.filter(or_(WorkItem.start_at <= date_to, WorkItem.due_at <= date_to))
        if search:
            needle = f"%{search.strip()}%"
            query = query.filter(or_(WorkItem.title.ilike(needle), WorkItem.party_name.ilike(needle)))
        total = query.count()
        rows = query.order_by(func.coalesce(WorkItem.due_at, WorkItem.start_at).asc().nulls_last(), WorkItem.id.asc()).offset(skip).limit(limit).all()
        return {
            "items": [
                self._read(
                    item,
                    assignee_display=assignee,
                    client_name=client,
                    prefetched=True,
                )
                for item, assignee, client in rows
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update(self, item_id: int, data: WorkItemUpdate, actor: User) -> WorkItemRead:
        item = self._active(item_id, lock=True)
        if item.version != data.expected_version:
            raise WorkItemConflictError("work_item_version_conflict")
        updates = data.model_dump(exclude_unset=True, exclude={"expected_version"})
        merged = {name: updates.get(name, getattr(item, name)) for name in WorkItemCreate.model_fields}
        validated = WorkItemCreate.model_validate(merged)
        updates = {key: value for key, value in validated.model_dump().items() if key in updates}
        assignee = updates.get("assignee_user_id", item.assignee_user_id)
        client = updates.get("client_id", item.client_id)
        target_type = updates.get("item_type", item.item_type)
        if item.project_id is not None and target_type != "realization":
            raise WorkItemConflictError("linked_realization_type_change_forbidden")
        if item.project_id is not None and client != item.client_id:
            raise WorkItemConflictError("realization_client_change_forbidden")
        if target_type == "realization" and client is None:
            raise WorkItemReferenceError("realization_client_required")
        if "assignee_user_id" in updates or "client_id" in updates:
            self._validate_references(assignee_user_id=assignee, client_id=client)
        before = self._snapshot(item)
        for key, value in updates.items():
            setattr(item, key, value)
        if item.status == "completed" and item.completed_at is None:
            item.completed_at = datetime.now(timezone.utc)
        elif item.status != "completed":
            item.completed_at = None
        item.updated_by_user_id = actor.id
        item.version += 1
        if item.item_type == "realization" and item.project_id is None and before["item_type"] != "realization":
            item.project_id = self._new_project(
                WorkItemCreate.model_validate({name: getattr(item, name) for name in WorkItemCreate.model_fields}),
                actor,
            ).id
        if item.project_id is not None:
            self._sync_project(item, actor)
        self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item", entity_id=item.id, action="status_changed" if before["status"] != item.status else "updated", before=before, after=self._snapshot(item), source_key=f"work-item:{item.id}:v{item.version}")
        self.db.commit()
        self.db.refresh(item)
        return self._read(item)

    def set_archived(self, item_id: int, expected_version: int, actor: User, *, archived: bool) -> WorkItemRead:
        item = self._active(item_id, include_archived=True, lock=True)
        if item.version != expected_version:
            raise WorkItemConflictError("work_item_version_conflict")
        if (item.deleted_at is not None) == archived:
            return self._read(item)
        before = self._snapshot(item)
        item.deleted_at = datetime.now(timezone.utc) if archived else None
        if item.project_id is not None:
            project = self.db.query(Project).filter(Project.id == item.project_id).with_for_update().one()
            project.deleted_at = item.deleted_at
            project.updated_by_user_id = actor.id
        item.updated_by_user_id = actor.id
        item.version += 1
        self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item", entity_id=item.id, action="deleted" if archived else "restored", before=before, after=self._snapshot(item), source_key=f"work-item:{item.id}:v{item.version}")
        self.db.commit()
        return self._read(item)

    def active_assignees(self, search: str | None, limit: int = 50):
        query = self.db.query(User).filter(User.is_active.is_(True))
        if search:
            query = query.filter(User.username.ilike(f"%{search.strip()}%"))
        return [{"id": row.id, "username": row.username} for row in query.order_by(User.username, User.id).limit(limit).all()]

    def list_notes(self, item_id: int, *, archived: bool = False):
        self._active(item_id)
        rows = self.db.query(WorkItemNote).filter(WorkItemNote.work_item_id == item_id, WorkItemNote.deleted_at.isnot(None) if archived else WorkItemNote.deleted_at.is_(None)).order_by(WorkItemNote.created_at, WorkItemNote.id).all()
        return [WorkItemNoteRead.model_validate(row) for row in rows]

    def create_note(self, item_id: int, data: WorkItemNoteCreate, actor: User):
        self._active(item_id)
        note = WorkItemNote(work_item_id=item_id, text=data.text, created_by_user_id=actor.id, updated_by_user_id=actor.id)
        self.db.add(note); self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item_note", entity_id=note.id, action="created", before={}, after={"work_item_id": item_id, "text": note.text, "version": 1}, source_key=f"work-item-note:{note.id}:created")
        self.db.commit(); self.db.refresh(note)
        return WorkItemNoteRead.model_validate(note)

    def update_note(self, item_id: int, note_id: int, data: WorkItemNoteUpdate, actor: User):
        note = self.db.query(WorkItemNote).filter(WorkItemNote.id == note_id, WorkItemNote.work_item_id == item_id).with_for_update().one_or_none()
        if note is None: raise WorkItemNotFoundError
        if note.version != data.expected_version: raise WorkItemConflictError("work_item_note_version_conflict")
        before = {"work_item_id": item_id, "text": note.text, "deleted_at": note.deleted_at, "version": note.version}
        note.text = data.text; note.updated_by_user_id = actor.id; note.version += 1
        self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item_note", entity_id=note.id, action="updated", before=before, after={"work_item_id": item_id, "text": note.text, "deleted_at": note.deleted_at, "version": note.version}, source_key=f"work-item-note:{note.id}:v{note.version}")
        self.db.commit(); return WorkItemNoteRead.model_validate(note)

    def set_note_archived(self, item_id: int, note_id: int, expected_version: int, actor: User, archived: bool):
        note = self.db.query(WorkItemNote).filter(WorkItemNote.id == note_id, WorkItemNote.work_item_id == item_id).with_for_update().one_or_none()
        if note is None: raise WorkItemNotFoundError
        if note.version != expected_version: raise WorkItemConflictError("work_item_note_version_conflict")
        before = {"work_item_id": item_id, "text": note.text, "deleted_at": note.deleted_at, "version": note.version}
        note.deleted_at = datetime.now(timezone.utc) if archived else None; note.version += 1; note.updated_by_user_id = actor.id
        self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item_note", entity_id=note.id, action="deleted" if archived else "restored", before=before, after={"work_item_id": item_id, "text": note.text, "deleted_at": note.deleted_at, "version": note.version}, source_key=f"work-item-note:{note.id}:v{note.version}")
        self.db.commit(); return WorkItemNoteRead.model_validate(note)

    def link_document(self, item_id: int, document_id: int, note_id: int | None, actor: User):
        item = self._active(item_id)
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.trashed_at.is_(None),
            Document.purged_at.is_(None),
        ).one_or_none()
        if document is None: raise WorkItemReferenceError("document_not_found")
        if item.client_id is not None and document.client_id not in (None, item.client_id): raise WorkItemReferenceError("cross_client_document")
        if item.project_id is not None and document.project_id not in (None, item.project_id): raise WorkItemReferenceError("cross_project_document")
        if item.project_id is not None:
            project = self.db.query(Project).filter(Project.id == item.project_id).one_or_none()
            if project is None or project.client_id != item.client_id:
                raise WorkItemReferenceError("realization_project_client_conflict")
        ownership_changed = False
        if document.client_id is None and item.client_id is not None:
            document.client_id = item.client_id
            ownership_changed = True
        if document.project_id is None and item.project_id is not None:
            document.project_id = item.project_id
            ownership_changed = True
        if note_id is not None and self.db.query(WorkItemNote).filter(WorkItemNote.id == note_id, WorkItemNote.work_item_id == item_id).one_or_none() is None: raise WorkItemReferenceError("note_not_found")
        existing = self.db.query(WorkItemDocument).filter(WorkItemDocument.work_item_id == item_id, WorkItemDocument.document_id == document_id, WorkItemDocument.detached_at.is_(None)).one_or_none()
        if existing:
            if ownership_changed:
                self.db.commit()
                self.db.refresh(document)
            return self._document_read(existing, document)
        link = WorkItemDocument(work_item_id=item_id, note_id=note_id, document_id=document_id, attached_by_user_id=actor.id)
        self.db.add(link); self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item_document", entity_id=link.id, action="created", before={}, after={"work_item_id": item_id, "note_id": note_id, "document_id": document_id}, source_key=f"work-item-document:{link.id}:created")
        self.db.commit(); return self._document_read(link, document)

    def list_documents(self, item_id: int):
        self._active(item_id)
        rows = self.db.query(WorkItemDocument, Document).join(Document, Document.id == WorkItemDocument.document_id).filter(
            WorkItemDocument.work_item_id == item_id,
            WorkItemDocument.detached_at.is_(None),
            Document.trashed_at.is_(None),
            Document.purged_at.is_(None),
        ).order_by(WorkItemDocument.created_at, WorkItemDocument.id).all()
        return [self._document_read(link, doc) for link, doc in rows]

    @staticmethod
    def _document_read(link, document):
        return WorkItemDocumentRead(
            id=link.id,
            work_item_id=link.work_item_id,
            note_id=link.note_id,
            document_id=document.id,
            filename=document.original_filename or document.filename,
            content_type=document.content_type,
            file_size=document.file_size,
            source_type=document.source_type,
            captured_at=document.captured_at,
            created_at=link.created_at,
        )

    def detach_document(self, item_id: int, document_id: int, actor: User):
        link = self.db.query(WorkItemDocument).filter(WorkItemDocument.work_item_id == item_id, WorkItemDocument.document_id == document_id, WorkItemDocument.detached_at.is_(None)).one_or_none()
        if link is None: raise WorkItemNotFoundError
        link.detached_at = datetime.now(timezone.utc); link.detached_by_user_id = actor.id; self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="work_item_document", entity_id=link.id, action="deleted", before={"work_item_id": item_id, "note_id": link.note_id, "document_id": document_id, "detached_at": None}, after={"work_item_id": item_id, "note_id": link.note_id, "document_id": document_id, "detached_at": link.detached_at}, source_key=f"work-item-document:{link.id}:detached")
        self.db.commit()


class AbsenceService:
    def __init__(self, db: Session): self.db, self.history = db, ChangeHistoryService(db)

    @staticmethod
    def _snapshot(row):
        return {name: getattr(row, name) for name in ("requester_user_id", "absence_type", "start_date", "end_date", "status", "note", "reviewed_by_user_id", "reviewed_at", "review_note", "cancelled_by_user_id", "cancelled_at", "version")}

    def _lock_and_check(self, requester_id: int, start: date, end: date, exclude_id: int | None = None):
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": requester_id})
        query = self.db.query(AbsenceRequest).filter(AbsenceRequest.requester_user_id == requester_id, AbsenceRequest.status.in_(("requested", "approved")), AbsenceRequest.start_date <= end, AbsenceRequest.end_date >= start)
        if exclude_id is not None: query = query.filter(AbsenceRequest.id != exclude_id)
        if query.first() is not None: raise AbsenceOverlapError("absence_overlap")

    def _read(self, row: AbsenceRequest, actor: User):
        display = self.db.query(User.username).filter(User.id == row.requester_user_id).scalar()
        result = AbsenceRead.model_validate(row).model_copy(update={"requester_display": display})
        if not _is_admin(actor) and row.requester_user_id != actor.id: raise AbsenceAuthorizationError
        return result

    def create(self, data: AbsenceCreate, actor: User):
        self._lock_and_check(actor.id, data.start_date, data.end_date)
        row = AbsenceRequest(**data.model_dump(), requester_user_id=actor.id)
        self.db.add(row); self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="absence_request", entity_id=row.id, action="created", before={}, after=self._snapshot(row), source_key=f"absence:{row.id}:created")
        self.db.commit(); self.db.refresh(row); return self._read(row, actor)

    def list(self, actor: User, *, status=None, requester_user_id=None, skip=0, limit=50):
        query = self.db.query(AbsenceRequest)
        if not _is_admin(actor): query = query.filter(AbsenceRequest.requester_user_id == actor.id)
        elif requester_user_id: query = query.filter(AbsenceRequest.requester_user_id == requester_user_id)
        if status: query = query.filter(AbsenceRequest.status == status)
        total = query.count(); rows = query.order_by(AbsenceRequest.start_date.desc(), AbsenceRequest.id.desc()).offset(skip).limit(limit).all()
        return {"items": [self._read(row, actor) for row in rows], "total": total, "skip": skip, "limit": limit}

    def get(self, row_id: int, actor: User):
        row = self.db.query(AbsenceRequest).filter(AbsenceRequest.id == row_id).one_or_none()
        if row is None: raise WorkItemNotFoundError
        return self._read(row, actor)

    def update(self, row_id: int, data: AbsenceUpdate, actor: User):
        row = self.db.query(AbsenceRequest).filter(AbsenceRequest.id == row_id).with_for_update().one_or_none()
        if row is None: raise WorkItemNotFoundError
        if row.requester_user_id != actor.id or row.status != "requested": raise AbsenceAuthorizationError
        if row.version != data.expected_version: raise WorkItemConflictError("absence_version_conflict")
        self._lock_and_check(row.requester_user_id, data.start_date, data.end_date, row.id)
        before = self._snapshot(row)
        for key, value in data.model_dump(exclude={"expected_version"}).items(): setattr(row, key, value)
        row.version += 1; self.db.flush()
        self.history.persist(actor_user_id=actor.id, entity_type="absence_request", entity_id=row.id, action="updated", before=before, after=self._snapshot(row), source_key=f"absence:{row.id}:v{row.version}")
        self.db.commit(); return self._read(row, actor)

    def review(self, row_id: int, expected_version: int, review_note: str | None, actor: User, *, approved: bool):
        if not _is_admin(actor): raise AbsenceAuthorizationError
        row = self.db.query(AbsenceRequest).filter(AbsenceRequest.id == row_id).with_for_update().one_or_none()
        if row is None: raise WorkItemNotFoundError
        if row.requester_user_id == actor.id or row.status != "requested": raise AbsenceAuthorizationError
        if row.version != expected_version: raise WorkItemConflictError("absence_version_conflict")
        if approved: self._lock_and_check(row.requester_user_id, row.start_date, row.end_date, row.id)
        before = self._snapshot(row); row.status = "approved" if approved else "rejected"; row.reviewed_by_user_id = actor.id; row.reviewed_at = datetime.now(timezone.utc); row.review_note = review_note; row.version += 1
        self.db.flush(); self.history.persist(actor_user_id=actor.id, entity_type="absence_request", entity_id=row.id, action="status_changed", before=before, after=self._snapshot(row), source_key=f"absence:{row.id}:v{row.version}")
        self.db.commit(); return self._read(row, actor)

    def cancel(self, row_id: int, expected_version: int, actor: User):
        row = self.db.query(AbsenceRequest).filter(AbsenceRequest.id == row_id).with_for_update().one_or_none()
        if row is None: raise WorkItemNotFoundError
        if row.version != expected_version: raise WorkItemConflictError("absence_version_conflict")
        if not _is_admin(actor) and (row.requester_user_id != actor.id or row.status != "requested"): raise AbsenceAuthorizationError
        if row.status not in ("requested", "approved"): raise AbsenceAuthorizationError
        before = self._snapshot(row); row.status = "cancelled"; row.cancelled_by_user_id = actor.id; row.cancelled_at = datetime.now(timezone.utc); row.version += 1
        self.db.flush(); self.history.persist(actor_user_id=actor.id, entity_type="absence_request", entity_id=row.id, action="status_changed", before=before, after=self._snapshot(row), source_key=f"absence:{row.id}:v{row.version}")
        self.db.commit(); return self._read(row, actor)


class CalendarService:
    WORK_LIMIT = 1000
    ABSENCE_LIMIT = 500
    def __init__(self, db: Session): self.db = db

    def month(self, year: int, month: int, actor: User) -> CalendarMonth:
        last_day = calendar.monthrange(year, month)[1]
        month_start = datetime.combine(date(year, month, 1), time.min, tzinfo=timezone.utc)
        month_end = datetime.combine(date(year, month, last_day), time.max, tzinfo=timezone.utc)
        work_query = self.db.query(WorkItem, User.username, Client.name).outerjoin(User, User.id == WorkItem.assignee_user_id).outerjoin(Client, Client.id == WorkItem.client_id).filter(
            WorkItem.deleted_at.is_(None),
            or_(
                and_(WorkItem.start_at.isnot(None), WorkItem.due_at.isnot(None), WorkItem.start_at <= month_end, WorkItem.due_at >= month_start),
                and_(WorkItem.start_at.isnot(None), WorkItem.due_at.is_(None), WorkItem.start_at >= month_start, WorkItem.start_at <= month_end),
                and_(WorkItem.start_at.is_(None), WorkItem.due_at.isnot(None), WorkItem.due_at >= month_start, WorkItem.due_at <= month_end),
            ),
        )
        work_total = work_query.count(); work_rows = work_query.order_by(func.coalesce(WorkItem.start_at, WorkItem.due_at), WorkItem.id).limit(self.WORK_LIMIT).all()
        absence_query = self.db.query(AbsenceRequest, User.username).join(User, User.id == AbsenceRequest.requester_user_id).filter(AbsenceRequest.status.in_(("requested", "approved")), AbsenceRequest.start_date <= month_end.date(), AbsenceRequest.end_date >= month_start.date())
        if not _is_admin(actor): absence_query = absence_query.filter(AbsenceRequest.requester_user_id == actor.id)
        absence_total = absence_query.count(); absence_rows = absence_query.order_by(AbsenceRequest.start_date, AbsenceRequest.id).limit(self.ABSENCE_LIMIT).all()
        items: list[CalendarEntry] = []
        for row, assignee, client in work_rows:
            start = row.start_at or row.due_at; end = row.due_at or row.start_at
            if row.all_day:
                zone = ZoneInfo(row.timezone_name or "Europe/Warsaw")
                start = start.astimezone(zone).date()
                end = end.astimezone(zone).date()
            items.append(CalendarEntry(entity_id=row.id, entity_kind="work_item", item_type=row.item_type, title=row.title, start=start, end=end, status=row.status, priority=row.priority, assignee_display=assignee, client_id=row.client_id, client_name=client, all_day=row.all_day))
        for row, requester in absence_rows:
            items.append(CalendarEntry(entity_id=row.id, entity_kind="absence", item_type="absence", title=f"Absencja — {requester}" if _is_admin(actor) else "Moja absencja", start=row.start_date, end=row.end_date, status=row.status, assignee_display=requester if _is_admin(actor) else None, all_day=True))
        counts = Counter()
        for item in items:
            start = item.start.date() if isinstance(item.start, datetime) else item.start
            end = item.end.date() if isinstance(item.end, datetime) else item.end
            cursor = max(start, month_start.date()); finish = min(end, month_end.date())
            while cursor <= finish:
                counts[cursor.isoformat()] += 1
                cursor = date.fromordinal(cursor.toordinal() + 1)
        return CalendarMonth(year=year, month=month, items=items, total=work_total + absence_total, day_counts=dict(counts), truncated=work_total > self.WORK_LIMIT or absence_total > self.ABSENCE_LIMIT)
