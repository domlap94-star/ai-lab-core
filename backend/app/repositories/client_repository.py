from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.repositories.base_repository import BaseRepository


class ClientRepository(BaseRepository[Client]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Client)

    def get(self, object_id: int) -> Client | None:
        return (
            self.db.query(Client)
            .options(joinedload(Client.industry))
            .filter(
                Client.id == object_id,
                Client.deleted_at.is_(None),
            )
            .first()
        )

    def get_all(
        self,
        *,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Client]:
        query = (
            self.db.query(Client)
            .options(joinedload(Client.industry))
            .filter(Client.deleted_at.is_(None))
        )

        if search:
            pattern = f"%{search.strip()}%"

            query = query.filter(
                or_(
                    Client.name.ilike(pattern),
                    Client.legal_name.ilike(pattern),
                    Client.tax_id.ilike(pattern),
                    Client.primary_email.ilike(pattern),
                    Client.primary_phone.ilike(pattern),
                    Client.city.ilike(pattern),
                )
            )

        return (
            query
            .order_by(Client.name.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_tax_id(self, tax_id: str) -> Client | None:
        return (
            self.db.query(Client)
            .filter(
                Client.tax_id == tax_id,
                Client.deleted_at.is_(None),
            )
            .first()
        )

    def soft_delete(self, client: Client) -> Client:
        client.deleted_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(client)

        return client