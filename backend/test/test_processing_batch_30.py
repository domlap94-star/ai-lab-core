from __future__ import annotations

import time
from collections import Counter

from sqlalchemy import func

from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.document_processing_service import (
    DocumentProcessingService,
)


BATCH_SIZE = 30


def shorten(value: str | None, length: int = 70) -> str:
    if not value:
        return ""

    value = value.replace("\r", " ").replace("\n", " ")

    if len(value) <= length:
        return value

    return value[: length - 3] + "..."


db = SessionLocal()

try:
    service = DocumentProcessingService(db)

    documents = (
        db.query(Document)
        .order_by(
            func.random()
        )
        .limit(BATCH_SIZE)
        .all()
    )

    print()
    print("=" * 120)
    print("DOCUMENT PROCESSING BATCH TEST")
    print("=" * 120)

    print(
        "documents:",
        len(documents),
    )

    print()

    results = []
    start_batch = time.perf_counter()

    for index, document in enumerate(
        documents,
        start=1,
    ):
        print()
        print("-" * 120)

        print(
            f"[{index}/{len(documents)}] "
            f"ID={document.id} "
            f"FILE={shorten(document.original_filename)}"
        )

        print(
            "content_type:",
            document.content_type,
        )

        print(
            "file_size:",
            document.file_size,
        )

        start = time.perf_counter()

        try:
            result = service.process_document(
                document_id=document.id,
                ocr_dpi=150,
                render_dpi=150,
                force=True,
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            pages = (
                db.query(DocumentPage)
                .filter(
                    DocumentPage.document_id
                    == document.id
                )
                .order_by(
                    DocumentPage.page_number.asc()
                )
                .all()
            )

            ocr_confidences = [
                page.ocr_confidence
                for page in pages
                if page.ocr_confidence is not None
            ]

            average_confidence = None

            if ocr_confidences:
                average_confidence = (
                    sum(ocr_confidences)
                    / len(ocr_confidences)
                )

            rendered_pages = sum(
                1
                for page in pages
                if page.render_path
            )

            failed_pages = sum(
                1
                for page in pages
                if page.processing_status
                == "failed"
            )

            print(
                "status:",
                result.status,
            )

            print(
                "pages:",
                result.page_count,
            )

            print(
                "native_chars:",
                result.native_character_count,
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
                "metadata:",
                result.metadata_status,
            )

            print(
                "render:",
                result.render_status,
            )

            print(
                "rendered_pages:",
                rendered_pages,
            )

            print(
                "failed_pages:",
                failed_pages,
            )

            print(
                "avg_ocr_confidence:",
                (
                    round(
                        average_confidence,
                        2,
                    )
                    if average_confidence
                    is not None
                    else None
                ),
            )

            print(
                "elapsed:",
                round(
                    elapsed,
                    2,
                ),
                "s",
            )

            print(
                "error:",
                result.error,
            )

            results.append(
                {
                    "id": document.id,
                    "filename": document.original_filename,
                    "content_type": document.content_type,
                    "status": result.status,
                    "pages": result.page_count,
                    "native_chars": (
                        result.native_character_count
                    ),
                    "ocr_chars": (
                        result.ocr_character_count
                    ),
                    "combined_chars": (
                        result.combined_character_count
                    ),
                    "metadata_status": (
                        result.metadata_status
                    ),
                    "render_status": (
                        result.render_status
                    ),
                    "rendered_pages": (
                        rendered_pages
                    ),
                    "failed_pages": (
                        failed_pages
                    ),
                    "ocr_confidence": (
                        average_confidence
                    ),
                    "elapsed": elapsed,
                    "error": result.error,
                }
            )

        except Exception as exc:
            elapsed = (
                time.perf_counter()
                - start
            )

            db.rollback()

            print(
                "EXCEPTION:",
                type(exc).__name__,
                str(exc),
            )

            print(
                "elapsed:",
                round(
                    elapsed,
                    2,
                ),
                "s",
            )

            results.append(
                {
                    "id": document.id,
                    "filename": document.original_filename,
                    "content_type": document.content_type,
                    "status": "exception",
                    "pages": 0,
                    "native_chars": 0,
                    "ocr_chars": 0,
                    "combined_chars": 0,
                    "metadata_status": None,
                    "render_status": None,
                    "rendered_pages": 0,
                    "failed_pages": 0,
                    "ocr_confidence": None,
                    "elapsed": elapsed,
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    total_elapsed = (
        time.perf_counter()
        - start_batch
    )

    print()
    print()
    print("=" * 120)
    print("SUMMARY")
    print("=" * 120)

    status_counts = Counter(
        result["status"]
        for result in results
    )

    metadata_counts = Counter(
        result["metadata_status"]
        for result in results
    )

    render_counts = Counter(
        result["render_status"]
        for result in results
    )

    print()
    print("STATUS COUNTS")

    for status, count in sorted(
        status_counts.items(),
        key=lambda item: str(item[0]),
    ):
        print(
            status,
            ":",
            count,
        )

    print()
    print("METADATA COUNTS")

    for status, count in sorted(
        metadata_counts.items(),
        key=lambda item: str(item[0]),
    ):
        print(
            status,
            ":",
            count,
        )

    print()
    print("RENDER COUNTS")

    for status, count in sorted(
        render_counts.items(),
        key=lambda item: str(item[0]),
    ):
        print(
            status,
            ":",
            count,
        )

    total_pages = sum(
        result["pages"]
        for result in results
    )

    total_native = sum(
        result["native_chars"]
        for result in results
    )

    total_ocr = sum(
        result["ocr_chars"]
        for result in results
    )

    total_combined = sum(
        result["combined_chars"]
        for result in results
    )

    total_rendered_pages = sum(
        result["rendered_pages"]
        for result in results
    )

    total_failed_pages = sum(
        result["failed_pages"]
        for result in results
    )

    print()
    print(
        "documents:",
        len(results),
    )

    print(
        "pages:",
        total_pages,
    )

    print(
        "rendered_pages:",
        total_rendered_pages,
    )

    print(
        "failed_pages:",
        total_failed_pages,
    )

    print(
        "native_characters:",
        total_native,
    )

    print(
        "ocr_characters:",
        total_ocr,
    )

    print(
        "combined_characters:",
        total_combined,
    )

    print(
        "elapsed_seconds:",
        round(
            total_elapsed,
            2,
        ),
    )

    if results:
        print(
            "average_seconds_per_document:",
            round(
                total_elapsed
                / len(results),
                2,
            ),
        )

    print()
    print("=" * 120)
    print("PROBLEMS")
    print("=" * 120)

    problems = [
        result
        for result in results
        if (
            result["status"]
            not in (
                "processed",
                "already_processed",
            )
            or result["error"]
            is not None
            or result["failed_pages"] > 0
        )
    ]

    if not problems:
        print(
            "NO PROCESSING PROBLEMS"
        )

    else:
        for result in problems:
            print()
            print(
                "ID:",
                result["id"],
            )

            print(
                "FILE:",
                result["filename"],
            )

            print(
                "TYPE:",
                result["content_type"],
            )

            print(
                "STATUS:",
                result["status"],
            )

            print(
                "FAILED PAGES:",
                result["failed_pages"],
            )

            print(
                "ERROR:",
                result["error"],
            )

    print()
    print("=" * 120)
    print("LOW OCR CONFIDENCE")
    print("=" * 120)

    low_confidence = [
        result
        for result in results
        if (
            result["ocr_confidence"]
            is not None
            and result["ocr_confidence"]
            < 60
        )
    ]

    if not low_confidence:
        print(
            "NO DOCUMENTS BELOW 60%"
        )

    else:
        for result in low_confidence:
            print(
                "ID:",
                result["id"],
                "| confidence:",
                round(
                    result["ocr_confidence"],
                    2,
                ),
                "| file:",
                result["filename"],
            )

finally:
    db.close()