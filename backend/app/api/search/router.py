from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.schemas.search import GlobalSearchPage
from app.services.global_search_service import (
    GlobalSearchService,
    SearchTypeError,
)


router = APIRouter(
    prefix="/search",
    tags=["Search"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=GlobalSearchPage)
def global_search(
    q: str = Query(min_length=2, max_length=200),
    types: str | None = Query(default=None, max_length=200),
    skip: int = Query(default=0, ge=0, le=500),
    limit: int = Query(default=25, ge=1, le=50),
    semantic: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> GlobalSearchPage:
    try:
        requested_types = GlobalSearchService.parse_types(types)
    except SearchTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return GlobalSearchService(db).search(
        query=q,
        types=requested_types,
        skip=skip,
        limit=limit,
        semantic=semantic,
    )
