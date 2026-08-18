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
    InspectionClientNotFoundError,
    InspectionNotFoundError,
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

        simplification = Path(
            "/app/alembic/versions/"
            "inspectclient_20260818_make_project_optional.py"
        ).read_text(encoding="utf-8")
        upgrade = simplification.split("def downgrade", 1)[0]
        self.assertIn('revision = "inspectclient_20260818"', simplification)
        self.assertIn('down_revision = "chunk11search_20260818"', simplification)
        self.assertIn('"project_id"', upgrade)
        self.assertIn("nullable=True", upgrade)
        self.assertNotIn("drop_", upgrade.lower())
        self.assertNotIn("update(", upgrade.lower())

    def test_schema_rejects_invalid_status_location_and_time_order(self) -> None:
        base = {"client_id": 1}
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
            "client_id": self.client_a.id,
            "status": "planned",
            "scheduled_at": datetime.now(UTC) + timedelta(days=1),
            "latitude": 52.2297,
            "longitude": 21.0122,
        }
        payload.update(overrides)
        return self.service.create(InspectionCreate.model_validate(payload), self.actor)

    def test_crud_filters_status_completion_and_soft_delete(self) -> None:
        inspection = self._create()
        self.assertIsNone(self.service.get(inspection.id).project_id)
        self.assertEqual(
            inspection.title,
            f"Wizja lokalna — {self.client_a.name}",
        )
        page = self.service.get_page(
            search="Wizja",
            project_id=None,
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

        cancelled = self._create(status="cancelled")
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

    def test_client_is_required_and_must_be_active(self) -> None:
        missing_id = max(self.client_a.id, self.client_b.id) + 1000000
        with self.assertRaises(InspectionClientNotFoundError):
            self._create(client_id=missing_id)
        self.client_b.deleted_at = datetime.now(UTC)
        self.db.flush()
        with self.assertRaises(InspectionClientNotFoundError):
            self._create(client_id=self.client_b.id)

    def test_legacy_project_relation_is_readable_and_preserved_on_update(self) -> None:
        legacy = Inspection(
            project_id=self.project.id,
            client_id=self.client_a.id,
            title="Legacy inspection",
            status="planned",
            created_by_user_id=self.actor.id,
            updated_by_user_id=self.actor.id,
        )
        self.db.add(legacy)
        self.db.flush()

        read = self.service.get(legacy.id)
        self.assertEqual(read.project_id, self.project.id)
        self.assertEqual(read.project_name, self.project.name)
        updated = self.service.update(
            legacy.id,
            InspectionUpdate(notes="Legacy relation retained"),
            self.actor,
        )
        self.assertEqual(updated.project_id, self.project.id)

    def test_partial_notes_and_location_updates_do_not_overwrite_each_other(self) -> None:
        inspection = self._create(notes="Initial field note")
        original_status = inspection.status
        original_scheduled_at = inspection.scheduled_at
        original_latitude = inspection.latitude
        original_longitude = inspection.longitude

        notes_updated = self.service.update(
            inspection.id,
            InspectionUpdate(notes="Autosaved field note"),
            self.actor,
        )
        self.assertEqual(notes_updated.notes, "Autosaved field note")
        self.assertEqual(notes_updated.status, original_status)
        self.assertEqual(notes_updated.scheduled_at, original_scheduled_at)
        self.assertEqual(notes_updated.latitude, original_latitude)
        self.assertEqual(notes_updated.longitude, original_longitude)

        location_updated = self.service.update(
            inspection.id,
            InspectionUpdate(
                latitude=50.0614,
                longitude=19.9383,
                location_accuracy_m=7.5,
            ),
            self.actor,
        )
        self.assertEqual(location_updated.notes, "Autosaved field note")
        self.assertEqual(location_updated.status, original_status)
        self.assertEqual(location_updated.latitude, 50.0614)
        self.assertEqual(location_updated.longitude, 19.9383)
        self.assertEqual(location_updated.location_accuracy_m, 7.5)

    def test_invalid_location_and_oversized_notes_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            InspectionUpdate(latitude=91)
        with self.assertRaises(ValidationError):
            InspectionUpdate(notes="x" * 10_001)

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
            project_id=None,
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
        self.assertIsNone(persisted.project_id)
        self.assertEqual(persisted.client_id, self.client_a.id)
        self.assertEqual(persisted.inspection_session_id, "legacy-session-reference")
        self.assertEqual(self.db.query(DocumentPage).filter_by(document_id=document_id).count(), 1)
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document_id).count(), 1)
        self.assertEqual(self.db.query(DocumentChunk).filter_by(document_id=document_id).count(), 1)

    def test_jwt_routes_and_upload_use_client_and_inspection_without_project(self) -> None:
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
            project_id=None,
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
        created_response = api.post(
            "/api/v1/inspections",
            json={
                "client_id": self.client_a.id,
                "status": "planned",
                "notes": "Created without project or manual title",
            },
        )
        self.assertEqual(created_response.status_code, 201, created_response.text)
        self.assertIsNone(created_response.json()["project_id"])
        self.assertEqual(
            created_response.json()["title"],
            f"Wizja lokalna — {self.client_a.name}",
        )
        updated_response = api.patch(
            f"/api/v1/inspections/{created_response.json()['id']}",
            json={"status": "in_progress", "notes": "Updated without project"},
        )
        self.assertEqual(updated_response.status_code, 200, updated_response.text)
        self.assertIsNone(updated_response.json()["project_id"])

        stored = SimpleNamespace(document=document, created=True, matched_by=None)
        with patch(
            "app.api.documents.router.DocumentService.store_document",
            return_value=stored,
        ) as store:
            response = api.post(
                "/api/v1/documents/user-upload",
                data={
                    "client_id": self.client_a.id,
                    "inspection_id": inspection.id,
                    "source_type": "camera_photo",
                    "captured_at": datetime.now(UTC).isoformat(),
                },
                files={"file": ("inspection.jpg", b"test", "image/jpeg")},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["document"]["inspection_id"], inspection.id)
            self.assertEqual(store.call_args.kwargs["inspection_id"], inspection.id)
            self.assertIsNone(store.call_args.kwargs["project_id"])
            self.assertEqual(store.call_args.kwargs["client_id"], self.client_a.id)

            mismatch = api.post(
                "/api/v1/documents/user-upload",
                data={
                    "client_id": self.client_b.id,
                    "inspection_id": inspection.id,
                },
                files={"file": ("inspection.jpg", b"test", "image/jpeg")},
            )
            self.assertEqual(mismatch.status_code, 409)
            self.assertEqual(store.call_count, 1)

    def test_controlled_end_to_end_smoke_is_fully_rollbackable(self) -> None:
        inspection = self._create()
        suffix = uuid.uuid4().hex
        document = Document(
            filename=f"{suffix}.jpg",
            original_filename="smoke.jpg",
            content_type="image/jpeg",
            file_size=4,
            source_type="camera_photo",
            storage_path=f"synthetic/{suffix}.jpg",
            client_id=self.client_a.id,
            project_id=None,
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
        self.assertIsNone(preserved.project_id)
        self.assertEqual(preserved.inspection_id, inspection.id)


if __name__ == "__main__":
    unittest.main()
