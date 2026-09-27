from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.client import Client
from app.models.client_access_grant import ClientAccessGrant
from app.models.role import Role
from app.models.user import User
from app.schemas.client_access_grant import (
    ClientAccessGrantCreate,
    ClientAccessGrantPage,
    ClientAccessGrantRead,
    ClientAccessManagerOptions,
    ClientAccessOption,
    ExternalUserOption,
    SharedClientRead,
)
from app.services.client_access_grant_service import ClientAccessGrantService, GrantValidationError
from app.services.client_scope_service import ClientScopeService


router = APIRouter(prefix="/client-access", tags=["Client access"])


def _manager(user: User = Depends(get_current_user)) -> User:
    try:
        ClientAccessGrantService.require_manager(user)
    except GrantValidationError as error:
        raise HTTPException(status_code=403, detail="Grant management unavailable") from error
    return user


@router.get("/shared-clients", response_model=list[SharedClientRead])
def shared_clients(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SharedClientRead]:
    if not ClientScopeService.is_external(user):
        raise HTTPException(status_code=403, detail="External role required")
    rows = db.query(Client, ClientAccessGrant.granted_at).join(
        ClientAccessGrant, ClientAccessGrant.client_id == Client.id
    ).filter(
        ClientAccessGrant.external_user_id == user.id,
        ClientAccessGrant.revoked_at.is_(None),
        Client.deleted_at.is_(None),
    ).order_by(Client.name, Client.id).all()
    return [SharedClientRead(id=client.id, name=client.name, granted_at=granted_at) for client, granted_at in rows]


@router.get("/grants", response_model=ClientAccessGrantPage)
def list_grants(
    client_id: int | None = Query(default=None, gt=0),
    external_user_id: int | None = Query(default=None, gt=0),
    active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> ClientAccessGrantPage:
    items, total = ClientAccessGrantService(db).page(
        client_id=client_id, external_user_id=external_user_id, active=active, skip=skip, limit=limit
    )
    return ClientAccessGrantPage(items=items, total=total, skip=skip, limit=limit)


@router.get("/manager-options", response_model=ClientAccessManagerOptions)
def manager_options(
    _: User = Depends(_manager), db: Session = Depends(get_db)
) -> ClientAccessManagerOptions:
    clients = db.query(Client.id, Client.name).filter(
        Client.deleted_at.is_(None)
    ).order_by(Client.name, Client.id).all()
    external_users = db.query(User.id, User.username).join(
        Role, Role.id == User.role_id
    ).filter(
        Role.name == "External",
        User.is_active.is_(True),
        User.trashed_at.is_(None),
        User.purged_at.is_(None),
    ).order_by(User.username, User.id).all()
    return ClientAccessManagerOptions(
        clients=[ClientAccessOption(id=row.id, name=row.name) for row in clients],
        external_users=[
            ExternalUserOption(id=row.id, username=row.username)
            for row in external_users
        ],
    )


@router.post("/grants", response_model=ClientAccessGrantRead, status_code=201)
def grant(
    data: ClientAccessGrantCreate,
    actor: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> ClientAccessGrantRead:
    try:
        return ClientAccessGrantService(db).grant(
            client_id=data.client_id, external_user_id=data.external_user_id, actor=actor
        )
    except GrantValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/grants", status_code=204)
def revoke(
    client_id: int = Query(gt=0),
    external_user_id: int = Query(gt=0),
    actor: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> Response:
    ClientAccessGrantService(db).revoke(
        client_id=client_id, external_user_id=external_user_id, actor=actor
    )
    return Response(status_code=204)
