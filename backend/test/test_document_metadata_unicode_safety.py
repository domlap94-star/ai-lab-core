from __future__ import annotations

import ast
import math
import tempfile
import unittest

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentPublicRead, DocumentRead
from app.services.document_metadata_service import (
    DocumentMetadataResult,
    DocumentMetadataService,
)
from app.services.document_metadata_unicode_safety import (
    DOCUMENT_METADATA_JSON_INVALID,
    DOCUMENT_METADATA_UNICODE_KEY_COLLISION,
    DOCUMENT_METADATA_UNICODE_UNSAFE,
    DocumentMetadataSafetyError,
    assert_json_compatible_safe,
    sanitize_json_compatible,
    sanitize_metadata_text,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
)
from app.services.document_service import (
    DocumentService,
    DocumentStorageError,
)
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()


class _Floatable:
    def __float__(self) -> float:
        return 2.5


class _Stringable:
    def __str__(self) -> str:
        return "za\udc00lacznik"


class DocumentMetadataUnicodeSafetyTests(unittest.TestCase):
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

    def test_u01_isolated_low_in_value(self) -> None:
        result = sanitize_metadata_text("a\udc00b")
        self.assertEqual(result.value, "a\ufffdb")
        self.assertEqual(result.stats.replaced_low, 1)

    def test_u02_isolated_high_in_value(self) -> None:
        result = sanitize_metadata_text("a\ud800b")
        self.assertEqual(result.value, "a\ufffdb")
        self.assertEqual(result.stats.replaced_high, 1)

    def test_u03_adjacent_low_surrogates(self) -> None:
        result = sanitize_metadata_text("a\udc00\udfffb")
        self.assertEqual(result.value, "a\ufffd\ufffdb")
        self.assertEqual(result.stats.replaced_low, 2)

    def test_u04_valid_pair_preserved(self) -> None:
        value = "a\ud83d\ude00b"
        result = sanitize_metadata_text(value)
        self.assertEqual(result.value, value)
        self.assertEqual(result.stats.preserved_valid_pairs, 1)

    def test_u05_supplementary_scalar_preserved(self) -> None:
        value = "symbol \U0001f600"
        self.assertEqual(sanitize_metadata_text(value).value, value)

    def test_u06_polish_unicode_preserved(self) -> None:
        value = "Za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144"
        self.assertEqual(sanitize_metadata_text(value).value, value)

    def test_u07_replacement_character_preserved(self) -> None:
        value = "a\ufffdb"
        self.assertEqual(sanitize_metadata_text(value).value, value)

    def test_u08_nested_collections_sanitized(self) -> None:
        source = {"a": ["x\udc00", ("y\ud800",), {"z\udc00"}]}
        result = sanitize_json_compatible(source)
        self.assertEqual(result["a"][0], "x\ufffd")
        self.assertEqual(result["a"][1], ["y\ufffd"])
        self.assertEqual(result["a"][2], ["z\ufffd"])

    def test_u09_dynamic_key_sanitized(self) -> None:
        result = sanitize_json_compatible({"k\udc00": 1})
        self.assertEqual(list(result), ["k\ufffd"])

    def test_u10_sanitized_key_collision_fails(self) -> None:
        with self.assertRaises(DocumentMetadataSafetyError) as raised:
            sanitize_json_compatible({"k\udc00": 1, "k\ufffd": 2})
        self.assertEqual(
            raised.exception.code,
            DOCUMENT_METADATA_UNICODE_KEY_COLLISION,
        )

    def test_u11_bytes_datetime_conversion(self) -> None:
        moment = datetime(2026, 9, 1, 12, 30, tzinfo=UTC)
        result = sanitize_json_compatible(
            {"bytes": b"\x00\xff", "datetime": moment}
        )
        self.assertEqual(result["bytes"], "00ff")
        self.assertEqual(result["datetime"], moment.isoformat())

    def test_u12_non_finite_float_to_none(self) -> None:
        result = sanitize_json_compatible(
            [math.nan, math.inf, -math.inf]
        )
        self.assertEqual(result, [None, None, None])

    def test_u13_numeric_and_string_fallback(self) -> None:
        result = sanitize_json_compatible([_Floatable(), _Stringable()])
        self.assertEqual(result, [2.5, "za\ufffdlacznik"])

    def test_u14_assertion_rejects_raw_surrogate(self) -> None:
        with self.assertRaises(DocumentMetadataSafetyError) as raised:
            assert_json_compatible_safe({"value": "x\udc00"})
        self.assertEqual(
            raised.exception.code,
            DOCUMENT_METADATA_UNICODE_UNSAFE,
        )

    def test_u15_assertion_accepts_sanitized(self) -> None:
        value = sanitize_json_compatible({"value": "x\udc00"})
        assert_json_compatible_safe(value)

    def test_u16_strict_json_dump_succeeds(self) -> None:
        value = sanitize_json_compatible(
            {"pair": "\ud83d\ude00", "polish": "\u017c\u00f3\u0142\u0107"}
        )
        assert_json_compatible_safe(value)

    def test_u17_metadata_service_json_safe_shared(self) -> None:
        self.assertEqual(
            DocumentMetadataService._json_safe({"x": "v\udc00"}),
            {"x": "v\ufffd"},
        )

    def test_u18_metadata_service_clean_shared(self) -> None:
        self.assertEqual(
            DocumentMetadataService._clean("  v\udc00  "),
            "v\ufffd",
        )

    def test_u19_extractor_error_is_stable_code(self) -> None:
        service = DocumentMetadataService()
        with tempfile.NamedTemporaryFile(suffix=".pdf") as fixture:
            with patch.object(
                service,
                "_extract_pdf",
                side_effect=DocumentMetadataSafetyError(
                    DOCUMENT_METADATA_UNICODE_KEY_COLLISION
                ),
            ):
                result = service.extract(
                    path=Path(fixture.name),
                    content_type="application/pdf",
                    original_filename="synthetic.pdf",
                )
        self.assertEqual(result.status, "failed")
        self.assertEqual(
            result.error,
            DOCUMENT_METADATA_UNICODE_KEY_COLLISION,
        )

    def test_u20_intake_sanitized_before_file_write(self) -> None:
        stored = DocumentService(self.db).store_document(
            content=b"synthetic-u20",
            original_filename="u20.txt",
            content_type="text/plain",
            source_type="manual_upload",
            intake_metadata={"note": "safe\udc00value"},
            commit=False,
        )
        self.assertEqual(
            stored.document.metadata_raw,
            {"intake": {"note": "safe\ufffdvalue"}},
        )

    def test_u21_intake_collision_creates_nothing(self) -> None:
        documents_before = self.db.query(Document).count()
        with self.assertRaises(DocumentStorageError) as raised:
            DocumentService(self.db).store_document(
                content=b"synthetic-u21",
                original_filename="u21.txt",
                content_type="text/plain",
                source_type="manual_upload",
                intake_metadata={"k\udc00": 1, "k\ufffd": 2},
                commit=False,
            )
        self.assertEqual(
            str(raised.exception),
            DOCUMENT_METADATA_UNICODE_KEY_COLLISION,
        )
        self.assertEqual(self.db.query(Document).count(), documents_before)
        self.assertEqual(list(Path(self.storage.name).rglob("*")), [])

    def test_u22_repository_create_rejects_unsafe(self) -> None:
        document = Document(
            filename="u22.txt",
            original_filename="u22.txt",
            content_type="text/plain",
            file_size=1,
            source_type="manual_upload",
            metadata_raw={"value": "x\udc00"},
        )
        with self.assertRaises(DocumentMetadataSafetyError):
            DocumentRepository(self.db).create(document)

    def test_u23_update_metadata_rejects_unsafe(self) -> None:
        document = SimpleNamespace()
        with self.assertRaises(DocumentMetadataSafetyError):
            DocumentRepository(self.db).update_metadata(
                document=document,
                status="processed",
                raw_metadata={"value": "x\udc00"},
                normalized_metadata=None,
                error=None,
            )

    def test_u24_generic_update_does_not_repair(self) -> None:
        db = MagicMock()
        document = SimpleNamespace(metadata_raw={"value": "x\udc00"})
        DocumentRepository(db).update(document)
        self.assertEqual(document.metadata_raw["value"], "x\udc00")
        db.add.assert_called_once_with(document)

    def test_u25_processing_uses_update_metadata(self) -> None:
        repository = MagicMock()
        metadata_service = MagicMock()
        metadata_service.extract.return_value = DocumentMetadataResult(
            status="processed",
            raw_metadata={"value": "safe"},
            normalized_metadata={"value": "safe"},
            error=None,
        )
        service = DocumentProcessingService.__new__(
            DocumentProcessingService
        )
        service.repository = repository
        service.metadata_service = metadata_service
        document = SimpleNamespace(
            id=1,
            content_type="text/plain",
            original_filename="u25.txt",
            metadata_status="pending",
            metadata_raw=None,
        )
        service._process_metadata(
            document=document,
            path=Path("synthetic-u25"),
            force=False,
        )
        repository.update_metadata.assert_called_once()
        repository.update.assert_not_called()

    def test_u26_intake_subobject_preserved_sanitized(self) -> None:
        repository = MagicMock()
        metadata_service = MagicMock()
        metadata_service.extract.return_value = DocumentMetadataResult(
            status="processed",
            raw_metadata={"format": "text"},
            normalized_metadata={"format": "text"},
            error=None,
        )
        service = DocumentProcessingService.__new__(
            DocumentProcessingService
        )
        service.repository = repository
        service.metadata_service = metadata_service
        document = SimpleNamespace(
            id=1,
            content_type="text/plain",
            original_filename="u26.txt",
            metadata_status="pending",
            metadata_raw={"intake": {"note": "safe\ufffd"}},
        )
        service._process_metadata(
            document=document,
            path=Path("synthetic-u26"),
            force=False,
        )
        self.assertEqual(
            repository.update_metadata.call_args.kwargs["raw_metadata"],
            {
                "format": "text",
                "intake": {"note": "safe\ufffd"},
            },
        )

    def test_u27_public_document_schemas_unchanged(self) -> None:
        for schema in (DocumentRead, DocumentPublicRead):
            self.assertNotIn("metadata_raw", schema.model_fields)
            self.assertNotIn("metadata_normalized", schema.model_fields)

    def test_u28_metadata_writer_allowlist(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        app = backend / "app"
        attribute_writers: set[str] = set()
        keyword_writers: set[str] = set()
        for source in app.rglob("*.py"):
            relative = source.relative_to(backend).as_posix()
            tree = ast.parse(source.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                targets: list[ast.expr] = []
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    if isinstance(node, ast.Assign):
                        targets.extend(node.targets)
                    else:
                        targets.append(node.target)
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr
                        in {"metadata_raw", "metadata_normalized"}
                    ):
                        attribute_writers.add(relative)
                if isinstance(node, ast.Call):
                    if any(
                        keyword.arg
                        in {"metadata_raw", "metadata_normalized"}
                        for keyword in node.keywords
                    ):
                        keyword_writers.add(relative)
        self.assertEqual(
            attribute_writers,
            {
                "app/repositories/document_repository.py",
                "app/services/trash_lifecycle_service.py",
            },
        )
        self.assertEqual(
            keyword_writers,
            {
                "app/services/document_archive_import_service.py",
                "app/services/document_service.py",
            },
        )


if __name__ == "__main__":
    unittest.main()
