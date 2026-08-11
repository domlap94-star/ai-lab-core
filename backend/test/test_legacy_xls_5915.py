from __future__ import annotations

from pathlib import Path
from pprint import pprint

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_legacy_office_service import (
    DocumentLegacyOfficeService,
)


DOCUMENT_ID = 5915


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

    if not document.storage_path:
        raise RuntimeError(
            "Document has no storage path."
        )

    path = (
        Path(settings.data_dir)
        / document.storage_path
    )

    print()
    print("=" * 100)
    print("SOURCE")
    print("=" * 100)

    print(
        "id:",
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
        "path:",
        path,
    )

    print(
        "exists:",
        path.exists(),
    )

    print()
    print("=" * 100)
    print("LEGACY OFFICE EXTRACTION")
    print("=" * 100)

    service = (
        DocumentLegacyOfficeService()
    )

    result = service.extract(
        path=path,
        content_type=(
            document.content_type
        ),
        original_filename=(
            document.original_filename
        ),
    )

    print(
        "status:",
        result.status,
    )

    print(
        "extractor:",
        result.extractor,
    )

    print(
        "characters:",
        result.character_count,
    )

    print(
        "error:",
        result.error,
    )

    print()
    print(
        "--- NORMALIZED METADATA ---"
    )

    pprint(
        result.normalized_metadata,
        sort_dicts=True,
        width=120,
    )

    print()
    print(
        "--- RAW METADATA ---"
    )

    pprint(
        result.raw_metadata,
        sort_dicts=True,
        width=120,
    )

    print()
    print(
        "--- TEXT PREVIEW ---"
    )

    print(
        (
            result.text
            or "[NO TEXT]"
        )[:3000]
    )

finally:
    db.close()