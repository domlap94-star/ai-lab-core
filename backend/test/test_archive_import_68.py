from __future__ import annotations

from app.database.session import SessionLocal
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_archive_import_service import (
    DocumentArchiveImportService,
)


PARENT_DOCUMENT_ID = 68


db = SessionLocal()

try:
    service = DocumentArchiveImportService(
        db
    )

    repository = DocumentRepository(
        db
    )

    print()
    print("=" * 100)
    print("FIRST IMPORT")
    print("=" * 100)

    result = service.import_zip(
        parent_document_id=(
            PARENT_DOCUMENT_ID
        ),
        cleanup_extracted=True,
    )

    print(
        "status:",
        result.status,
    )

    print(
        "archive_type:",
        result.archive_type,
    )

    print(
        "archive_member_count:",
        result.archive_member_count,
    )

    print(
        "imported_count:",
        result.imported_count,
    )

    print(
        "existing_count:",
        result.existing_count,
    )

    print(
        "skipped_count:",
        result.skipped_count,
    )

    print(
        "failed_count:",
        result.failed_count,
    )

    print(
        "error:",
        result.error,
    )

    print()
    print("--- CHILD RESULTS ---")

    for child in result.children:
        print()

        print(
            "document_id:",
            child.document_id,
        )

        print(
            "archive_member_path:",
            child.archive_member_path,
        )

        print(
            "original_filename:",
            child.original_filename,
        )

        print(
            "status:",
            child.status,
        )

        print(
            "created:",
            child.created,
        )

        print(
            "checksum:",
            child.checksum_sha256,
        )

        print(
            "error:",
            child.error,
        )

    print()
    print("=" * 100)
    print("DATABASE CHILDREN")
    print("=" * 100)

    children = (
        repository.get_archive_children(
            PARENT_DOCUMENT_ID
        )
    )

    print(
        "count:",
        len(children),
    )

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
            "parent_document_id:",
            child.parent_document_id,
        )

        print(
            "archive_member_path:",
            child.archive_member_path,
        )

        print(
            "archive_depth:",
            child.archive_depth,
        )

        print(
            "source_type:",
            child.source_type,
        )

        print(
            "candidate_id:",
            child.candidate_id,
        )

        print(
            "client_id:",
            child.client_id,
        )

        print(
            "match_status:",
            child.match_status,
        )

        print(
            "match_method:",
            child.match_method,
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

        print(
            "checksum:",
            child.checksum_sha256,
        )

    print()
    print("=" * 100)
    print("SECOND IMPORT - IDEMPOTENCY TEST")
    print("=" * 100)

    second_result = service.import_zip(
        parent_document_id=(
            PARENT_DOCUMENT_ID
        ),
        cleanup_extracted=True,
    )

    print(
        "status:",
        second_result.status,
    )

    print(
        "imported_count:",
        second_result.imported_count,
    )

    print(
        "existing_count:",
        second_result.existing_count,
    )

    print(
        "skipped_count:",
        second_result.skipped_count,
    )

    print(
        "failed_count:",
        second_result.failed_count,
    )

    final_children = (
        repository.get_archive_children(
            PARENT_DOCUMENT_ID
        )
    )

    print()
    print(
        "final_database_children:",
        len(final_children),
    )

finally:
    db.close()