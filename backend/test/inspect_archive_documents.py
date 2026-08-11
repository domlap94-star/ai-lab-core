from __future__ import annotations

import zipfile
from pathlib import Path

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document


ARCHIVE_CONTENT_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/rar",
    "application/x-rar-compressed",
    "application/7z",
    "application/x-7z-compressed",
    "application/x-compressed",
    "application/ms-tnef",
}

ARCHIVE_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".dat",
}


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"

    return f"{size / 1024 / 1024:.2f} MB"


db = SessionLocal()

try:
    documents = (
        db.query(Document)
        .filter(
            Document.content_type.in_(
                ARCHIVE_CONTENT_TYPES
            )
        )
        .order_by(
            Document.id.asc()
        )
        .all()
    )

    print()
    print("=" * 120)
    print("ARCHIVE / CONTAINER INVENTORY")
    print("=" * 120)

    print(
        "documents:",
        len(documents),
    )

    for document in documents:
        print()
        print("-" * 120)

        print(
            "ID:",
            document.id,
        )

        print(
            "FILE:",
            document.original_filename,
        )

        print(
            "CONTENT TYPE:",
            document.content_type,
        )

        print(
            "SIZE:",
            format_size(
                document.file_size
            ),
        )

        path = (
            Path(settings.data_dir)
            / document.storage_path
        )

        print(
            "PATH:",
            path,
        )

        print(
            "EXISTS:",
            path.exists(),
        )

        if not path.exists():
            continue

        extension = Path(
            document.original_filename
            or path.name
        ).suffix.lower()

        if (
            document.content_type
            in {
                "application/zip",
                "application/x-zip-compressed",
            }
            or extension == ".zip"
        ):
            try:
                with zipfile.ZipFile(
                    path,
                    "r",
                ) as archive:
                    members = archive.infolist()

                    print(
                        "TYPE: ZIP"
                    )

                    print(
                        "ENTRIES:",
                        len(members),
                    )

                    for member in members[:50]:
                        print(
                            "  -",
                            member.filename,
                            "|",
                            format_size(
                                member.file_size
                            ),
                        )

                    if len(members) > 50:
                        print(
                            "  ...",
                            len(members) - 50,
                            "more entries",
                        )

            except Exception as error:
                print(
                    "ZIP ERROR:",
                    str(error),
                )

        else:
            print(
                "TYPE: NEEDS SPECIAL HANDLER"
            )

finally:
    db.close()