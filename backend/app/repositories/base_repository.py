from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository implementing basic CRUD operations.
    """

    def __init__(
        self,
        db: Session,
        model: type[ModelType],
    ) -> None:
        self.db = db
        self.model = model

    def get(self, object_id: int) -> ModelType | None:
        return self.db.get(self.model, object_id)

    def get_all(self) -> list[ModelType]:
        return self.db.query(self.model).all()

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType) -> ModelType:
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.commit()