from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

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
from app.schemas.business_assistant import BusinessAskRequest, BusinessAskResponse
from app.services.business_assistant_service import (
    BusinessAssistantModelUnavailable,
    BusinessAssistantService,
)
from app.schemas.technical_ai import TechnicalAskRequest, TechnicalAskResponse
from app.schemas.agent import AgentAskRequest, AgentAskResponse
from app.services.agent_service import (
    AgentContextMismatch,
    AgentContextNotFound,
    AgentModelUnavailable,
    AgentService,
)
from app.services.technical_ai_service import (
    TechnicalAiModelUnavailable, TechnicalAiService,
    TechnicalContextMismatch, TechnicalContextNotFound,
)
from app.schemas.unified_assistant import UnifiedAssistantRequest, UnifiedAssistantResponse
from app.services.unified_assistant_service import (
    UnifiedAssistantContextError, UnifiedAssistantModelUnavailable,
    UnifiedAssistantService,
)
from app.schemas.assistant_pipeline import (
    AssistantRunCreateRequest,
    AssistantRunListResponse,
    AssistantRunResponse,
)
from app.services.assistant_run_planner import AssistantRunScopeError
from app.services.assistant_run_service import (
    AssistantRunActiveConflict,
    AssistantPipelineDisabled,
    AssistantRunIdempotencyConflict,
    AssistantRunNotFound,
    AssistantRunService,
)

router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


@router.post("/assistant/ask", response_model=UnifiedAssistantResponse)
async def ask_unified_assistant(
    request: UnifiedAssistantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnifiedAssistantResponse:
    try:
        return await UnifiedAssistantService(
            db, release_db_before_model=True
        ).ask(request=request, user_id=current_user.id)
    except UnifiedAssistantContextError as error:
        raise HTTPException(status_code=422, detail="Wskazany kontekst nie należy do bieżącego zakresu.") from error
    except UnifiedAssistantModelUnavailable as error:
        raise HTTPException(status_code=503, detail="Asystent AI jest chwilowo niedostępny. Spróbuj ponownie.") from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Nie udało się odczytać danych CRM. Spróbuj ponownie.") from error


@router.post(
    "/assistant/runs",
    response_model=AssistantRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_assistant_run(
    request: AssistantRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantRunResponse:
    try:
        return AssistantRunService(db).create(request=request, user_id=current_user.id)
    except AssistantPipelineDisabled as error:
        raise HTTPException(status_code=404, detail="Durable Assistant API is not enabled.") from error
    except AssistantRunScopeError as error:
        raise HTTPException(status_code=422, detail="Wskazany kontekst nie należy do bieżącego zakresu.") from error
    except AssistantRunIdempotencyConflict as error:
        raise HTTPException(status_code=409, detail="Identyfikator próby został już użyty dla innego żądania.") from error
    except AssistantRunActiveConflict as error:
        raise HTTPException(
            status_code=409,
            detail="Masz już aktywną analizę. Otwórz ją lub anuluj przed rozpoczęciem następnej.",
        ) from error


@router.get("/assistant/runs", response_model=AssistantRunListResponse)
def list_assistant_runs(
    active: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantRunListResponse:
    try:
        return AssistantRunService(db).list_owned(
            user_id=current_user.id, active=active, limit=limit
        )
    except AssistantPipelineDisabled as error:
        raise HTTPException(status_code=404, detail="Durable Assistant API is not enabled.") from error


@router.get("/assistant/runs/{run_id}", response_model=AssistantRunResponse)
def get_assistant_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantRunResponse:
    try:
        return AssistantRunService(db).get(run_id=run_id, user_id=current_user.id)
    except AssistantPipelineDisabled as error:
        raise HTTPException(status_code=404, detail="Durable Assistant API is not enabled.") from error
    except AssistantRunNotFound as error:
        raise HTTPException(status_code=404, detail="Nie znaleziono analizy.") from error


@router.post("/assistant/runs/{run_id}/cancel", response_model=AssistantRunResponse)
def cancel_assistant_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantRunResponse:
    try:
        return AssistantRunService(db).cancel(run_id=run_id, user_id=current_user.id)
    except AssistantPipelineDisabled as error:
        raise HTTPException(status_code=404, detail="Durable Assistant API is not enabled.") from error
    except AssistantRunNotFound as error:
        raise HTTPException(status_code=404, detail="Nie znaleziono analizy.") from error


@router.post("/assistant/{request_id}/cancel", response_model=UnifiedAssistantResponse)
async def cancel_unified_assistant(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnifiedAssistantResponse:
    try:
        return await UnifiedAssistantService(db).cancel(
            request_id=request_id, user_id=current_user.id
        )
    except UnifiedAssistantContextError as error:
        raise HTTPException(status_code=404, detail="Nie znaleziono aktywnej analizy.") from error


@router.get("/assistant/{request_id}", response_model=UnifiedAssistantResponse)
async def get_unified_assistant_status(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnifiedAssistantResponse:
    try:
        return await UnifiedAssistantService(db).status(request_id=request_id, user_id=current_user.id)
    except UnifiedAssistantContextError as error:
        raise HTTPException(status_code=404, detail="Nie znaleziono aktywnej analizy.") from error


@router.post("/agent/ask", response_model=AgentAskResponse)
async def ask_agent(
    request: AgentAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentAskResponse:
    try:
        return await AgentService(db).ask(
            question=request.question,
            user_id=current_user.id,
            client_id=request.client_id,
            inspection_id=request.inspection_id,
            conversation=request.conversation,
        )
    except AgentContextNotFound as error:
        raise HTTPException(status_code=404, detail="Nie znaleziono wskazanej wizji lokalnej.") from error
    except AgentContextMismatch as error:
        raise HTTPException(status_code=422, detail="Wizja lokalna nie należy do wskazanego klienta.") from error
    except AgentModelUnavailable as error:
        raise HTTPException(status_code=503, detail="Agent AI jest chwilowo niedostępny. Spróbuj ponownie.") from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Nie udało się odczytać danych CRM. Spróbuj ponownie.") from error


@router.post("/business/ask", response_model=BusinessAskResponse)
async def ask_business_assistant(
    request: BusinessAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BusinessAskResponse:
    del current_user
    try:
        return await BusinessAssistantService(db).ask(
            question=request.question,
            conversation=request.conversation,
        )
    except BusinessAssistantModelUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asystent AI jest chwilowo niedostępny. Spróbuj ponownie.",
        ) from error


@router.post("/technical/ask", response_model=TechnicalAskResponse)
async def ask_technical_assistant(
    request: TechnicalAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TechnicalAskResponse:
    del current_user
    try:
        return await TechnicalAiService(db).ask(
            question=request.question,
            client_id=request.client_id,
            inspection_id=request.inspection_id,
            conversation=request.conversation,
        )
    except TechnicalContextNotFound as error:
        raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego kontekstu technicznego.") from error
    except TechnicalContextMismatch as error:
        raise HTTPException(status_code=422, detail="Wizja lokalna nie należy do wskazanego klienta.") from error
    except TechnicalAiModelUnavailable as error:
        raise HTTPException(status_code=503, detail="Asystent AI jest chwilowo niedostępny. Spróbuj ponownie.") from error


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
            detail="Asystent AI jest chwilowo niedostępny. Spróbuj ponownie.",
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
            detail="Wyszukiwanie AI jest chwilowo niedostępne. Spróbuj ponownie.",
        ) from exc
