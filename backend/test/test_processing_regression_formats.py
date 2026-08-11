from __future__ import annotations

from dataclasses import dataclass

from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
)


@dataclass(frozen=True)
class RegressionCase:
    document_id: int
    label: str
    expected_min_pages: int | None = None
    expected_text: bool | None = None


CASES = [
    RegressionCase(
        document_id=37,
        label="PDF - rzut fundamentow",
        expected_min_pages=1,
        expected_text=True,
    ),
    RegressionCase(
        document_id=1608,
        label="IMAGE - tiny PNG",
        expected_min_pages=1,
        expected_text=False,
    ),
    RegressionCase(
        document_id=52,
        label="DOCX - umowa",
        expected_min_pages=1,
        expected_text=True,
    ),
    RegressionCase(
        document_id=184,
        label="ODT",
        expected_min_pages=1,
        expected_text=True,
    ),
    RegressionCase(
        document_id=5915,
        label="XLS - CPT data",
        expected_min_pages=None,
        expected_text=True,
    ),
    RegressionCase(
        document_id=2815,
        label="XLSX",
        expected_min_pages=None,
        expected_text=True,
    ),
]


db = SessionLocal()

try:
    repository = DocumentRepository(
        db
    )

    service = DocumentProcessingService(
        db
    )

    passed = 0
    warnings = 0
    failed = 0

    print()
    print("=" * 120)
    print("DOCUMENT PROCESSING REGRESSION")
    print("=" * 120)

    for case in CASES:
        print()
        print("=" * 120)
        print(
            f"DOCUMENT {case.document_id} "
            f"- {case.label}"
        )
        print("=" * 120)

        document = repository.get(
            case.document_id
        )

        if document is None:
            print(
                "RESULT: SKIPPED - "
                "document not found"
            )

            warnings += 1
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
            "processing_before:",
            document.processing_status,
        )

        result = service.process_document(
            document_id=case.document_id,
            ocr_dpi=150,
            render_dpi=150,
            force=True,
        )

        document = repository.get(
            case.document_id
        )

        pages = repository.get_pages(
            case.document_id
        )

        assets = (
            db.query(DocumentAsset)
            .filter(
                DocumentAsset.document_id
                == case.document_id
            )
            .all()
        )

        print()
        print("--- RESULT ---")

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
            "text_chars:",
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
            "page_processed:",
            sum(
                1
                for page in pages
                if page.processing_status
                == "processed"
            ),
        )

        print(
            "page_no_text:",
            sum(
                1
                for page in pages
                if page.processing_status
                == "no_text"
            ),
        )

        print(
            "page_failed:",
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
            "assets:",
            len(assets),
        )

        case_errors: list[str] = []

        if result.status not in {
            "processed",
            "already_processed",
        }:
            case_errors.append(
                f"unexpected status: "
                f"{result.status}"
            )

        if (
            document.processing_status
            != "processed"
        ):
            case_errors.append(
                "document not processed"
            )

        if (
            case.expected_min_pages
            is not None
            and len(pages)
            < case.expected_min_pages
        ):
            case_errors.append(
                f"expected at least "
                f"{case.expected_min_pages} "
                f"page(s), got {len(pages)}"
            )

        text_length = len(
            document.extracted_text
            or ""
        )

        if (
            case.expected_text is True
            and text_length == 0
        ):
            case_errors.append(
                "expected extracted text"
            )

        if (
            case.expected_text is False
            and text_length > 0
        ):
            print(
                "NOTE: text was extracted "
                "although test did not require it"
            )

        failed_pages = sum(
            1
            for page in pages
            if page.processing_status
            == "failed"
        )

        if failed_pages > 0:
            case_errors.append(
                f"{failed_pages} failed page(s)"
            )

        if case_errors:
            print()
            print(
                "CASE RESULT: FAILED"
            )

            for error in case_errors:
                print(
                    " -",
                    error,
                )

            failed += 1

        else:
            print()
            print(
                "CASE RESULT: OK"
            )

            passed += 1

    print()
    print("=" * 120)
    print("SUMMARY")
    print("=" * 120)

    print(
        "passed:",
        passed,
    )

    print(
        "warnings:",
        warnings,
    )

    print(
        "failed:",
        failed,
    )

    print(
        "tested:",
        len(CASES),
    )

    if failed == 0:
        print(
            "DOCUMENT PROCESSING REGRESSION: OK"
        )
    else:
        print(
            "DOCUMENT PROCESSING REGRESSION: "
            "CHECK RESULTS"
        )

finally:
    db.close()