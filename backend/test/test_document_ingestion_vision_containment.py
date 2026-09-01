from __future__ import annotations

import ast
import asyncio
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.assistant_pipeline import AssistantRun
from app.models.document import Document
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.knowledge_base import AnalysisJob
from app.services.document_preparation_dispatcher import process_preparation_vision
from app.services.document_preparation_service import (
    INGESTION_EXTERNAL_VISION_BLOCKED,
    DocumentPreparationService,
    PreparationClaim,
)
from app.services.document_service import DocumentService
from app.services.unified_document_content_service import (
    FILE_FOUND_NATIVE_TEXT_AVAILABLE,
    FILE_FOUND_REQUIRES_OCR,
)
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()


class DocumentIngestionVisionContainmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db = SessionLocal()
        try:
            assert_isolated_database(db, TEST_DATABASE_NAME)
            cls.analysis_jobs_before = db.query(AnalysisJob).count()
            cls.assistant_runs_before = db.query(AssistantRun).count()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls) -> None:
        db = SessionLocal()
        try:
            assert_isolated_database(db, TEST_DATABASE_NAME)
            if db.query(AnalysisJob).count() != cls.analysis_jobs_before:
                raise AssertionError("containment tests created AnalysisJob rows")
            if db.query(AssistantRun).count() != cls.assistant_runs_before:
                raise AssertionError("containment tests created AssistantRun rows")
        finally:
            db.close()

    def setUp(self) -> None:
        self.storage = tempfile.TemporaryDirectory()
        self.previous_data_dir = settings.data_dir
        settings.data_dir = self.storage.name
        self.db = SessionLocal()
        assert_isolated_database(self.db, TEST_DATABASE_NAME)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        settings.data_dir = self.previous_data_dir
        self.storage.cleanup()

    def _store(self, *, suffix: str, content_type: str) -> tuple[Document, DocumentPreparationJob]:
        marker = uuid.uuid4().hex
        stored = DocumentService(self.db).store_document(
            content=(f"synthetic DOC-01 {marker}\n").encode("utf-8"),
            original_filename=f"doc01-{marker}.{suffix}",
            content_type=content_type,
            source_type="manual_upload",
        )
        job = self.db.query(DocumentPreparationJob).filter_by(
            document_id=stored.document.id
        ).one()
        return stored.document, job

    def _running(
        self,
        job: DocumentPreparationJob,
        *,
        trigger: str = "ingestion",
        stage: str = "validating",
    ) -> PreparationClaim:
        job.trigger = trigger
        job.status = "running"
        job.stage = stage
        job.attempt_count = 1
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.error_code = None
        job.retryability = None
        job.lease_owner = f"isolated-doc01-worker:{uuid.uuid4()}"
        job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=45)
        self.db.commit()
        return PreparationClaim(job_id=job.id, lease_owner=job.lease_owner)

    @staticmethod
    def _assert_contained(test: unittest.TestCase, job: DocumentPreparationJob) -> None:
        test.assertEqual(job.status, "failed")
        test.assertEqual(job.stage, "failed")
        test.assertEqual(job.error_code, INGESTION_EXTERNAL_VISION_BLOCKED)
        test.assertEqual(job.retryability, "owner_action")
        test.assertIsNone(job.lease_owner)
        test.assertIsNone(job.lease_expires_at)
        test.assertIsNotNone(job.finished_at)

    def _process_claimed_with_content(
        self, claim: PreparationClaim, state: str
    ) -> None:
        safety = SimpleNamespace(
            state="supported",
            detected_format="text",
            error_code=None,
        )
        processed = SimpleNamespace(status="processed")
        content = SimpleNamespace(state=state)
        with (
            patch(
                "app.services.document_preparation_service."
                "DocumentFileSafetyService.classify",
                return_value=safety,
            ),
            patch(
                "app.services.document_preparation_service."
                "DocumentProcessingService.process_document",
                return_value=processed,
            ),
            patch(
                "app.services.document_preparation_service."
                "UnifiedDocumentContentService.access",
                return_value=content,
            ),
        ):
            DocumentPreparationService(self.db).process_claimed(claim)

    def _complete_legacy_vision(self, document_id: int) -> None:
        db = SessionLocal()
        try:
            document = db.get(Document, document_id)
            assert document is not None
            document.vision_status = "complete"
            db.commit()
        finally:
            db.close()

    def test_t01_new_ingestion_never_enters_vision(self) -> None:
        document, job = self._store(suffix="txt", content_type="text/plain")
        claim = self._running(job)
        original_vision = (
            document.vision_status,
            document.vision_attempt_count,
            document.vision_error_code,
            document.vision_source_checksum,
        )
        with (
            patch(
                "app.services.document_preparation_dispatcher."
                "process_explicit_vision_document"
            ) as explicit,
            patch(
                "app.services.vision_processing_service."
                "VisionProcessingService.advance"
            ) as advance,
            patch(
                "app.services.vision_supervisor_client."
                "VisionSupervisorClient.create_job"
            ) as create_job,
        ):
            self._process_claimed_with_content(
                claim, FILE_FOUND_REQUIRES_OCR
            )

        self.db.expire_all()
        terminal = self.db.get(DocumentPreparationJob, job.id)
        current_document = self.db.get(Document, document.id)
        assert terminal is not None and current_document is not None
        self._assert_contained(self, terminal)
        self.assertNotEqual(terminal.stage, "vision_processing")
        self.assertEqual(
            (
                current_document.vision_status,
                current_document.vision_attempt_count,
                current_document.vision_error_code,
                current_document.vision_source_checksum,
            ),
            original_vision,
        )
        explicit.assert_not_called()
        advance.assert_not_called()
        create_job.assert_not_called()

    def test_t02_existing_ingestion_vision_processing_is_contained(self) -> None:
        document, job = self._store(suffix="txt", content_type="text/plain")
        claim = self._running(job, stage="vision_processing")
        original_vision = (
            document.vision_status,
            document.vision_attempt_count,
            document.vision_error_code,
            document.vision_source_checksum,
        )
        with patch(
            "app.services.document_preparation_dispatcher."
            "process_explicit_vision_document",
            side_effect=AssertionError("legacy Vision must not run for ingestion"),
        ) as explicit:
            self.assertFalse(asyncio.run(process_preparation_vision(claim)))

        self.db.expire_all()
        terminal = self.db.get(DocumentPreparationJob, job.id)
        current_document = self.db.get(Document, document.id)
        assert terminal is not None and current_document is not None
        self._assert_contained(self, terminal)
        self.assertEqual(
            (
                current_document.vision_status,
                current_document.vision_attempt_count,
                current_document.vision_error_code,
                current_document.vision_source_checksum,
            ),
            original_vision,
        )
        explicit.assert_not_called()

    def test_t03_containment_is_idempotent(self) -> None:
        _document, job = self._store(suffix="txt", content_type="text/plain")
        claim = self._running(job, stage="vision_processing")
        service = DocumentPreparationService(self.db)
        attempts = job.attempt_count
        self.assertTrue(service.contain_ingestion_external_vision(claim))
        self.db.commit()
        self.db.expire_all()
        first = self.db.get(DocumentPreparationJob, job.id)
        assert first is not None
        first_finished = first.finished_at
        self.assertTrue(service.contain_ingestion_external_vision(claim))
        self.db.commit()
        self.db.expire_all()
        second = self.db.get(DocumentPreparationJob, job.id)
        assert second is not None
        self._assert_contained(self, second)
        self.assertEqual(second.attempt_count, attempts)
        self.assertEqual(second.finished_at, first_finished)

        _other_document, other = self._store(
            suffix="txt", content_type="text/plain"
        )
        other.status = "unsupported"
        other.stage = "unsupported"
        other.error_code = "UNSUPPORTED_FORMAT"
        other.retryability = "unsupported"
        other.finished_at = datetime.now(UTC)
        self.db.commit()
        other_finished = other.finished_at
        self.assertFalse(service.contain_ingestion_external_vision(
            PreparationClaim(
                job_id=other.id,
                lease_owner="isolated-doc01-non-owner",
            )
        ))
        self.db.commit()
        self.db.expire_all()
        unchanged = self.db.get(DocumentPreparationJob, other.id)
        assert unchanged is not None
        self.assertEqual(unchanged.status, "unsupported")
        self.assertEqual(unchanged.stage, "unsupported")
        self.assertEqual(unchanged.error_code, "UNSUPPORTED_FORMAT")
        self.assertEqual(unchanged.finished_at, other_finished)

    def _assert_explicit_compatibility(self, trigger: str) -> None:
        document, job = self._store(suffix="txt", content_type="text/plain")
        claim = self._running(
            job, trigger=trigger, stage="vision_processing"
        )
        with patch(
            "app.services.document_preparation_dispatcher."
            "process_explicit_vision_document",
            side_effect=self._complete_legacy_vision,
        ) as explicit:
            self.assertTrue(asyncio.run(process_preparation_vision(claim)))
        explicit.assert_called_once_with(document.id)
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        self.assertEqual(current.status, "running")
        self.assertEqual(current.stage, "local_analysis")
        self.assertIsNone(current.error_code)

    def test_t04_assistant_explicit_compatibility_remains(self) -> None:
        self._assert_explicit_compatibility("assistant")

    def test_t05_operator_retry_is_not_misclassified_as_ingestion(self) -> None:
        self._assert_explicit_compatibility("operator_retry")

    def test_t06_local_text_ingestion_still_proceeds_locally(self) -> None:
        _document, job = self._store(suffix="txt", content_type="text/plain")
        claim = self._running(job)
        self._process_claimed_with_content(
            claim, FILE_FOUND_NATIVE_TEXT_AVAILABLE
        )
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        self.assertEqual(current.status, "running")
        self.assertEqual(current.stage, "local_analysis")
        self.assertIsNone(current.error_code)

    def test_t07_document_creation_remains_atomic(self) -> None:
        document, job = self._store(suffix="txt", content_type="text/plain")
        rows = self.db.query(DocumentPreparationJob).filter_by(
            document_id=document.id
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, job.id)
        self.assertEqual(rows[0].trigger, "ingestion")
        self.assertEqual((rows[0].status, rows[0].stage), ("queued", "queued"))

    def test_t08_no_global_vision_disable(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        service_source = (
            backend / "app/services/document_preparation_service.py"
        ).read_text(encoding="utf-8")
        dispatcher_source = (
            backend / "app/services/document_preparation_dispatcher.py"
        ).read_text(encoding="utf-8")
        router_source = (backend / "app/api/documents/router.py").read_text(
            encoding="utf-8"
        )
        combined = service_source + dispatcher_source
        self.assertNotIn("settings.vision_automation_enabled =", combined)
        self.assertNotIn("settings.document_preparation_enabled =", combined)
        self.assertNotIn("vision_auto_eligible =", combined)
        self.assertIn(
            "background_tasks.add_task(process_explicit_vision_document",
            router_source,
        )
        self.assertIn("process_explicit_vision_document", dispatcher_source)

    def test_t09_source_path_regression_assertion(self) -> None:
        services_root = Path(__file__).resolve().parents[1] / "app/services"
        assignments: list[tuple[Path, ast.Assign, ast.AST | None]] = []
        for path in services_root.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8-sig"), filename=str(path)
            )
            parents: dict[ast.AST, ast.AST] = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                if not isinstance(node.value, ast.Constant):
                    continue
                if node.value.value != "vision_processing":
                    continue
                if not any(
                    isinstance(target, ast.Attribute) and target.attr == "stage"
                    for target in node.targets
                ):
                    continue
                assignments.append((path, node, parents.get(node)))

        self.assertEqual(len(assignments), 1)
        path, assignment, parent = assignments[0]
        self.assertEqual(path.name, "document_preparation_service.py")
        self.assertIsInstance(parent, ast.If)
        assert isinstance(parent, ast.If)
        self.assertIn(assignment, parent.orelse)
        condition = ast.unparse(parent.test)
        self.assertIn("job.trigger", condition)
        self.assertIn("ingestion", condition)


if __name__ == "__main__":
    unittest.main(verbosity=2)
