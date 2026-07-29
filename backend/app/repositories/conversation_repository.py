from sqlalchemy.orm import Session

from app.models.conversation import Conversation

from .base_repository import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, db: Session):
        super().__init__(db, Conversation)

    def get_user_conversations(
        self,
        user_id: int,
    ) -> list[Conversation]:

        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )