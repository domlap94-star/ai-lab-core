from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_access_grant import ClientAccessGrant
from app.models.user import User
from app.schemas.client_access_grant import ClientAccessGrantRead
from app.services.client_scope_service import EXTERNAL_ROLE


class GrantValidationError(ValueError):
    pass


class ClientAccessGrantService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _read(row: ClientAccessGrant) -> ClientAccessGrantRead:
        return ClientAccessGrantRead(
            id=row.id,
            client_id=row.client_id,
            external_user_id=row.external_user_id,
            granted_by_user_id=row.granted_by_user_id,
            granted_at=row.granted_at,
            revoked_by_user_id=row.revoked_by_user_id,
            revoked_at=row.revoked_at,
            active=row.revoked_at is None,
        )

    @staticmethod
    def require_manager(actor: User) -> None:
        if not actor.is_active or actor.role.name not in {"Administrator", "User"}:
            raise GrantValidationError("grant_manager_required")

    def _targets(self, client_id: int, external_user_id: int) -> tuple[Client, User]:
        client = self.db.query(Client).filter(
            Client.id == client_id, Client.deleted_at.is_(None)
        ).with_for_update().one_or_none()
        user = self.db.query(User).filter(
            User.id == external_user_id,
            User.is_active.is_(True),
            User.trashed_at.is_(None),
            User.purged_at.is_(None),
        ).with_for_update().one_or_none()
        if client is None:
            raise GrantValidationError("client_not_found")
        if user is None or user.role.name != EXTERNAL_ROLE:
            raise GrantValidationError("active_external_user_required")
        return client, user

    def grant(self, *, client_id: int, external_user_id: int, actor: User) -> ClientAccessGrantRead:
        self.require_manager(actor)
        self._targets(client_id, external_user_id)
        existing = self.db.query(ClientAccessGrant).filter(
            ClientAccessGrant.client_id == client_id,
            ClientAccessGrant.external_user_id == external_user_id,
            ClientAccessGrant.revoked_at.is_(None),
        ).with_for_update().one_or_none()
        if existing is not None:
            return self._read(existing)
        row = ClientAccessGrant(
            client_id=client_id,
            external_user_id=external_user_id,
            granted_by_user_id=actor.id,
            granted_at=datetime.now(timezone.utc),
        )
        try:
            self.db.add(row)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            row = self.db.query(ClientAccessGrant).filter(
                ClientAccessGrant.client_id == client_id,
                ClientAccessGrant.external_user_id == external_user_id,
                ClientAccessGrant.revoked_at.is_(None),
            ).one()
        self.db.refresh(row)
        return self._read(row)

    def revoke(self, *, client_id: int, external_user_id: int, actor: User) -> ClientAccessGrantRead | None:
        self.require_manager(actor)
        row = self.db.query(ClientAccessGrant).filter(
            ClientAccessGrant.client_id == client_id,
            ClientAccessGrant.external_user_id == external_user_id,
            ClientAccessGrant.revoked_at.is_(None),
        ).with_for_update().one_or_none()
        if row is None:
            return None
        row.revoked_by_user_id = actor.id
        row.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return self._read(row)

    def page(self, *, client_id: int | None, external_user_id: int | None, active: bool | None, skip: int, limit: int):
        query = self.db.query(ClientAccessGrant)
        if client_id is not None:
            query = query.filter(ClientAccessGrant.client_id == client_id)
        if external_user_id is not None:
            query = query.filter(ClientAccessGrant.external_user_id == external_user_id)
        if active is True:
            query = query.filter(ClientAccessGrant.revoked_at.is_(None))
        elif active is False:
            query = query.filter(ClientAccessGrant.revoked_at.isnot(None))
        total = query.count()
        rows = query.order_by(ClientAccessGrant.granted_at.desc(), ClientAccessGrant.id.desc()).offset(skip).limit(limit).all()
        return [self._read(row) for row in rows], total
