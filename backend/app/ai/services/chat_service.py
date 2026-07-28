from app.ai.clients.ollama_client import OllamaClient
from app.ai.schemas.chat_response import ChatResponse


class ChatService:

    def __init__(self):

        self.client = OllamaClient()

    async def chat(
        self,
        model: str,
        message: str,
    ) -> ChatResponse:

        response = await self.client.generate(
            model=model,
            prompt=message,
        )

        return ChatResponse(
            response=response["response"],
            model=response["model"],
        )