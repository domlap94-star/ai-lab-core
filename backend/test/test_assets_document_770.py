from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.repositories.document_asset_repository import (
    DocumentAssetRepository,
)
from app.services.document_asset_extraction_service import (
    DocumentAssetExtractionService,
)


DOCUMENT_ID = 770


db = SessionLocal()

try:
    service = (
        DocumentAssetExtractionService(
            db
        )
    )

    repository = (
        DocumentAssetRepository(
            db
        )
    )

    print()
    print("=" * 100)
    print("FIRST EXTRACTION")
    print("=" * 100)

    result = (
        service.extract_document_assets(
            document_id=DOCUMENT_ID,
            force=True,
        )
    )

    print(
        "status:",
        result.status,
    )

    print(
        "source_format:",
        result.source_format,
    )

    print(
        "discovered_count:",
        result.discovered_count,
    )

    print(
        "extracted_count:",
        result.extracted_count,
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
    print("=" * 100)
    print("ASSETS")
    print("=" * 100)

    assets = (
        repository.get_for_document(
            DOCUMENT_ID
        )
    )

    print(
        "assets_in_db:",
        len(assets),
    )

    for asset in assets:
        print()
        print("-" * 100)

        print(
            "id:",
            asset.id,
        )

        print(
            "asset_index:",
            asset.asset_index,
        )

        print(
            "original_name:",
            asset.original_name,
        )

        print(
            "container_name:",
            asset.container_name,
        )

        print(
            "mime_type:",
            asset.mime_type,
        )

        print(
            "dimensions:",
            asset.width,
            "x",
            asset.height,
        )

        print(
            "file_size:",
            asset.file_size,
        )

        print(
            "checksum:",
            asset.checksum_sha256,
        )

        print(
            "extraction_method:",
            asset.extraction_method,
        )

        print(
            "processing_status:",
            asset.processing_status,
        )

        print(
            "storage_path:",
            asset.storage_path,
        )

        absolute_path = (
            Path(settings.data_dir)
            / asset.storage_path
        )

        print(
            "file_exists:",
            absolute_path.exists(),
        )

    print()
    print("=" * 100)
    print("SECOND EXTRACTION - IDEMPOTENCY")
    print("=" * 100)

    second = (
        service.extract_document_assets(
            document_id=DOCUMENT_ID,
            force=False,
        )
    )

    print(
        "status:",
        second.status,
    )

    print(
        "discovered_count:",
        second.discovered_count,
    )

    print(
        "extracted_count:",
        second.extracted_count,
    )

    print(
        "existing_count:",
        second.existing_count,
    )

    print(
        "skipped_count:",
        second.skipped_count,
    )

    print(
        "failed_count:",
        second.failed_count,
    )

    final_assets = (
        repository.get_for_document(
            DOCUMENT_ID
        )
    )

    print(
        "final_assets_in_db:",
        len(final_assets),
    )

finally:
    db.close()