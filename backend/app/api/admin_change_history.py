from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.admin_users import require_admin
from app.database.session import get_db
from app.models.user import User
from app.schemas.change_history import ChangeHistoryPage
from app.services.change_history_query_service import ChangeHistoryQueryService


router = APIRouter(prefix="/admin/change-history", tags=["Admin Change History"])


@router.get("", response_model=ChangeHistoryPage)
def get_change_history(
    entity_type: str | None = Query(default=None, max_length=64),
    entity_id: int | None = Query(default=None, ge=1),
    actor_user_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, max_length=32),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ChangeHistoryPage:
    return ChangeHistoryQueryService(db).get_page(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
