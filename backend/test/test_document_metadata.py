from pathlib import Path
from pprint import pprint

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_metadata_service import (
    DocumentMetadataService,
)


DOCUMENT_IDS = [
    37,    # PDF - rzut fundamentów
    52,    # DOCX
    184,   # ODT
    2815,  # XLSX
    1608,  # PNG
]


db = SessionLocal()
service = DocumentMetadataService()

try:
    documents = (
        db.query(Document)
        .filter(
            Document.id.in_(DOCUMENT_IDS)
        )
        .order_by(
            Document.id.asc()
        )
        .all()
    )

    for document in documents:
        print()
        print("=" * 100)
        print(
            "DOCUMENT:",
            document.id,
        )
        print("=" * 100)

        print(
            "filename:",
            document.original_filename,
        )

        print(
            "content_type:",
            document.content_type,
        )

        print(
            "file_size:",
            document.file_size,
        )

        print(
            "metadata_status_in_db:",
            document.metadata_status,
        )

        path = (
            Path(settings.data_dir)
            / document.storage_path
        )

        print(
            "path:",
            path,
        )

        print(
            "path_exists:",
            path.exists(),
        )

        result = service.extract(
            path=path,
            content_type=document.content_type,
            original_filename=document.original_filename,
        )

        print()
        print(
            "RESULT STATUS:",
            result.status,
        )

        print(
            "ERROR:",
            result.error,
        )

        print()
        print("--- NORMALIZED METADATA ---")

        if result.normalized_metadata:
            pprint(
                result.normalized_metadata,
                sort_dicts=True,
                width=120,
            )
        else:
            print("[NONE]")

        print()
        print("--- RAW METADATA ---")

        if result.raw_metadata:
            pprint(
                result.raw_metadata,
                sort_dicts=True,
                width=120,
            )
        else:
            print("[NONE]")

finally:
    db.close()