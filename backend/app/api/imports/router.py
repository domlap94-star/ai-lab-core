from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.import_ingest import (
    ImportIngestRequest,
    ImportIngestResponse,
)
from app.services.import_ingest_service import (
    ImportIngestService,
    ImportRunNotFoundError,
    ImportRunSourceMismatchError,
    ImportSourceDisabledError,
    ImportSourceNotFoundError,
)

router = APIRouter(
    prefix="/import",
    tags=["Import"],
)


@router.post(
    "/ingest",
    response_model=ImportIngestResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_import_record(
    request: ImportIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportIngestResponse:
    del current_user

    service = ImportIngestService(db)

    try:
        return service.ingest(request)

    except ImportSourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import source not found",
        ) from error

    except ImportSourceDisabledError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import source is disabled",
        ) from error

    except ImportRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import run not found",
        ) from error

    except ImportRunSourceMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import run does not belong to the selected source",
        ) from error

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The source record has already been imported",
        ) from error