from sqlalchemy.orm import Session

from app.models.role import Role
from app.repositories.base_repository import BaseRepository
from app.services.base_service import BaseService


class RoleService(BaseService[Role]):
    def __init__(self, db: Session):
        repository = BaseRepository(db, Role)
        super().__init__(repository)