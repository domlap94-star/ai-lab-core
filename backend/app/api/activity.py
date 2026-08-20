from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.recent_activity import RecentActivityPage
from app.services.recent_activity_service import RecentActivityService


router = APIRouter(prefix="/activity", tags=["Activity"])


@router.get("/recent", response_model=RecentActivityPage)
def recent_activity(
    skip: int = Query(default=0, ge=0, le=RecentActivityService.MAX_SKIP),
    limit: int = Query(default=8, ge=1, le=RecentActivityService.MAX_LIMIT),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecentActivityPage:
    return RecentActivityService(db).get_page(
        viewer=current_user,
        skip=skip,
        limit=limit,
    )
