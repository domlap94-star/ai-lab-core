from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_processing_service import (
    DocumentProcessingService,
)


DOCUMENT_ID = 5066


db = SessionLocal()

try:
    service = DocumentProcessingService(
        db
    )

    result = service.process_document(
        document_id=DOCUMENT_ID,
        ocr_dpi=150,
        render_dpi=150,
        force=True,
    )

    print()
    print("=" * 100)
    print("PROCESSING RESULT")
    print("=" * 100)

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
    print("=" * 100)
    print("DOCUMENT DATABASE STATE")
    print("=" * 100)

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
        print(
            "TEXT PREVIEW:"
        )

        print(
            (
                document.extracted_text
                or ""
            )[:1500]
        )

finally:
    db.close()