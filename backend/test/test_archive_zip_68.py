from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_archive_service import (
    DocumentArchiveService,
)


DOCUMENT_ID = 68


db = SessionLocal()

try:
    document = (
        db.query(Document)
        .filter(
            Document.id == DOCUMENT_ID
        )
        .first()
    )

    if document is None:
        raise RuntimeError(
            f"Document {DOCUMENT_ID} not found."
        )

    source_path = (
        Path(settings.data_dir)
        / document.storage_path
    )

    output_dir = (
        Path(settings.data_dir)
        / "archive-extracted"
        / str(document.id)
    )

    print()
    print("document_id:", document.id)
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
        "source_exists:",
        source_path.exists(),
    )
    print(
        "output_dir:",
        output_dir,
    )

    service = DocumentArchiveService()

    service.clear_output_directory(
        output_dir
    )

    result = service.extract_zip(
        source_path=source_path,
        output_dir=output_dir,
    )

    print()
    print("status:", result.status)
    print(
        "archive_type:",
        result.archive_type,
    )
    print(
        "member_count:",
        result.member_count,
    )
    print(
        "extracted_count:",
        result.extracted_count,
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
        "total_extracted_size:",
        result.total_extracted_size,
    )
    print(
        "error:",
        result.error,
    )

    print()
    print("--- MEMBERS ---")

    for member in result.members:
        print()
        print(
            "archive_name:",
            member.archive_name,
        )
        print(
            "safe_name:",
            member.safe_name,
        )
        print(
            "relative_path:",
            member.relative_path,
        )
        print(
            "content_type:",
            member.content_type,
        )
        print(
            "file_size:",
            member.file_size,
        )
        print(
            "compressed_size:",
            member.compressed_size,
        )
        print(
            "checksum_sha256:",
            member.checksum_sha256,
        )
        print(
            "status:",
            member.status,
        )
        print(
            "error:",
            member.error,
        )

finally:
    db.close()