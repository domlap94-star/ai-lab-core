from typing import Generic, TypeVar

from app.database.base import Base
from app.repositories.base_repository import BaseRepository

ModelType = TypeVar("ModelType", bound=Base)


class BaseService(Generic[ModelType]):
    """
    Base service containing common CRUD operations.
    """

    def __init__(self, repository: BaseRepository[ModelType]):
        self.repository = repository

    def get(self, object_id: int) -> ModelType | None:
        return self.repository.get(object_id)

    def get_all(self) -> list[ModelType]:
        return self.repository.get_all()

    def create(self, obj: ModelType) -> ModelType:
        return self.repository.create(obj)

    def update(self, obj: ModelType) -> ModelType:
        return self.repository.update(obj)

    def delete(self, obj: ModelType) -> None:
        self.repository.delete(obj)