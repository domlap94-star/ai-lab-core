from __future__ import annotations

from app.database.session import SessionLocal
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_service import DocumentProcessingService


DOCUMENT_IDS = [
    3277,
    2879,
]


def main() -> None:
    db = SessionLocal()

    try:
        repository = DocumentRepository(
            db
        )

        service = DocumentProcessingService(
            db
        )

        failed = 0

        print()
        print("=" * 100)
        print("HEIC NAN METADATA REGRESSION")
        print("=" * 100)

        for document_id in DOCUMENT_IDS:
            print()
            print("=" * 100)
            print(
                "DOCUMENT:",
                document_id,
            )
            print("=" * 100)

            document = repository.get(
                document_id
            )

            if document is None:
                print(
                    "DOCUMENT NOT FOUND"
                )

                failed += 1
                continue

            print(
                "filename:",
                document.original_filename,
            )

            print(
                "content_type:",
                document.content_type,
            )

            print(
                "processing_status_before:",
                document.processing_status,
            )

            print(
                "metadata_status_before:",
                document.metadata_status,
            )

            result = service.process_document(
                document_id=document_id,
                ocr_dpi=150,
                render_dpi=150,
                force=True,
            )

            document = repository.get(
                document_id
            )

            pages = repository.get_pages(
                document_id
            )

            print()
            print("--- PROCESSING RESULT ---")

            print(
                "result_status:",
                result.status,
            )

            print(
                "page_count:",
                result.page_count,
            )

            print(
                "ocr_chars:",
                result.ocr_character_count,
            )

            print(
                "combined_chars:",
                result.combined_character_count,
            )

            print(
                "result_error:",
                result.error,
            )

            print()
            print("--- DATABASE ---")

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
                "metadata_error:",
                document.metadata_error,
            )

            print(
                "metadata_normalized:",
                document.metadata_normalized,
            )

            print(
                "pages:",
                len(pages),
            )

            print(
                "failed_pages:",
                sum(
                    1
                    for page in pages
                    if page.processing_status
                    == "failed"
                ),
            )

            if (
                result.status != "processed"
                or document.processing_status
                != "processed"
                or document.metadata_status
                != "processed"
                or document.processing_error
                is not None
                or document.metadata_error
                is not None
            ):
                failed += 1

                print()
                print(
                    "DOCUMENT RESULT: FAILED"
                )

            else:
                print()
                print(
                    "DOCUMENT RESULT: OK"
                )

        print()
        print("=" * 100)
        print("FINAL")
        print("=" * 100)

        print(
            "tested:",
            len(DOCUMENT_IDS),
        )

        print(
            "failed:",
            failed,
        )

        if failed == 0:
            print(
                "HEIC NAN METADATA FIX: OK"
            )
        else:
            print(
                "HEIC NAN METADATA FIX: CHECK RESULTS"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()