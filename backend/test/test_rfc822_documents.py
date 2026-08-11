from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.services.document_email_service import (
    DocumentEmailService,
)


db = SessionLocal()
service = DocumentEmailService()

try:
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
    print(
        "RFC822 DOCUMENTS:",
        len(documents),
    )

    for document in documents:
        print()
        print("=" * 100)

        print(
            "ID:",
            document.id,
        )

        print(
            "FILE:",
            document.original_filename,
        )

        path = (
            Path(settings.data_dir)
            / document.storage_path
        )

        result = service.extract(
            path=path
        )

        print(
            "STATUS:",
            result.status,
        )

        print(
            "TEXT CHARS:",
            len(
                result.text or ""
            ),
        )

        print(
            "ATTACHMENTS:",
            result.attachment_count,
        )

        print(
            "ERROR:",
            result.error,
        )

        if result.normalized_metadata:
            print(
                "SUBJECT:",
                result.normalized_metadata.get(
                    "subject"
                ),
            )

            print(
                "FROM:",
                result.normalized_metadata.get(
                    "from"
                ),
            )

            print(
                "TO:",
                result.normalized_metadata.get(
                    "to"
                ),
            )

            print(
                "DATE:",
                result.normalized_metadata.get(
                    "date"
                ),
            )

            print(
                "MESSAGE-ID:",
                result.normalized_metadata.get(
                    "message_id"
                ),
            )

            print(
                "ATTACHMENT NAMES:",
                result.normalized_metadata.get(
                    "attachment_names"
                ),
            )

        if result.text:
            print()
            print(
                "TEXT PREVIEW:"
            )

            print(
                result.text[:1000]
            )

finally:
    db.close()