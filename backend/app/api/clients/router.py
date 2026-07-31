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
    ClientRead,
    ClientUpdate,
)
from app.schemas.industry import IndustryRead
from app.repositories.industry_repository import IndustryRepository
from app.services.client_service import (
    ClientNotFoundError,
    ClientService,
    DuplicateTaxIdError,
    IndustryNotFoundError,
)

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
    )


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