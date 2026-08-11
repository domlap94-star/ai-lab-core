from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_extraction_service import (
    DocumentExtractionService,
)

db = SessionLocal()
service = DocumentExtractionService()

document_ids = [
    52,    # DOCX
    1608,  # IMAGE
    184,   # ODT
    4812,  # PDF
    2815,  # XLSX
]

try:
    documents = (
        db.query(Document)
        .filter(Document.id.in_(document_ids))
        .order_by(Document.id.asc())
        .all()
    )

    for document in documents:
        print()
        print("=" * 80)
        print(f"DOCUMENT {document.id}")
        print("=" * 80)

        path = Path(settings.data_dir) / document.storage_path

        result = service.extract(
            path=path,
            content_type=document.content_type,
            original_filename=document.original_filename,
        )

        print("filename:", document.original_filename)
        print("content_type:", document.content_type)
        print("path:", path)
        print("path_exists:", path.exists())
        print("status:", result.status)
        print("extractor:", result.extractor)
        print("characters:", result.character_count)
        print("error:", result.error)

        if result.text:
            preview = (
                result.text[:1000]
                .replace("\r", " ")
                .replace("\n", " ")
            )

            print("preview:")
            print(preview)
        else:
            print("preview: [NO TEXT]")

finally:
    db.close()
