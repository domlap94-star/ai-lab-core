"""Focused PRE-CHUNK 11 DB checks; every synthetic mutation is rolled back."""

from datetime import date

from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.repositories.client_repository import ClientRepository
from app.schemas.client_bulk import ClientWorkflowBatchRequest
from app.services.client_bulk_service import ClientBulkService


def _assert_search(repo: ClientRepository, value: str, expected_id: int) -> None:
    rows, _ = repo.get_page(search=value, limit=100)
    assert expected_id in {row.id for row in rows}


def main() -> None:
    db = SessionLocal()
    try:
        repo = ClientRepository(db)
        search_ids: dict[str, int] = {}

        name = db.query(Client).filter(Client.deleted_at.is_(None)).first()
        assert name is not None
        _assert_search(repo, name.name, name.id)
        search_ids["name"] = name.id

        for label, field in (
            ("legal", Client.legal_name),
            ("nip", Client.tax_id),
            ("email", Client.primary_email),
            ("phone", Client.primary_phone),
            ("street", Client.street),
            ("city", Client.city),
            ("postal", Client.postal_code),
        ):
            row = (
                db.query(Client)
                .filter(Client.deleted_at.is_(None), field.is_not(None), field != "")
                .first()
            )
            if row is not None:
                value = getattr(row, field.key)
                _assert_search(repo, value, row.id)
                search_ids[label] = row.id

        for kind, label in (("email", "secondary_email"), ("phone", "secondary_phone")):
            contact = (
                db.query(ClientContactPoint)
                .join(Client, Client.id == ClientContactPoint.client_id)
                .filter(
                    Client.deleted_at.is_(None),
                    ClientContactPoint.deleted_at.is_(None),
                    ClientContactPoint.kind == kind,
                    ClientContactPoint.is_primary.is_(False),
                )
                .first()
            )
            if contact is not None:
                query = contact.value
                if kind == "phone":
                    query = "".join(character for character in query if character.isdigit())
                    if query.startswith("48") and len(query) == 11:
                        query = query[2:]
                _assert_search(repo, query, contact.client_id)
                search_ids[label] = contact.client_id

        address = (
            db.query(ClientAddress)
            .join(Client, Client.id == ClientAddress.client_id)
            .filter(Client.deleted_at.is_(None), ClientAddress.deleted_at.is_(None))
            .first()
        )
        if address is not None:
            value = address.street or address.city or address.postal_code
            if value:
                _assert_search(repo, value, address.client_id)
                search_ids["structured_address"] = address.client_id

        synthetic = [
            Client(client_type="company", name="PRECHUNK11 rollback A", country_code="PL"),
            Client(client_type="company", name="PRECHUNK11 rollback B", country_code="PL"),
        ]
        db.add_all(synthetic)
        db.flush()
        ids = [row.id for row in synthetic]
        synthetic[0].contact_points.extend(
            [
                ClientContactPoint(
                    kind="email",
                    value="secondary-search@example.test",
                    normalized_value="secondary-search@example.test",
                    is_primary=False,
                    position=0,
                    origin="manual",
                ),
                ClientContactPoint(
                    kind="phone",
                    value="+48 599 888 777",
                    normalized_value="+48599888777",
                    is_primary=False,
                    position=1,
                    origin="manual",
                ),
            ]
        )
        synthetic[0].address_records.append(
            ClientAddress(
                label="Adres testowy",
                street="Rollbackowa",
                postal_code="00-987",
                city="Testowo",
                country_code="PL",
                is_primary=False,
                position=0,
                origin="manual",
            )
        )
        db.flush()
        _assert_search(repo, "SECONDARY-SEARCH@EXAMPLE.TEST", synthetic[0].id)
        _assert_search(repo, "599888777", synthetic[0].id)
        _assert_search(repo, "Rollbackowa", synthetic[0].id)
        search_ids["synthetic_secondary_email"] = synthetic[0].id
        search_ids["synthetic_secondary_phone"] = synthetic[0].id
        search_ids["synthetic_structured_address"] = synthetic[0].id
        original_commit = db.commit
        db.commit = db.flush  # type: ignore[method-assign]
        try:
            service = ClientBulkService(db)
            status = service.set_workflow_status(
                ClientWorkflowBatchRequest(
                    client_ids=ids + [2_147_483_647],
                    status="inspection",
                    effective_date=date(2026, 8, 17),
                )
            )
            assert status.succeeded == 2 and status.failed == 1
            assert all(
                item.status == "inspection"
                for item in service.workflow_statuses(ids)
            )
            deleted = service.soft_delete(ids)
            assert deleted.succeeded == 2
            assert all(row.deleted_at is not None for row in synthetic)
        finally:
            db.commit = original_commit  # type: ignore[method-assign]

        print(f"PRE-CHUNK 11 CRM DB ROLLBACK PASS search_ids={search_ids}")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
