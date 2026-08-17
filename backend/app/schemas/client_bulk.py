from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ClientWorkflowState = Literal[
    "obsolete", "in_progress", "inspection", "completed", "untouched", "phone_contact"
]


class ClientIdBatchRequest(BaseModel):
    client_ids: list[int] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.client_ids)) != len(self.client_ids):
            raise ValueError("client_ids must be unique")
        if any(value <= 0 for value in self.client_ids):
            raise ValueError("client_ids must be positive")
        return self


class ClientWorkflowBatchRequest(ClientIdBatchRequest):
    status: ClientWorkflowState
    effective_date: date | None = None

    @model_validator(mode="after")
    def validate_date(self):
        if self.status in {"inspection", "phone_contact"} and self.effective_date is None:
            raise ValueError("effective_date is required for this status")
        if self.status not in {"inspection", "phone_contact"}:
            self.effective_date = None
        return self


class ClientBatchResultItem(BaseModel):
    client_id: int
    result: Literal["updated", "deleted", "not_found", "already_deleted"]


class ClientBatchResponse(BaseModel):
    requested: int
    succeeded: int
    failed: int
    results: list[ClientBatchResultItem]


class ClientWorkflowStatusRead(BaseModel):
    client_id: int
    status: ClientWorkflowState
    effective_date: date | None = None
