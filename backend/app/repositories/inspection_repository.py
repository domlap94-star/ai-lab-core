from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.inspection import Inspection
from app.models.project import Project
from app.repositories.base_repository import BaseRepository


class InspectionRepository(BaseRepository[Inspection]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Inspection)

    def get(self, object_id: int) -> Inspection | None:
        return (
            self.db.query(Inspection)
            .options(joinedload(Inspection.project), joinedload(Inspection.client))
            .filter(Inspection.id == object_id, Inspection.deleted_at.is_(None))
            .first()
        )

    def get_page(
        self,
        *,
        search: str | None,
        project_id: int | None,
        client_id: int | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Inspection], int]:
        query = (
            self.db.query(Inspection)
            .join(Project, Inspection.project_id == Project.id)
            .join(Client, Inspection.client_id == Client.id)
            .options(joinedload(Inspection.project), joinedload(Inspection.client))
            .filter(
                Inspection.deleted_at.is_(None),
                Project.deleted_at.is_(None),
                Client.deleted_at.is_(None),
            )
        )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Inspection.title.ilike(pattern),
                    Inspection.notes.ilike(pattern),
                    Project.name.ilike(pattern),
                    Client.name.ilike(pattern),
                )
            )
        if project_id is not None:
            query = query.filter(Inspection.project_id == project_id)
        if client_id is not None:
            query = query.filter(Inspection.client_id == client_id)
        if status is not None:
            query = query.filter(Inspection.status == status)
        if date_from is not None:
            query = query.filter(Inspection.scheduled_at >= date_from)
        if date_to is not None:
            query = query.filter(Inspection.scheduled_at <= date_to)
        total = query.count()
        items = (
            query.order_by(
                Inspection.scheduled_at.desc().nullslast(),
                Inspection.created_at.desc(),
                Inspection.id.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def soft_delete(self, inspection: Inspection) -> Inspection:
        inspection.deleted_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(inspection)
        return inspection
