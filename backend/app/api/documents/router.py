from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.imports.dependencies import require_import_api_key
from app.database.session import get_db
from app.schemas.document import (
    DocumentRead,
    DocumentUploadResponse,
)
from app.services.document_service import (
    DocumentService,
    DocumentStorageError,
    EmptyDocumentError,
    InvalidDocumentSourceTypeError,
    InvalidLocationMetadataError,
    MissingLocationMetadataError,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


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