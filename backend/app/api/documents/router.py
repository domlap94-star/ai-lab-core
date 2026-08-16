from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.imports.dependencies import require_import_api_key
from app.api.auth import get_current_user
from app.database.session import get_db
from app.schemas.document import (
    DocumentClientLinkRequest,
    DocumentClientLinkResult,
    DocumentClientMatchRead,
    DocumentClientUnlinkRequest,
    DocumentRead,
    DocumentLinkState,
    DocumentPublicPage,
    DocumentPublicRead,
    DocumentUploadResponse,
)
from app.services.document_service import (
    DocumentService,
    DocumentStorageError,
    EmptyDocumentError,
    InvalidDocumentSourceTypeError,
    InvalidLocationMetadataError,
    MissingLocationMetadataError,
    DocumentContentUnavailableError,
    UnsafeDocumentStoragePathError,
)
from app.models.user import User
from app.services.document_client_matching_service import (
    DocumentClientMatchingService,
    DocumentMatchConflictError,
    DocumentMatchInvalidOperationError,
    DocumentMatchNotFoundError,
)
from app.services.document_read_service import (
    DocumentNotFoundError,
    DocumentReadService,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


def _matching_error(error: Exception) -> HTTPException:
    if isinstance(error, DocumentMatchNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, DocumentMatchConflictError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("/{document_id}/client-match", response_model=DocumentClientMatchRead)
def get_document_client_match(
    document_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentClientMatchRead:
    try:
        return DocumentClientMatchingService(db).get_match(document_id)
    except DocumentMatchNotFoundError as error:
        raise _matching_error(error) from error


@router.post("/{document_id}/link-client", response_model=DocumentClientLinkResult)
def link_document_client(
    document_id: int,
    request: DocumentClientLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentClientLinkResult:
    try:
        _, event = DocumentClientMatchingService(db).link(document_id, current_user, request)
        document = DocumentReadService(db).get_document(document_id)
        result = DocumentClientLinkResult(document=document, event=event)
        db.commit()
        return result
    except (DocumentMatchNotFoundError, DocumentMatchConflictError, DocumentMatchInvalidOperationError) as error:
        db.rollback()
        raise _matching_error(error) from error
    except Exception:
        db.rollback()
        raise


@router.post("/{document_id}/move-client", response_model=DocumentClientLinkResult)
def move_document_client(
    document_id: int,
    request: DocumentClientLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentClientLinkResult:
    return link_document_client(document_id, request, current_user, db)


@router.post("/{document_id}/unlink-client", response_model=DocumentClientLinkResult)
def unlink_document_client(
    document_id: int,
    request: DocumentClientUnlinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentClientLinkResult:
    try:
        _, event = DocumentClientMatchingService(db).unlink(
            document_id, current_user, request.reason, confirm=request.confirm
        )
        document = DocumentReadService(db).get_document(document_id)
        result = DocumentClientLinkResult(document=document, event=event)
        db.commit()
        return result
    except (DocumentMatchNotFoundError, DocumentMatchInvalidOperationError) as error:
        db.rollback()
        raise _matching_error(error) from error
    except Exception:
        db.rollback()
        raise


@router.post("/{document_id}/undo-client-link", response_model=DocumentClientLinkResult)
def undo_document_client_link(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentClientLinkResult:
    try:
        _, event = DocumentClientMatchingService(db).undo(document_id, current_user)
        document = DocumentReadService(db).get_document(document_id)
        result = DocumentClientLinkResult(document=document, event=event)
        db.commit()
        return result
    except (DocumentMatchNotFoundError, DocumentMatchInvalidOperationError) as error:
        db.rollback()
        raise _matching_error(error) from error
    except Exception:
        db.rollback()
        raise


@router.get(
    "",
    response_model=DocumentPublicPage,
)
def list_documents(
    search: str | None = Query(default=None, max_length=255),
    client_id: int | None = Query(default=None, ge=1),
    source_type: str | None = Query(default=None, max_length=30),
    match_status: str | None = Query(default=None, max_length=30),
    processing_status: str | None = Query(default=None, max_length=30),
    link_state: DocumentLinkState = Query(default="ALL"),
    content_type: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentPublicPage:
    return DocumentReadService(db).get_page(
        search=search,
        client_id=client_id,
        source_type=source_type,
        match_status=match_status,
        processing_status=processing_status,
        link_state=link_state,
        content_type=content_type,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{document_id}/content",
    response_class=FileResponse,
)
def get_document_content(
    document_id: int,
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        document, path, filename = DocumentReadService(db).get_content(
            document_id
        )
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Document not found") from error
    except (
        DocumentContentUnavailableError,
        UnsafeDocumentStoragePathError,
    ) as error:
        raise HTTPException(
            status_code=409,
            detail="Document content is unavailable",
        ) from error

    return FileResponse(
        path=path,
        media_type=document.content_type,
        filename=filename,
        content_disposition_type="inline",
    )


@router.get(
    "/{document_id}",
    response_model=DocumentPublicRead,
)
def get_document(
    document_id: int,
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentPublicRead:
    try:
        return DocumentReadService(db).get_document(document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Document not found") from error


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(require_import_api_key),
    ],
)
async def upload_document(
    file: UploadFile = File(...),
    source_type: str = Form(
        default="manual_upload",
    ),
    external_id: str | None = Form(
        default=None,
    ),
    gmail_message_id: str | None = Form(
        default=None,
    ),
    gmail_thread_id: str | None = Form(
        default=None,
    ),
    candidate_id: int | None = Form(
        default=None,
    ),
    client_id: int | None = Form(
        default=None,
    ),
    captured_at: datetime | None = Form(
        default=None,
    ),
    latitude: float | None = Form(
        default=None,
    ),
    longitude: float | None = Form(
        default=None,
    ),
    location_accuracy_m: float | None = Form(
        default=None,
    ),
    location_source: str | None = Form(
        default=None,
    ),
    inspection_session_id: str | None = Form(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    content = await file.read()

    service = DocumentService(db)

    try:
        result = service.store_document(
            content=content,
            original_filename=(
                file.filename
                or "document.bin"
            ),
            content_type=(
                file.content_type
                or "application/octet-stream"
            ),
            source_type=source_type,
            external_id=external_id,
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            candidate_id=candidate_id,
            client_id=client_id,
            captured_at=captured_at,
            latitude=latitude,
            longitude=longitude,
            location_accuracy_m=location_accuracy_m,
            location_source=location_source,
            inspection_session_id=inspection_session_id,
        )

        return DocumentUploadResponse(
            document=DocumentRead.model_validate(
                result.document,
            ),
            created=result.created,
            matched_by=result.matched_by,
        )

    except (
        EmptyDocumentError,
        InvalidDocumentSourceTypeError,
        MissingLocationMetadataError,
        InvalidLocationMetadataError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    except DocumentStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
