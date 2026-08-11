from __future__ import annotations

from app.database.session import SessionLocal
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_office_ocr_service import (
    DocumentOfficeOCRService,
)


DOCUMENT_ID = 770


db = SessionLocal()

try:
    repository = DocumentRepository(
        db
    )

    service = (
        DocumentOfficeOCRService(
            db
        )
    )

    print()
    print("=" * 100)
    print("BEFORE OCR")
    print("=" * 100)

    pages_before = (
        repository.get_pages(
            DOCUMENT_ID
        )
    )

    print(
        "pages:",
        len(pages_before),
    )

    print(
        "pages_with_ocr:",
        sum(
            1
            for page in pages_before
            if page.ocr_text
        ),
    )

    print()
    print("=" * 100)
    print("FIRST OCR")
    print("=" * 100)

    first = service.process_document(
        document_id=DOCUMENT_ID,
        force=True,
    )

    print(
        "status:",
        first.status,
    )

    print(
        "page_count:",
        first.page_count,
    )

    print(
        "processed_count:",
        first.processed_count,
    )

    print(
        "no_text_count:",
        first.no_text_count,
    )

    print(
        "failed_count:",
        first.failed_count,
    )

    print(
        "total_character_count:",
        first.total_character_count,
    )

    print(
        "average_confidence:",
        first.average_confidence,
    )

    print(
        "error:",
        first.error,
    )

    print()
    print("=" * 100)
    print("PAGE RESULTS")
    print("=" * 100)

    for page in first.pages:
        print()
        print("-" * 100)

        print(
            "page_number:",
            page.page_number,
        )

        print(
            "status:",
            page.status,
        )

        print(
            "characters:",
            page.character_count,
        )

        print(
            "confidence:",
            page.confidence,
        )

        print(
            "render_path:",
            page.render_path,
        )

        print(
            "error:",
            page.error,
        )

    pages_after = (
        repository.get_pages(
            DOCUMENT_ID
        )
    )

    print()
    print("=" * 100)
    print("DATABASE STATE")
    print("=" * 100)

    print(
        "pages:",
        len(pages_after),
    )

    print(
        "processed:",
        sum(
            1
            for page in pages_after
            if (
                page.processing_status
                == "processed"
            )
        ),
    )

    print(
        "no_text:",
        sum(
            1
            for page in pages_after
            if (
                page.processing_status
                == "no_text"
            )
        ),
    )

    print(
        "failed:",
        sum(
            1
            for page in pages_after
            if (
                page.processing_status
                == "failed"
            )
        ),
    )

    print(
        "ocr_characters:",
        sum(
            len(
                page.ocr_text
                or ""
            )
            for page in pages_after
        ),
    )

    print()
    print("=" * 100)
    print("SECOND OCR - IDEMPOTENCY")
    print("=" * 100)

    second = service.process_document(
        document_id=DOCUMENT_ID,
        force=False,
    )

    print(
        "status:",
        second.status,
    )

    print(
        "page_count:",
        second.page_count,
    )

    print(
        "processed_count:",
        second.processed_count,
    )

    print(
        "no_text_count:",
        second.no_text_count,
    )

    print(
        "failed_count:",
        second.failed_count,
    )

    print(
        "total_character_count:",
        second.total_character_count,
    )

    print(
        "average_confidence:",
        second.average_confidence,
    )

    print(
        "error:",
        second.error,
    )

    print()
    print("=" * 100)
    print("FINAL RESULT")
    print("=" * 100)

    if (
        first.status
        in {
            "processed",
            "partial",
        }
        and first.page_count == 21
        and first.failed_count == 0
        and first.total_character_count > 0
        and second.status
        == "processed"
        and second.page_count == 21
        and second.failed_count == 0
    ):
        print(
            "OFFICE OCR TEST: OK"
        )

    else:
        print(
            "OFFICE OCR TEST: "
            "CHECK RESULTS"
        )

finally:
    db.close()