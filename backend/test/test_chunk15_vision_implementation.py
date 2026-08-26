from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from app.core.config import settings
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.vision import VisionResult
from app.services.vision_need_classifier import VisionNeedClassifier
from app.services.vision_processing_service import VisionProcessingService
from app.services.vision_supervisor_client import VisionSupervisorUnavailable
from app.services.document_service import DocumentService


class _Documents:
    def __init__(self, document, pages):
        self.document = document
        self.pages = pages
        self.commits = 0

    def get(self, document_id):
        return self.document if self.document.id == document_id else None

    def get_pages(self, document_id):
        return self.pages

    def commit(self):
        self.commits += 1


class _Assets:
    def get_for_document(self, document_id):
        return []


class _Unavailable:
    def create_job(self, payload):
        raise VisionSupervisorUnavailable


class _StoreRepository:
    def __init__(self, existing=None):
        self.existing = existing
        self.created = []
        self.db = object()

    def get_by_external_id(self, **kwargs):
        return None

    def get_by_checksum(self, checksum):
        return self.existing

    def create(self, document):
        document.id = 100
        self.created.append(document)
        return document

    def commit(self):
        return None

    def rollback(self):
        return None


class Chunk15VisionImplementationTests(unittest.TestCase):
    def test_classifier_is_text_first_and_page_bounded(self):
        classifier = VisionNeedClassifier()
        document = Document(id=1, original_filename="report.pdf", content_type="application/pdf")
        text_pages = [DocumentPage(document_id=1, page_number=1, extracted_text="A" * 300, render_path="page.png")]
        self.assertEqual(classifier.classify(document=document, pages=text_pages, assets=[]).classification, "text_sufficient")
        visual_pages = [DocumentPage(document_id=1, page_number=index, extracted_text="", render_path=f"p{index}.png") for index in range(1, 15)]
        result = classifier.classify(document=document, pages=visual_pages, assets=[])
        self.assertEqual(result.classification, "vision_required")
        self.assertEqual(len(result.sources), 8)
        self.assertTrue(result.partial)

    def test_pdf_policy_selects_only_visual_pages(self):
        classifier = VisionNeedClassifier()
        document = Document(id=10, original_filename="mixed.pdf", content_type="application/pdf")
        pages = [
            DocumentPage(
                document_id=10,
                page_number=1,
                extracted_text="Pełna tekstowa treść dokumentu " * 12,
                render_path="p1.png",
            ),
            DocumentPage(
                document_id=10,
                page_number=2,
                extracted_text="Rysunek przekroju fundamentu",
                render_path="p2.png",
                page_type="drawing",
            ),
        ]
        result = classifier.classify(document=document, pages=pages, assets=[])
        self.assertEqual(result.classification, "vision_required")
        self.assertEqual([item.page.page_number for item in result.sources], [2])

    def test_large_pdf_never_selects_all_pages(self):
        classifier = VisionNeedClassifier()
        document = Document(id=11, original_filename="large.pdf", content_type="application/pdf")
        for count in (50, 200):
            pages = [
                DocumentPage(
                    document_id=11,
                    page_number=index,
                    extracted_text="",
                    render_path=f"p{index}.png",
                    page_type="scan",
                )
                for index in range(1, count + 1)
            ]
            result = classifier.classify(document=document, pages=pages, assets=[])
            self.assertEqual(len(result.sources), 8)
            self.assertTrue(result.partial)

    def test_classifier_images_and_unsupported(self):
        classifier = VisionNeedClassifier()
        image = Document(id=2, original_filename="photo.jpg", content_type="image/jpeg", client_id=1, inspection_id=2)
        page = DocumentPage(document_id=2, page_number=1, width=1200, height=800)
        self.assertEqual(classifier.classify(document=image, pages=[page], assets=[]).classification, "vision_required")
        tiny = Document(id=3, original_filename="icon.png", content_type="image/png")
        tiny_page = DocumentPage(document_id=3, page_number=1, width=32, height=32)
        self.assertEqual(classifier.classify(document=tiny, pages=[tiny_page], assets=[]).classification, "text_sufficient")
        binary = Document(id=4, original_filename="payload.bin", content_type="application/octet-stream")
        self.assertEqual(classifier.classify(document=binary, pages=[], assets=[]).classification, "unsupported")

    def test_result_contract_rejects_unknown_source_and_measurement_without_basis(self):
        base = {
            "schema_version": "NEXT_STABIL_VISION_V1", "job_id": "12345678-1234-1234-1234-123456789abc",
            "observations": [], "possible_interpretations": [], "uncertainties": [], "visible_text": [], "measurements": [],
            "image_quality": [{"source_ref": "S1", "quality": "good"}],
        }
        VisionResult.model_validate(base)
        with self.assertRaises(ValidationError):
            VisionResult.model_validate({**base, "measurements": [{"source_ref": "S1", "value": 2, "unit": "mm"}]})
        with self.assertRaises(ValidationError):
            VisionResult.model_validate({**base, "unexpected": True})

    def test_large_image_is_bounded_without_changing_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "large.png"
            Image.new("RGB", (3000, 1200), "white").save(source)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            service = VisionProcessingService(object())
            service.spool_root = root / "vision-spool"
            prepared, extension = service._prepare_path(source)
            self.assertEqual(extension, ".jpg")
            with Image.open(prepared) as bounded:
                self.assertLessEqual(max(bounded.size), 2048)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_new_document_queues_local_preparation_without_auto_external_vision(self):
        with tempfile.TemporaryDirectory() as temporary:
            original_data_dir = settings.data_dir
            settings.data_dir = temporary
            try:
                service = DocumentService(object())
                repository = _StoreRepository()
                service.repository = repository
                with patch(
                    "app.services.document_preparation_service."
                    "DocumentPreparationService.get_or_create"
                ) as prepare:
                    result = service.store_document(
                        content=b"new synthetic document",
                        original_filename="fixture.txt",
                        content_type="text/plain",
                        source_type="manual_upload",
                    )
                self.assertTrue(result.created)
                self.assertFalse(result.document.vision_auto_eligible)
                self.assertEqual(result.document.vision_status, "not_evaluated")
                prepare.assert_called_once()

                historical = Document(
                    id=99, filename="old.txt", original_filename="old.txt",
                    content_type="text/plain", file_size=3, source_type="manual_upload",
                    vision_auto_eligible=False, vision_status="not_evaluated",
                )
                service.repository = _StoreRepository(existing=historical)
                duplicate = service.store_document(
                    content=b"new synthetic document",
                    original_filename="fixture.txt",
                    content_type="text/plain",
                    source_type="manual_upload",
                )
                self.assertFalse(duplicate.created)
                self.assertFalse(duplicate.document.vision_auto_eligible)
            finally:
                settings.data_dir = original_data_dir

    def test_worker_unavailable_preserves_document_and_sets_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (800, 600), "white").save(root / "photo.jpg")
            document = Document(id=5, original_filename="photo.jpg", content_type="image/jpeg", storage_path="photo.jpg", client_id=1, vision_auto_eligible=True, vision_status="not_evaluated", vision_attempt_count=0)
            page = DocumentPage(document_id=5, page_number=1, width=800, height=600, vision_status="not_evaluated", vision_attempt_count=0)
            service = VisionProcessingService(object(), supervisor=_Unavailable())
            service.data_root = root.resolve()
            service.spool_root = (root / "vision-spool").resolve()
            service.documents = _Documents(document, [page])
            service.assets = _Assets()
            result = service.advance(5)
            self.assertEqual(result.status, "failed_retryable")
            self.assertEqual(document.vision_error_code, "WORKER_UNAVAILABLE")
            self.assertEqual(document.vision_attempt_count, 1)
            self.assertTrue((root / "photo.jpg").exists())

    def test_historical_document_is_never_automatic_but_explicit_request_is_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (800, 600), "white").save(root / "photo.jpg")
            document = Document(
                id=7, original_filename="photo.jpg", content_type="image/jpeg",
                storage_path="photo.jpg", client_id=1,
                vision_auto_eligible=False, vision_status="not_evaluated",
                vision_attempt_count=0,
            )
            page = DocumentPage(document_id=7, page_number=1, width=800, height=600)
            service = VisionProcessingService(object(), supervisor=_Unavailable())
            service.data_root = root.resolve()
            service.spool_root = (root / "vision-spool").resolve()
            service.documents = _Documents(document, [page])
            service.assets = _Assets()
            self.assertEqual(service.advance(7).status, "not_evaluated")
            self.assertEqual(document.vision_attempt_count, 0)
            self.assertEqual(service.advance(7, explicit=True).status, "failed_retryable")
            self.assertEqual(document.vision_attempt_count, 1)

    def test_complete_result_is_versioned_and_persisted_on_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (800, 600), "white").save(root / "photo.jpg")
            document = Document(id=6, original_filename="photo.jpg", content_type="image/jpeg", storage_path="photo.jpg", client_id=1, vision_auto_eligible=True, vision_status="not_evaluated", vision_attempt_count=0)
            page = DocumentPage(document_id=6, page_number=1, width=800, height=600, vision_status="not_evaluated", vision_attempt_count=0)
            service = VisionProcessingService(object())
            service.data_root = root.resolve()
            service.spool_root = (root / "vision-spool").resolve()
            service.documents = _Documents(document, [page])
            service.assets = _Assets()

            class _Complete:
                def create_job(self, payload):
                    job_id = "12345678-1234-1234-1234-123456789abc"
                    job_dir = service.spool_root / "jobs" / job_id
                    (job_dir / "output").mkdir(parents=True)
                    sources = [{
                        "source_ref": item["source_ref"], "document_id": item["document_id"],
                        "page_number": item["page_number"], "asset_id": item["asset_id"],
                        "sha256": item["sha256"], "relative_input_path": f"input/{item['source_ref']}.jpg",
                    } for item in payload["sources"]]
                    (job_dir / "manifest.json").write_text(json.dumps({"sources": sources}), encoding="utf-8")
                    value = {
                        "schema_version": "NEXT_STABIL_VISION_V1", "job_id": job_id,
                        "observations": [{"source_ref": "S1", "text": "Widoczna linia."}],
                        "possible_interpretations": [], "uncertainties": [], "visible_text": [], "measurements": [],
                        "image_quality": [{"source_ref": "S1", "quality": "good"}],
                    }
                    (job_dir / "output" / "vision.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                    output_hash = hashlib.sha256((json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()).hexdigest()
                    (job_dir / "output" / "result_manifest.json").write_text(json.dumps({"output_sha256": output_hash, "source_sha256": {"S1": sources[0]["sha256"]}}), encoding="utf-8")
                    return {"job_id": job_id, "state": "COMPLETE", "attempt_count": 1}

            service.supervisor = _Complete()
            result = service.advance(6)
            self.assertEqual(result.status, "complete")
            self.assertEqual(page.vision_status, "complete")
            self.assertEqual(page.vision_schema_version, "NEXT_STABIL_VISION_V1")
            self.assertIn("Widoczna linia", page.vision_analysis)


if __name__ == "__main__":
    unittest.main()
