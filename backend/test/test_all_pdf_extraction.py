from pathlib import Path
from time import perf_counter

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_extraction_service import (
    DocumentExtractionService,
)

db = SessionLocal()
service = DocumentExtractionService()

try:
    documents = (
        db.query(Document)
        .filter(
            Document.storage_path.isnot(None),
            Document.content_type == "application/pdf",
        )
        .order_by(Document.id.asc())
        .all()
    )

    counters = {
        "extracted": 0,
        "requires_ocr": 0,
        "unsupported": 0,
        "failed": 0,
    }

    failed_documents = []
    ocr_documents = []

    total_characters = 0
    started = perf_counter()

    print()
    print("ALL PDF EXTRACTION DRY RUN")
    print("=" * 80)
    print("documents:", len(documents))
    print()

    for index, document in enumerate(documents, start=1):
        path = Path(settings.data_dir) / document.storage_path

        result = service.extract(
            path=path,
            content_type=document.content_type,
            original_filename=document.original_filename,
        )

        counters[result.status] += 1
        total_characters += result.character_count

        if result.status == "failed":
            try:
                with path.open("rb") as file:
                    header = repr(file.read(16))
            except Exception as error:
                header = f"READ ERROR: {error}"

            failed_documents.append(
                {
                    "id": document.id,
                    "filename": document.original_filename,
                    "size": document.file_size,
                    "header": header,
                    "error": result.error,
                }
            )

        elif result.status == "requires_ocr":
            ocr_documents.append(
                {
                    "id": document.id,
                    "filename": document.original_filename,
                    "characters": result.character_count,
                }
            )

        if index % 100 == 0 or index == len(documents):
            elapsed = perf_counter() - started

            print(
                f"{index}/{len(documents)} | "
                f"extracted={counters['extracted']} | "
                f"ocr={counters['requires_ocr']} | "
                f"failed={counters['failed']} | "
                f"time={elapsed:.1f}s"
            )

    elapsed = perf_counter() - started

    print()
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    for status, count in counters.items():
        percentage = (
            count / len(documents) * 100
            if documents
            else 0
        )

        print(
            f"{status}: {count} "
            f"({percentage:.2f}%)"
        )

    print()
    print("total_characters:", total_characters)
    print("elapsed_seconds:", round(elapsed, 2))

    if documents:
        print(
            "average_seconds_per_document:",
            round(elapsed / len(documents), 4),
        )

    print()
    print("=" * 80)
    print("FAILED DOCUMENTS")
    print("=" * 80)

    if not failed_documents:
        print("NONE")
    else:
        for item in failed_documents:
            print()
            print("ID:", item["id"])
            print("FILE:", item["filename"])
            print("SIZE:", item["size"])
            print("HEADER:", item["header"])
            print("ERROR:", item["error"])

    print()
    print("=" * 80)
    print("FIRST 30 OCR CANDIDATES")
    print("=" * 80)

    for item in ocr_documents[:30]:
        print(
            item["id"],
            "|",
            item["filename"],
            "| existing chars:",
            item["characters"],
        )

finally:
    db.close()
