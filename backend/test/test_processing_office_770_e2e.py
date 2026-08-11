from __future__ import annotations

from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
)


DOCUMENT_ID = 770


db = SessionLocal()

try:
    repository = DocumentRepository(
        db
    )

    service = DocumentProcessingService(
        db
    )

    document = repository.get(
        DOCUMENT_ID
    )

    if document is None:
        raise RuntimeError(
            f"Document {DOCUMENT_ID} "
            "not found."
        )

    print()
    print("=" * 110)
    print("SOURCE")
    print("=" * 110)

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

    print()
    print("=" * 110)
    print("FORCED END-TO-END PROCESS")
    print("=" * 110)

    result = service.process_document(
        document_id=DOCUMENT_ID,
        ocr_dpi=150,
        render_dpi=150,
        force=True,
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

    document = repository.get(
        DOCUMENT_ID
    )

    pages = repository.get_pages(
        DOCUMENT_ID
    )

    assets = (
        db.query(DocumentAsset)
        .filter(
            DocumentAsset.document_id
            == DOCUMENT_ID
        )
        .order_by(
            DocumentAsset.asset_index.asc()
        )
        .all()
    )

    print()
    print("=" * 110)
    print("DATABASE STATE")
    print("=" * 110)

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
        "document_text_chars:",
        len(
            document.extracted_text
            or ""
        ),
    )

    print(
        "pages:",
        len(pages),
    )

    print(
        "pages_processed:",
        sum(
            1
            for page in pages
            if page.processing_status
            == "processed"
        ),
    )

    print(
        "pages_no_text:",
        sum(
            1
            for page in pages
            if page.processing_status
            == "no_text"
        ),
    )

    print(
        "pages_failed:",
        sum(
            1
            for page in pages
            if page.processing_status
            == "failed"
        ),
    )

    print(
        "pages_with_render:",
        sum(
            1
            for page in pages
            if page.render_path
        ),
    )

    print(
        "ocr_chars:",
        sum(
            len(
                page.ocr_text
                or ""
            )
            for page in pages
        ),
    )

    print(
        "assets:",
        len(assets),
    )

    for asset in assets:
        print(
            "asset:",
            asset.asset_index,
            "|",
            asset.original_name,
            "|",
            asset.mime_type,
            "|",
            asset.width,
            "x",
            asset.height,
            "|",
            asset.processing_status,
        )

    print()
    print("=" * 110)
    print("SECOND PROCESS - IDEMPOTENCY")
    print("=" * 110)

    second = service.process_document(
        document_id=DOCUMENT_ID,
        ocr_dpi=150,
        render_dpi=150,
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
        "native_character_count:",
        second.native_character_count,
    )

    print(
        "ocr_character_count:",
        second.ocr_character_count,
    )

    print(
        "combined_character_count:",
        second.combined_character_count,
    )

    print(
        "render_status:",
        second.render_status,
    )

    print(
        "error:",
        second.error,
    )

    print()
    print("=" * 110)
    print("FINAL RESULT")
    print("=" * 110)

    if (
        result.status == "processed"
        and result.page_count == 21
        and result.native_character_count > 0
        and result.ocr_character_count > 0
        and len(pages) == 21
        and sum(
            1
            for page in pages
            if page.processing_status
            == "failed"
        ) == 0
        and sum(
            1
            for page in pages
            if page.render_path
        ) == 21
        and len(assets) > 0
        and second.status
        == "already_processed"
    ):
        print(
            "OFFICE END-TO-END TEST: OK"
        )

    else:
        print(
            "OFFICE END-TO-END TEST: "
            "CHECK RESULTS"
        )

finally:
    db.close()