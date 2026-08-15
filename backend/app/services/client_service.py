from sqlalchemy.orm import Session

from app.models.client import Client
from app.repositories.client_repository import ClientRepository
from app.repositories.industry_repository import IndustryRepository
from app.schemas.client import (
    ClientCreate,
    ClientPage,
    ClientPageSortOrder,
    ClientUpdate,
)
from app.services.base_service import BaseService
from app.services.client_source_record_date_service import (
    ClientSourceRecordDateService,
)


class ClientNotFoundError(Exception):
    pass


class IndustryNotFoundError(Exception):
    pass


class DuplicateTaxIdError(Exception):
    pass


class ClientService(BaseService[Client]):
    def __init__(self, db: Session) -> None:
        self.db = db
        self.client_repository = ClientRepository(db)
        self.industry_repository = IndustryRepository(db)
        self.source_record_date_service = ClientSourceRecordDateService(db)

        super().__init__(self.client_repository)

    def get_client(self, client_id: int) -> Client:
        client = self.client_repository.get(client_id)

        if client is None:
            raise ClientNotFoundError

        source_dates = self.source_record_date_service.get_for_client_ids(
            [client.id]
        )
        client.source_record_date = source_dates.get(client.id)

        return client

    def get_clients(
        self,
        *,
        search: str | None = None,
        client_type: str | None = None,
        industry_id: int | None = None,
        sort_order: ClientPageSortOrder | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> ClientPage:
        if sort_order is not None:
            return self._get_clients_sorted_by_effective_date(
                search=search,
                client_type=client_type,
                industry_id=industry_id,
                sort_order=sort_order,
                skip=skip,
                limit=limit,
            )

        items, total = self.client_repository.get_page(
            search=search,
            client_type=client_type,
            industry_id=industry_id,
            skip=skip,
            limit=limit,
        )

        self._attach_source_dates(items)

        return ClientPage(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    def _get_clients_sorted_by_effective_date(
        self,
        *,
        search: str | None,
        client_type: str | None,
        industry_id: int | None,
        sort_order: ClientPageSortOrder,
        skip: int,
        limit: int,
    ) -> ClientPage:
        candidates = self.client_repository.get_sort_candidates(
            search=search,
            client_type=client_type,
            industry_id=industry_id,
        )
        source_dates = self.source_record_date_service.get_for_client_ids(
            [client_id for client_id, _ in candidates]
        )
        ordered_ids = self.source_record_date_service.order_client_ids(
            candidates,
            source_dates,
            sort_order=sort_order,
        )
        page_ids = ordered_ids[skip : skip + limit]
        clients_by_id = {
            client.id: client
            for client in self.client_repository.get_by_ids(page_ids)
        }
        items = [
            clients_by_id[client_id]
            for client_id in page_ids
            if client_id in clients_by_id
        ]

        for item in items:
            item.source_record_date = source_dates.get(item.id)

        return ClientPage(
            items=items,
            total=len(ordered_ids),
            skip=skip,
            limit=limit,
        )

    def _attach_source_dates(self, items: list[Client]) -> None:
        source_dates = self.source_record_date_service.get_for_client_ids(
            [item.id for item in items]
        )
        for item in items:
            item.source_record_date = source_dates.get(item.id)

    def create_client(
        self,
        data: ClientCreate,
    ) -> Client:
        payload = data.model_dump()

        self._validate_industry(payload.get("industry_id"))
        self._validate_tax_id(payload.get("tax_id"))

        client = Client(**payload)

        self.client_repository.create(client)

        return self.get_client(client.id)

    def update_client(
        self,
        client_id: int,
        data: ClientUpdate,
    ) -> Client:
        client = self.get_client(client_id)

        payload = data.model_dump(
            exclude_unset=True,
        )

        if "industry_id" in payload:
            self._validate_industry(
                payload["industry_id"],
            )

        if "tax_id" in payload:
            self._validate_tax_id(
                payload["tax_id"],
                excluded_client_id=client.id,
            )

        for field_name, value in payload.items():
            setattr(client, field_name, value)

        self.client_repository.update(client)

        return self.get_client(client.id)

    def delete_client(
        self,
        client_id: int,
    ) -> None:
        client = self.get_client(client_id)
        self.client_repository.soft_delete(client)

    def _validate_industry(
        self,
        industry_id: int | None,
    ) -> None:
        if industry_id is None:
            return

        industry = self.industry_repository.get_active(
            industry_id,
        )

        if industry is None:
            raise IndustryNotFoundError

    def _validate_tax_id(
        self,
        tax_id: str | None,
        *,
        excluded_client_id: int | None = None,
    ) -> None:
        if not tax_id:
            return

        existing_client = self.client_repository.get_by_tax_id(
            tax_id,
        )

        if existing_client is None:
            return

        if existing_client.id == excluded_client_id:
            return

        raise DuplicateTaxIdError
