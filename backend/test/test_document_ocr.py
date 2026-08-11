from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_ocr_service import (
    DocumentOCRService,
)

db = SessionLocal()
service = DocumentOCRService()

document_ids = [
    1608,
    22,
]

try:
    documents = (
        db.query(Document)
        .filter(
            Document.id.in_(
                document_ids
            )
        )
        .order_by(
            Document.id.asc()
        )
        .all()
    )

    for document in documents:
        print()
        print("=" * 80)
        print(
            "DOCUMENT:",
            document.id,
        )
        print("=" * 80)

        path = (
            Path(settings.data_dir)
            / document.storage_path
        )

        max_pages = (
            3
            if document.content_type
            == "application/pdf"
            else None
        )

        result = service.ocr_document(
            path=path,
            content_type=(
                document.content_type
            ),
            original_filename=(
                document.original_filename
            ),
            dpi=150,
            max_pages=max_pages,
        )

        print(
            "filename:",
            document.original_filename,
        )
        print(
            "status:",
            result.status,
        )
        print(
            "pages:",
            result.page_count,
        )
        print(
            "characters:",
            result.character_count,
        )
        print(
            "confidence:",
            result.average_confidence,
        )
        print(
            "elapsed:",
            round(
                result.elapsed_seconds,
                2,
            ),
        )
        print(
            "error:",
            result.error,
        )

        for page in result.pages:
            print()
            print(
                "PAGE:",
                page.page_number,
            )
            print(
                "STATUS:",
                page.status,
            )
            print(
                "CONFIDENCE:",
                page.confidence,
            )
            print(
                "SIZE:",
                page.width,
                "x",
                page.height,
            )
            print(
                "TIME:",
                round(
                    page.elapsed_seconds,
                    2,
                ),
            )

            if page.text:
                print(
                    "TEXT:",
                    page.text[:500],
                )
            else:
                print(
                    "TEXT: [NONE]"
                )

finally:
    db.close()
