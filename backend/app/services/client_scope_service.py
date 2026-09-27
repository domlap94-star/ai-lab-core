from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import Query, Session

from app.models.client import Client
from app.models.client_access_grant import ClientAccessGrant
from app.models.document import Document
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.user import User
from app.models.work_item import WorkItem


EXTERNAL_ROLE = "External"


class ClientScopeNotFound(LookupError):
    """Fail-closed result deliberately mapped to HTTP 404."""


@dataclass(frozen=True)
class ResourceClientScope:
    client_id: int | None
    resolved: bool


class ClientScopeService:
    """Single, request-current policy for all client-owned resources."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def is_external(user: User) -> bool:
        return bool(user.role and user.role.name == EXTERNAL_ROLE)

    def active_client_ids(self, user: User):
        return select(ClientAccessGrant.client_id).where(
            ClientAccessGrant.external_user_id == user.id,
            ClientAccessGrant.revoked_at.is_(None),
        )

    def scope_client_query(
        self,
        user: User,
        query: Query,
        client_column=Client.id,
    ) -> Query:
        if not self.is_external(user):
            return query
        return query.filter(client_column.in_(self.active_client_ids(user)))

    def can_access_client(self, user: User, client_id: int | None) -> bool:
        if client_id is None:
            return False if self.is_external(user) else True
        active_client = self.db.query(Client.id).filter(
            Client.id == client_id,
            Client.deleted_at.is_(None),
        )
        if self.is_external(user):
            active_client = active_client.filter(
                exists().where(
                    ClientAccessGrant.client_id == Client.id,
                    ClientAccessGrant.external_user_id == user.id,
                    ClientAccessGrant.revoked_at.is_(None),
                )
            )
        return active_client.first() is not None

    def require_client_access(self, user: User, client_id: int | None) -> int:
        if client_id is None or not self.can_access_client(user, client_id):
            raise ClientScopeNotFound
        return client_id

    def resolve_resource_client_scope(self, resource: Any) -> ResourceClientScope:
        if isinstance(resource, Client):
            return ResourceClientScope(resource.id, resource.deleted_at is None)
        if isinstance(resource, Project):
            return ResourceClientScope(resource.client_id, resource.client_id is not None)
        if isinstance(resource, WorkItem):
            direct = resource.client_id
            project_client = None
            if resource.project_id is not None:
                project_client = self.db.query(Project.client_id).filter(
                    Project.id == resource.project_id,
                    Project.deleted_at.is_(None),
                ).scalar()
            if direct is not None and project_client is not None and direct != project_client:
                return ResourceClientScope(None, False)
            value = direct if direct is not None else project_client
            return ResourceClientScope(value, value is not None)
        if isinstance(resource, Inspection):
            direct = resource.client_id
            project_client = None
            if resource.project_id is not None:
                project_client = self.db.query(Project.client_id).filter(
                    Project.id == resource.project_id,
                    Project.deleted_at.is_(None),
                ).scalar()
            if direct is not None and project_client is not None and direct != project_client:
                return ResourceClientScope(None, False)
            value = direct if direct is not None else project_client
            return ResourceClientScope(value, value is not None)
        if isinstance(resource, Document):
            candidates = {value for value in (resource.client_id,) if value is not None}
            if resource.project_id is not None:
                value = self.db.query(Project.client_id).filter(
                    Project.id == resource.project_id,
                    Project.deleted_at.is_(None),
                ).scalar()
                if value is not None:
                    candidates.add(value)
            if resource.inspection_id is not None:
                value = self.db.query(Inspection.client_id).filter(
                    Inspection.id == resource.inspection_id,
                    Inspection.deleted_at.is_(None),
                ).scalar()
                if value is not None:
                    candidates.add(value)
            return ResourceClientScope(
                next(iter(candidates)) if len(candidates) == 1 else None,
                len(candidates) == 1,
            )
        return ResourceClientScope(None, False)

    def require_resource_access(self, user: User, resource: Any) -> int:
        resolved = self.resolve_resource_client_scope(resource)
        if not resolved.resolved:
            raise ClientScopeNotFound
        return self.require_client_access(user, resolved.client_id)
