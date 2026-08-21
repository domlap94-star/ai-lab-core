import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.admin_users import require_admin
from app.database.session import get_db
from app.models.user import User
from app.schemas.knowledge_base import KnowledgeBaseItemRead, KnowledgeBaseMetadata, KnowledgeBasePageResult, KnowledgeBasePatch, KnowledgeBaseSearchResult, KnowledgeBaseUploadResponse
from app.services.knowledge_base_service import KnowledgeBaseError, KnowledgeBaseService

router = APIRouter(prefix="/admin/knowledge-base", tags=["Admin Knowledge Base"])


def mapped(error: KnowledgeBaseError) -> HTTPException:
    code = str(error); return HTTPException(status_code=404 if code.endswith("not_found") else 422, detail={"code": code})


@router.get("", response_model=KnowledgeBasePageResult)
def list_items(q: str | None = Query(None, max_length=255), category: str | None = None, item_status: str | None = Query(None, alias="status"), publisher: str | None = Query(None, max_length=255), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    items, total = KnowledgeBaseService(db).list(query=q, category=category, status=item_status, publisher=publisher, skip=skip, limit=limit)
    return KnowledgeBasePageResult(items=items, total=total, skip=skip, limit=limit)


@router.get("/search", response_model=list[KnowledgeBaseSearchResult])
def search(q: str = Query(..., min_length=2, max_length=255), limit: int = Query(20, ge=1, le=50), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return KnowledgeBaseService(db).search(q, limit)


@router.post("", response_model=KnowledgeBaseUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_item(metadata_json: str = Form(...), file: UploadFile = File(...), actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        metadata = KnowledgeBaseMetadata.model_validate(json.loads(metadata_json)); content = await file.read()
        item, duplicates = KnowledgeBaseService(db).create(metadata=metadata, filename=file.filename or "material", content_type=file.content_type or "application/octet-stream", content=content, actor=actor)
        return KnowledgeBaseUploadResponse(item=item, duplicate_checksum_item_ids=duplicates)
    except (KnowledgeBaseError, ValueError, json.JSONDecodeError) as error:
        db.rollback(); raise mapped(KnowledgeBaseError(str(error))) from error


@router.get("/{item_id}", response_model=KnowledgeBaseItemRead)
def detail(item_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    try: return KnowledgeBaseService(db).get(item_id)
    except KnowledgeBaseError as error: raise mapped(error) from error


@router.patch("/{item_id}", response_model=KnowledgeBaseItemRead)
def update(item_id: int, patch: KnowledgeBasePatch, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    service = KnowledgeBaseService(db)
    try: return service.update(service.get(item_id), patch, actor)
    except KnowledgeBaseError as error: db.rollback(); raise mapped(error) from error


@router.post("/{item_id}/retry", response_model=KnowledgeBaseItemRead)
def retry(item_id: int, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    service = KnowledgeBaseService(db)
    try: return service.process(service.get(item_id), actor=actor)
    except KnowledgeBaseError as error: db.rollback(); raise mapped(error) from error


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive(item_id: int, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    service = KnowledgeBaseService(db)
    try:
        service.archive(service.get(item_id), actor)
    except KnowledgeBaseError as error:
        db.rollback()
        raise mapped(error) from error
