from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.work_item import CalendarMonth
from app.services.work_item_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["Calendar"])

@router.get("/month", response_model=CalendarMonth)
def month(year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return CalendarService(db).month(year, month, user)
