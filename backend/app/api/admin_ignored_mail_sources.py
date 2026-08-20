from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.admin_users import require_admin
from app.database.session import get_db
from app.models.user import User
from app.schemas.ignored_mail_source import IgnoredMailSourceCreate, IgnoredMailSourceRead
from app.services.ignored_mail_source_service import (
    IgnoredMailSourceNotFoundError,
    IgnoredMailSourceService,
    IgnoredMailSourceValidationError,
)


router = APIRouter(prefix="/admin/ignored-mail-sources", tags=["Admin Ignored Mail Sources"])


@router.get("", response_model=list[IgnoredMailSourceRead])
def list_ignored_mail_sources(
    include_inactive: bool = Query(default=False),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return IgnoredMailSourceService(db).list(include_inactive=include_inactive)


@router.post("", response_model=IgnoredMailSourceRead)
def ignore_mail_source(
    request: IgnoredMailSourceCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        rule = IgnoredMailSourceService(db).ignore(
            rule_type=request.rule_type,
            value=request.value,
            actor_user_id=actor.id,
        )
        db.commit()
        db.refresh(rule)
        return rule
    except IgnoredMailSourceValidationError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": str(error)}) from error
    except Exception:
        db.rollback()
        raise


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def unignore_mail_source(
    rule_id: int,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        IgnoredMailSourceService(db).unignore(rule_id=rule_id, actor_user_id=actor.id)
        db.commit()
    except IgnoredMailSourceNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail={"code": str(error)}) from error
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
