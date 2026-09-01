from __future__ import annotations

import hashlib
import io
import stat
import tempfile
import unittest
import uuid
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.assistant_pipeline import AssistantRun
from app.models.document_asset import DocumentAsset
from app.models.knowledge_base import AnalysisJob
from app.services.document_asset_extraction_service import (
    DocumentAssetExtractionResult,
    DocumentAssetExtractionService,
)
from app.services.document_file_safety_service import (
    DocumentFileSafetyService,
)
from app.services.document_office_archive_safety import (
    DEFAULT_OFFICE_ARCHIVE_POLICY,
    DocumentOfficeArchiveSafety,
    OfficeArchiveMember,
    OfficeArchiveSafetyError,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
)
from app.services.document_service import DocumentService
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()


class DocumentOfficeArchiveSafetyTests(unittest.TestCase):
    MIME_TYPES = {
        ".docx": (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        ".xlsx": (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        ".pptx": (
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
        ".odt": "application/vnd.oasis.opendocument.text",
    }

    ROOT_MEMBERS = {
        ".docx": (
            ("[Content_Types].xml", b"<Types/>"),
            ("word/document.xml", b"<document/>"),
        ),
        ".xlsx": (
            ("[Content_Types].xml", b"<Types/>"),
            ("xl/workbook.xml", b"<workbook/>"),
        ),
        ".pptx": (
            ("[Content_Types].xml", b"<Types/>"),
            ("ppt/presentation.xml", b"<presentation/>"),
        ),
        ".odt": (
            ("mimetype", b"application/vnd.oasis.opendocument.text"),
            ("content.xml", b"<document-content/>"),
        ),
    }

    MEDIA_PREFIXES = {
        ".docx": "word/media/",
        ".xlsx": "xl/media/",
        ".pptx": "ppt/media/",
        ".odt": "Pictures/",
    }

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
                raise AssertionError("Office safety tests created AnalysisJob rows")
            if db.query(AssistantRun).count() != cls.assistant_runs_before:
                raise AssertionError("Office safety tests created AssistantRun rows")
        finally:
            db.close()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.staging_root = self.root / "staging"
        self.staging_root.mkdir()
        self.previous_data_dir = settings.data_dir
        settings.data_dir = str(self.root / "data")
        self.db = SessionLocal()
        assert_isolated_database(self.db, TEST_DATABASE_NAME)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        settings.data_dir = self.previous_data_dir
        self.assertEqual(list(self.staging_root.iterdir()), [])
        self.temp.cleanup()

    @staticmethod
    def _png(width: int = 32, height: int = 32) -> bytes:
        image = Image.new("RGB", (width, height))
        image.putdata(
            [
                ((index * 17) % 256, (index * 31) % 256, (index * 47) % 256)
                for index in range(width * height)
            ]
        )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", compress_level=1)
        return buffer.getvalue()

    def _archive_bytes(
        self,
        extension: str,
        *,
        media: list[tuple[str, bytes]] | None = None,
        extras: list[tuple[str | zipfile.ZipInfo, bytes]] | None = None,
        compression: int = zipfile.ZIP_DEFLATED,
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
            for name, content in self.ROOT_MEMBERS[extension]:
                archive.writestr(name, content)
            archive.writestr(
                (
                    "META-INF/"
                    if extension == ".odt"
                    else "docProps/"
                )
                + f"doc02-{uuid.uuid4().hex}.txt",
                b"isolated-doc02-fixture",
            )
            for name, content in media or []:
                archive.writestr(name, content)
            for name, content in extras or []:
                archive.writestr(name, content)
        return buffer.getvalue()

    def _write_archive(
        self,
        extension: str,
        **kwargs,
    ) -> Path:
        path = self.root / f"fixture-{uuid.uuid4().hex}{extension}"
        path.write_bytes(self._archive_bytes(extension, **kwargs))
        return path

    def _store_archive(
        self,
        extension: str,
        **kwargs,
    ):
        content = self._archive_bytes(extension, **kwargs)
        stored = DocumentService(self.db).store_document(
            content=content,
            original_filename=f"office-{uuid.uuid4().hex}{extension}",
            content_type=self.MIME_TYPES.get(
                extension,
                "application/octet-stream",
            ),
            source_type="manual_upload",
        )
        return stored.document

    def _service(self, policy=DEFAULT_OFFICE_ARCHIVE_POLICY):
        return DocumentAssetExtractionService(
            self.db,
            office_archive_policy=policy,
            staging_parent=self.staging_root,
        )

    @staticmethod
    def _policy(**changes):
        return replace(DEFAULT_OFFICE_ARCHIVE_POLICY, **changes)

    def _source_path(self, document) -> Path:
        return Path(settings.data_dir) / document.storage_path

    def _assert_rejected_before_body(
        self,
        *,
        document,
        policy,
        expected_code: str,
    ) -> None:
        with patch.object(
            zipfile.ZipFile,
            "open",
            side_effect=AssertionError("member body was opened"),
        ) as body_open:
            result = self._service(policy).extract_document_assets(
                document_id=document.id
            )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, expected_code)
        body_open.assert_not_called()
        self.assertEqual(
            self.db.query(DocumentAsset).filter_by(
                document_id=document.id
            ).count(),
            0,
        )

    def test_t01_safe_docx_streams_and_persists_exact_asset(self) -> None:
        png = self._png()
        document = self._store_archive(
            ".docx",
            media=[("word/media/image1.png", png)],
        )
        source_path = self._source_path(document)
        safety = DocumentFileSafetyService().classify(
            path=source_path,
            original_filename=document.original_filename,
            declared_mime=document.content_type,
        )
        self.assertEqual(safety.state, "supported")
        self.assertEqual(safety.detected_format, "docx")
        with patch.object(
            zipfile.ZipFile,
            "read",
            side_effect=AssertionError("ZipFile.read is forbidden"),
        ):
            result = self._service().extract_document_assets(
                document_id=document.id
            )
        self.assertEqual(result.status, "extracted", result)
        self.assertEqual(result.extracted_count, 1)
        asset = self.db.query(DocumentAsset).filter_by(
            document_id=document.id
        ).one()
        self.assertEqual(asset.checksum_sha256, hashlib.sha256(png).hexdigest())
        self.assertEqual(asset.file_size, len(png))
        self.assertEqual((asset.width, asset.height), (32, 32))
        self.assertEqual((Path(settings.data_dir) / asset.storage_path).read_bytes(), png)

    def test_t02_safe_xlsx_pptx_odt_structure_and_canonical_formats(self) -> None:
        service = DocumentFileSafetyService()
        for extension in (".xlsx", ".pptx", ".odt"):
            with self.subTest(extension=extension):
                path = self._write_archive(extension)
                result = service.classify(
                    path=path,
                    original_filename=path.name,
                    declared_mime=self.MIME_TYPES[extension],
                )
                self.assertEqual(result.state, "supported")
                self.assertEqual(result.detected_format, extension.lstrip("."))

        mismatch = self.root / "missing-root.docx"
        with zipfile.ZipFile(mismatch, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
        mismatch_result = service.classify(
            path=mismatch,
            original_filename=mismatch.name,
            declared_mime=self.MIME_TYPES[".docx"],
        )
        self.assertEqual(mismatch_result.state, "integrity_failed")
        self.assertEqual(mismatch_result.error_code, "OFFICE_CONTAINER_MISMATCH")

    def test_t03_compressed_container_limit_precedes_zip_open(self) -> None:
        path = self._write_archive(".docx")
        policy = self._policy(max_compressed_container_bytes=1)
        with patch(
            "app.services.document_office_archive_safety.zipfile.ZipFile",
            side_effect=AssertionError("archive was opened"),
        ) as archive_open:
            result = DocumentFileSafetyService(policy).classify(
                path=path,
                original_filename=path.name,
                declared_mime=self.MIME_TYPES[".docx"],
            )
        self.assertEqual(result.state, "unsupported")
        self.assertEqual(result.error_code, "OFFICE_CONTAINER_COMPRESSED_SIZE_LIMIT")
        archive_open.assert_not_called()

    def test_t04_entry_count_limit_precedes_member_body(self) -> None:
        document = self._store_archive(
            ".docx",
            extras=[("docProps/core.xml", b"x")],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(max_container_entries=2),
            expected_code="OFFICE_CONTAINER_ENTRY_COUNT_LIMIT",
        )

    def test_t05_encrypted_member_metadata_fails_closed(self) -> None:
        path = self.root / "metadata.docx"
        path.write_bytes(b"x")
        content_types = zipfile.ZipInfo("[Content_Types].xml")
        content_types.file_size = content_types.compress_size = 1
        document_xml = zipfile.ZipInfo("word/document.xml")
        document_xml.file_size = document_xml.compress_size = 1
        document_xml.flag_bits |= 0x1
        fake_archive = SimpleNamespace(
            infolist=lambda: [content_types, document_xml]
        )
        with self.assertRaises(OfficeArchiveSafetyError) as caught:
            DocumentOfficeArchiveSafety().preflight(
                path=path,
                extension=".docx",
                archive=fake_archive,
            )
        self.assertEqual(caught.exception.code, "OFFICE_CONTAINER_ENCRYPTED")
        self.assertEqual(caught.exception.state, "unsupported")

    def test_t06_unsafe_path_symlink_and_duplicate_normalized_path(self) -> None:
        symlink = zipfile.ZipInfo("word/media/link.png")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        cases = (
            [("../escape.png", b"x")],
            [("/absolute.png", b"x")],
            [("C:/drive.png", b"x")],
            [(symlink, b"target")],
            [
                ("word/media/duplicate.png", b"a"),
                ("word\\media\\duplicate.png", b"b"),
            ],
        )
        for extras in cases:
            with self.subTest(extras=extras):
                path = self._write_archive(".docx", extras=extras)
                result = DocumentFileSafetyService().classify(
                    path=path,
                    original_filename=path.name,
                    declared_mime=self.MIME_TYPES[".docx"],
                )
                self.assertEqual(result.state, "unsupported")
                self.assertEqual(result.error_code, "OFFICE_CONTAINER_UNSAFE_MEMBER")

        nul_path = self.root / "nul-member.docx"
        nul_path.write_bytes(b"x")
        content_types = zipfile.ZipInfo("[Content_Types].xml")
        content_types.file_size = content_types.compress_size = 1
        document_xml = zipfile.ZipInfo("word/document.xml")
        document_xml.file_size = document_xml.compress_size = 1
        nul_member = zipfile.ZipInfo("word/media/truncated.png")
        nul_member.orig_filename = "word/media/unsafe\x00name.png"
        nul_member.file_size = nul_member.compress_size = 1
        with self.assertRaises(OfficeArchiveSafetyError) as caught:
            DocumentOfficeArchiveSafety().preflight(
                path=nul_path,
                extension=".docx",
                archive=SimpleNamespace(
                    infolist=lambda: [content_types, document_xml, nul_member]
                ),
            )
        self.assertEqual(caught.exception.code, "OFFICE_CONTAINER_UNSAFE_MEMBER")

    def test_t07_member_uncompressed_limit_is_metadata_only(self) -> None:
        document = self._store_archive(
            ".docx",
            extras=[("word/large.xml", b"0123456789")],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(max_member_uncompressed_bytes=9),
            expected_code="OFFICE_CONTAINER_MEMBER_SIZE_LIMIT",
        )

    def test_t08_total_uncompressed_limit_is_metadata_only(self) -> None:
        document = self._store_archive(
            ".docx",
            extras=[("word/a.xml", b"12345"), ("word/b.xml", b"67890")],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(max_total_uncompressed_bytes=20),
            expected_code="OFFICE_CONTAINER_TOTAL_SIZE_LIMIT",
        )

    def test_t09_compression_ratio_limit_is_metadata_only(self) -> None:
        document = self._store_archive(
            ".docx",
            extras=[("word/compressible.xml", b"A" * 4096)],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(max_compression_ratio=2.0),
            expected_code="OFFICE_CONTAINER_COMPRESSION_RATIO_LIMIT",
        )

    def test_t10_media_count_limit_precedes_extraction(self) -> None:
        png = self._png()
        document = self._store_archive(
            ".docx",
            media=[
                ("word/media/a.png", png),
                ("word/media/b.png", png),
            ],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(max_media_members=1),
            expected_code="OFFICE_MEDIA_COUNT_LIMIT",
        )

    def test_t11_media_member_limit_precedes_extraction(self) -> None:
        png = self._png()
        document = self._store_archive(
            ".docx",
            media=[("word/media/image.png", png)],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(
                max_media_member_uncompressed_bytes=len(png) - 1
            ),
            expected_code="OFFICE_MEDIA_MEMBER_SIZE_LIMIT",
        )

    def test_t12_total_media_limit_precedes_persistence(self) -> None:
        png = self._png()
        document = self._store_archive(
            ".docx",
            media=[
                ("word/media/a.png", png),
                ("word/media/b.png", png),
            ],
        )
        self._assert_rejected_before_body(
            document=document,
            policy=self._policy(
                max_total_media_uncompressed_bytes=(len(png) * 2) - 1
            ),
            expected_code="OFFICE_MEDIA_TOTAL_SIZE_LIMIT",
        )

    def test_t13_streaming_never_uses_zip_read_or_oversized_reads(self) -> None:
        png = self._png(64, 64)
        document = self._store_archive(
            ".docx",
            media=[("word/media/image.png", png)],
        )
        policy = self._policy(stream_chunk_bytes=127)
        requested_reads: list[int] = []
        original_read = zipfile.ZipExtFile.read

        def tracked_read(stream, size=-1):
            requested_reads.append(size)
            self.assertGreaterEqual(size, 0)
            self.assertLessEqual(size, policy.stream_chunk_bytes)
            return original_read(stream, size)

        with (
            patch.object(
                zipfile.ZipFile,
                "read",
                side_effect=AssertionError("ZipFile.read is forbidden"),
            ),
            patch.object(zipfile.ZipExtFile, "read", new=tracked_read),
        ):
            result = self._service(policy).extract_document_assets(
                document_id=document.id
            )
        self.assertEqual(result.status, "extracted")
        self.assertTrue(requested_reads)
        self.assertLessEqual(max(requested_reads), policy.stream_chunk_bytes)

    def test_t14_actual_stream_overrun_removes_staging(self) -> None:
        declared = b"1234"
        info = zipfile.ZipInfo("word/media/image.png")
        info.file_size = len(declared)
        info.compress_size = len(declared)
        member = OfficeArchiveMember(info=info, normalized_path=info.filename)
        fake_archive = SimpleNamespace(
            open=lambda *_args, **_kwargs: io.BytesIO(declared + b"overflow")
        )
        staged_path = self.staging_root / "overrun.bin"
        with self.assertRaises(OfficeArchiveSafetyError) as caught:
            self._service()._stream_media_member_to_stage(
                archive=fake_archive,
                member=member,
                staged_path=staged_path,
                aggregate_bytes_before=0,
            )
        self.assertEqual(caught.exception.code, "OFFICE_MEDIA_ACTUAL_SIZE_MISMATCH")
        self.assertFalse(staged_path.exists())

    def test_t15_image_dimension_limit_precedes_decode(self) -> None:
        png = self._png(64, 32)
        document = self._store_archive(
            ".docx",
            media=[("word/media/wide.png", png)],
        )
        result = self._service(
            self._policy(max_image_dimension_px=63)
        ).extract_document_assets(document_id=document.id)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "OFFICE_MEDIA_IMAGE_DIMENSION_LIMIT")
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document.id).count(), 0)

    def test_t16_image_pixel_limit_precedes_decode(self) -> None:
        png = self._png(40, 40)
        document = self._store_archive(
            ".docx",
            media=[("word/media/pixels.png", png)],
        )
        result = self._service(
            self._policy(max_image_pixels=1599)
        ).extract_document_assets(document_id=document.id)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "OFFICE_MEDIA_IMAGE_PIXEL_LIMIT")

    def test_t17_invalid_image_is_bounded_member_failure(self) -> None:
        document = self._store_archive(
            ".docx",
            media=[("word/media/not-image.bin", b"not-an-image" * 20)],
        )
        result = self._service().extract_document_assets(
            document_id=document.id
        )
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.assets[0].error, "OFFICE_MEDIA_IMAGE_INVALID")
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document.id).count(), 0)

    def test_t18_force_rejection_preserves_existing_asset_and_file(self) -> None:
        png = self._png()
        document = self._store_archive(
            ".docx",
            media=[("word/media/image.png", png)],
        )
        first = self._service().extract_document_assets(document_id=document.id)
        self.assertEqual(first.status, "extracted")
        existing = self.db.query(DocumentAsset).filter_by(document_id=document.id).one()
        existing_path = Path(settings.data_dir) / existing.storage_path
        existing_hash = hashlib.sha256(existing_path.read_bytes()).hexdigest()
        self._source_path(document).write_bytes(
            self._archive_bytes(
                ".docx",
                media=[("word/media/image.png", png)],
                extras=[("word/large.xml", b"x" * 64)],
            )
        )
        result = self._service(
            self._policy(max_member_uncompressed_bytes=63)
        ).extract_document_assets(document_id=document.id, force=True)
        self.assertEqual(result.error, "OFFICE_CONTAINER_MEMBER_SIZE_LIMIT")
        self.db.expire_all()
        preserved = self.db.get(DocumentAsset, existing.id)
        self.assertIsNotNone(preserved)
        self.assertTrue(existing_path.exists())
        self.assertEqual(hashlib.sha256(existing_path.read_bytes()).hexdigest(), existing_hash)

    def test_t19_safe_extraction_is_idempotent_by_checksum(self) -> None:
        document = self._store_archive(
            ".docx",
            media=[("word/media/image.png", self._png())],
        )
        first = self._service().extract_document_assets(document_id=document.id)
        second = self._service().extract_document_assets(document_id=document.id)
        self.assertEqual(first.extracted_count, 1)
        self.assertEqual(second.status, "existing")
        self.assertEqual(second.existing_count, 1)
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document.id).count(), 1)

    def test_t20_persistence_failure_rolls_back_and_removes_final_file(self) -> None:
        document = self._store_archive(
            ".docx",
            media=[("word/media/image.png", self._png())],
        )
        service = self._service()
        with patch.object(
            service.asset_repository,
            "commit",
            side_effect=RuntimeError("synthetic persistence failure"),
        ):
            result = service.extract_document_assets(document_id=document.id)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "OFFICE_MEDIA_PERSISTENCE_FAILED")
        self.assertEqual(self.db.query(DocumentAsset).filter_by(document_id=document.id).count(), 0)
        final_directory = Path(settings.data_dir) / "document-assets" / str(document.id)
        self.assertFalse(final_directory.exists())

    def test_t21_legacy_doc_conversion_reuses_bounded_streaming_policy(self) -> None:
        marker = uuid.uuid4().hex
        stored = DocumentService(self.db).store_document(
            content=f"legacy-doc-synthetic-{marker}".encode("ascii"),
            original_filename=f"legacy-{marker}.doc",
            content_type="application/msword",
            source_type="manual_upload",
        )
        png = self._png()

        def fake_convert(arguments, **_kwargs):
            outdir = Path(arguments[arguments.index("--outdir") + 1])
            (outdir / "converted.docx").write_bytes(
                self._archive_bytes(
                    ".docx",
                    media=[("word/media/image.png", png)],
                )
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with (
            patch(
                "app.services.document_asset_extraction_service.subprocess.run",
                side_effect=fake_convert,
            ) as conversion,
            patch.object(
                zipfile.ZipFile,
                "read",
                side_effect=AssertionError("ZipFile.read is forbidden"),
            ),
        ):
            result = self._service().extract_document_assets(
                document_id=stored.document.id
            )
        self.assertEqual(result.status, "extracted", result)
        self.assertEqual(result.extracted_count, 1)
        self.assertEqual(conversion.call_args.kwargs["timeout"], 180)
        self.assertEqual(result.assets[0].checksum_sha256, hashlib.sha256(png).hexdigest())

    def test_t22_canonical_file_safety_does_not_expand_formats(self) -> None:
        policy = DEFAULT_OFFICE_ARCHIVE_POLICY
        self.assertEqual(policy.max_compressed_container_bytes, 256 * 1024 * 1024)
        self.assertEqual(policy.max_container_entries, 5000)
        self.assertEqual(policy.max_member_uncompressed_bytes, 256 * 1024 * 1024)
        self.assertEqual(policy.max_total_uncompressed_bytes, 1024 * 1024 * 1024)
        self.assertEqual(policy.max_compression_ratio, 500.0)
        self.assertEqual(policy.max_media_members, 512)
        self.assertEqual(policy.max_media_member_uncompressed_bytes, 64 * 1024 * 1024)
        self.assertEqual(policy.max_total_media_uncompressed_bytes, 512 * 1024 * 1024)
        self.assertEqual(policy.max_image_dimension_px, 8192)
        self.assertEqual(policy.max_image_pixels, 32_000_000)
        self.assertEqual(policy.stream_chunk_bytes, 1024 * 1024)
        service = DocumentFileSafetyService()
        for extension in (".docx", ".xlsx", ".pptx", ".odt"):
            path = self._write_archive(extension)
            self.assertEqual(
                service.classify(
                    path=path,
                    original_filename=path.name,
                    declared_mime=self.MIME_TYPES[extension],
                ).state,
                "supported",
            )
        for extension in (".odp", ".ods", ".rar", ".7z"):
            path = self.root / f"unsupported{extension}"
            path.write_bytes(b"synthetic")
            self.assertEqual(
                service.classify(
                    path=path,
                    original_filename=path.name,
                    declared_mime="application/octet-stream",
                ).state,
                "unsupported",
            )

    def test_t23_useful_office_text_survives_bounded_asset_failure(self) -> None:
        document = self._store_archive(".xlsx")
        processing = DocumentProcessingService(self.db)
        text_result = SimpleNamespace(
            status="extracted",
            text="Syntetyczny użyteczny tekst arkusza.",
            error=None,
        )
        asset_result = DocumentAssetExtractionResult(
            document_id=document.id,
            status="failed",
            source_format="xlsx",
            discovered_count=1,
            extracted_count=0,
            existing_count=0,
            skipped_count=0,
            failed_count=1,
            assets=[],
            error="OFFICE_MEDIA_TOTAL_SIZE_LIMIT",
        )
        with (
            patch.object(processing.extraction_service, "extract", return_value=text_result),
            patch.object(
                processing.asset_service,
                "extract_document_assets",
                return_value=asset_result,
            ),
        ):
            result = processing._process_asset_text_document(
                document=document,
                path=self._source_path(document),
                force=False,
            )
        self.assertEqual(result.status, "processed")
        self.assertIn("OFFICE_MEDIA_TOTAL_SIZE_LIMIT", result.error or "")

    def test_t24_no_external_side_effects(self) -> None:
        before_analysis = self.db.query(AnalysisJob).count()
        before_assistant = self.db.query(AssistantRun).count()
        document = self._store_archive(
            ".docx",
            media=[("word/media/image.png", self._png())],
        )
        with (
            patch(
                "app.services.vision_processing_service."
                "VisionProcessingService.advance",
                side_effect=AssertionError("Vision must not run"),
            ) as vision,
            patch(
                "app.services.document_asset_extraction_service.subprocess.run",
                side_effect=AssertionError("LibreOffice must not run"),
            ) as process,
        ):
            result = self._service().extract_document_assets(
                document_id=document.id
            )
        self.assertEqual(result.status, "extracted")
        vision.assert_not_called()
        process.assert_not_called()
        self.assertEqual(self.db.query(AnalysisJob).count(), before_analysis)
        self.assertEqual(self.db.query(AssistantRun).count(), before_assistant)
