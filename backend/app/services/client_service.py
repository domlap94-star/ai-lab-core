from sqlalchemy.orm import Session

from app.models.client import Client
from app.repositories.client_repository import ClientRepository
from app.repositories.industry_repository import IndustryRepository
from app.schemas.client import ClientCreate, ClientPage, ClientUpdate
from app.services.base_service import BaseService


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

        super().__init__(self.client_repository)

    def get_client(self, client_id: int) -> Client:
        client = self.client_repository.get(client_id)

        if client is None:
            raise ClientNotFoundError

        return client

    def get_clients(
        self,
        *,
        search: str | None = None,
        client_type: str | None = None,
        industry_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> ClientPage:
        items, total = self.client_repository.get_page(
            search=search,
            client_type=client_type,
            industry_id=industry_id,
            skip=skip,
            limit=limit,
        )

        return ClientPage(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

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
