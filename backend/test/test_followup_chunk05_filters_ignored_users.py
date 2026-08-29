from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.security import hash_password
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.client import Client
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.client_workflow_status import ClientWorkflowStatus
from app.models.change_history_event import ChangeHistoryEvent
from app.models.ignored_mail_source import IgnoredMailSource
from app.models.import_source import ImportSource
from app.models.role import Role
from app.models.user import User
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
)
from app.services.client_service import ClientService
from app.services.change_history_service import ChangeHistoryService
from app.services.ignored_mail_source_service import (
    IgnoredMailSourceService,
    normalize_ignored_mail_value,
)
from app.services.import_ingest_service import ImportIngestService


PASSWORD = "Chunk05-Synthetic-Password-2026"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


@contextmanager
def rollback_database():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


def login(client: TestClient, username: str) -> str:
    result = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": PASSWORD},
    )
    require(result.status_code == 200, result.text)
    return result.json()["access_token"]


def seed_isolated_roles() -> None:
    with Session(bind=engine) as db:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        for name, description in (
            ("Administrator", "Synthetic isolated-test administrator"),
            ("User", "Synthetic isolated-test user"),
        ):
            if db.query(Role).filter(Role.name == name).first() is None:
                db.add(Role(name=name, description=description))
        db.commit()


def main() -> None:
    require(
        normalize_ignored_mail_value("email", " Test.User@Example.COM ")
        == "test.user@example.com",
        "email normalization failed",
    )
    require(
        normalize_ignored_mail_value("domain", " @Example.COM ")
        == "example.com",
        "domain normalization failed",
    )
    for invalid in ("https://example.com", "*.example.com", "example.com/path"):
        try:
            normalize_ignored_mail_value("domain", invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid domain accepted: {invalid}")
    for invalid in ("", "missing-at.example.com", "two@@example.com", "x@localhost"):
        try:
            normalize_ignored_mail_value("email", invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid email accepted: {invalid}")

    seed_isolated_roles()
    suffix = uuid4().hex[:10]
    with rollback_database() as db:
        admin_role = db.query(Role).filter(Role.name == "Administrator").one()
        user_role = db.query(Role).filter(Role.name == "User").one()
        admin = User(
            username=f"chunk05_admin_{suffix}",
            email=f"chunk05_admin_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            is_active=True,
            must_change_password=False,
            password_reset_requested=False,
            role=admin_role,
        )
        ordinary = User(
            username=f"chunk05_user_{suffix}",
            email=f"chunk05_user_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            is_active=True,
            must_change_password=False,
            password_reset_requested=False,
            role=user_role,
        )
        clients = [
            Client(client_type="company", name=f"Chunk05_{suffix} A"),
            Client(client_type="company", name=f"Chunk05_{suffix} B"),
            Client(client_type="company", name=f"Chunk05_{suffix} C"),
        ]
        db.add_all([admin, ordinary, *clients])
        db.flush()
        db.add_all(
            [
                ClientWorkflowStatus(client_id=clients[0].id, status="completed"),
                ClientWorkflowStatus(client_id=clients[1].id, status="obsolete"),
            ]
        )
        db.flush()

        page = ClientService(db).get_clients(
            search=f"Chunk05_{suffix}",
            exclude_statuses=["completed", "untouched"],
            sort_order="newest",
        )
        require([item.id for item in page.items] == [clients[1].id], "status exclusions")
        all_page = ClientService(db).get_clients(
            search=f"Chunk05_{suffix}",
            exclude_statuses=[],
            sort_order="oldest",
            skip=0,
            limit=2,
        )
        require(all_page.total == 3, "no-exclusion total")
        require(len(all_page.items) == 2, "pagination limit")
        one_excluded = ClientService(db).get_clients(
            search=f"Chunk05_{suffix}",
            exclude_statuses=["obsolete"],
            sort_order="oldest",
            skip=1,
            limit=10,
        )
        require(one_excluded.total == 2, "single exclusion before pagination")
        require(len(one_excluded.items) == 1, "pagination applied before filtering")

        ignored = IgnoredMailSourceService(db)
        historical_counts = (
            db.query(Client).count(),
            db.query(ClientCandidate).count(),
            db.query(CandidateSource).count(),
        )
        email_rule = ignored.ignore(
            rule_type="email",
            value="Sender@Example.com",
            actor_user_id=admin.id,
        )
        domain_rule = ignored.ignore(
            rule_type="domain",
            value="@noise.invalid",
            actor_user_id=admin.id,
        )
        db.flush()
        require(ignored.matches("sender@example.com"), "exact email match")
        require(ignored.matches("x@noise.invalid"), "exact domain match")
        require(not ignored.matches("x@sub.noise.invalid"), "no subdomain fuzzy match")
        require(not ignored.matches("other@example.com"), "unrelated sender match")
        same = ignored.ignore(
            rule_type="email",
            value="sender@example.com",
            actor_user_id=admin.id,
        )
        require(same.id == email_rule.id, "duplicate rule was not reused")
        overlap_domain = ignored.ignore(
            rule_type="domain",
            value="example.com",
            actor_user_id=admin.id,
        )
        ignored.unignore(rule_id=email_rule.id, actor_user_id=admin.id)
        require(
            ignored.matches("sender@example.com"),
            "domain overlap was incorrectly removed with exact email",
        )
        ignored.unignore(rule_id=overlap_domain.id, actor_user_id=admin.id)
        require(not ignored.matches("sender@example.com"), "unignore failed")
        reactivated = ignored.ignore(
            rule_type="email",
            value="SENDER@example.com",
            actor_user_id=admin.id,
        )
        require(reactivated.id == email_rule.id, "reactivation created duplicate")
        actions = [
            row.action
            for row in db.query(ChangeHistoryEvent)
            .filter(
                ChangeHistoryEvent.entity_type == "ignored_mail_source",
                ChangeHistoryEvent.entity_id == email_rule.id,
            )
            .order_by(ChangeHistoryEvent.id)
        ]
        require(actions == ["created", "deactivated", "activated"], str(actions))
        history_rows = (
            db.query(ChangeHistoryEvent)
            .filter(ChangeHistoryEvent.entity_type == "ignored_mail_source")
            .all()
        )
        require(
            all("sender@example.com" not in str(row.after_values) for row in history_rows),
            "raw ignored email leaked into Change History",
        )
        require(domain_rule.is_active, "domain rule unexpectedly changed")
        require(
            historical_counts
            == (
                db.query(Client).count(),
                db.query(ClientCandidate).count(),
                db.query(CandidateSource).count(),
            ),
            "ignore rule lifecycle mutated historical business rows",
        )

        gmail_source = (
            db.query(ImportSource)
            .filter(
                ImportSource.source_type == "gmail",
                ImportSource.is_enabled.is_(True),
            )
            .first()
        )
        if gmail_source is None:
            gmail_source = ImportSource(
                source_type="gmail",
                display_name=f"Synthetic ignored-mail source {suffix}",
                status="active",
                is_enabled=True,
            )
            db.add(gmail_source)
            db.flush()

        def gmail_request(address: str, external_id: str) -> ImportIngestRequest:
            return ImportIngestRequest(
                import_source_id=gmail_source.id,
                candidate=CandidateDataInput(
                    client_type="person",
                    name="Synthetic ignored-mail fixture",
                    primary_email=address,
                    country_code="PL",
                    confidence=0.9,
                ),
                source=CandidateSourceInput(
                    source_type="gmail_message",
                    external_id=external_id,
                    source_label="Synthetic CHUNK 05 ignored-mail fixture",
                    raw_payload={
                        "from": {
                            "value": [
                                {
                                    "address": address,
                                    "name": "Synthetic fixture",
                                }
                            ]
                        },
                        "direction": "incoming",
                    },
                ),
            )

        ingest = ImportIngestService(db)
        ignored_request = gmail_request(
            "sender@example.com",
            f"chunk05-ignored-{suffix}",
        )
        ignored_preview = ingest.preview_email_resolution(ignored_request)
        require(ignored_preview.match.matched_client is None, "ignored fixture matched Client")
        require(ignored_preview.ignored_unresolved, "ignored unresolved preview missing")
        ignored_result = ingest.ingest(
            ignored_request,
            email_resolution=ignored_preview,
        )
        ignored_candidate = db.get(ClientCandidate, ignored_result.candidate_id)
        ignored_source = db.get(CandidateSource, ignored_result.source_id)
        require(ignored_result.created_source, "ignored canonical source was not created")
        require(ignored_candidate is not None, "ignored Candidate missing")
        require(ignored_candidate.status == "rejected", "ignored Candidate not suppressed")
        require(ignored_source is not None, "ignored canonical source missing")

        linked_client = Client(
            client_type="company",
            name=f"Chunk05 linked {suffix}",
            primary_email=f"linked-{suffix}@noise.invalid",
        )
        db.add(linked_client)
        db.flush()
        linked_request = gmail_request(
            linked_client.primary_email,
            f"chunk05-linked-{suffix}",
        )
        linked_preview = ingest.preview_email_resolution(linked_request)
        require(
            linked_preview.match.matched_client is not None
            and linked_preview.match.matched_client.id == linked_client.id,
            "deterministic Client match was not preserved",
        )
        require(
            not linked_preview.ignored_unresolved,
            "ignore rule overrode deterministic Client match",
        )
        db.commit()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                admin_headers = {"Authorization": f"Bearer {login(client, admin.username)}"}
                user_headers = {"Authorization": f"Bearer {login(client, ordinary.username)}"}
                anonymous = client.patch(
                    f"/api/v1/admin/users/{ordinary.id}", json={"username": "ignored"}
                )
                require(anonymous.status_code == 401, "anonymous edit must be 401")
                forbidden = client.patch(
                    f"/api/v1/admin/users/{ordinary.id}",
                    json={"username": "ignored"},
                    headers=user_headers,
                )
                require(forbidden.status_code == 403, "non-admin edit must be 403")
                updated_name = f"chunk05_edited_{suffix}"
                success = client.patch(
                    f"/api/v1/admin/users/{ordinary.id}",
                    json={
                        "username": updated_name,
                        "email": f"edited_{suffix}@example.invalid",
                        "role": "User",
                    },
                    headers=admin_headers,
                )
                require(success.status_code == 200, success.text)
                require(success.json()["username"] == updated_name, "edit not returned")
                user_headers = {
                    "Authorization": f"Bearer {login(client, updated_name)}"
                }
                duplicate = client.patch(
                    f"/api/v1/admin/users/{ordinary.id}",
                    json={"username": admin.username},
                    headers=admin_headers,
                )
                require(duplicate.status_code == 409, "duplicate username must be 409")
                self_demote = client.patch(
                    f"/api/v1/admin/users/{admin.id}",
                    json={"role": "User"},
                    headers=admin_headers,
                )
                require(self_demote.status_code == 409, "self demotion must be blocked")
                admin_rules = client.get(
                    "/api/v1/admin/ignored-mail-sources", headers=admin_headers
                )
                require(admin_rules.status_code == 200, admin_rules.text)
                user_rules = client.get(
                    "/api/v1/admin/ignored-mail-sources", headers=user_headers
                )
                require(user_rules.status_code == 403, "ignored rules admin guard")
                anonymous_rule = client.post(
                    "/api/v1/admin/ignored-mail-sources",
                    json={"rule_type": "email", "value": "x@example.invalid"},
                )
                require(anonymous_rule.status_code == 401, "anonymous ignore must be 401")
                user_rule = client.post(
                    "/api/v1/admin/ignored-mail-sources",
                    json={"rule_type": "email", "value": "x@example.invalid"},
                    headers=user_headers,
                )
                require(user_rule.status_code == 403, "non-admin ignore must be 403")
                user_unignore = client.delete(
                    f"/api/v1/admin/ignored-mail-sources/{email_rule.id}",
                    headers=user_headers,
                )
                require(
                    user_unignore.status_code == 403,
                    "non-admin unignore must be 403",
                )
                api_rule_value = f"api-{suffix}@example.invalid"
                api_create = client.post(
                    "/api/v1/admin/ignored-mail-sources",
                    json={"rule_type": "email", "value": api_rule_value.upper()},
                    headers=admin_headers,
                )
                require(api_create.status_code == 200, api_create.text)
                require(
                    api_create.json()["normalized_value"] == api_rule_value,
                    "API create did not return normalized value",
                )
                api_rule_id = int(api_create.json()["id"])
                api_duplicate = client.post(
                    "/api/v1/admin/ignored-mail-sources",
                    json={"rule_type": "email", "value": api_rule_value},
                    headers=admin_headers,
                )
                require(api_duplicate.status_code == 200, api_duplicate.text)
                require(
                    int(api_duplicate.json()["id"]) == api_rule_id,
                    "API duplicate created another rule",
                )
                api_delete = client.delete(
                    f"/api/v1/admin/ignored-mail-sources/{api_rule_id}",
                    headers=admin_headers,
                )
                require(api_delete.status_code == 204, api_delete.text)
                api_rules_after = client.get(
                    "/api/v1/admin/ignored-mail-sources", headers=admin_headers
                )
                require(api_rules_after.status_code == 200, api_rules_after.text)
                require(
                    all(row["id"] != api_rule_id for row in api_rules_after.json()),
                    "deactivated API rule remained in active list",
                )
                rollback_value = f"rollback-{suffix}@example.invalid"
                with patch.object(
                    ChangeHistoryService,
                    "persist",
                    side_effect=RuntimeError("synthetic audit failure"),
                ):
                    audit_failure = client.post(
                        "/api/v1/admin/ignored-mail-sources",
                        json={"rule_type": "email", "value": rollback_value},
                        headers=admin_headers,
                    )
                require(audit_failure.status_code == 500, "audit failure must fail request")
                require(
                    db.query(IgnoredMailSource).filter(
                        IgnoredMailSource.normalized_value == rollback_value
                    ).count()
                    == 0,
                    "audit failure did not roll back ignored rule",
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

    print("FOLLOW-UP CHUNK 05 focused backend: PASS")


if __name__ == "__main__":
    main()
