from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.inspection import Inspection
from app.models.user import User
from app.repositories.client_repository import ClientRepository
from app.repositories.inspection_repository import InspectionRepository
from app.schemas.inspection import (
    InspectionCreate,
    InspectionPage,
    InspectionUpdate,
)


class InspectionNotFoundError(Exception):
    pass


class InspectionClientNotFoundError(Exception):
    pass


class InspectionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InspectionRepository(db)
        self.clients = ClientRepository(db)

    @staticmethod
    def _read(inspection: Inspection) -> Inspection:
        inspection.project_name = (
            inspection.project.name if inspection.project is not None else None
        )
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

    def _client(self, client_id: int):
        client = self.clients.get(client_id)
        if client is None:
            raise InspectionClientNotFoundError
        return client

    @staticmethod
    def _title(client_name: str, client_id: int) -> str:
        normalized = " ".join(client_name.split())
        suffix = normalized or f"klient #{client_id}"
        return f"Wizja lokalna — {suffix}"[:255]

    @staticmethod
    def _complete_payload(payload: dict) -> dict:
        if payload["status"] == "completed" and payload.get("completed_at") is None:
            payload["completed_at"] = datetime.now(UTC)
        return payload

    def create(self, data: InspectionCreate, actor: User) -> Inspection:
        payload = self._complete_payload(data.model_dump())
        client = self._client(payload["client_id"])
        validated = InspectionCreate.model_validate(payload).model_dump()
        inspection = Inspection(
            **validated,
            project_id=None,
            title=self._title(client.name, client.id),
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
        client = self._client(merged["client_id"])
        validated = InspectionCreate.model_validate(merged).model_dump()
        for key, value in validated.items():
            setattr(inspection, key, value)
        inspection.title = self._title(client.name, client.id)
        inspection.updated_by_user_id = actor.id
        self.repository.update(inspection)
        return self.get(inspection.id)

    def delete(self, inspection_id: int, actor: User) -> None:
        inspection = self.get(inspection_id)
        inspection.updated_by_user_id = actor.id
        self.repository.soft_delete(inspection)
