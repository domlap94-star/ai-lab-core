from pydantic import BaseModel


class ChatRequest(BaseModel):

    message: str

    model: str = "llama3.2"