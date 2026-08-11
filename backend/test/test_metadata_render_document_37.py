from pathlib import Path
from pprint import pprint

from app.core.config import settings
from app.database.session import SessionLocal
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_metadata_service import (
    DocumentMetadataService,
)
from app.services.document_page_render_service import (
    DocumentPageRenderService,
)


DOCUMENT_ID = 37
RENDER_DPI = 150


db = SessionLocal()

repository = DocumentRepository(
    db
)

metadata_service = (
    DocumentMetadataService()
)

render_service = (
    DocumentPageRenderService()
)


try:
    document = repository.get(
        DOCUMENT_ID
    )

    if document is None:
        raise RuntimeError(
            f"Document {DOCUMENT_ID} not found."
        )

    if not document.storage_path:
        raise RuntimeError(
            "Document has no storage_path."
        )

    source_path = (
        Path(settings.data_dir)
        / document.storage_path
    )

    print()
    print("=" * 80)
    print("SOURCE")
    print("=" * 80)

    print(
        "document_id:",
        document.id,
    )

    print(
        "filename:",
        document.original_filename,
    )

    print(
        "source_path:",
        source_path,
    )

    print(
        "exists:",
        source_path.exists(),
    )

    print()
    print("=" * 80)
    print("METADATA")
    print("=" * 80)

    metadata_result = (
        metadata_service.extract(
            path=source_path,
            content_type=(
                document.content_type
            ),
            original_filename=(
                document.original_filename
            ),
        )
    )

    print(
        "status:",
        metadata_result.status,
    )

    print(
        "error:",
        metadata_result.error,
    )

    print()
    print(
        "normalized_metadata:"
    )

    pprint(
        metadata_result.normalized_metadata,
        sort_dicts=True,
        width=120,
    )

    repository.update_metadata(
        document=document,
        status=metadata_result.status,
        raw_metadata=(
            metadata_result.raw_metadata
        ),
        normalized_metadata=(
            metadata_result
            .normalized_metadata
        ),
        error=(
            metadata_result.error
        ),
    )

    repository.commit()

    print()
    print(
        "METADATA DATABASE SAVE: OK"
    )

    print()
    print("=" * 80)
    print("RENDER")
    print("=" * 80)

    render_result = (
        render_service.render_pdf(
            document_id=DOCUMENT_ID,
            path=source_path,
            dpi=RENDER_DPI,
            force=True,
        )
    )

    print(
        "status:",
        render_result.status,
    )

    print(
        "page_count:",
        render_result.page_count,
    )

    print(
        "error:",
        render_result.error,
    )

    for page in render_result.pages:
        print()
        print("-" * 80)

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
            "error:",
            page.error,
        )

        if (
            page.render_path
            and page.width is not None
            and page.height is not None
            and page.status
            in {
                "rendered",
                "existing",
            }
        ):
            repository.update_page_render(
                document_id=(
                    DOCUMENT_ID
                ),
                page_number=(
                    page.page_number
                ),
                render_path=(
                    page.render_path
                ),
                render_dpi=(
                    page.dpi
                ),
                width=(
                    page.width
                ),
                height=(
                    page.height
                ),
            )

    repository.commit()

    print()
    print(
        "RENDER DATABASE SAVE: OK"
    )

finally:
    db.close()