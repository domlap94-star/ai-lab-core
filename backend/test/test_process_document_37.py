from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.document_processing_service import (
    DocumentProcessingService,
)

DOCUMENT_ID = 37

db = SessionLocal()

try:
    service = DocumentProcessingService(db)

    result = service.process_document(
        document_id=DOCUMENT_ID,
        ocr_dpi=150,
        force=True,
    )

    print()
    print("=" * 80)
    print("PROCESSING RESULT")
    print("=" * 80)

    print("document_id:", result.document_id)
    print("status:", result.status)
    print("page_count:", result.page_count)
    print("native_character_count:", result.native_character_count)
    print("ocr_character_count:", result.ocr_character_count)
    print("combined_character_count:", result.combined_character_count)
    print("error:", result.error)

    print()
    print("=" * 80)
    print("DOCUMENT")
    print("=" * 80)

    document = (
        db.query(Document)
        .filter(Document.id == DOCUMENT_ID)
        .first()
    )

    if document is None:
        print("DOCUMENT NOT FOUND")
    else:
        print("id:", document.id)
        print("filename:", document.original_filename)
        print("processing_status:", document.processing_status)
        print("processing_error:", document.processing_error)

        extracted_text = document.extracted_text or ""

        print("extracted_text_length:", len(extracted_text))

        if extracted_text:
            print()
            print("DOCUMENT TEXT PREVIEW:")
            print(extracted_text[:3000])

    print()
    print("=" * 80)
    print("DOCUMENT PAGES")
    print("=" * 80)

    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == DOCUMENT_ID)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )

    print("pages_in_database:", len(pages))

    for page in pages:
        print()
        print("-" * 80)
        print("PAGE:", page.page_number)
        print("-" * 80)

        print("processing_status:", page.processing_status)
        print("processing_error:", page.processing_error)

        print(
            "native_characters:",
            len(page.extracted_text or ""),
        )

        print(
            "ocr_characters:",
            len(page.ocr_text or ""),
        )

        print(
            "ocr_confidence:",
            page.ocr_confidence,
        )

        print(
            "dimensions:",
            page.width,
            "x",
            page.height,
        )

        if page.extracted_text:
            print()
            print("NATIVE TEXT:")
            print(page.extracted_text[:1500])

        if page.ocr_text:
            print()
            print("OCR TEXT:")
            print(page.ocr_text[:1500])

finally:
    db.close()