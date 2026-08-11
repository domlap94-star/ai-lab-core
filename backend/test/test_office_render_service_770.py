from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_office_render_service import (
    DocumentOfficeRenderService,
)


DOCUMENT_ID = 770
DPI = 150


db = SessionLocal()

try:
    document = (
        db.query(Document)
        .filter(
            Document.id
            == DOCUMENT_ID
        )
        .first()
    )

    if document is None:
        raise RuntimeError(
            f"Document {DOCUMENT_ID} "
            f"not found."
        )

    if not document.storage_path:
        raise RuntimeError(
            "Document has no "
            "storage_path."
        )

    source_path = (
        Path(settings.data_dir)
        / document.storage_path
    )

    print()
    print("=" * 100)
    print("SOURCE")
    print("=" * 100)

    print(
        "document_id:",
        document.id,
    )

    print(
        "filename:",
        document.original_filename,
    )

    print(
        "content_type:",
        document.content_type,
    )

    print(
        "source_path:",
        source_path,
    )

    print(
        "exists:",
        source_path.exists(),
    )

    service = (
        DocumentOfficeRenderService()
    )

    print()
    print("=" * 100)
    print("SUPPORT TEST")
    print("=" * 100)

    print(
        "supported:",
        service.supports(
            content_type=(
                document.content_type
            ),
            original_filename=(
                document.original_filename
            ),
        ),
    )

    print()
    print("=" * 100)
    print("FIRST RENDER")
    print("=" * 100)

    first = service.render_document(
        document_id=document.id,
        path=source_path,
        content_type=(
            document.content_type
        ),
        original_filename=(
            document.original_filename
        ),
        dpi=DPI,
        force=True,
    )

    print(
        "status:",
        first.status,
    )

    print(
        "source_format:",
        first.source_format,
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
        "failed_count:",
        first.failed_count,
    )

    print(
        "error:",
        first.error,
    )

    print()
    print(
        "conversion_stdout:",
        first.conversion_stdout,
    )

    print(
        "conversion_stderr:",
        first.conversion_stderr,
    )

    print()
    print("=" * 100)
    print("PAGE VERIFICATION")
    print("=" * 100)

    verified_pages = 0

    for page in first.pages:
        print()
        print("-" * 100)

        print(
            "page:",
            page.page_number,
        )

        print(
            "status:",
            page.status,
        )

        print(
            "render_path:",
            page.render_path,
        )

        print(
            "dpi:",
            page.dpi,
        )

        print(
            "dimensions:",
            page.width,
            "x",
            page.height,
        )

        print(
            "file_size:",
            page.file_size,
        )

        print(
            "error:",
            page.error,
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

        if not absolute_path.exists():
            continue

        try:
            with Image.open(
                absolute_path
            ) as image:
                image.verify()

            print(
                "image_verify: OK"
            )

            verified_pages += 1

        except Exception as error:
            print(
                "image_verify: FAILED"
            )

            print(
                "verify_error:",
                error,
            )

    print()
    print("=" * 100)
    print("FIRST RENDER SUMMARY")
    print("=" * 100)

    print(
        "verified_pages:",
        verified_pages,
    )

    print()
    print("=" * 100)
    print("SECOND RENDER - IDEMPOTENCY")
    print("=" * 100)

    second = service.render_document(
        document_id=document.id,
        path=source_path,
        content_type=(
            document.content_type
        ),
        original_filename=(
            document.original_filename
        ),
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
        "failed_count:",
        second.failed_count,
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
        first.status == "rendered"
        and first.page_count == 21
        and first.rendered_count == 21
        and first.failed_count == 0
        and verified_pages == 21
        and second.status == "existing"
        and second.page_count == 21
        and second.rendered_count == 0
        and second.existing_count == 21
        and second.failed_count == 0
    ):
        print(
            "OFFICE RENDER SERVICE TEST: OK"
        )

    else:
        print(
            "OFFICE RENDER SERVICE TEST: "
            "CHECK RESULTS"
        )

finally:
    db.close()