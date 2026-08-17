from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.project import Project
from app.repositories.base_repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Project)

    def get(self, object_id: int) -> Project | None:
        return self.db.query(Project).options(joinedload(Project.client)).filter(Project.id == object_id, Project.deleted_at.is_(None)).first()

    def get_page(self, *, search: str | None, client_id: int | None, status: str | None, skip: int, limit: int) -> tuple[list[Project], int]:
        query = self.db.query(Project).join(Client).options(joinedload(Project.client)).filter(Project.deleted_at.is_(None), Client.deleted_at.is_(None))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.filter(or_(Project.name.ilike(pattern), Project.description.ilike(pattern), Project.city.ilike(pattern), Client.name.ilike(pattern)))
        if client_id is not None:
            query = query.filter(Project.client_id == client_id)
        if status is not None:
            query = query.filter(Project.status == status)
        total = query.count()
        items = query.order_by(Project.created_at.desc(), Project.id.desc()).offset(skip).limit(limit).all()
        return items, total

    def soft_delete(self, project: Project) -> Project:
        project.deleted_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(project)
        return project
