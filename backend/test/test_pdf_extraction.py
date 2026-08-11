from pathlib import Path

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
        .limit(30)
        .all()
    )

    counters = {
        "extracted": 0,
        "requires_ocr": 0,
        "unsupported": 0,
        "failed": 0,
    }

    print()
    print("PDF EXTRACTION TEST")
    print("=" * 100)

    for document in documents:
        path = Path(settings.data_dir) / document.storage_path

        result = service.extract(
            path=path,
            content_type=document.content_type,
            original_filename=document.original_filename,
        )

        counters[result.status] += 1

        try:
            with path.open("rb") as file:
                header = file.read(8)
        except Exception as error:
            header = f"ERROR: {error}"

        print()
        print("ID:", document.id)
        print("FILE:", document.original_filename)
        print("SIZE:", document.file_size)
        print("HEADER:", repr(header))
        print("STATUS:", result.status)
        print("EXTRACTOR:", result.extractor)
        print("CHARACTERS:", result.character_count)

        if result.error:
            print("ERROR:", result.error)

        if result.text:
            preview = (
                result.text[:200]
                .replace("\r", " ")
                .replace("\n", " ")
            )
            print("PREVIEW:", preview)

    print()
    print("=" * 100)
    print("SUMMARY")

    for status, count in counters.items():
        print(f"{status}: {count}")

finally:
    db.close()
