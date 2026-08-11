from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_office_page_service import (
    DocumentOfficePageService,
)


DOCUMENT_ID = 770
DPI = 150


db = SessionLocal()

try:
    repository = DocumentRepository(
        db
    )

    service = DocumentOfficePageService(
        db
    )

    print()
    print("=" * 100)
    print("BEFORE")
    print("=" * 100)

    before_pages = (
        repository.get_pages(
            DOCUMENT_ID
        )
    )

    print(
        "pages_in_db:",
        len(before_pages),
    )

    print()
    print("=" * 100)
    print("FIRST PROCESS")
    print("=" * 100)

    first = service.process_document(
        document_id=DOCUMENT_ID,
        dpi=DPI,
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
        "rendered_count:",
        first.rendered_count,
    )

    print(
        "existing_count:",
        first.existing_count,
    )

    print(
        "stored_page_count:",
        first.stored_page_count,
    )

    print(
        "failed_count:",
        first.failed_count,
    )

    print(
        "error:",
        first.error,
    )

    print()
    print("=" * 100)
    print("DATABASE PAGES")
    print("=" * 100)

    pages = repository.get_pages(
        DOCUMENT_ID
    )

    print(
        "pages_in_db:",
        len(pages),
    )

    valid_pages = 0

    for page in pages:
        print()
        print("-" * 100)

        print(
            "page_number:",
            page.page_number,
        )

        print(
            "processing_status:",
            page.processing_status,
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

        if not page.render_path:
            continue

        absolute_path = (
            Path(settings.data_dir)
            / page.render_path
        )

        print(
            "file_exists:",
            absolute_path.exists(),
        )

        if (
            absolute_path.exists()
            and page.render_dpi == DPI
            and page.width is not None
            and page.height is not None
        ):
            valid_pages += 1

    print()
    print("=" * 100)
    print("SECOND PROCESS - IDEMPOTENCY")
    print("=" * 100)

    second = service.process_document(
        document_id=DOCUMENT_ID,
        dpi=DPI,
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
        "rendered_count:",
        second.rendered_count,
    )

    print(
        "existing_count:",
        second.existing_count,
    )

    print(
        "stored_page_count:",
        second.stored_page_count,
    )

    print(
        "failed_count:",
        second.failed_count,
    )

    print(
        "error:",
        second.error,
    )

    final_pages = repository.get_pages(
        DOCUMENT_ID
    )

    print()
    print("=" * 100)
    print("FINAL RESULT")
    print("=" * 100)

    print(
        "valid_pages:",
        valid_pages,
    )

    print(
        "final_pages_in_db:",
        len(final_pages),
    )

    if (
        first.status == "processed"
        and first.page_count == 21
        and first.stored_page_count == 21
        and first.failed_count == 0
        and valid_pages == 21
        and second.status == "processed"
        and second.page_count == 21
        and second.existing_count == 21
        and second.stored_page_count == 21
        and second.failed_count == 0
        and len(final_pages) == 21
    ):
        print(
            "OFFICE PAGE DATABASE TEST: OK"
        )

    else:
        print(
            "OFFICE PAGE DATABASE TEST: "
            "CHECK RESULTS"
        )

finally:
    db.close()