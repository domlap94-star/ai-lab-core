from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.ai.schemas.chat_request import ChatRequest
from app.ai.schemas.chat_response import ChatResponse
from app.ai.schemas.rag_request import RagRequest
from app.ai.schemas.rag_response import (
    RagApiResponse,
    RagClaimResponse,
    RagEvidenceResponse,
    RagSourceResponse,
)
from app.ai.services.chat_service import ChatService
from app.ai.services.rag_service import RagService
from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        service = ChatService(db)

        return await service.chat(
            user_id=current_user.id,
            model=request.model,
            message=request.message,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post(
    "/rag",
    response_model=RagApiResponse,
)
async def rag(
    request: RagRequest,
    current_user: User = Depends(get_current_user),
) -> RagApiResponse:
    del current_user

    try:
        service = RagService()

        result = await service.answer(
            question=request.question,
            model=request.model,
            retrieval_limit=request.retrieval_limit,
            client_id=request.client_id,
            document_id=request.document_id,
            content_type=request.content_type,
            score_threshold=request.score_threshold,
        )

        return RagApiResponse(
            question=result.question,
            answer=result.answer,
            model=result.model,
            sources=[
                RagSourceResponse(
                    source_number=item.source_number,
                    score=item.score,
                    document_id=item.document_id,
                    chunk_id=item.chunk_id,
                    chunk_index=item.chunk_index,
                    filename=item.filename,
                    page_from=item.page_from,
                    page_to=item.page_to,
                    client_id=item.client_id,
                    content_source=item.content_source,
                    fragment=item.fragment,
                )
                for item in result.sources
            ],
            evidence=[
                RagEvidenceResponse(
                    evidence_id=item.evidence_id,
                    source_number=item.source_number,
                    text=item.text,
                )
                for item in result.evidence
            ],
            claims=[
                RagClaimResponse(
                    evidence_id=item.evidence_id,
                    source_number=item.source_number,
                    quote=item.quote,
                )
                for item in result.claims
            ],
            cited_source_numbers=(
                result.cited_source_numbers
            ),
            generation_attempts=(
                result.generation_attempts
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
