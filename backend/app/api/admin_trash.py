from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin_users import require_admin
from app.database.session import get_db
from app.models.user import User
from app.schemas.trash import TrashEntityType, TrashEntryRead, TrashPage, TrashState
from app.services.trash_lifecycle_service import (
    TrashAuthorizationError,
    TrashConflictError,
    TrashLifecycleService,
    TrashNotFoundError,
)


router = APIRouter(prefix="/admin/trash", tags=["Admin Trash"])


def trash_error(error: Exception) -> HTTPException:
    if isinstance(error, TrashNotFoundError):
        return HTTPException(status_code=404, detail={"code": str(error)})
    if isinstance(error, TrashAuthorizationError):
        return HTTPException(status_code=403, detail={"code": "administrator_required"})
    return HTTPException(status_code=409, detail={"code": str(error)})


@router.get("", response_model=TrashPage)
def list_trash(
    entity_type: TrashEntityType | None = None,
    state_filter: TrashState | None = Query(None, alias="state"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TrashPage:
    items, total = TrashLifecycleService(db).list_entries(
        entity_type=entity_type, state=state_filter, skip=skip, limit=limit
    )
    return TrashPage(items=items, total=total, skip=skip, limit=limit)


@router.post("/{entry_id}/restore", response_model=TrashEntryRead)
def restore_trash(
    entry_id: int,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TrashEntryRead:
    try:
        entry = TrashLifecycleService(db).restore(entry_id=entry_id, actor=actor)
        db.commit()
        db.refresh(entry)
        return TrashEntryRead.model_validate(entry)
    except (TrashNotFoundError, TrashAuthorizationError, TrashConflictError) as error:
        db.rollback()
        raise trash_error(error) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "restore_identity_conflict"},
        ) from error
    except Exception:
        db.rollback()
        raise
