from sqlalchemy.orm import Session

from app.models.message import Message

from .base_repository import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: Session):
        super().__init__(db, Message)

    def get_conversation_messages(
        self,
        conversation_id: int,
    ) -> list[Message]:

        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )