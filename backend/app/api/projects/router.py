from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectPage, ProjectRead, ProjectStatus, ProjectUpdate
from app.services.project_service import ProjectClientNotFoundError, ProjectNotFoundError, ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


def _error(error: Exception) -> HTTPException:
    if isinstance(error, ProjectNotFoundError):
        return HTTPException(status_code=404, detail="Project not found")
    return HTTPException(status_code=422, detail="Client does not exist or is inactive")


@router.get("", response_model=ProjectPage)
def list_projects(search: str | None = Query(default=None), client_id: int | None = Query(default=None), project_status: ProjectStatus | None = Query(default=None, alias="status"), skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProjectPage:
    return ProjectService(db).get_page(search=search, client_id=client_id, status=project_status, skip=skip, limit=limit)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProjectRead:
    try:
        return ProjectService(db).get(project_id)
    except ProjectNotFoundError as error:
        raise _error(error) from error


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProjectRead:
    try:
        return ProjectService(db).create(data, current_user)
    except ProjectClientNotFoundError as error:
        raise _error(error) from error


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, data: ProjectUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProjectRead:
    try:
        return ProjectService(db).update(project_id, data, current_user)
    except (ProjectNotFoundError, ProjectClientNotFoundError) as error:
        raise _error(error) from error


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    try:
        ProjectService(db).delete(project_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as error:
        raise _error(error) from error
