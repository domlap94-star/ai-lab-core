from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.client import Client
from app.models.document import Document
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.client_scope_service import ClientScopeNotFound, ClientScopeService


def scope_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


def require_non_external(current_user: User = Depends(get_current_user)) -> User:
    if ClientScopeService.is_external(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation unavailable")
    return current_user


def guard_path_resource(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Guard canonical ID path parameters before endpoint logic executes."""
    if not ClientScopeService.is_external(current_user):
        return
    mapping = (
        ("client_id", Client),
        ("project_id", Project),
        ("inspection_id", Inspection),
        ("document_id", Document),
        ("item_id", WorkItem),
        ("work_item_id", WorkItem),
    )
    policy = ClientScopeService(db)
    for parameter, model in mapping:
        raw = request.path_params.get(parameter)
        if raw is None:
            continue
        try:
            object_id = int(raw)
        except (TypeError, ValueError):
            raise scope_not_found()
        resource = db.query(model).filter(model.id == object_id).first()
        try:
            if resource is None:
                raise ClientScopeNotFound
            policy.require_resource_access(current_user, resource)
        except ClientScopeNotFound as error:
            raise scope_not_found() from error
