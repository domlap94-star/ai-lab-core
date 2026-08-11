from __future__ import annotations

import hashlib
import subprocess
import tempfile
import zipfile

from collections import Counter
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document


DOCUMENT_ID = 770


def inspect_with_pillow(
    content: bytes,
) -> tuple[
    bool,
    str | None,
    int | None,
    int | None,
    str | None,
]:
    try:
        with Image.open(
            BytesIO(content)
        ) as image:
            image.load()

            return (
                True,
                image.format,
                image.width,
                image.height,
                None,
            )

    except Exception as error:
        return (
            False,
            None,
            None,
            None,
            str(error),
        )


db = SessionLocal()

try:
    document = (
        db.query(Document)
        .filter(
            Document.id == DOCUMENT_ID
        )
        .first()
    )

    if document is None:
        raise RuntimeError(
            f"Document {DOCUMENT_ID} not found."
        )

    if not document.storage_path:
        raise RuntimeError(
            "Document has no storage path."
        )

    source_path = (
        Path(settings.data_dir)
        / document.storage_path
    )

    print()
    print("=" * 120)
    print("SOURCE")
    print("=" * 120)

    print(
        "document_id:",
        document.id,
    )

    print(
        "filename:",
        document.original_filename,
    )

    print(
        "path:",
        source_path,
    )

    print(
        "exists:",
        source_path.exists(),
    )

    with tempfile.TemporaryDirectory(
        prefix="ai-lab-doc-media-inspect-"
    ) as temp_dir:
        temp_path = Path(
            temp_dir
        )

        print()
        print("=" * 120)
        print("CONVERT DOC -> DOCX")
        print("=" * 120)

        process = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(temp_path),
                str(source_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )

        print(
            "return_code:",
            process.returncode,
        )

        print(
            "stdout:",
            process.stdout.strip(),
        )

        print(
            "stderr:",
            process.stderr.strip(),
        )

        converted_files = list(
            temp_path.glob(
                "*.docx"
            )
        )

        if not converted_files:
            raise RuntimeError(
                "LibreOffice did not produce DOCX."
            )

        docx_path = converted_files[0]

        print(
            "docx:",
            docx_path,
        )

        print()
        print("=" * 120)
        print("WORD/MEDIA INVENTORY")
        print("=" * 120)

        rows: list[dict] = []

        with zipfile.ZipFile(
            docx_path,
            "r",
        ) as archive:
            members = [
                member
                for member in archive.infolist()
                if (
                    not member.is_dir()
                    and member.filename.startswith(
                        "word/media/"
                    )
                )
            ]

            print(
                "media_members:",
                len(members),
            )

            for index, member in enumerate(
                members,
                start=1,
            ):
                content = archive.read(
                    member
                )

                extension = Path(
                    member.filename
                ).suffix.lower()

                (
                    pillow_ok,
                    pillow_format,
                    width,
                    height,
                    pillow_error,
                ) = inspect_with_pillow(
                    content
                )

                sha256 = hashlib.sha256(
                    content
                ).hexdigest()

                skip_reason = None

                if len(content) < 100:
                    skip_reason = (
                        "below_100_bytes"
                    )

                elif not pillow_ok:
                    skip_reason = (
                        "not_supported_by_pillow"
                    )

                elif (
                    width is not None
                    and height is not None
                    and (
                        width < 16
                        or height < 16
                    )
                ):
                    skip_reason = (
                        "tiny_image"
                    )

                else:
                    skip_reason = (
                        "would_extract"
                    )

                row = {
                    "index": index,
                    "name": member.filename,
                    "extension": extension,
                    "size": len(content),
                    "pillow_ok": pillow_ok,
                    "pillow_format": (
                        pillow_format
                    ),
                    "width": width,
                    "height": height,
                    "reason": skip_reason,
                    "sha256": sha256,
                    "pillow_error": (
                        pillow_error
                    ),
                }

                rows.append(
                    row
                )

                print()
                print("-" * 120)

                print(
                    "index:",
                    index,
                )

                print(
                    "name:",
                    member.filename,
                )

                print(
                    "extension:",
                    extension,
                )

                print(
                    "size:",
                    len(content),
                )

                print(
                    "pillow_ok:",
                    pillow_ok,
                )

                print(
                    "pillow_format:",
                    pillow_format,
                )

                print(
                    "dimensions:",
                    width,
                    "x",
                    height,
                )

                print(
                    "classification:",
                    skip_reason,
                )

                print(
                    "sha256:",
                    sha256,
                )

                if pillow_error:
                    print(
                        "pillow_error:",
                        pillow_error,
                    )

        print()
        print()
        print("=" * 120)
        print("SUMMARY BY EXTENSION")
        print("=" * 120)

        extension_counts = Counter(
            row["extension"]
            or "[NO EXTENSION]"
            for row in rows
        )

        for extension, count in sorted(
            extension_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):
            print(
                extension,
                ":",
                count,
            )

        print()
        print("=" * 120)
        print("SUMMARY BY CLASSIFICATION")
        print("=" * 120)

        reason_counts = Counter(
            row["reason"]
            for row in rows
        )

        for reason, count in sorted(
            reason_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):
            print(
                reason,
                ":",
                count,
            )

        print()
        print("=" * 120)
        print("UNSUPPORTED BY PILLOW")
        print("=" * 120)

        unsupported = [
            row
            for row in rows
            if row["reason"]
            == "not_supported_by_pillow"
        ]

        if not unsupported:
            print(
                "NONE"
            )

        else:
            for row in unsupported:
                print(
                    row["index"],
                    "|",
                    row["extension"],
                    "|",
                    row["size"],
                    "bytes",
                    "|",
                    row["name"],
                )

        print()
        print("=" * 120)
        print("TINY IMAGES")
        print("=" * 120)

        tiny = [
            row
            for row in rows
            if row["reason"]
            == "tiny_image"
        ]

        if not tiny:
            print(
                "NONE"
            )

        else:
            for row in tiny:
                print(
                    row["index"],
                    "|",
                    row["width"],
                    "x",
                    row["height"],
                    "|",
                    row["size"],
                    "bytes",
                    "|",
                    row["name"],
                )

finally:
    db.close()