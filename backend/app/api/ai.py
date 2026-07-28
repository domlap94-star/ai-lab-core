from fastapi import APIRouter, HTTPException

from app.ai.schemas.chat_request import ChatRequest
from app.ai.schemas.chat_response import ChatResponse
from app.ai.services.chat_service import ChatService

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(request: ChatRequest):

    try:
        service = ChatService()

        return await service.chat(
            model=request.model,
            message=request.message,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )