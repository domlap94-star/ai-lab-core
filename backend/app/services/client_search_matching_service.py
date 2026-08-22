from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import and_, func, or_
from sqlalchemy.sql.elements import ColumnElement

from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.models.contact_person import ContactPerson


@dataclass(frozen=True)
class ClientSearchQuery:
    value: str
    folded: str
    digits: str
    phone_digits: str


class ClientSearchMatchingService:
    """Canonical normalization and SQL candidate matching for Client search."""

    @classmethod
    def normalize(cls, value: str | None) -> ClientSearchQuery:
        normalized = " ".join((value or "").split())
        digits = re.sub(r"\D", "", normalized)
        return ClientSearchQuery(
            value=normalized,
            folded=normalized.casefold(),
            digits=digits,
            phone_digits=cls.local_phone_digits(normalized),
        )

    @staticmethod
    def local_phone_digits(value: object | None) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 11 and digits.startswith("48"):
            return digits[2:]
        return digits

    @classmethod
    def condition(cls, query: ClientSearchQuery) -> ColumnElement[bool]:
        pattern = f"%{query.value}%"
        conditions: list[ColumnElement[bool]] = [
            Client.name.ilike(pattern),
            Client.legal_name.ilike(pattern),
            Client.tax_id.ilike(pattern),
            Client.primary_email.ilike(pattern),
            Client.primary_phone.ilike(pattern),
            Client.street.ilike(pattern),
            Client.building_number.ilike(pattern),
            Client.postal_code.ilike(pattern),
            Client.city.ilike(pattern),
            Client.notes.ilike(pattern),
            Client.contact_points.any(
                and_(
                    ClientContactPoint.deleted_at.is_(None),
                    ClientContactPoint.normalized_value.ilike(pattern),
                )
            ),
            Client.contact_persons.any(
                and_(
                    ContactPerson.deleted_at.is_(None),
                    or_(
                        ContactPerson.display_name.ilike(pattern),
                        ContactPerson.role.ilike(pattern),
                    ),
                )
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
        ]
        if query.digits:
            phone_pattern = f"%{query.phone_digits or query.digits}%"
            conditions.extend(
                [
                    func.regexp_replace(
                        Client.primary_phone,
                        r"[^0-9]",
                        "",
                        "g",
                    ).ilike(phone_pattern),
                    func.regexp_replace(
                        Client.tax_id,
                        r"[^0-9]",
                        "",
                        "g",
                    ).ilike(f"%{query.digits}%"),
                    Client.contact_points.any(
                        and_(
                            ClientContactPoint.deleted_at.is_(None),
                            ClientContactPoint.kind == "phone",
                            func.regexp_replace(
                                ClientContactPoint.normalized_value,
                                r"[^0-9]",
                                "",
                                "g",
                            ).ilike(phone_pattern),
                        )
                    ),
                ]
            )
        return or_(*conditions)
