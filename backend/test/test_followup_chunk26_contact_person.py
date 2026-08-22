from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from test.support.database_safety import assert_isolated_database, require_test_database_environment


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.security import create_access_token, hash_password
from app.database.session import SessionLocal
from app.main import app
from app.models.change_history_event import ChangeHistoryEvent
from app.models.client import Client
from app.models.client_contact_point import ClientContactPoint
from app.models.contact_person import ContactPerson
from app.models.role import Role
from app.models.user import User
from app.repositories.client_repository import ClientRepository
from app.repositories.import_repository import ImportRepository
from app.schemas.import_ingest import CandidateDataInput, CandidateSourceInput, ImportIngestRequest
from app.services.email_client_matching_service import EmailClientMatchingService
from app.services.forward_source_ingestion_service import ForwardSourceIngestionService
from app.services.global_search_service import GlobalSearchService
from app.services.agent_tool_registry import AgentToolRegistry


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        role = db.query(Role).filter(Role.name == "User").first()
        if role is None:
            role = Role(name="User", description="Isolated Client editor")
            db.add(role)
            db.flush()
        user = User(
            username=f"cp_{suffix}",
            email=f"cp_{suffix}@example.invalid",
            password_hash=hash_password("Chunk26-Test!"),
            role=role,
            is_active=True,
        )
        client = Client(client_type="company", name=f"Chunk26 Alpha {suffix}", country_code="PL")
        other_client = Client(client_type="company", name=f"Chunk26 Beta {suffix}", country_code="PL")
        db.add_all([user, client, other_client])
        db.flush()
        generic = ClientContactPoint(
            client_id=client.id,
            kind="email",
            value=f"office-{suffix}@example.invalid",
            normalized_value=f"office-{suffix}@example.invalid",
            is_primary=True,
            position=0,
            origin="manual",
        )
        foreign_point = ClientContactPoint(
            client_id=other_client.id,
            kind="phone",
            value="+48 599 000 000",
            normalized_value="599000000",
            is_primary=True,
            position=0,
            origin="manual",
        )
        db.add_all([generic, foreign_point])
        db.commit()
        db.refresh(user); db.refresh(client); db.refresh(other_client); db.refresh(generic); db.refresh(foreign_point)
        headers = {"Authorization": f"Bearer {create_access_token({'sub': user.username, 'auth_version': user.auth_version})}"}
        api = TestClient(app)

        unauthenticated = api.get(f"/api/v1/clients/{client.id}/contact-persons")
        require(unauthenticated.status_code == 401, "unauthenticated person list was allowed")
        created = api.post(
            f"/api/v1/clients/{client.id}/contact-persons",
            headers=headers,
            json={
                "display_name": "  Jan   Kowalski  ",
                "role": "Kierownik obiektu",
                "is_preferred": True,
                "is_decision_maker": True,
                "notes": "Kontakt syntetyczny",
                "contact_point_ids": [generic.id],
                "emails": [{"value": f"jan-{suffix}@example.invalid"}],
                "phones": [{"value": "+48 500 000 001"}],
            },
        )
        require(created.status_code == 201, f"person create failed: {created.text}")
        person = created.json()
        require(person["display_name"] == "Jan Kowalski", "display name was not normalized")
        require(len(person["contact_points"]) == 3, "coordinate assignment/create failed")
        person_id = person["id"]

        second_preferred = api.post(
            f"/api/v1/clients/{client.id}/contact-persons",
            headers=headers,
            json={"display_name": "Druga Preferowana", "is_preferred": True},
        )
        require(second_preferred.status_code == 409, "second preferred person was allowed")
        decision_maker = api.post(
            f"/api/v1/clients/{client.id}/contact-persons",
            headers=headers,
            json={"display_name": "Anna Decyzyjna", "is_decision_maker": True},
        )
        require(decision_maker.status_code == 201, "multiple decision makers were rejected")
        cross_client = api.patch(
            f"/api/v1/clients/{client.id}/contact-persons/{person_id}",
            headers=headers,
            json={"contact_point_ids": [foreign_point.id]},
        )
        require(cross_client.status_code == 422, "cross-client coordinate assignment was allowed")
        duplicate = api.patch(
            f"/api/v1/clients/{client.id}/contact-persons/{person_id}",
            headers=headers,
            json={"emails": [{"value": f"JAN-{suffix}@example.invalid"}]},
        )
        require(duplicate.status_code == 409, "duplicate normalized coordinate was allowed")

        for query in ("Jan Kowalski", "Kierownik obiektu", f"jan-{suffix}@example.invalid", "500000001"):
            rows, total = ClientRepository(db).get_page(search=query)
            require(total == 1 and rows[0].id == client.id, f"Client Search failed for {query}")
        global_result = GlobalSearchService(db).search(
            query="Jan Kowalski", types=("client",), semantic=False
        )
        require(global_result.items and global_result.items[0].id == client.id,
                "Global Search failed for ContactPerson name")
        require("Osoba kontaktowa: Jan Kowalski" in (global_result.items[0].subtitle or ""),
                "Global Search omitted person match context")

        sender = f"jan-{suffix}@example.invalid"
        mail_request = ForwardSourceIngestionService().prepare(ImportIngestRequest(
            import_source_id=1,
            candidate=CandidateDataInput(name="Synthetic sender", primary_email=sender),
            source=CandidateSourceInput(
                source_type="gmail_message",
                external_id=f"chunk26-{suffix}",
                raw_payload={"from": {"value": [{"address": sender, "name": "Synthetic sender"}]}},
            ),
        ))
        mail_match = EmailClientMatchingService(ImportRepository(db)).match(mail_request)
        require(mail_match.client is not None and mail_match.client.id == client.id,
                "person-owned email stopped Client matching")
        require(mail_match.matched_contact_person_id == person_id,
                "exact person-owned email did not add person attribution")
        agent_contacts = AgentToolRegistry(db, client_id=client.id).execute(
            "get_client_contacts", {"client_id": client.id}
        ).data["contacts"]
        attributed = next(row for row in agent_contacts if row["value"] == sender)
        require(attributed["person_id"] == person_id and attributed["person_name"] == "Jan Kowalski",
                "Agent contact projection omitted person attribution")

        removed = api.delete(f"/api/v1/clients/{client.id}/contact-persons/{person_id}", headers=headers)
        require(removed.status_code == 204, f"person archive failed: {removed.text}")
        db.expire_all()
        require(db.get(ContactPerson, person_id).deleted_at is not None, "person was not soft-deleted")
        owned = db.query(ClientContactPoint).filter(ClientContactPoint.client_id == client.id).all()
        require(len(owned) == 3 and all(point.contact_person_id is None for point in owned),
                "archive lost or retained coordinate ownership")
        actions = {
            row.action for row in db.query(ChangeHistoryEvent).filter(
                ChangeHistoryEvent.entity_type == "contact_person",
                ChangeHistoryEvent.entity_id == person_id,
            ).all()
        }
        require({"created", "deleted"}.issubset(actions), "ContactPerson history missing")

        # Clean only this isolated fixture; production is structurally unreachable by the guard.
        db.query(ChangeHistoryEvent).filter(ChangeHistoryEvent.source_key.like(f"contact-person:%")).delete(synchronize_session=False)
        db.query(ClientContactPoint).filter(ClientContactPoint.client_id.in_([client.id, other_client.id])).delete(synchronize_session=False)
        db.query(ContactPerson).filter(ContactPerson.client_id.in_([client.id, other_client.id])).delete(synchronize_session=False)
        db.delete(client); db.delete(other_client); db.delete(user); db.commit()
    finally:
        db.close()
    print("FOLLOWUP_CHUNK26_CONTACT_PERSON_API=PASS")
    print("AUTH=PASS")
    print("SEARCH_MATRIX=PASS")
    print("MAIL_CLIENT_MATCH_AND_PERSON_ATTRIBUTION=PASS")
    print("LIFECYCLE_COORDINATES_PRESERVED=PASS")


if __name__ == "__main__":
    main()
