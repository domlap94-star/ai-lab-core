from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.repositories.client_repository import ClientRepository
from app.repositories.industry_repository import IndustryRepository
from app.schemas.client import (
    ClientCreate,
    ClientPage,
    ClientPageSortOrder,
    ClientUpdate,
)
from app.services.base_service import BaseService
from app.services.client_added_date_projection_service import (
    ClientAddedDateProjectionService,
)
from app.services.client_workflow_status_projection_service import (
    ClientWorkflowStatusProjectionService,
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
        self.added_date_projection = ClientAddedDateProjectionService(db)
        self.workflow_status_projection = ClientWorkflowStatusProjectionService(db)

        super().__init__(self.client_repository)

    def get_client(self, client_id: int) -> Client:
        client = self.client_repository.get(client_id)

        if client is None:
            raise ClientNotFoundError

        self.added_date_projection.attach([client])
        self.workflow_status_projection.attach([client])

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

        self.added_date_projection.attach(items)
        self.workflow_status_projection.attach(items)

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
        source_dates = self.added_date_projection.source_dates_for(
            [client_id for client_id, _, _ in candidates]
        )
        ordered_ids = self.added_date_projection.order_client_ids(
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

        self.added_date_projection.attach(items, source_dates=source_dates)
        self.workflow_status_projection.attach(items)

        return ClientPage(
            items=items,
            total=len(ordered_ids),
            skip=skip,
            limit=limit,
        )

    def create_client(
        self,
        data: ClientCreate,
    ) -> Client:
        payload = data.model_dump(exclude={"emails", "phones", "addresses"})
        if data.emails is not None:
            payload["primary_email"] = self._primary_value(data.emails)
        if data.phones is not None:
            payload["primary_phone"] = self._primary_value(data.phones)

        self._validate_industry(payload.get("industry_id"))
        self._validate_tax_id(payload.get("tax_id"))

        client = Client(**payload)

        self.client_repository.create(client)

        if data.emails is not None:
            self._replace_contacts(client, "email", data.emails)
        elif client.primary_email:
            self._replace_contacts(client, "email", [{"value": client.primary_email, "is_primary": True}])
        if data.phones is not None:
            self._replace_contacts(client, "phone", data.phones)
        elif client.primary_phone:
            self._replace_contacts(client, "phone", [{"value": client.primary_phone, "is_primary": True}])
        if data.addresses is not None:
            self._replace_addresses(client, data.addresses)
            self._sync_primary_address_scalars(client)
        elif self._has_scalar_address(client):
            self._replace_addresses(client, [self._scalar_address_payload(client)])
        self.db.commit()

        return self.get_client(client.id)

    def update_client(
        self,
        client_id: int,
        data: ClientUpdate,
    ) -> Client:
        client = self.get_client(client_id)

        payload = data.model_dump(
            exclude_unset=True,
            exclude={"emails", "phones", "addresses"},
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

        if "emails" in data.model_fields_set:
            self._replace_contacts(client, "email", data.emails or [])
            client.primary_email = self._primary_value(data.emails or [])
        elif "primary_email" in payload:
            self._set_legacy_primary(client, "email", payload["primary_email"])
        if "phones" in data.model_fields_set:
            self._replace_contacts(client, "phone", data.phones or [])
            client.primary_phone = self._primary_value(data.phones or [])
        elif "primary_phone" in payload:
            self._set_legacy_primary(client, "phone", payload["primary_phone"])
        if "addresses" in data.model_fields_set:
            self._replace_addresses(client, data.addresses or [])
            self._sync_primary_address_scalars(client)
        elif any(
            field in payload
            for field in (
                "street", "building_number", "unit_number", "postal_code", "city", "country_code"
            )
        ):
            self._set_legacy_primary_address(client)

        self.client_repository.update(client)

        return self.get_client(client.id)

    def delete_client(
        self,
        client_id: int,
    ) -> None:
        client = self.get_client(client_id)
        self.client_repository.soft_delete(client)

    def _replace_contacts(self, client: Client, kind: str, contacts: list) -> None:
        client.contact_points[:] = [item for item in client.contact_points if item.kind != kind]
        self.db.flush()
        for position, raw in enumerate(contacts):
            value = raw.value if hasattr(raw, "value") else raw["value"]
            primary = raw.is_primary if hasattr(raw, "is_primary") else raw["is_primary"]
            client.contact_points.append(ClientContactPoint(
                kind=kind, value=value.strip(),
                normalized_value=self._normalize_contact(kind, value),
                is_primary=primary, position=position, origin="manual",
            ))

    def _replace_addresses(self, client: Client, addresses: list) -> None:
        for existing in client.address_records:
            if existing.deleted_at is None:
                existing.deleted_at = datetime.now(timezone.utc)
        self.db.flush()
        for position, raw in enumerate(addresses):
            get = lambda name, default=None: (
                getattr(raw, name, default)
                if hasattr(raw, name)
                else raw.get(name, default)
            )
            client.address_records.append(
                ClientAddress(
                    label=get("label", "Adres"),
                    street=get("street"),
                    building_number=get("building_number"),
                    unit_number=get("unit_number"),
                    postal_code=get("postal_code"),
                    city=get("city"),
                    country_code=get("country_code", "PL"),
                    is_primary=get("is_primary", False),
                    position=position,
                    origin="manual",
                )
            )

    def _sync_primary_address_scalars(self, client: Client) -> None:
        primary = next((item for item in client.addresses if item.is_primary), None)
        for field in (
            "street", "building_number", "unit_number", "postal_code", "city", "country_code"
        ):
            setattr(client, field, getattr(primary, field) if primary else ("PL" if field == "country_code" else None))

    def _set_legacy_primary_address(self, client: Client) -> None:
        primary = next((item for item in client.addresses if item.is_primary), None)
        if primary is None and self._has_scalar_address(client):
            client.address_records.append(ClientAddress(**self._scalar_address_payload(client), origin="manual", position=len(client.address_records)))
            return
        if primary is not None:
            for field in ("street", "building_number", "unit_number", "postal_code", "city", "country_code"):
                setattr(primary, field, getattr(client, field))

    @staticmethod
    def _has_scalar_address(client: Client) -> bool:
        return any(getattr(client, field) for field in ("street", "building_number", "unit_number", "postal_code", "city"))

    @staticmethod
    def _scalar_address_payload(client: Client) -> dict:
        return {
            "label": "Adres główny",
            "street": client.street,
            "building_number": client.building_number,
            "unit_number": client.unit_number,
            "postal_code": client.postal_code,
            "city": client.city,
            "country_code": client.country_code,
            "is_primary": True,
        }

    def _set_legacy_primary(self, client: Client, kind: str, value: str | None) -> None:
        normalized = self._normalize_contact(kind, value) if value else None
        matching = None
        for item in client.contact_points:
            if item.kind == kind:
                item.is_primary = False
                if normalized and item.normalized_value == normalized:
                    matching = item
        if value and matching is None:
            matching = ClientContactPoint(
                kind=kind, value=value, normalized_value=normalized,
                is_primary=True, position=len(client.contact_points), origin="manual",
            )
            client.contact_points.append(matching)
        elif matching is not None:
            matching.is_primary = True

    @staticmethod
    def _normalize_contact(kind: str, value: str) -> str:
        if kind == "email":
            return value.strip().casefold()
        import re
        return re.sub(r"[^0-9+]", "", value)

    @staticmethod
    def _primary_value(contacts: list) -> str | None:
        if not contacts:
            return None
        for item in contacts:
            primary = item.is_primary if hasattr(item, "is_primary") else item["is_primary"]
            if primary:
                return item.value if hasattr(item, "value") else item["value"]
        first = contacts[0]
        return first.value if hasattr(first, "value") else first["value"]

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
