from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import fitz

from app.database.session import SessionLocal
from app.models.document import Document
from app.services.unified_document_content_service import UnifiedDocumentContentService


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="unified-document-readonly-") as temporary:
        root = Path(temporary)
        path = root / "synthetic-native.pdf"
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "Synthetic public-safe foundation report. Soil bearing and local settlement evidence.",
        )
        pdf.save(path)
        pdf.close()
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        document = Document(
            id=-91001,
            filename=path.name,
            original_filename=path.name,
            content_type="application/pdf",
            file_size=path.stat().st_size,
            storage_path=path.name,
            checksum_sha256=checksum,
            processing_status="stored",
            extracted_text=None,
        )
        db = SessionLocal()
        try:
            result = UnifiedDocumentContentService(db, data_root=root).access(
                document, query="soil settlement"
            )
            print(json.dumps({
                "state": result.state,
                "extractor": result.extractor,
                "characters": result.character_count,
                "pages": [page.page_number for page in result.pages],
                "db_new": len(db.new),
                "db_dirty": len(db.dirty),
                "db_deleted": len(db.deleted),
            }))
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    main()
