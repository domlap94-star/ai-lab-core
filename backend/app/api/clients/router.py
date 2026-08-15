from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.client import (
    ClientCreate,
    ClientPage,
    ClientPageSortOrder,
    ClientRead,
    ClientType,
    ClientUpdate,
)
from app.schemas.client_email import ClientEmailPage
from app.schemas.industry import IndustryRead
from app.repositories.industry_repository import IndustryRepository
from app.services.client_service import (
    ClientNotFoundError,
    ClientService,
    DuplicateTaxIdError,
    IndustryNotFoundError,
)
from app.services.client_email_service import ClientEmailService

router = APIRouter(
    prefix="/clients",
    tags=["Clients"],
    dependencies=[
        Depends(get_current_user),
    ],
)


@router.get(
    "/industries",
    response_model=list[IndustryRead],
)
def get_industries(
    db: Session = Depends(get_db),
) -> list[IndustryRead]:
    repository = IndustryRepository(db)
    return repository.get_all_active()


@router.post(
    "",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
) -> ClientRead:
    service = ClientService(db)

    try:
        return service.create_client(data)

    except IndustryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected industry does not exist or is inactive",
        ) from error

    except DuplicateTaxIdError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active client with this tax ID already exists",
        ) from error


@router.get(
    "/page",
    response_model=ClientPage,
)
def get_clients_page(
    search: str | None = Query(
        default=None,
        max_length=255,
    ),
    client_type: ClientType | None = Query(default=None),
    industry_id: int | None = Query(default=None, ge=1),
    sort_order: ClientPageSortOrder = Query(default="newest"),
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
) -> ClientPage:
    service = ClientService(db)

    return service.get_clients(
        search=search,
        client_type=client_type,
        industry_id=industry_id,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )


@router.get(
    "",
    response_model=list[ClientRead],
)
def get_clients(
    search: str | None = Query(
        default=None,
        max_length=255,
    ),
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
) -> list[ClientRead]:
    service = ClientService(db)

    return service.get_clients(
        search=search,
        skip=skip,
        limit=limit,
    ).items


@router.get(
    "/{client_id}/emails",
    response_model=ClientEmailPage,
)
def get_client_emails(
    client_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ClientEmailPage:
    try:
        return ClientEmailService(db).get_emails(
            client_id=client_id,
            skip=skip,
            limit=limit,
        )
    except ClientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        ) from error


@router.get(
    "/{client_id}",
    response_model=ClientRead,
)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
) -> ClientRead:
    service = ClientService(db)

    try:
        return service.get_client(client_id)

    except ClientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        ) from error


@router.patch(
    "/{client_id}",
    response_model=ClientRead,
)
def update_client(
    client_id: int,
    data: ClientUpdate,
    db: Session = Depends(get_db),
) -> ClientRead:
    service = ClientService(db)

    try:
        return service.update_client(
            client_id,
            data,
        )

    except ClientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        ) from error

    except IndustryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected industry does not exist or is inactive",
        ) from error

    except DuplicateTaxIdError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active client with this tax ID already exists",
        ) from error


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
) -> Response:
    service = ClientService(db)

    try:
        service.delete_client(client_id)

    except ClientNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        ) from error

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
