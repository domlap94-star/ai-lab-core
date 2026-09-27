from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClientAccessGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: int = Field(gt=0)
    external_user_id: int = Field(gt=0)


class ClientAccessGrantBulkRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grant_ids: list[int] = Field(min_length=1, max_length=100)


class ClientAccessGrantBulkRevokeResult(BaseModel):
    revoked_count: int
    grant_ids: list[int]
    revoked_at: datetime


class ClientAccessGrantRead(BaseModel):
    id: int
    client_id: int
    external_user_id: int
    granted_by_user_id: int
    granted_at: datetime
    revoked_by_user_id: int | None
    revoked_at: datetime | None
    active: bool


class SharedClientRead(BaseModel):
    id: int
    name: str
    granted_at: datetime


class ClientAccessGrantPage(BaseModel):
    items: list[ClientAccessGrantRead]
    total: int
    skip: int
    limit: int


class ClientAccessOption(BaseModel):
    id: int
    name: str


class ExternalUserOption(BaseModel):
    id: int
    username: str


class ClientAccessManagerOptions(BaseModel):
    clients: list[ClientAccessOption]
    external_users: list[ExternalUserOption]
