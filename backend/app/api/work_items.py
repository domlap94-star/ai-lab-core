from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.models.work_item_note import WorkItemNote
from app.schemas.work_item import (
    AssigneeRead, VersionRequest, WorkItemCreate, WorkItemDocumentLink,
    WorkItemDocumentRead, WorkItemNoteCreate, WorkItemNoteRead,
    WorkItemNoteUpdate, WorkItemPage, WorkItemRead, WorkItemStatusUpdate,
    WorkItemUpdate, WorkItemType, WorkItemStatus, WorkItemPriority,
)
from app.services.work_item_service import (
    WorkItemConflictError, WorkItemNotFoundError, WorkItemReferenceError,
    WorkItemService,
)
from app.services.document_service import DocumentService, DocumentStorageError, DocumentTooLargeError, EmptyDocumentError

router = APIRouter(prefix="/work-items", tags=["Work Items"])


def _http(error: Exception) -> HTTPException:
    if isinstance(error, WorkItemNotFoundError): return HTTPException(404, "work_item_not_found")
    if isinstance(error, WorkItemConflictError): return HTTPException(409, str(error))
    return HTTPException(422, str(error))


@router.get("", response_model=WorkItemPage)
def list_items(item_type: WorkItemType | None = None, item_status: WorkItemStatus | None = Query(None, alias="status"), priority: WorkItemPriority | None = None, assignee_user_id: int | None = None, client_id: int | None = None, date_from: datetime | None = None, date_to: datetime | None = None, search: str | None = Query(None, max_length=255), archived: bool = False, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WorkItemService(db).list(item_type=item_type, status=item_status, priority=priority, assignee_user_id=assignee_user_id, client_id=client_id, date_from=date_from, date_to=date_to, search=search, archived=archived, skip=skip, limit=limit)


@router.get("/assignees", response_model=list[AssigneeRead])
def assignees(search: str | None = Query(None, max_length=100), limit: int = Query(50, ge=1, le=100), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WorkItemService(db).active_assignees(search, limit)


@router.post("", response_model=WorkItemRead, status_code=201)
def create_item(data: WorkItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).create(data, user)
    except WorkItemReferenceError as error: raise _http(error) from error


@router.get("/{item_id}", response_model=WorkItemRead)
def get_item(item_id: int, include_archived: bool = False, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).get(item_id, include_archived=include_archived)
    except WorkItemNotFoundError as error: raise _http(error) from error


@router.patch("/{item_id}", response_model=WorkItemRead)
def update_item(item_id: int, data: WorkItemUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).update(item_id, data, user)
    except (WorkItemNotFoundError, WorkItemConflictError, WorkItemReferenceError) as error: raise _http(error) from error


@router.post("/{item_id}/status", response_model=WorkItemRead)
def update_status(item_id: int, data: WorkItemStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).update(item_id, WorkItemUpdate(expected_version=data.expected_version, status=data.status), user)
    except (WorkItemNotFoundError, WorkItemConflictError) as error: raise _http(error) from error


@router.post("/{item_id}/archive", response_model=WorkItemRead)
def archive(item_id: int, data: VersionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).set_archived(item_id, data.expected_version, user, archived=True)
    except (WorkItemNotFoundError, WorkItemConflictError) as error: raise _http(error) from error


@router.post("/{item_id}/restore", response_model=WorkItemRead)
def restore(item_id: int, data: VersionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).set_archived(item_id, data.expected_version, user, archived=False)
    except (WorkItemNotFoundError, WorkItemConflictError) as error: raise _http(error) from error


@router.get("/{item_id}/notes", response_model=list[WorkItemNoteRead])
def notes(item_id: int, archived: bool = False, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).list_notes(item_id, archived=archived)
    except WorkItemNotFoundError as error: raise _http(error) from error


@router.post("/{item_id}/notes", response_model=WorkItemNoteRead, status_code=201)
def add_note(item_id: int, data: WorkItemNoteCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).create_note(item_id, data, user)
    except WorkItemNotFoundError as error: raise _http(error) from error


@router.patch("/{item_id}/notes/{note_id}", response_model=WorkItemNoteRead)
def update_note(item_id: int, note_id: int, data: WorkItemNoteUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).update_note(item_id, note_id, data, user)
    except (WorkItemNotFoundError, WorkItemConflictError) as error: raise _http(error) from error


@router.post("/{item_id}/notes/{note_id}/archive", response_model=WorkItemNoteRead)
def archive_note(item_id: int, note_id: int, data: VersionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).set_note_archived(item_id, note_id, data.expected_version, user, True)
    except (WorkItemNotFoundError, WorkItemConflictError) as error: raise _http(error) from error


@router.post("/{item_id}/notes/{note_id}/restore", response_model=WorkItemNoteRead)
def restore_note(item_id: int, note_id: int, data: VersionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).set_note_archived(item_id, note_id, data.expected_version, user, False)
    except (WorkItemNotFoundError, WorkItemConflictError) as error: raise _http(error) from error


@router.get("/{item_id}/documents", response_model=list[WorkItemDocumentRead])
def documents(item_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).list_documents(item_id)
    except WorkItemNotFoundError as error: raise _http(error) from error


@router.post("/{item_id}/documents", response_model=WorkItemDocumentRead, status_code=201)
def link_document(item_id: int, data: WorkItemDocumentLink, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return WorkItemService(db).link_document(item_id, data.document_id, data.note_id, user)
    except (WorkItemNotFoundError, WorkItemReferenceError) as error: raise _http(error) from error


@router.post("/{item_id}/documents/upload", response_model=WorkItemDocumentRead, status_code=201)
async def upload_document(item_id: int, file: UploadFile = File(...), note_id: int | None = Form(None), source_type: str = Form("manual_upload"), captured_at: datetime | None = Form(None), latitude: float | None = Form(None), longitude: float | None = Form(None), location_accuracy_m: float | None = Form(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service = WorkItemService(db)
    try:
        if source_type not in {"manual_upload", "camera_photo"}:
            raise WorkItemReferenceError("unsupported_work_item_source_type")
        item = service._active(item_id)
        if note_id is not None and db.query(WorkItemNote).filter(WorkItemNote.id == note_id, WorkItemNote.work_item_id == item_id, WorkItemNote.deleted_at.is_(None)).one_or_none() is None:
            raise WorkItemReferenceError("note_not_found")
        content = await file.read(250 * 1024 * 1024 + 1)
        document_service = DocumentService(db)
        result = document_service.store_document(
            content=content, original_filename=file.filename or "document.bin",
            content_type=file.content_type or "application/octet-stream",
            source_type=source_type, client_id=item.client_id, project_id=item.project_id,
            captured_at=captured_at, latitude=latitude, longitude=longitude,
            location_accuracy_m=location_accuracy_m,
            location_source="device_gps" if latitude is not None else None,
            intake_metadata={"origin": "work_item_note" if note_id else "work_item", "work_item_id": item_id, "note_id": note_id, "actor_user_id": user.id},
            commit=False,
        )
        try:
            return service.link_document(item_id, result.document.id, note_id, user)
        except Exception:
            db.rollback()
            if result.created:
                document_service.discard_uncommitted_file(result.document)
            raise
    except (WorkItemNotFoundError, WorkItemReferenceError) as error: raise _http(error) from error
    except DocumentTooLargeError as error: raise HTTPException(413, "document_too_large") from error
    except EmptyDocumentError as error: raise HTTPException(422, "empty_document") from error
    except DocumentStorageError as error: raise HTTPException(500, "document_storage_failed") from error


@router.delete("/{item_id}/documents/{document_id}", status_code=204)
def detach_document(item_id: int, document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: WorkItemService(db).detach_document(item_id, document_id, user); return Response(status_code=204)
    except WorkItemNotFoundError as error: raise _http(error) from error
