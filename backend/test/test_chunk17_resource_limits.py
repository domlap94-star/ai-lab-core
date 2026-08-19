from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient
from PIL import Image

from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.user import User
from app.services.document_ocr_service import DocumentOCRService
from app.services.document_page_render_service import DocumentPageRenderService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService, DocumentTooLargeError
from app.services.agent_service import AgentService


class Chunk17ResourceLimitTests(unittest.TestCase):
    @staticmethod
    def _pdf(path: Path, pages: int) -> None:
        document = fitz.open()
        for index in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {index + 1}")
        document.save(path)
        document.close()

    def test_pdf_renderer_stops_at_bounded_page_limit(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "three-pages.pdf"
            self._pdf(source, 3)
            service = DocumentPageRenderService()
            service.data_directory = root
            service.render_root = root / "renders"

            result = service.render_pdf(
                document_id=17,
                path=source,
                max_pages=2,
            )

            self.assertEqual(result.status, "partial")
            self.assertEqual(result.page_count, 2)
            self.assertEqual([page.page_number for page in result.pages], [1, 2])
            self.assertIn("first 2 of 3", result.error or "")

    def test_pdf_renderer_rejects_unbounded_dpi(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "one-page.pdf"
            self._pdf(source, 1)
            result = DocumentPageRenderService().render_pdf(
                document_id=17,
                path=source,
                dpi=1200,
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("DPI", result.error or "")

    def test_native_text_extraction_is_page_bounded(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "three-pages.pdf"
            self._pdf(source, 3)
            service = DocumentProcessingService.__new__(DocumentProcessingService)
            pages = service._extract_pdf_native_pages(source, max_pages=2)
            self.assertEqual(len(pages), 2)

    def test_tesseract_receives_per_page_timeout(self) -> None:
        service = DocumentOCRService()
        image = Image.new("RGB", (32, 32), "white")
        with patch(
            "app.services.document_ocr_service.pytesseract.image_to_data",
            return_value={"text": [], "conf": []},
        ) as image_to_data:
            result = service._ocr_pil_image(
                image=image,
                page_number=1,
                started=0.0,
            )
        self.assertEqual(result.status, "no_text")
        self.assertEqual(
            image_to_data.call_args.kwargs["timeout"],
            service.PAGE_TIMEOUT_SECONDS,
        )

    def test_document_storage_rejects_oversized_content(self) -> None:
        service = DocumentService.__new__(DocumentService)
        service.MAX_DOCUMENT_BYTES = 4

        with self.assertRaises(DocumentTooLargeError):
            service.store_document(
                content=b"12345",
                original_filename="bounded.bin",
                content_type="application/octet-stream",
                source_type="manual_upload",
            )

    def test_agent_routes_exact_visual_read_without_planner_guessing(self) -> None:
        action = AgentService._direct_read_action(
            "Sprawdź zapisaną analizę wizualną dokumentu 17.",
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.tool, "get_visual_analysis")
        self.assertEqual(action.arguments, {"id": 17})
        self.assertIsNone(
            AgentService._direct_read_action(
                "Sprawdź, czy dokumentacja zawiera analizę.",
            )
        )

    def test_client_upload_rejects_oversized_body_before_storage(self) -> None:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.is_active.is_(True)).first()
            self.assertIsNotNone(user)
            token = create_access_token(data={"sub": user.username})
        finally:
            db.close()

        with patch.object(DocumentService, "MAX_DOCUMENT_BYTES", 4):
            response = TestClient(app).post(
                "/api/v1/clients/1/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("large.bin", b"12345", "application/octet-stream")},
            )

        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
