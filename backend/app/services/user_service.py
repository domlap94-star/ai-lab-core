from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.base_service import BaseService


class UserService(BaseService[User]):
    def __init__(self, db: Session):
        super().__init__(UserRepository(db))

    def get_by_username(self, username: str) -> User | None:
        return self.repository.get_by_username(username)

    def get_by_email(self, email: str) -> User | None:
        return self.repository.get_by_email(email)