from sqlalchemy.orm import Session

from app.ai.clients.ollama_client import OllamaClient
from app.ai.schemas.chat_response import ChatResponse
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.client = OllamaClient()
        self.conversation_service = ConversationService(db)
        self.message_service = MessageService(db)

    async def chat(
        self,
        user_id: int,
        model: str,
        message: str,
    ) -> ChatResponse:
        cleaned_message = message.strip()

        if not cleaned_message:
            raise ValueError("Message cannot be empty.")

        conversation_title = cleaned_message[:100]

        conversation = Conversation(
            user_id=user_id,
            title=conversation_title,
            model=model,
        )

        conversation = self.conversation_service.create(conversation)

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=cleaned_message,
        )

        self.message_service.create(user_message)

        ollama_response = await self.client.generate(
            model=model,
            prompt=cleaned_message,
        )

        assistant_content = ollama_response.get("response", "").strip()

        if not assistant_content:
            raise RuntimeError("Ollama returned an empty response.")

        response_model = ollama_response.get("model", model)

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
        )

        self.message_service.create(assistant_message)

        return ChatResponse(
            conversation_id=conversation.id,
            response=assistant_content,
            model=response_model,
        )