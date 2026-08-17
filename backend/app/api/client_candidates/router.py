from __future__ import annotations

from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.schemas.client_candidate_review import (
    CandidateAcceptResponse,
    CandidateBulkAcceptItem,
    CandidateBulkAcceptRequest,
    CandidateBulkAcceptResponse,
    CandidateRejectResponse,
    ClientCandidateContextResponse,
    ClientCandidateListItem,
)
from app.services.client_candidate_promotion_service import (
    CandidateAlreadyMatchedError,
    CandidateDuplicateClientError,
    CandidateNotFoundError,
    CandidateNotPendingError,
    CandidatePromotionError,
)
from app.services.client_candidate_review_service import (
    CandidateReviewInvalidStateError,
    CandidateReviewNotFoundError,
    ClientCandidateReviewService,
)


router = APIRouter(
    prefix="/client-candidates",
    tags=["Client Candidates"],
    dependencies=[
        Depends(get_current_user),
    ],
)


@router.post("/bulk-accept", response_model=CandidateBulkAcceptResponse)
def bulk_accept_client_candidates(
    data: CandidateBulkAcceptRequest,
    db: Session = Depends(get_db),
) -> CandidateBulkAcceptResponse:
    service = ClientCandidateReviewService(db)
    results: list[CandidateBulkAcceptItem] = []
    for candidate_id in data.candidate_ids:
        try:
            client = service.accept_candidate(candidate_id)
            results.append(CandidateBulkAcceptItem(
                candidate_id=candidate_id, result="promoted", client_id=client.id
            ))
        except CandidateDuplicateClientError as error:
            results.append(CandidateBulkAcceptItem(
                candidate_id=candidate_id, result="duplicate",
                client_id=error.client_id, message=f"duplicate:{error.matched_by}",
            ))
        except CandidateNotFoundError:
            results.append(CandidateBulkAcceptItem(candidate_id=candidate_id, result="not_found"))
        except (CandidateNotPendingError, CandidateAlreadyMatchedError) as error:
            results.append(CandidateBulkAcceptItem(
                candidate_id=candidate_id, result="conflict", message=str(error)
            ))
        except CandidatePromotionError as error:
            results.append(CandidateBulkAcceptItem(
                candidate_id=candidate_id, result="failed", message=str(error)
            ))
    promoted = sum(item.result == "promoted" for item in results)
    return CandidateBulkAcceptResponse(
        requested=len(data.candidate_ids), promoted=promoted,
        failed=len(results) - promoted, results=results,
    )


@router.get(
    "",
    response_model=list[
        ClientCandidateListItem
    ],
)
def get_client_candidates(
    candidate_status: Literal[
        "pending",
        "accepted",
        "rejected",
        "merged",
        "duplicate",
    ]
    | None = Query(
        default="pending",
        alias="status",
    ),
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
) -> list[ClientCandidateListItem]:
    service = ClientCandidateReviewService(
        db
    )

    return service.get_candidates(
        status=candidate_status,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{candidate_id}",
    response_model=(
        ClientCandidateContextResponse
    ),
)
def get_client_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> ClientCandidateContextResponse:
    service = ClientCandidateReviewService(
        db
    )

    try:
        return service.get_candidate_context(
            candidate_id
        )

    except CandidateReviewNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client candidate not found",
        ) from error


@router.post(
    "/{candidate_id}/accept",
    response_model=CandidateAcceptResponse,
)
def accept_client_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> CandidateAcceptResponse:
    service = ClientCandidateReviewService(
        db
    )

    try:
        client = service.accept_candidate(
            candidate_id
        )

        return CandidateAcceptResponse(
            candidate_id=candidate_id,
            candidate_status="accepted",
            client_id=client.id,
            client_name=client.name,
        )

    except CandidateDuplicateClientError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": (
                    "candidate_matches_existing_client"
                ),
                "message": (
                    "Candidate matches an "
                    "existing client."
                ),
                "matched_client_id": (
                    error.client_id
                ),
                "matched_by": (
                    error.matched_by
                ),
            },
        ) from error

    except CandidateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client candidate not found",
        ) from error

    except (
        CandidateNotPendingError,
        CandidateAlreadyMatchedError,
        CandidatePromotionError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/{candidate_id}/reject",
    response_model=CandidateRejectResponse,
)
def reject_client_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> CandidateRejectResponse:
    service = ClientCandidateReviewService(
        db
    )

    try:
        candidate = service.reject_candidate(
            candidate_id
        )

        return CandidateRejectResponse(
            candidate_id=candidate.id,
            candidate_status=candidate.status,
        )

    except CandidateReviewNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client candidate not found",
        ) from error

    except CandidateReviewInvalidStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
