from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assistant_pipeline import AssistantRun
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.assistant_conversation import (
    AssistantConversationCreateRequest,
    AssistantConversationDeleteResponse,
    AssistantConversationDetail,
    AssistantConversationListResponse,
    AssistantConversationMessageResponse,
    AssistantConversationRenameRequest,
    AssistantConversationSummary,
)
from app.schemas.unified_assistant import UnifiedAssistantResponse, UnifiedConversationMessage


ACTIVE_RUN_STATUSES = ("created", "queued", "running", "waiting")
DEFAULT_TITLE = "Nowa rozmowa"
MAX_CONTEXT_MESSAGES = 8
MAX_CONTEXT_CHARACTERS = 6000


class AssistantConversationNotFound(RuntimeError):
    pass


class AssistantConversationService:
    """Canonical server-backed history for durable Assistant V2 runs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, *, request: AssistantConversationCreateRequest, user_id: int
    ) -> AssistantConversationDetail:
        now = datetime.now(UTC)
        conversation = Conversation(
            user_id=user_id,
            title=request.title or DEFAULT_TITLE,
            model="assistant_v2",
            kind="assistant_v2",
            last_activity_at=now,
            deleted_at=None,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return self._detail(conversation, message_limit=100)

    def list_owned(
        self, *, user_id: int, limit: int = 20
    ) -> AssistantConversationListResponse:
        bounded_limit = max(1, min(50, limit))
        preview = (
            select(Message.content)
            .where(Message.conversation_id == Conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        latest_run_id = (
            select(AssistantRun.id)
            .where(AssistantRun.conversation_id == Conversation.id)
            .order_by(AssistantRun.created_at.desc(), AssistantRun.id.desc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        latest_run_status = (
            select(AssistantRun.status)
            .where(AssistantRun.conversation_id == Conversation.id)
            .order_by(AssistantRun.created_at.desc(), AssistantRun.id.desc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        rows = (
            self.db.query(
                Conversation,
                preview.label("last_message_preview"),
                latest_run_id.label("latest_run_id"),
                latest_run_status.label("latest_run_status"),
            )
            .filter(
                Conversation.user_id == user_id,
                Conversation.kind == "assistant_v2",
                Conversation.deleted_at.is_(None),
            )
            .order_by(
                func.coalesce(
                    Conversation.last_activity_at,
                    Conversation.created_at,
                ).desc(),
                Conversation.id.desc(),
            )
            .limit(bounded_limit)
            .all()
        )
        return AssistantConversationListResponse(
            items=[
                self._summary(
                    conversation,
                    preview_value,
                    run_id,
                    run_status,
                )
                for conversation, preview_value, run_id, run_status in rows
            ]
        )

    def get_owned_detail(
        self, *, conversation_id: int, user_id: int, message_limit: int = 100
    ) -> AssistantConversationDetail:
        conversation = self.resolve_owned(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        return self._detail(conversation, message_limit=message_limit)

    def rename(
        self,
        *,
        conversation_id: int,
        user_id: int,
        request: AssistantConversationRenameRequest,
    ) -> AssistantConversationDetail:
        conversation = self.resolve_owned(
            conversation_id=conversation_id,
            user_id=user_id,
            lock=True,
        )
        conversation.title = request.title
        self.db.commit()
        self.db.refresh(conversation)
        return self._detail(conversation, message_limit=100)

    def soft_delete(
        self, *, conversation_id: int, user_id: int
    ) -> AssistantConversationDeleteResponse:
        conversation = self.resolve_owned(
            conversation_id=conversation_id,
            user_id=user_id,
            lock=True,
        )
        active = (
            self.db.query(AssistantRun)
            .filter(
                AssistantRun.conversation_id == conversation.id,
                AssistantRun.created_by_user_id == user_id,
                AssistantRun.status.in_(ACTIVE_RUN_STATUSES),
            )
            .order_by(AssistantRun.created_at.desc(), AssistantRun.id.desc())
            .first()
        )
        conversation.deleted_at = datetime.now(UTC)
        self.db.commit()
        return AssistantConversationDeleteResponse(
            id=conversation.id,
            deleted_at=conversation.deleted_at,
            active_run_id=active.id if active is not None else None,
        )

    def resolve_owned(
        self,
        *,
        conversation_id: int,
        user_id: int,
        lock: bool = False,
    ) -> Conversation:
        query = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.kind == "assistant_v2",
            Conversation.deleted_at.is_(None),
        )
        if lock:
            query = query.with_for_update()
        conversation = query.one_or_none()
        if conversation is None:
            raise AssistantConversationNotFound("ASSISTANT_CONVERSATION_NOT_FOUND")
        return conversation

    def canonical_history(
        self, *, conversation_id: int
    ) -> list[UnifiedConversationMessage]:
        rows = (
            self.db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.role.in_(("user", "assistant")),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(MAX_CONTEXT_MESSAGES)
            .all()
        )
        selected: list[Message] = []
        total = 0
        for row in rows:
            size = len(row.content)
            if total + size > MAX_CONTEXT_CHARACTERS:
                continue
            selected.append(row)
            total += size
        selected.reverse()
        return [
            UnifiedConversationMessage(role=row.role, content=row.content)
            for row in selected
        ]

    def _detail(
        self, conversation: Conversation, *, message_limit: int
    ) -> AssistantConversationDetail:
        bounded_limit = max(1, min(100, message_limit))
        total = (
            self.db.query(func.count(Message.id))
            .filter(Message.conversation_id == conversation.id)
            .scalar()
            or 0
        )
        rows = (
            self.db.query(Message, AssistantRun)
            .outerjoin(AssistantRun, Message.assistant_run_id == AssistantRun.id)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(bounded_limit)
            .all()
        )
        rows.reverse()
        latest_run = (
            self.db.query(AssistantRun)
            .filter(AssistantRun.conversation_id == conversation.id)
            .order_by(AssistantRun.created_at.desc(), AssistantRun.id.desc())
            .first()
        )
        preview_value = rows[-1][0].content if rows else None
        summary = self._summary(
            conversation,
            preview_value,
            latest_run.id if latest_run is not None else None,
            latest_run.status if latest_run is not None else None,
        )
        return AssistantConversationDetail(
            **summary.model_dump(),
            messages=[self._message(message, run) for message, run in rows],
            has_older=total > len(rows),
        )

    @staticmethod
    def _message(
        message: Message, run: AssistantRun | None
    ) -> AssistantConversationMessageResponse:
        result = None
        if (
            message.role == "assistant"
            and run is not None
            and isinstance(run.result_payload, dict)
        ):
            result = UnifiedAssistantResponse.model_validate(run.result_payload)
        return AssistantConversationMessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            assistant_run_id=message.assistant_run_id,
            created_at=message.created_at,
            run_status=run.status if run is not None else None,
            run_current_stage=run.current_stage if run is not None else None,
            run_result=result,
        )

    @staticmethod
    def _summary(
        conversation: Conversation,
        preview: str | None,
        latest_run_id: str | None,
        latest_run_status: str | None,
    ) -> AssistantConversationSummary:
        normalized_preview = None
        if preview:
            normalized_preview = " ".join(preview.split())[:160]
        activity = conversation.last_activity_at or conversation.created_at
        return AssistantConversationSummary(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            last_activity_at=activity,
            last_message_preview=normalized_preview,
            latest_run_id=latest_run_id,
            latest_run_status=latest_run_status,
            active=latest_run_status in ACTIVE_RUN_STATUSES,
        )
