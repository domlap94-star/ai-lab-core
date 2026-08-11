from __future__ import annotations

import time
from collections import Counter

from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_processing_service import (
    DocumentProcessingService,
)


db = SessionLocal()

try:
    service = DocumentProcessingService(
        db
    )

    documents = (
        db.query(Document)
        .filter(
            Document.content_type
            == "message/rfc822"
        )
        .order_by(
            Document.id.asc()
        )
        .all()
    )

    print()
    print("=" * 110)
    print("RFC822 FULL PIPELINE TEST")
    print("=" * 110)

    print(
        "documents:",
        len(documents),
    )

    results = []

    batch_start = time.perf_counter()

    for index, document in enumerate(
        documents,
        start=1,
    ):
        print()
        print("-" * 110)

        print(
            f"[{index}/{len(documents)}] "
            f"ID={document.id}"
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

            refreshed = (
                db.query(Document)
                .filter(
                    Document.id
                    == document.id
                )
                .first()
            )

            metadata = (
                refreshed.metadata_normalized
                or {}
            )

            print(
                "status:",
                result.status,
            )

            print(
                "processing_status:",
                refreshed.processing_status,
            )

            print(
                "metadata_status:",
                refreshed.metadata_status,
            )

            print(
                "text_chars:",
                len(
                    refreshed.extracted_text
                    or ""
                ),
            )

            print(
                "subject:",
                metadata.get(
                    "subject"
                ),
            )

            print(
                "from:",
                metadata.get(
                    "from"
                ),
            )

            print(
                "to:",
                metadata.get(
                    "to"
                ),
            )

            print(
                "attachments:",
                metadata.get(
                    "attachment_count"
                ),
            )

            print(
                "error:",
                result.error,
            )

            print(
                "elapsed:",
                round(
                    elapsed,
                    3,
                ),
                "s",
            )

            results.append(
                {
                    "id": document.id,
                    "status": result.status,
                    "processing_status": (
                        refreshed.processing_status
                    ),
                    "metadata_status": (
                        refreshed.metadata_status
                    ),
                    "text_chars": len(
                        refreshed.extracted_text
                        or ""
                    ),
                    "error": result.error,
                    "elapsed": elapsed,
                }
            )

        except Exception as error:
            elapsed = (
                time.perf_counter()
                - start
            )

            db.rollback()

            print(
                "EXCEPTION:",
                type(error).__name__,
                str(error),
            )

            results.append(
                {
                    "id": document.id,
                    "status": "exception",
                    "processing_status": None,
                    "metadata_status": None,
                    "text_chars": 0,
                    "error": (
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                    "elapsed": elapsed,
                }
            )

    total_elapsed = (
        time.perf_counter()
        - batch_start
    )

    print()
    print()
    print("=" * 110)
    print("SUMMARY")
    print("=" * 110)

    processing_counts = Counter(
        item["processing_status"]
        for item in results
    )

    metadata_counts = Counter(
        item["metadata_status"]
        for item in results
    )

    print()
    print("PROCESSING STATUS")

    for key, value in sorted(
        processing_counts.items(),
        key=lambda item: str(
            item[0]
        ),
    ):
        print(
            key,
            ":",
            value,
        )

    print()
    print("METADATA STATUS")

    for key, value in sorted(
        metadata_counts.items(),
        key=lambda item: str(
            item[0]
        ),
    ):
        print(
            key,
            ":",
            value,
        )

    print()
    print(
        "documents:",
        len(results),
    )

    print(
        "total_text_chars:",
        sum(
            item["text_chars"]
            for item in results
        ),
    )

    print(
        "elapsed_seconds:",
        round(
            total_elapsed,
            3,
        ),
    )

    print()
    print("=" * 110)
    print("PROBLEMS")
    print("=" * 110)

    problems = [
        item
        for item in results
        if (
            item["processing_status"]
            != "processed"
            or item["metadata_status"]
            != "processed"
            or item["error"]
            is not None
        )
    ]

    if not problems:
        print(
            "NO RFC822 PROCESSING PROBLEMS"
        )

    else:
        for item in problems:
            print(
                item
            )

finally:
    db.close()