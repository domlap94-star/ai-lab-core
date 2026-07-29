from pydantic import BaseModel


class ChatResponse(BaseModel):
    conversation_id: int
    response: str
    model: str