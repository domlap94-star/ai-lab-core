from pathlib import Path

import fitz

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document

db = SessionLocal()

try:
    documents = (
        db.query(Document)
        .filter(
            Document.content_type == "application/pdf",
            Document.storage_path.isnot(None),
        )
        .order_by(Document.id.asc())
        .all()
    )

    found = 0

    for document in documents:
        path = (
            Path(settings.data_dir)
            / document.storage_path
        )

        try:
            pdf = fitz.open(str(path))
            page_count = len(pdf)
            pdf.close()
        except Exception:
            continue

        if 1 <= page_count <= 3:
            print(
                "ID:",
                document.id,
                "| pages:",
                page_count,
                "| size:",
                document.file_size,
                "| file:",
                document.original_filename,
            )

            found += 1

        if found >= 10:
            break

finally:
    db.close()
