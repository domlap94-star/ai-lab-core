from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_workflow_status import ClientWorkflowStatus
from app.schemas.client_bulk import (
    ClientBatchResponse,
    ClientBatchResultItem,
    ClientWorkflowBatchRequest,
    ClientWorkflowStatusRead,
)


class ClientBulkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def workflow_statuses(self, client_ids: list[int]) -> list[ClientWorkflowStatusRead]:
        active_ids = {
            row[0]
            for row in self.db.query(Client.id).filter(
                Client.id.in_(client_ids), Client.deleted_at.is_(None)
            )
        }
        records = {
            row.client_id: row
            for row in self.db.query(ClientWorkflowStatus).filter(
                ClientWorkflowStatus.client_id.in_(active_ids),
                ClientWorkflowStatus.deleted_at.is_(None),
            )
        }
        return [
            ClientWorkflowStatusRead(
                client_id=client_id,
                status=records[client_id].status if client_id in records else "untouched",
                effective_date=(records[client_id].effective_date if client_id in records else None),
            )
            for client_id in client_ids
            if client_id in active_ids
        ]

    def set_workflow_status(self, request: ClientWorkflowBatchRequest) -> ClientBatchResponse:
        clients = {
            row.id: row
            for row in self.db.query(Client).filter(Client.id.in_(request.client_ids)).with_for_update()
        }
        records = {
            row.client_id: row
            for row in self.db.query(ClientWorkflowStatus).filter(
                ClientWorkflowStatus.client_id.in_(request.client_ids),
                ClientWorkflowStatus.deleted_at.is_(None),
            ).with_for_update()
        }
        results: list[ClientBatchResultItem] = []
        for client_id in request.client_ids:
            client = clients.get(client_id)
            if client is None or client.deleted_at is not None:
                results.append(ClientBatchResultItem(client_id=client_id, result="not_found"))
                continue
            record = records.get(client_id)
            if record is None:
                record = ClientWorkflowStatus(client_id=client_id, status=request.status)
                self.db.add(record)
            record.status = request.status
            record.effective_date = request.effective_date
            results.append(ClientBatchResultItem(client_id=client_id, result="updated"))
        self.db.commit()
        succeeded = sum(item.result == "updated" for item in results)
        return ClientBatchResponse(
            requested=len(request.client_ids), succeeded=succeeded,
            failed=len(results) - succeeded, results=results,
        )

    def soft_delete(self, client_ids: list[int]) -> ClientBatchResponse:
        clients = {
            row.id: row
            for row in self.db.query(Client).filter(Client.id.in_(client_ids)).with_for_update()
        }
        now = datetime.now(UTC)
        results: list[ClientBatchResultItem] = []
        for client_id in client_ids:
            client = clients.get(client_id)
            if client is None:
                results.append(ClientBatchResultItem(client_id=client_id, result="not_found"))
            elif client.deleted_at is not None:
                results.append(ClientBatchResultItem(client_id=client_id, result="already_deleted"))
            else:
                client.deleted_at = now
                results.append(ClientBatchResultItem(client_id=client_id, result="deleted"))
        self.db.commit()
        succeeded = sum(item.result == "deleted" for item in results)
        return ClientBatchResponse(
            requested=len(client_ids), succeeded=succeeded,
            failed=len(results) - succeeded, results=results,
        )
