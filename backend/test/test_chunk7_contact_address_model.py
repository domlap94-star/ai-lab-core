from pydantic import ValidationError

from sqlalchemy.orm import Session

from app.database.session import engine
from app.models.client import Client
from app.schemas.client import ClientAddressInput, ClientCreate, ClientRead, ClientUpdate
from app.services.client_service import ClientService


def test_multiple_addresses_primary_switch_and_soft_removal() -> None:
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection)
    try:
        service = ClientService(db)
        client = service.create_client(
            ClientCreate(
                client_type="company",
                name="Chunk 7 isolated fixture",
                addresses=[
                    ClientAddressInput(
                        label="Siedziba",
                        street="Pierwsza",
                        building_number="1",
                        city="Warszawa",
                        country_code="PL",
                        is_primary=True,
                    )
                ],
            )
        )
        assert len(client.addresses) == 1
        assert client.street == "Pierwsza"
        assert client.city == "Warszawa"

        updated = service.update_client(
            client.id,
            ClientUpdate(
                addresses=[
                    ClientAddressInput(
                        label="Siedziba",
                        street="Pierwsza",
                        building_number="1",
                        city="Warszawa",
                        country_code="PL",
                    ),
                    ClientAddressInput(
                        label="Korespondencja",
                        street="Druga",
                        building_number="2",
                        city="Kraków",
                        country_code="PL",
                        is_primary=True,
                    ),
                ]
            ),
        )
        assert len(updated.addresses) == 2
        assert updated.street == "Druga"
        assert updated.city == "Kraków"
        assert sum(item.is_primary for item in updated.addresses) == 1
        assert all(item.origin == "manual" for item in updated.addresses)

        removed = service.update_client(
            client.id,
            ClientUpdate(
                addresses=[
                    ClientAddressInput(
                        label="Siedziba",
                        street="Pierwsza",
                        building_number="1",
                        city="Warszawa",
                        country_code="PL",
                    )
                ]
            ),
        )
        assert len(removed.addresses) == 1
        assert removed.addresses[0].is_primary is True
        assert removed.street == "Pierwsza"
        assert db.query(Client).filter(Client.id == client.id).one().address_records
        assert any(item.deleted_at is not None for item in removed.address_records)
    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_duplicate_addresses_rejected() -> None:
    address = ClientAddressInput(street="Ta sama", city="Łódź")
    try:
        ClientUpdate(addresses=[address, address.model_copy()])
    except ValidationError as error:
        assert "Duplicate client address" in str(error)
    else:
        raise AssertionError("Duplicate address must be rejected")


def test_provenance_is_reference_only() -> None:
    fields = ClientRead.model_fields
    address_fields = fields["addresses"].annotation.__args__[0].model_fields
    contact_fields = fields["emails"].annotation.__args__[0].model_fields
    for provenance_fields in (address_fields, contact_fields):
        assert {"origin", "source_type", "source_id"}.issubset(provenance_fields)
        assert "body" not in provenance_fields
        assert "raw_payload" not in provenance_fields


if __name__ == "__main__":
    test_multiple_addresses_primary_switch_and_soft_removal()
    test_duplicate_addresses_rejected()
    test_provenance_is_reference_only()
    print("CHUNK 7 contact/address tests: PASS")
