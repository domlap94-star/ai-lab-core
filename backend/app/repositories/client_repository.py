from datetime import date, datetime, timezone

from sqlalchemy import exists, func, not_
from sqlalchemy.orm import Query
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.client import Client
from app.models.contact_person import ContactPerson
from app.models.client_workflow_status import ClientWorkflowStatus
from app.repositories.base_repository import BaseRepository
from app.services.client_search_matching_service import (
    ClientSearchMatchingService,
)


class ClientRepository(BaseRepository[Client]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Client)

    def get(self, object_id: int) -> Client | None:
        return (
            self.db.query(Client)
            .options(
                joinedload(Client.industry),
                selectinload(Client.contact_points),
                selectinload(Client.contact_persons).selectinload(ContactPerson.contact_points),
                selectinload(Client.address_records),
            )
            .filter(
                Client.id == object_id,
                Client.deleted_at.is_(None),
            )
            .first()
        )

    def get_page(
        self,
        *,
        search: str | None = None,
        client_type: str | None = None,
        industry_id: int | None = None,
        exclude_statuses: list[str] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Client], int]:
        filtered_query = self._filtered_query(
            search=search,
            client_type=client_type,
            industry_id=industry_id,
            exclude_statuses=exclude_statuses,
        )

        total = filtered_query.count()

        items = (
            filtered_query
            .options(
                joinedload(Client.industry),
                selectinload(Client.contact_points),
                selectinload(Client.contact_persons).selectinload(ContactPerson.contact_points),
                selectinload(Client.address_records),
            )
            .order_by(
                func.lower(Client.name).asc(),
                Client.id.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, total

    def get_sort_candidates(
        self,
        *,
        search: str | None = None,
        client_type: str | None = None,
        industry_id: int | None = None,
        exclude_statuses: list[str] | None = None,
    ) -> list[tuple[int, datetime, date | None]]:
        return (
            self._filtered_query(
                search=search,
                client_type=client_type,
                industry_id=industry_id,
                exclude_statuses=exclude_statuses,
            )
            .with_entities(Client.id, Client.created_at, Client.client_added_at)
            .all()
        )

    def get_by_ids(self, client_ids: list[int]) -> list[Client]:
        if not client_ids:
            return []

        return (
            self.db.query(Client)
            .options(
                joinedload(Client.industry),
                selectinload(Client.contact_points),
                selectinload(Client.contact_persons).selectinload(ContactPerson.contact_points),
                selectinload(Client.address_records),
            )
            .filter(
                Client.id.in_(client_ids),
                Client.deleted_at.is_(None),
            )
            .all()
        )

    def _filtered_query(
        self,
        *,
        search: str | None,
        client_type: str | None,
        industry_id: int | None,
        exclude_statuses: list[str] | None,
    ) -> Query:
        query = self.db.query(Client).filter(
            Client.deleted_at.is_(None)
        )

        normalized_search = ClientSearchMatchingService.normalize(search)

        if normalized_search.value:
            query = query.filter(
                ClientSearchMatchingService.condition(normalized_search)
            )

        if client_type is not None:
            query = query.filter(Client.client_type == client_type)

        if industry_id is not None:
            query = query.filter(Client.industry_id == industry_id)

        excluded = set(exclude_statuses or [])
        if excluded:
            explicit_excluded = exists().where(
                ClientWorkflowStatus.client_id == Client.id,
                ClientWorkflowStatus.deleted_at.is_(None),
                ClientWorkflowStatus.status.in_(excluded),
            )
            query = query.filter(not_(explicit_excluded))
            if "untouched" in excluded:
                status_exists = exists().where(
                    ClientWorkflowStatus.client_id == Client.id,
                    ClientWorkflowStatus.deleted_at.is_(None),
                )
                query = query.filter(status_exists)

        return query

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
