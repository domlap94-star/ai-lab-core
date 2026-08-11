from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
)


PARENT_DOCUMENT_ID = 68


db = SessionLocal()

try:
    repository = DocumentRepository(
        db
    )

    processing_service = (
        DocumentProcessingService(
            db
        )
    )

    children = (
        repository.get_archive_children(
            PARENT_DOCUMENT_ID
        )
    )

    print()
    print("=" * 100)
    print("ARCHIVE CHILDREN")
    print("=" * 100)

    print(
        "children:",
        len(children),
    )

    pdf_children = []

    for child in children:
        print()

        print(
            "id:",
            child.id,
        )

        print(
            "filename:",
            child.original_filename,
        )

        print(
            "content_type:",
            child.content_type,
        )

        print(
            "archive_member_path:",
            child.archive_member_path,
        )

        print(
            "processing_status:",
            child.processing_status,
        )

        print(
            "metadata_status:",
            child.metadata_status,
        )

        print(
            "storage_path:",
            child.storage_path,
        )

        path = (
            Path(settings.data_dir)
            / child.storage_path
        )

        print(
            "file_exists:",
            path.exists(),
        )

        if (
            child.content_type
            == "application/pdf"
        ):
            pdf_children.append(
                child
            )

    print()
    print("=" * 100)
    print("PROCESS PDF CHILDREN")
    print("=" * 100)

    for index, child in enumerate(
        pdf_children,
        start=1,
    ):
        print()
        print("-" * 100)

        print(
            f"[{index}/{len(pdf_children)}] "
            f"ID={child.id}"
        )

        print(
            "filename:",
            child.original_filename,
        )

        result = (
            processing_service
            .process_document(
                document_id=child.id,
                ocr_dpi=150,
                render_dpi=150,
                force=True,
            )
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
    print("FINAL STATE")
    print("=" * 100)

    refreshed_children = (
        repository.get_archive_children(
            PARENT_DOCUMENT_ID
        )
    )

    for child in refreshed_children:
        print()
        print(
            "id:",
            child.id,
            "| file:",
            child.original_filename,
            "| type:",
            child.content_type,
            "| processing:",
            child.processing_status,
            "| metadata:",
            child.metadata_status,
            "| text_chars:",
            len(
                child.extracted_text
                or ""
            ),
        )

finally:
    db.close()