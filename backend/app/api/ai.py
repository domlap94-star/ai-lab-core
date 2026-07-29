from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.schemas.chat_request import ChatRequest
from app.ai.schemas.chat_response import ChatResponse
from app.ai.services.chat_service import ChatService
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