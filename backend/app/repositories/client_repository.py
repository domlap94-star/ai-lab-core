from datetime import datetime, timezone

import re

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.repositories.base_repository import BaseRepository


class ClientRepository(BaseRepository[Client]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Client)

    def get(self, object_id: int) -> Client | None:
        return (
            self.db.query(Client)
            .options(
                joinedload(Client.industry),
                selectinload(Client.contact_points),
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
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Client], int]:
        filtered_query = self._filtered_query(
            search=search,
            client_type=client_type,
            industry_id=industry_id,
        )

        total = filtered_query.count()

        items = (
            filtered_query
            .options(
                joinedload(Client.industry),
                selectinload(Client.contact_points),
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
    ) -> list[tuple[int, datetime]]:
        return (
            self._filtered_query(
                search=search,
                client_type=client_type,
                industry_id=industry_id,
            )
            .with_entities(Client.id, Client.created_at)
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
    ) -> Query:
        query = self.db.query(Client).filter(
            Client.deleted_at.is_(None)
        )

        normalized_search = search.strip() if search else ""

        if normalized_search:
            pattern = f"%{normalized_search}%"
            normalized_email_pattern = f"%{normalized_search.casefold()}%"
            phone_digits = re.sub(r"\D", "", normalized_search)
            phone_patterns = []
            if len(phone_digits) >= 3:
                local_phone = phone_digits[2:] if len(phone_digits) == 11 and phone_digits.startswith("48") else phone_digits
                phone_patterns = [f"%{local_phone}%", f"%48{local_phone}%"]
            query = query.filter(
                or_(
                    Client.name.ilike(pattern),
                    Client.legal_name.ilike(pattern),
                    Client.tax_id.ilike(pattern),
                    Client.primary_email.ilike(pattern),
                    Client.primary_phone.ilike(pattern),
                    Client.street.ilike(pattern),
                    Client.building_number.ilike(pattern),
                    Client.postal_code.ilike(pattern),
                    Client.city.ilike(pattern),
                    Client.contact_points.any(
                        and_(
                            ClientContactPoint.deleted_at.is_(None),
                            ClientContactPoint.kind == "email",
                            ClientContactPoint.normalized_value.ilike(normalized_email_pattern),
                        )
                    ),
                    *(
                        [
                            Client.contact_points.any(
                                and_(
                                    ClientContactPoint.deleted_at.is_(None),
                                    ClientContactPoint.kind == "phone",
                                    or_(*[
                                        func.regexp_replace(
                                            ClientContactPoint.normalized_value, r"[^0-9]", "", "g"
                                        ).ilike(phone_pattern)
                                        for phone_pattern in phone_patterns
                                    ]),
                                )
                            ),
                            or_(*[
                                func.regexp_replace(
                                    Client.primary_phone, r"[^0-9]", "", "g"
                                ).ilike(phone_pattern)
                                for phone_pattern in phone_patterns
                            ]),
                        ]
                        if phone_patterns else []
                    ),
                    Client.address_records.any(
                        and_(
                            ClientAddress.deleted_at.is_(None),
                            or_(
                                ClientAddress.street.ilike(pattern),
                                ClientAddress.building_number.ilike(pattern),
                                ClientAddress.postal_code.ilike(pattern),
                                ClientAddress.city.ilike(pattern),
                            ),
                        )
                    ),
                )
            )

        if client_type is not None:
            query = query.filter(Client.client_type == client_type)

        if industry_id is not None:
            query = query.filter(Client.industry_id == industry_id)

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
