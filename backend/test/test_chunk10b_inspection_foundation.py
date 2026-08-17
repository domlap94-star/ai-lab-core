from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.database.engine import engine
from app.main import app
from app.models.client import Client
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.user import User
from app.schemas.inspection import InspectionCreate, InspectionUpdate
from app.services.inspection_service import (
    InspectionClientProjectMismatchError,
    InspectionNotFoundError,
    InspectionProjectNotFoundError,
    InspectionService,
)


class InspectionFoundationContractTests(unittest.TestCase):
    def test_migration_is_additive_and_preserves_legacy_session_metadata(self) -> None:
        migration = Path(
            "/app/alembic/versions/"
            "chunk10binspect_20260817_add_inspection_foundation.py"
        ).read_text(encoding="utf-8")
        upgrade = migration.split("def downgrade", 1)[0]
        self.assertIn('revision = "chunk10binspect_20260817"', migration)
        self.assertIn('down_revision = "chunk10aproject_20260817"', migration)
        self.assertIn('op.create_table(\n        "inspections"', upgrade)
        self.assertIn('op.add_column("documents"', upgrade)
        self.assertIn('ondelete="RESTRICT"', upgrade)
        self.assertNotIn("drop_", upgrade.lower())
        self.assertNotIn("update(", upgrade.lower())
        self.assertNotIn("inspection_session_id", migration)

    def test_schema_rejects_invalid_status_location_and_time_order(self) -> None:
        base = {"project_id": 1, "client_id": 1, "title": "Wizja"}
        invalid = [
            {**base, "status": "unknown"},
            {**base, "latitude": 52.1},
            {**base, "latitude": 91, "longitude": 21},
            {
                **base,
                "status": "completed",
                "started_at": datetime(2026, 8, 17, 12, tzinfo=UTC),
                "completed_at": datetime(2026, 8, 17, 11, tzinfo=UTC),
            },
            {**base, "status": "planned", "completed_at": datetime.now(UTC)},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                InspectionCreate.model_validate(payload)


class InspectionFoundationDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        if not inspect(engine).has_table("inspections"):
            self.skipTest("chunk10binspect_20260817 is not applied")
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
            client_type="company", name=f"Inspection A {suffix}", country_code="PL"
        )
        self.client_b = Client(
            client_type="company", name=f"Inspection B {suffix}", country_code="PL"
        )
        self.db.add_all([self.client_a, self.client_b])
        self.db.flush()
        self.project = Project(
            client_id=self.client_a.id,
            name=f"Project {suffix}",
            status="active",
            created_by_user_id=self.actor.id,
            updated_by_user_id=self.actor.id,
        )
        self.db.add(self.project)
        self.db.flush()
        self.service = InspectionService(self.db)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        if hasattr(self, "db"):
            self.db.close()
            self.outer_transaction.rollback()
            self.connection.close()

    def _create(self, **overrides) -> Inspection:
        payload = {
            "project_id": self.project.id,
            "client_id": self.client_a.id,
            "title": "Wizja testowa",
            "status": "planned",
            "scheduled_at": datetime.now(UTC) + timedelta(days=1),
            "latitude": 52.2297,
            "longitude": 21.0122,
        }
        payload.update(overrides)
        return self.service.create(InspectionCreate.model_validate(payload), self.actor)

    def test_crud_filters_status_completion_and_soft_delete(self) -> None:
        inspection = self._create()
        self.assertEqual(self.service.get(inspection.id).project_id, self.project.id)
        page = self.service.get_page(
            search="Wizja",
            project_id=self.project.id,
            client_id=self.client_a.id,
            status="planned",
            date_from=datetime.now(UTC),
            date_to=datetime.now(UTC) + timedelta(days=2),
            skip=0,
            limit=20,
        )
        self.assertEqual(page.total, 1)

        updated = self.service.update(
            inspection.id,
            InspectionUpdate(status="completed", notes="Raport terenowy"),
            self.actor,
        )
        self.assertEqual(updated.status, "completed")
        self.assertIsNotNone(updated.completed_at)
        reopened = self.service.update(
            inspection.id, InspectionUpdate(status="in_progress"), self.actor
        )
        self.assertIsNone(reopened.completed_at)

        cancelled = self._create(title="Wizja anulowana", status="cancelled")
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(
            self.service.get_page(
                search=None,
                project_id=None,
                client_id=None,
                status="cancelled",
                date_from=None,
                date_to=None,
                skip=0,
                limit=20,
            ).items[0].id,
            cancelled.id,
        )

        self.service.delete(inspection.id, self.actor)
        with self.assertRaises(InspectionNotFoundError):
            self.service.get(inspection.id)

    def test_project_client_invariants_and_deleted_project(self) -> None:
        with self.assertRaises(InspectionClientProjectMismatchError):
            self._create(client_id=self.client_b.id)
        self.project.deleted_at = datetime.now(UTC)
        self.db.flush()
        with self.assertRaises(InspectionProjectNotFoundError):
            self._create()

    def test_soft_delete_preserves_document_and_legacy_session_value(self) -> None:
        inspection = self._create()
        suffix = uuid.uuid4().hex
        document = Document(
            filename=f"{suffix}.jpg",
            original_filename="inspection.jpg",
            content_type="image/jpeg",
            file_size=4,
            source_type="camera_photo",
            storage_path=f"synthetic/{suffix}.jpg",
            client_id=self.client_a.id,
            project_id=self.project.id,
            inspection_id=inspection.id,
            inspection_session_id="legacy-session-reference",
            captured_at=datetime.now(UTC),
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.db.add(document)
        self.db.flush()
        document_id = document.id
        self.db.add_all(
            [
                DocumentPage(document_id=document_id, page_number=1),
                DocumentAsset(
                    document_id=document_id,
                    asset_index=1,
                    storage_path=f"synthetic/{suffix}-asset.bin",
                ),
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=0,
                    content="synthetic",
                    token_count=1,
                    character_count=9,
                ),
            ]
        )
        self.db.flush()

        self.service.delete(inspection.id, self.actor)
        persisted = self.db.query(Document).filter(Document.id == document_id).one()
        self.assertEqual(persisted.inspection_id, inspection.id)
        self.assertEqual(persisted.project_id, self.project.id)
        self.assertEqual(persisted.client_id, self.client_a.id)
        self.assertEqual(persisted.inspection_session_id, "legacy-session-reference")
        self.assertEqual(self.db.query(DocumentPage).filter_by(document_id=document_id).count(), 1)
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document_id).count(), 1)
        self.assertEqual(self.db.query(DocumentChunk).filter_by(document_id=document_id).count(), 1)

    def test_jwt_routes_and_upload_enforce_inspection_project_client_relation(self) -> None:
        inspection = self._create()
        suffix = uuid.uuid4().hex
        document = Document(
            filename=f"{suffix}.jpg",
            original_filename="inspection.jpg",
            content_type="image/jpeg",
            file_size=4,
            source_type="camera_photo",
            storage_path=f"synthetic/{suffix}.jpg",
            client_id=self.client_a.id,
            project_id=self.project.id,
            inspection_id=inspection.id,
            captured_at=datetime.now(UTC),
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.db.add(document)
        self.db.flush()
        app.dependency_overrides[get_db] = lambda: self.db
        api = TestClient(app)
        unauthenticated = api.get("/api/v1/inspections")
        self.assertIn(unauthenticated.status_code, {401, 403})

        app.dependency_overrides[get_current_user] = lambda: self.actor
        stored = SimpleNamespace(document=document, created=True, matched_by=None)
        with patch(
            "app.api.documents.router.DocumentService.store_document",
            return_value=stored,
        ) as store:
            response = api.post(
                "/api/v1/documents/user-upload",
                data={
                    "client_id": self.client_a.id,
                    "project_id": self.project.id,
                    "inspection_id": inspection.id,
                    "source_type": "camera_photo",
                    "captured_at": datetime.now(UTC).isoformat(),
                },
                files={"file": ("inspection.jpg", b"test", "image/jpeg")},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["document"]["inspection_id"], inspection.id)
            self.assertEqual(store.call_args.kwargs["inspection_id"], inspection.id)
            self.assertEqual(store.call_args.kwargs["project_id"], self.project.id)
            self.assertEqual(store.call_args.kwargs["client_id"], self.client_a.id)

            mismatch = api.post(
                "/api/v1/documents/user-upload",
                data={
                    "client_id": self.client_b.id,
                    "project_id": self.project.id,
                    "inspection_id": inspection.id,
                },
                files={"file": ("inspection.jpg", b"test", "image/jpeg")},
            )
            self.assertEqual(mismatch.status_code, 409)
            self.assertEqual(store.call_count, 1)

    def test_controlled_end_to_end_smoke_is_fully_rollbackable(self) -> None:
        inspection = self._create(title="Wizja smoke")
        suffix = uuid.uuid4().hex
        document = Document(
            filename=f"{suffix}.jpg",
            original_filename="smoke.jpg",
            content_type="image/jpeg",
            file_size=4,
            source_type="camera_photo",
            storage_path=f"synthetic/{suffix}.jpg",
            client_id=self.client_a.id,
            project_id=self.project.id,
            inspection_id=inspection.id,
            captured_at=datetime.now(UTC),
            processing_status="stored",
            metadata_status="pending",
            match_status="matched",
        )
        self.db.add(document)
        self.db.flush()
        document_id = document.id

        active = self.service.update(
            inspection.id, InspectionUpdate(status="in_progress"), self.actor
        )
        self.assertEqual(active.status, "in_progress")
        completed = self.service.update(
            inspection.id, InspectionUpdate(status="completed"), self.actor
        )
        self.assertIsNotNone(completed.completed_at)
        reopened = self.service.update(
            inspection.id, InspectionUpdate(status="in_progress"), self.actor
        )
        self.assertIsNone(reopened.completed_at)
        self.service.delete(inspection.id, self.actor)

        preserved = self.db.query(Document).filter(Document.id == document_id).one()
        self.assertEqual(preserved.client_id, self.client_a.id)
        self.assertEqual(preserved.project_id, self.project.id)
        self.assertEqual(preserved.inspection_id, inspection.id)


if __name__ == "__main__":
    unittest.main()
