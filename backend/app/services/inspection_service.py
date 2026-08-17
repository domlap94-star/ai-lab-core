from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.inspection import Inspection
from app.models.user import User
from app.repositories.inspection_repository import InspectionRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.inspection import (
    InspectionCreate,
    InspectionPage,
    InspectionUpdate,
)


class InspectionNotFoundError(Exception):
    pass


class InspectionProjectNotFoundError(Exception):
    pass


class InspectionClientProjectMismatchError(Exception):
    pass


class InspectionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InspectionRepository(db)
        self.projects = ProjectRepository(db)

    @staticmethod
    def _read(inspection: Inspection) -> Inspection:
        inspection.project_name = inspection.project.name
        inspection.client_name = inspection.client.name
        return inspection

    def get(self, inspection_id: int) -> Inspection:
        inspection = self.repository.get(inspection_id)
        if inspection is None:
            raise InspectionNotFoundError
        return self._read(inspection)

    def get_page(self, **filters) -> InspectionPage:
        items, total = self.repository.get_page(**filters)
        return InspectionPage(
            items=[self._read(item) for item in items],
            total=total,
            skip=filters["skip"],
            limit=filters["limit"],
        )

    def _validate_project_client(self, project_id: int, client_id: int) -> None:
        project = self.projects.get(project_id)
        if project is None:
            raise InspectionProjectNotFoundError
        if project.client_id != client_id:
            raise InspectionClientProjectMismatchError

    @staticmethod
    def _complete_payload(payload: dict) -> dict:
        if payload["status"] == "completed" and payload.get("completed_at") is None:
            payload["completed_at"] = datetime.now(UTC)
        return payload

    def create(self, data: InspectionCreate, actor: User) -> Inspection:
        payload = self._complete_payload(data.model_dump())
        self._validate_project_client(payload["project_id"], payload["client_id"])
        validated = InspectionCreate.model_validate(payload).model_dump()
        inspection = Inspection(
            **validated,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        self.repository.create(inspection)
        return self.get(inspection.id)

    def update(
        self, inspection_id: int, data: InspectionUpdate, actor: User
    ) -> Inspection:
        inspection = self.get(inspection_id)
        payload = data.model_dump(exclude_unset=True)
        current = {
            key: getattr(inspection, key) for key in InspectionCreate.model_fields
        }
        merged = {**current, **payload}
        if "status" in payload and payload["status"] != "completed":
            merged["completed_at"] = None
        merged = self._complete_payload(merged)
        self._validate_project_client(merged["project_id"], merged["client_id"])
        validated = InspectionCreate.model_validate(merged).model_dump()
        for key, value in validated.items():
            setattr(inspection, key, value)
        inspection.updated_by_user_id = actor.id
        self.repository.update(inspection)
        return self.get(inspection.id)

    def delete(self, inspection_id: int, actor: User) -> None:
        inspection = self.get(inspection_id)
        inspection.updated_by_user_id = actor.id
        self.repository.soft_delete(inspection)
