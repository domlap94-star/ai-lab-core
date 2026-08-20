from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.work_item import AbsenceCreate, AbsencePage, AbsenceRead, AbsenceReview, AbsenceStatus, AbsenceUpdate, VersionRequest
from app.services.work_item_service import AbsenceAuthorizationError, AbsenceOverlapError, AbsenceService, WorkItemConflictError, WorkItemNotFoundError

router = APIRouter(prefix="/absence-requests", tags=["Absence Requests"])

def _http(error):
    if isinstance(error, WorkItemNotFoundError): return HTTPException(404, "absence_not_found")
    if isinstance(error, AbsenceAuthorizationError): return HTTPException(403, "absence_action_forbidden")
    if isinstance(error, (AbsenceOverlapError, WorkItemConflictError)): return HTTPException(409, str(error))
    return HTTPException(422, str(error))

@router.get("", response_model=AbsencePage)
def list_absences(absence_status: AbsenceStatus | None = Query(None, alias="status"), requester_user_id: int | None = None, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return AbsenceService(db).list(user, status=absence_status, requester_user_id=requester_user_id, skip=skip, limit=limit)

@router.post("", response_model=AbsenceRead, status_code=201)
def create_absence(data: AbsenceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return AbsenceService(db).create(data, user)
    except AbsenceOverlapError as error: raise _http(error) from error

@router.get("/{absence_id}", response_model=AbsenceRead)
def get_absence(absence_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return AbsenceService(db).get(absence_id, user)
    except (WorkItemNotFoundError, AbsenceAuthorizationError) as error: raise _http(error) from error

@router.patch("/{absence_id}", response_model=AbsenceRead)
def update_absence(absence_id: int, data: AbsenceUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return AbsenceService(db).update(absence_id, data, user)
    except (WorkItemNotFoundError, AbsenceAuthorizationError, AbsenceOverlapError, WorkItemConflictError) as error: raise _http(error) from error

@router.post("/{absence_id}/approve", response_model=AbsenceRead)
def approve(absence_id: int, data: AbsenceReview, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return AbsenceService(db).review(absence_id, data.expected_version, data.review_note, user, approved=True)
    except (WorkItemNotFoundError, AbsenceAuthorizationError, AbsenceOverlapError, WorkItemConflictError) as error: raise _http(error) from error

@router.post("/{absence_id}/reject", response_model=AbsenceRead)
def reject(absence_id: int, data: AbsenceReview, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return AbsenceService(db).review(absence_id, data.expected_version, data.review_note, user, approved=False)
    except (WorkItemNotFoundError, AbsenceAuthorizationError, WorkItemConflictError) as error: raise _http(error) from error

@router.post("/{absence_id}/cancel", response_model=AbsenceRead)
def cancel(absence_id: int, data: VersionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try: return AbsenceService(db).cancel(absence_id, data.expected_version, user)
    except (WorkItemNotFoundError, AbsenceAuthorizationError, WorkItemConflictError) as error: raise _http(error) from error
