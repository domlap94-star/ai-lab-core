from sqlalchemy.orm import Session

from app.models.message import Message
from app.repositories.message_repository import MessageRepository
from app.services.base_service import BaseService


class MessageService(BaseService[Message]):
    def __init__(self, db: Session):
        super().__init__(MessageRepository(db))

    def get_conversation_messages(
        self,
        conversation_id: int,
    ) -> list[Message]:

        return self.repository.get_conversation_messages(
            conversation_id
        )