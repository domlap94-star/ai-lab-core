from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_workflow_status import ClientWorkflowStatus


CLIENT_WORKFLOW_STATUS_LABELS = {
    "obsolete": "Nieaktualne",
    "in_progress": "W trakcie",
    "inspection": "Oględziny",
    "completed": "Usługa wykonana",
    "untouched": "Brak modyfikacji",
    "phone_contact": "Kontakt telefoniczny",
}
DEFAULT_CLIENT_WORKFLOW_STATUS = "untouched"


@dataclass(frozen=True)
class ClientWorkflowStatusProjection:
    status: str
    label: str
    effective_date: date | None = None


class ClientWorkflowStatusProjectionService:
    """Canonical read projection for a Client workflow status."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def default() -> ClientWorkflowStatusProjection:
        return ClientWorkflowStatusProjection(
            status=DEFAULT_CLIENT_WORKFLOW_STATUS,
            label=CLIENT_WORKFLOW_STATUS_LABELS[DEFAULT_CLIENT_WORKFLOW_STATUS],
        )

    def get_for_client_ids(
        self,
        client_ids: list[int],
    ) -> dict[int, ClientWorkflowStatusProjection]:
        unique_ids = list(dict.fromkeys(client_ids))
        if not unique_ids:
            return {}

        records = {
            record.client_id: record
            for record in self.db.query(ClientWorkflowStatus).filter(
                ClientWorkflowStatus.client_id.in_(unique_ids),
                ClientWorkflowStatus.deleted_at.is_(None),
            )
        }
        default = self.default()
        return {
            client_id: (
                ClientWorkflowStatusProjection(
                    status=record.status,
                    label=CLIENT_WORKFLOW_STATUS_LABELS[record.status],
                    effective_date=record.effective_date,
                )
                if (record := records.get(client_id)) is not None
                else default
            )
            for client_id in unique_ids
        }

    def attach(self, clients: list[Client]) -> None:
        projections = self.get_for_client_ids([client.id for client in clients])
        for client in clients:
            projection = projections.get(client.id, self.default())
            client.workflow_status = projection.status
            client.workflow_status_label = projection.label
            client.workflow_effective_date = projection.effective_date
