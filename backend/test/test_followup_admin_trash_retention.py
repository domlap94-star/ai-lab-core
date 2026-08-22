from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.security import create_access_token, hash_password
from app.database.session import SessionLocal
from app.main import app
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.models.contact_person import ContactPerson
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.role import Role
from app.models.trash_entry import TrashEntry
from app.models.user import User
from app.repositories.client_repository import ClientRepository
from app.repositories.document_repository import DocumentRepository
from app.services.qdrant_vector_store import (
    DocumentVectorPurgePlan,
    QdrantDocumentPurgeError,
    QdrantVectorStore,
)
from app.services.trash_lifecycle_service import (
    TrashConflictError,
    TrashLifecycleService,
    TrashPurgeRunner,
)
from app.services.user_lifecycle_service import UserLifecycleConflictError, UserLifecycleService


TEST_ROOT = Path("/tmp/ai-lab-trash-lifecycle")
PASSWORD = "Trash-Test-Password-2026"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def synthetic_qdrant_plan(*, document_id, references):
    if references:
        raise QdrantDocumentPurgeError("qdrant_ownership_mismatch")
    return DocumentVectorPurgePlan(
        document_id=document_id,
        expected_vector_ids=(),
        present_vector_ids=(),
        missing_vector_ids=(),
    )


def make_document(db, suffix: str, content: bytes) -> tuple[Document, Path]:
    relative = Path("documents") / f"trash-{suffix}.bin"
    path = TEST_ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    document = Document(
        filename=path.name,
        original_filename=f"synthetic-{suffix}.bin",
        content_type="application/octet-stream",
        file_size=len(content),
        storage_path=str(relative).replace("\\", "/"),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        source_type="manual_upload",
        processing_status="processed",
        metadata_status="processed",
        match_status="unmatched",
    )
    db.add(document)
    db.flush()
    return document, path


def age_entry(db, entry: TrashEntry) -> None:
    old = datetime.now(timezone.utc) - timedelta(days=8)
    entry.trashed_at = old
    entry.purge_after = old + timedelta(days=7)
    if entry.entity_type == "document":
        db.query(Document).filter(Document.id == entry.entity_id).update({"trashed_at": old})
    elif entry.entity_type == "client":
        db.query(Client).filter(Client.id == entry.entity_id).update({"deleted_at": old})
    else:
        db.query(User).filter(User.id == entry.entity_id).update({"trashed_at": old})
    db.commit()


def main() -> None:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
    TEST_ROOT.mkdir(parents=True)
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        admin_role = db.query(Role).filter(Role.name == "Administrator").one()
        user_role = db.query(Role).filter(Role.name == "User").one()
        admin = User(
            username=f"trash_admin_{suffix}",
            email=f"trash_admin_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            role=admin_role,
            is_active=True,
        )
        second_admin = User(
            username=f"trash_admin2_{suffix}",
            email=f"trash_admin2_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            role=admin_role,
            is_active=True,
        )
        normal = User(
            username=f"trash_user_{suffix}",
            email=f"trash_user_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            role=user_role,
            is_active=True,
        )
        legacy_inactive = User(
            username=f"trash_inactive_{suffix}",
            email=f"trash_inactive_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            role=user_role,
            is_active=False,
        )
        db.add_all([admin, second_admin, normal, legacy_inactive])
        db.commit()

        legacy_token = create_access_token({"sub": normal.username})
        versioned_token = create_access_token(
            {"sub": normal.username, "auth_version": normal.auth_version}
        )
        admin_token = create_access_token(
            {"sub": admin.username, "auth_version": admin.auth_version}
        )
        with TestClient(app) as http:
            require(
                http.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy_token}"}).status_code == 200,
                "Legacy auth_version=0 token was rejected",
            )
            require(
                http.get(
                    "/api/v1/admin/trash",
                    headers={"Authorization": f"Bearer {versioned_token}"},
                ).status_code == 403,
                "Normal User accessed admin Trash",
            )
            require(
                http.get(
                    "/api/v1/admin/trash",
                    headers={"Authorization": f"Bearer {admin_token}"},
                ).status_code == 200,
                "Administrator could not list Trash",
            )
            users = http.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            require(users.status_code == 200, "Administrator could not list users")
            listed_ids = {row["id"] for row in users.json()}
            require(normal.id in listed_ids, "Active User missing from management list")
            require(
                legacy_inactive.id not in listed_ids,
                "Inactive legacy User leaked into active management list",
            )

        service = TrashLifecycleService(db, data_root=TEST_ROOT)
        inactive_entry = service.trash(
            entity_type="user",
            entity_id=legacy_inactive.id,
            actor=admin,
        )
        db.commit()
        require(not legacy_inactive.is_active, "Inactive User was reactivated during Trash")
        require(
            legacy_inactive.trashed_at is not None and legacy_inactive.auth_version == 1,
            "Inactive-to-Trash lifecycle markers missing",
        )
        require(inactive_entry.state == "trashed", "Inactive User Trash entry missing")
        try:
            service.trash(entity_type="user", entity_id=admin.id, actor=admin)
        except TrashConflictError as error:
            require(str(error) == "self_trash_forbidden", "Wrong self-trash error")
            db.rollback()
        else:
            raise AssertionError("Self-trash was accepted")
        try:
            UserLifecycleService.ensure_admin_survives(
                target_user_id=admin.id,
                active_administrator_ids={admin.id},
            )
        except UserLifecycleConflictError:
            pass
        else:
            raise AssertionError("Last Administrator protection failed")

        user_entry = service.trash(entity_type="user", entity_id=normal.id, actor=admin)
        db.commit()
        require(not normal.is_active and normal.auth_version == 1, "User trash state mismatch")
        with TestClient(app) as http:
            require(
                http.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {versioned_token}"}).status_code == 401,
                "Pre-trash JWT remained valid",
            )
        service.restore(entry_id=user_entry.id, actor=admin)
        db.commit()
        require(normal.is_active and normal.auth_version == 2, "User restore state mismatch")
        with TestClient(app) as http:
            require(
                http.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {versioned_token}"}).status_code == 401,
                "Old JWT became valid after restore",
            )
            login = http.post(
                "/api/v1/auth/login",
                data={"username": normal.username, "password": PASSWORD},
            )
            require(login.status_code == 200, "Restored user could not log in")

        client = Client(
            client_type="company",
            name=f"Synthetic Trash Client {suffix}",
            primary_email=f"client-{suffix}@example.invalid",
            primary_phone="+48000000000",
            country_code="PL",
            notes="synthetic private note",
        )
        db.add(client)
        db.flush()
        db.add(ClientContactPoint(
            client_id=client.id,
            kind="email",
            value=f"contact-{suffix}@example.invalid",
            normalized_value=f"contact-{suffix}@example.invalid",
            origin="manual",
        ))
        db.add(ClientAddress(client_id=client.id, label="Synthetic", city="Test City"))
        db.commit()
        client_entry = service.trash(entity_type="client", entity_id=client.id, actor=admin)
        db.commit()
        require(ClientRepository(db).get(client.id) is None, "Trashed Client remains active")
        service.restore(entry_id=client_entry.id, actor=admin)
        db.commit()
        require(ClientRepository(db).get(client.id) is not None, "Client restore failed")

        document, document_path = make_document(db, suffix + "-restore", b"same canonical bytes")
        db.commit()
        document_entry = service.trash(entity_type="document", entity_id=document.id, actor=admin)
        db.commit()
        require(DocumentRepository(db).get(document.id) is None, "Trashed Document remains visible")
        require(document_path.read_bytes() == b"same canonical bytes", "Trash changed bytes")
        with TestClient(app) as http:
            headers = {"Authorization": f"Bearer {admin_token}"}
            require(http.get(f"/api/v1/documents/{document.id}", headers=headers).status_code == 404, "Trashed detail is visible")
            require(http.get(f"/api/v1/documents/{document.id}/content", headers=headers).status_code == 404, "Trashed content is visible")
            require(http.get(f"/api/v1/documents/{document.id}/thumbnail", headers=headers).status_code == 404, "Trashed thumbnail is visible")
        service.restore(entry_id=document_entry.id, actor=admin)
        db.commit()
        require(DocumentRepository(db).get(document.id).id == document.id, "Document same-ID restore failed")
        require(document_path.read_bytes() == b"same canonical bytes", "Restore changed bytes")

        early, early_path = make_document(db, suffix + "-early", b"not due")
        db.commit()
        early_entry = service.trash(entity_type="document", entity_id=early.id, actor=admin)
        db.commit()
        with patch.object(QdrantVectorStore, "prepare_document_purge", side_effect=synthetic_qdrant_plan), patch.object(QdrantVectorStore, "delete_document_points", return_value=0):
            early_summary = TrashPurgeRunner(data_root=TEST_ROOT).run()
        require(early_path.exists(), "Document purged before seven days")
        require(db.get(TrashEntry, early_entry.id).state == "trashed", "Early entry state changed")

        vector, vector_path = make_document(db, suffix + "-vector", b"vector bytes")
        db.add(DocumentChunk(
            document_id=vector.id,
            chunk_index=0,
            content="synthetic",
            token_count=1,
            character_count=9,
            vector_id=f"synthetic-vector-{suffix}",
        ))
        db.commit()
        vector_entry = service.trash(entity_type="document", entity_id=vector.id, actor=admin)
        db.commit()
        age_entry(db, vector_entry)
        with patch.object(QdrantVectorStore, "prepare_document_purge", side_effect=TimeoutError("synthetic outage")):
            summary = TrashPurgeRunner(data_root=TEST_ROOT).run()
        db.expire_all()
        blocked = db.get(TrashEntry, vector_entry.id)
        require(blocked.state == "blocked", "Vectorized Document was not blocked")
        require(blocked.last_error_code == "qdrant_preflight_unavailable", "Wrong outage block code")
        require(vector_path.exists(), "Vectorized Document bytes changed")
        require(db.get(Document, vector.id).extracted_text == vector.extracted_text, "Vectorized Document content changed")
        require(int(summary["blocked"]) >= 1, "Vector block not reported")

        purge_doc, purge_path = make_document(db, suffix + "-purge", b"purge-safe bytes")
        purge_doc.extracted_text = "sensitive extracted text"
        db.commit()
        purge_entry = service.trash(entity_type="document", entity_id=purge_doc.id, actor=admin)
        db.commit()
        age_entry(db, purge_entry)
        with patch.object(QdrantVectorStore, "prepare_document_purge", side_effect=synthetic_qdrant_plan), patch.object(QdrantVectorStore, "delete_document_points", return_value=0):
            purge_summary = TrashPurgeRunner(data_root=TEST_ROOT).run()
        db.expire_all()
        purged_doc = db.get(Document, purge_doc.id)
        require(int(purge_summary["purged"]) >= 1, "Non-vector Document was not purged")
        require(not purge_path.exists(), "Purged storage bytes remain")
        require(purged_doc.purged_at is not None and purged_doc.extracted_text is None, "Document tombstone not scrubbed")

        purge_client = Client(
            client_type="person",
            name=f"Private {suffix}",
            primary_email=f"private-{suffix}@example.invalid",
            country_code="PL",
            notes="sensitive",
        )
        db.add(purge_client)
        db.flush()
        purge_person = ContactPerson(
            client_id=purge_client.id,
            display_name=f"Private Person {suffix}",
            role="Sensitive role",
            notes="sensitive person note",
            is_preferred=True,
            is_decision_maker=True,
            position=0,
            origin="manual",
        )
        db.add(purge_person)
        db.commit()
        purge_client_entry = service.trash(entity_type="client", entity_id=purge_client.id, actor=admin)
        db.commit()
        age_entry(db, purge_client_entry)

        purge_user = User(
            username=f"purge_user_{suffix}",
            email=f"purge_user_{suffix}@example.invalid",
            password_hash=hash_password(PASSWORD),
            role=user_role,
            is_active=True,
        )
        db.add(purge_user)
        db.commit()
        purge_user_entry = service.trash(entity_type="user", entity_id=purge_user.id, actor=admin)
        db.commit()
        age_entry(db, purge_user_entry)
        with patch.object(QdrantVectorStore, "prepare_document_purge", side_effect=synthetic_qdrant_plan), patch.object(QdrantVectorStore, "delete_document_points", return_value=0):
            tombstone_summary = TrashPurgeRunner(data_root=TEST_ROOT).run()
        db.expire_all()
        purge_client = db.get(Client, purge_client.id)
        purge_person = db.get(ContactPerson, purge_person.id)
        purge_user = db.get(User, purge_user.id)
        require(purge_client.purged_at is not None and purge_client.primary_email is None, "Client PII tombstone failed")
        require(
            purge_person.deleted_at is not None
            and purge_person.display_name == f"Usunięta osoba #{purge_person.id}"
            and purge_person.role is None
            and purge_person.notes is None
            and not purge_person.is_preferred
            and not purge_person.is_decision_maker,
            "ContactPerson PII tombstone failed",
        )
        require(purge_user.purged_at is not None and purge_user.email.endswith(".invalid"), "User tombstone failed")
        require(not purge_user.is_active and purge_user.auth_version == 2, "User purge auth state mismatch")
        require(int(tombstone_summary["purged"]) >= 2, "Tombstone purge count mismatch")

        try:
            service.restore(entry_id=purge_user_entry.id, actor=admin)
        except TrashConflictError as error:
            require(str(error) == "trash_entry_already_purged", "Wrong irreversible restore error")
            db.rollback()
        else:
            raise AssertionError("Purged entry was restored")

        require(db.query(TrashEntry).filter(TrashEntry.entity_id == early.id, TrashEntry.entity_type == "document").count() == 1, "Duplicate active Trash entry")
        print("FOLLOWUP_ADMIN_TRASH_RETENTION=PASS")
        print("legacy_token_compatibility=PASS")
        print("user_auth_versioning=PASS")
        print("document_vector_fail_closed=PASS")
        print("document_nonvector_purge=PASS")
        print("client_user_tombstones=PASS")
        print(f"early_runner_eligible={early_summary['eligible']}")
    finally:
        db.close()
        shutil.rmtree(TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    main()
