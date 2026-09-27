from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.client_scope import guard_path_resource, scope_not_found
from app.database.session import get_db
from app.models.user import User
from app.schemas.inspection import (
    InspectionCreate,
    InspectionPage,
    InspectionRead,
    InspectionStatus,
    InspectionUpdate,
)
from app.services.inspection_service import (
    InspectionClientNotFoundError,
    InspectionDateRequiredError,
    InspectionNotFoundError,
    InspectionService,
)
from app.services.client_scope_service import ClientScopeNotFound, ClientScopeService

router = APIRouter(prefix="/inspections", tags=["Inspections"], dependencies=[Depends(guard_path_resource)])


def _error(error: Exception) -> HTTPException:
    if isinstance(error, InspectionNotFoundError):
        return HTTPException(status_code=404, detail="Inspection not found")
    return HTTPException(status_code=422, detail="Client does not exist or is inactive")


@router.get("", response_model=InspectionPage)
def list_inspections(
    search: str | None = Query(default=None),
    project_id: int | None = Query(default=None, ge=1),
    client_id: int | None = Query(default=None, ge=1),
    inspection_status: InspectionStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InspectionPage:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to cannot precede date_from")
    return InspectionService(db).get_page(
        search=search,
        project_id=project_id,
        client_id=client_id,
        status=inspection_status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
        viewer=current_user,
    )


@router.get("/{inspection_id}", response_model=InspectionRead)
def get_inspection(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InspectionRead:
    try:
        return InspectionService(db).get(inspection_id, viewer=current_user)
    except InspectionNotFoundError as error:
        raise _error(error) from error


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def create_inspection(
    data: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InspectionRead:
    try:
        ClientScopeService(db).require_client_access(current_user, data.client_id)
        return InspectionService(db).create(data, current_user)
    except ClientScopeNotFound as error:
        raise scope_not_found() from error
    except InspectionClientNotFoundError as error:
        raise _error(error) from error


@router.patch("/{inspection_id}", response_model=InspectionRead)
def update_inspection(
    inspection_id: int,
    data: InspectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InspectionRead:
    try:
        if "client_id" in data.model_fields_set:
            ClientScopeService(db).require_client_access(current_user, data.client_id)
        return InspectionService(db).update(inspection_id, data, current_user)
    except ClientScopeNotFound as error:
        raise scope_not_found() from error
    except (
        InspectionNotFoundError,
        InspectionClientNotFoundError,
    ) as error:
        raise _error(error) from error
    except InspectionDateRequiredError as error:
        raise HTTPException(status_code=422, detail="scheduled_date is required") from error


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspection(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        InspectionService(db).delete(inspection_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except InspectionNotFoundError as error:
        raise _error(error) from error
