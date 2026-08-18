from __future__ import annotations

import importlib.util
import unittest

from pathlib import Path
from typing import get_args
from unittest.mock import MagicMock, patch

from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.schemas.document import VisionClassification, VisionStatus


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "chunk15vision_20260818_add_persistent_vision_state.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "chunk15vision_20260818",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Vision migration could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Chunk15VisionStateMigrationTests(unittest.TestCase):
    def test_revision_is_linear_and_upgrade_is_additive_only(self) -> None:
        migration = _load_migration()
        operations = MagicMock()

        with patch.object(migration, "op", operations):
            migration.upgrade()

        self.assertEqual(migration.revision, "chunk15vision_20260818")
        self.assertEqual(migration.down_revision, "inspectclient_20260818")
        self.assertEqual(operations.add_column.call_count, 21)
        self.assertEqual(operations.create_index.call_count, 4)
        operations.execute.assert_not_called()
        operations.drop_column.assert_not_called()
        operations.drop_table.assert_not_called()

    def test_downgrade_removes_only_added_columns_and_indexes(self) -> None:
        migration = _load_migration()
        operations = MagicMock()

        with patch.object(migration, "op", operations):
            migration.downgrade()

        self.assertEqual(operations.drop_column.call_count, 21)
        self.assertEqual(operations.drop_index.call_count, 4)
        operations.drop_table.assert_not_called()
        operations.execute.assert_not_called()

    def test_models_expose_independent_vision_state(self) -> None:
        document_columns = Document.__table__.c
        page_columns = DocumentPage.__table__.c
        asset_columns = DocumentAsset.__table__.c

        for name in (
            "vision_classification",
            "vision_status",
            "vision_auto_eligible",
            "vision_attempt_count",
            "vision_next_retry_at",
            "vision_error_code",
            "vision_analyzed_at",
            "vision_schema_version",
            "vision_source_checksum",
        ):
            self.assertIn(name, document_columns)

        for columns in (page_columns, asset_columns):
            for name in (
                "vision_status",
                "vision_attempt_count",
                "vision_error_code",
                "vision_analyzed_at",
                "vision_schema_version",
                "vision_source_checksum",
            ):
                self.assertIn(name, columns)
            self.assertIn("vision_analysis", columns)

        self.assertEqual(
            str(document_columns.vision_status.server_default.arg),
            "not_evaluated",
        )
        self.assertEqual(
            str(document_columns.vision_auto_eligible.server_default.arg),
            "false",
        )

    def test_schema_contract_contains_all_approved_states(self) -> None:
        self.assertEqual(
            set(get_args(VisionClassification)),
            {
                "text_sufficient",
                "vision_required",
                "vision_optional",
                "unsupported",
            },
        )
        self.assertEqual(
            set(get_args(VisionStatus)),
            {
                "not_evaluated",
                "not_needed",
                "pending",
                "queued",
                "processing",
                "complete",
                "failed_retryable",
                "failed_permanent",
                "pending_auth",
                "ui_changed",
                "partial",
            },
        )


if __name__ == "__main__":
    unittest.main()
