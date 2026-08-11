from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.document_processing_service import (
    DocumentProcessingService,
)


DOCUMENT_IDS = [
    18,    # mały PDF - faktura
    1608,  # PNG
]


db = SessionLocal()

try:
    service = DocumentProcessingService(
        db
    )

    for document_id in DOCUMENT_IDS:
        print()
        print("=" * 100)
        print(
            "PROCESS DOCUMENT:",
            document_id,
        )
        print("=" * 100)

        result = service.process_document(
            document_id=document_id,
            ocr_dpi=150,
            render_dpi=150,
            force=True,
        )

        print(
            "status:",
            result.status,
        )

        print(
            "page_count:",
            result.page_count,
        )

        print(
            "native_character_count:",
            result.native_character_count,
        )

        print(
            "ocr_character_count:",
            result.ocr_character_count,
        )

        print(
            "combined_character_count:",
            result.combined_character_count,
        )

        print(
            "metadata_status:",
            result.metadata_status,
        )

        print(
            "render_status:",
            result.render_status,
        )

        print(
            "error:",
            result.error,
        )

        document = (
            db.query(Document)
            .filter(
                Document.id == document_id
            )
            .first()
        )

        print()
        print("--- DOCUMENT DB ---")

        if document is None:
            print(
                "DOCUMENT NOT FOUND"
            )

        else:
            print(
                "processing_status:",
                document.processing_status,
            )

            print(
                "processing_error:",
                document.processing_error,
            )

            print(
                "metadata_status:",
                document.metadata_status,
            )

            print(
                "metadata_error:",
                document.metadata_error,
            )

            print(
                "extracted_text_length:",
                len(
                    document.extracted_text
                    or ""
                ),
            )

            print(
                "metadata_normalized:",
                document.metadata_normalized,
            )

        pages = (
            db.query(DocumentPage)
            .filter(
                DocumentPage.document_id
                == document_id
            )
            .order_by(
                DocumentPage.page_number.asc()
            )
            .all()
        )

        print()
        print("--- PAGES ---")

        print(
            "count:",
            len(pages),
        )

        for page in pages:
            print()

            print(
                "page_number:",
                page.page_number,
            )

            print(
                "processing_status:",
                page.processing_status,
            )

            print(
                "native_chars:",
                len(
                    page.extracted_text
                    or ""
                ),
            )

            print(
                "ocr_chars:",
                len(
                    page.ocr_text
                    or ""
                ),
            )

            print(
                "ocr_confidence:",
                page.ocr_confidence,
            )

            print(
                "render_path:",
                page.render_path,
            )

            print(
                "render_dpi:",
                page.render_dpi,
            )

            print(
                "dimensions:",
                page.width,
                "x",
                page.height,
            )

finally:
    db.close()