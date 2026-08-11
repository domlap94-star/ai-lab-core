from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.document_processing_service import (
    DocumentProcessingService,
)


DOCUMENT_ID = 37


db = SessionLocal()

try:
    service = DocumentProcessingService(
        db
    )

    result = service.process_document(
        document_id=DOCUMENT_ID,
        ocr_dpi=150,
        render_dpi=150,
        force=False,
    )

    print()
    print("=" * 80)
    print("PROCESSING RESULT")
    print("=" * 80)

    print(
        "document_id:",
        result.document_id,
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

    print()
    print("=" * 80)
    print("DOCUMENT DATABASE STATE")
    print("=" * 80)

    document = (
        db.query(Document)
        .filter(
            Document.id == DOCUMENT_ID
        )
        .first()
    )

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
            "metadata_extracted_at:",
            document.metadata_extracted_at,
        )

        print(
            "extracted_text_length:",
            len(
                document.extracted_text
                or ""
            ),
        )

        print()
        print(
            "metadata_normalized:"
        )

        print(
            document.metadata_normalized
        )

    print()
    print("=" * 80)
    print("DOCUMENT PAGES")
    print("=" * 80)

    pages = (
        db.query(DocumentPage)
        .filter(
            DocumentPage.document_id
            == DOCUMENT_ID
        )
        .order_by(
            DocumentPage.page_number.asc()
        )
        .all()
    )

    print(
        "page_count_in_db:",
        len(pages),
    )

    for page in pages:
        print()
        print("-" * 80)

        print(
            "page_number:",
            page.page_number,
        )

        print(
            "processing_status:",
            page.processing_status,
        )

        print(
            "processing_error:",
            page.processing_error,
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