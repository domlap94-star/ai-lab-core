from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.client import Client
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import (
    ProjectClientNotFoundError,
    ProjectNotFoundError,
    ProjectService,
)


class ProjectFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not inspect(engine).has_table("projects"):
            self.skipTest("chunk10aproject_20260817 is not applied")
        self.connection = engine.connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.actor = self.db.query(User).filter(User.is_active.is_(True)).first()
        self.assertIsNotNone(self.actor)
        suffix = uuid.uuid4().hex
        self.client_a = Client(
            client_type="company",
            name=f"Chunk10A A {suffix}",
            country_code="PL",
        )
        self.client_b = Client(
            client_type="company",
            name=f"Chunk10A B {suffix}",
            country_code="PL",
        )
        self.db.add_all([self.client_a, self.client_b])
        self.db.flush()
        self.service = ProjectService(self.db)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def _create_project(
        self,
        *,
        client_id: int | None = None,
        name: str = "Realizacja testowa",
        status: str = "planned",
    ) -> Project:
        return self.service.create(
            ProjectCreate(
                client_id=client_id or self.client_a.id,
                name=name,
                status=status,
                start_date=date(2026, 8, 17),
                street="Projektowa",
                building_number="10",
                city="Warszawa",
                latitude=52.2297,
                longitude=21.0122,
            ),
            self.actor,
        )

    def test_migration_contract_and_schema_are_additive(self) -> None:
        migration_path = Path(
            "/app/alembic/versions/"
            "chunk10aproject_20260817_add_project_foundation.py"
        )
        migration = migration_path.read_text(encoding="utf-8")
        upgrade = migration.split("def downgrade", 1)[0]
        self.assertIn("create_table", upgrade)
        self.assertIn("op.add_column", upgrade)
        self.assertIn('ondelete="RESTRICT"', upgrade)
        self.assertNotIn("drop_", upgrade.lower())
        self.assertNotIn("update(", upgrade.lower())
        inspector = inspect(self.connection)
        self.assertTrue(inspector.has_table("projects"))
        self.assertIn(
            "project_id",
            {column["name"] for column in inspector.get_columns("documents")},
        )

    def test_crud_search_filters_pagination_and_soft_delete(self) -> None:
        first = self._create_project(name="Alpha realizacja")
        second = self._create_project(
            client_id=self.client_b.id,
            name="Beta realizacja",
            status="active",
        )

        page = self.service.get_page(
            search="Alpha", client_id=None, status=None, skip=0, limit=1
        )
        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].id, first.id)
        self.assertEqual(
            self.service.get_page(
                search=None,
                client_id=self.client_b.id,
                status=None,
                skip=0,
                limit=50,
            ).items[0].id,
            second.id,
        )
        self.assertEqual(
            self.service.get_page(
                search=None,
                client_id=None,
                status="active",
                skip=0,
                limit=50,
            ).items[0].id,
            second.id,
        )

        updated = self.service.update(
            first.id,
            ProjectUpdate(name="Alpha po zmianie", status="completed", city="Łódź"),
            self.actor,
        )
        self.assertEqual(updated.name, "Alpha po zmianie")
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.city, "Łódź")
        self.assertEqual(updated.street, "Projektowa")
        self.assertEqual(updated.client_id, self.client_a.id)

        with self.assertRaises(ProjectClientNotFoundError):
            self.service.update(
                first.id,
                ProjectUpdate(client_id=9_999_999_999),
                self.actor,
            )

        self.service.delete(first.id, self.actor)
        with self.assertRaises(ProjectNotFoundError):
            self.service.get(first.id)
        self.assertEqual(
            self.service.get_page(
                search="Alpha", client_id=None, status=None, skip=0, limit=50
            ).total,
            0,
        )

    def test_deleted_client_and_schema_validation_are_rejected(self) -> None:
        self.client_b.deleted_at = datetime.now(UTC)
        self.db.flush()
        with self.assertRaises(ProjectClientNotFoundError):
            self._create_project(client_id=self.client_b.id)

        invalid_payloads = [
            {"client_id": self.client_a.id, "name": "x", "status": "invalid"},
            {
                "client_id": self.client_a.id,
                "name": "x",
                "start_date": date(2026, 8, 18),
                "end_date": date(2026, 8, 17),
            },
            {"client_id": self.client_a.id, "name": "x", "latitude": 52.1},
            {
                "client_id": self.client_a.id,
                "name": "x",
                "latitude": 91,
                "longitude": 21,
            },
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ProjectCreate.model_validate(payload)

    def test_project_delete_preserves_document_and_derived_records(self) -> None:
        project = self._create_project()
        suffix = uuid.uuid4().hex
        document = Document(
            filename=f"{suffix}.pdf",
            original_filename="project.pdf",
            content_type="application/pdf",
            file_size=4,
            source_type="manual_upload",
            storage_path=f"synthetic/{suffix}.pdf",
            client_id=self.client_a.id,
            project_id=project.id,
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.db.add(document)
        self.db.flush()
        self.db.add_all(
            [
                DocumentPage(document_id=document.id, page_number=1),
                DocumentAsset(
                    document_id=document.id,
                    asset_index=1,
                    storage_path=f"synthetic/{suffix}-asset.bin",
                ),
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    content="synthetic",
                    token_count=1,
                    character_count=9,
                ),
            ]
        )
        self.db.flush()

        self.service.delete(project.id, self.actor)
        persisted = self.db.query(Document).filter(Document.id == document.id).one()
        self.assertEqual(persisted.project_id, project.id)
        self.assertEqual(persisted.storage_path, document.storage_path)
        self.assertEqual(self.db.query(DocumentPage).filter_by(document_id=document.id).count(), 1)
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document.id).count(), 1)
        self.assertEqual(self.db.query(DocumentChunk).filter_by(document_id=document.id).count(), 1)

    def test_user_upload_validates_project_client_and_returns_relation(self) -> None:
        project = self._create_project()
        suffix = uuid.uuid4().hex
        document = Document(
            filename=f"{suffix}.txt",
            original_filename="project.txt",
            content_type="text/plain",
            file_size=4,
            source_type="manual_upload",
            storage_path=f"synthetic/{suffix}.txt",
            client_id=self.client_a.id,
            project_id=project.id,
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.db.add(document)
        self.db.flush()

        app.dependency_overrides[get_current_user] = lambda: self.actor
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)
        stored = SimpleNamespace(document=document, created=True, matched_by=None)
        with patch(
            "app.api.documents.router.DocumentService.store_document",
            return_value=stored,
        ) as store:
            response = client.post(
                "/api/v1/documents/user-upload",
                data={"client_id": self.client_a.id, "project_id": project.id},
                files={"file": ("project.txt", b"test", "text/plain")},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["document"]["project_id"], project.id)
            self.assertEqual(store.call_args.kwargs["client_id"], self.client_a.id)
            self.assertEqual(store.call_args.kwargs["project_id"], project.id)

            mismatch = client.post(
                "/api/v1/documents/user-upload",
                data={"client_id": self.client_b.id, "project_id": project.id},
                files={"file": ("project.txt", b"test", "text/plain")},
            )
            self.assertEqual(mismatch.status_code, 409)

    def test_project_endpoints_require_authentication(self) -> None:
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/projects").status_code, 401)
        self.assertEqual(client.get("/api/v1/projects/1").status_code, 401)
        self.assertEqual(
            client.post(
                "/api/v1/projects",
                json={"client_id": self.client_a.id, "name": "x"},
            ).status_code,
            401,
        )


def print_read_only_audit() -> None:
    connection = engine.connect()
    transaction = connection.begin()
    try:
        values = connection.execute(
            text(
                "select "
                "(select count(1) from clients) clients_total, "
                "(select count(1) from clients where deleted_at is null) clients_active, "
                "(select count(1) from documents) documents, "
                "(select count(1) from projects) projects, "
                "(select count(1) from documents where project_id is not null) project_documents"
            )
        ).mappings().one()
        print(f"CHUNK 10A post-migration audit: {dict(values)}")
    finally:
        transaction.rollback()
        connection.close()


if __name__ == "__main__":
    print_read_only_audit()
    unittest.main()
