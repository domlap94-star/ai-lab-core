from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.repositories.conversation_repository import ConversationRepository
from app.services.base_service import BaseService


class ConversationService(BaseService[Conversation]):
    def __init__(self, db: Session):
        super().__init__(ConversationRepository(db))

    def get_user_conversations(
        self,
        user_id: int,
    ) -> list[Conversation]:

        return self.repository.get_user_conversations(user_id)