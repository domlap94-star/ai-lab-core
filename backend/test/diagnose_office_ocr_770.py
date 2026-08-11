from __future__ import annotations

import subprocess
from pathlib import Path

import pytesseract
from PIL import Image

from app.core.config import settings
from app.database.session import SessionLocal
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_ocr_service import (
    DocumentOCRService,
)


DOCUMENT_ID = 770
TEST_PAGE = 1


db = SessionLocal()

try:
    repository = DocumentRepository(
        db
    )

    pages = repository.get_pages(
        DOCUMENT_ID
    )

    print()
    print("=" * 120)
    print("DATABASE PAGE ERRORS")
    print("=" * 120)

    print(
        "pages:",
        len(pages),
    )

    for page in pages:
        print()
        print(
            "page:",
            page.page_number,
            "| status:",
            page.processing_status,
            "| error:",
            page.processing_error,
        )

    page = repository.get_page(
        document_id=DOCUMENT_ID,
        page_number=TEST_PAGE,
    )

    if page is None:
        raise RuntimeError(
            f"Page {TEST_PAGE} not found."
        )

    if not page.render_path:
        raise RuntimeError(
            f"Page {TEST_PAGE} has no render_path."
        )

    image_path = (
        Path(settings.data_dir)
        / page.render_path
    )

    print()
    print("=" * 120)
    print("TEST PAGE")
    print("=" * 120)

    print(
        "page_number:",
        page.page_number,
    )

    print(
        "render_path:",
        page.render_path,
    )

    print(
        "absolute_path:",
        image_path,
    )

    print(
        "exists:",
        image_path.exists(),
    )

    if image_path.exists():
        print(
            "file_size:",
            image_path.stat().st_size,
        )

    print()
    print("=" * 120)
    print("PIL TEST")
    print("=" * 120)

    try:
        with Image.open(
            image_path
        ) as image:
            image.load()

            print(
                "PIL: OK"
            )

            print(
                "format:",
                image.format,
            )

            print(
                "mode:",
                image.mode,
            )

            print(
                "dimensions:",
                image.width,
                "x",
                image.height,
            )

    except Exception as error:
        print(
            "PIL: FAILED"
        )

        print(
            "type:",
            type(error).__name__,
        )

        print(
            "error:",
            repr(error),
        )

    print()
    print("=" * 120)
    print("TESSERACT SYSTEM")
    print("=" * 120)

    version_process = subprocess.run(
        [
            "tesseract",
            "--version",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    print(
        "return_code:",
        version_process.returncode,
    )

    print(
        "version:"
    )

    print(
        version_process.stdout[:1000]
    )

    print()
    print(
        "pytesseract version:",
        pytesseract.get_tesseract_version(),
    )

    print()
    print(
        "languages:",
        pytesseract.get_languages(
            config=""
        ),
    )

    print()
    print("=" * 120)
    print("DIRECT PYTESSERACT TEST")
    print("=" * 120)

    try:
        with Image.open(
            image_path
        ) as image:
            image.load()

            direct_text = (
                pytesseract.image_to_string(
                    image,
                    lang="pol+eng",
                    config="--psm 3",
                )
            )

        print(
            "DIRECT OCR: OK"
        )

        print(
            "characters:",
            len(
                direct_text
            ),
        )

        print(
            "preview:"
        )

        print(
            direct_text[:1500]
        )

    except Exception as error:
        print(
            "DIRECT OCR: FAILED"
        )

        print(
            "type:",
            type(error).__name__,
        )

        print(
            "error:",
            repr(error),
        )

    print()
    print("=" * 120)
    print("DOCUMENT OCR SERVICE TEST")
    print("=" * 120)

    service = DocumentOCRService()

    try:
        result = service.ocr_image(
            path=image_path,
            page_number=TEST_PAGE,
        )

        print(
            "status:",
            result.status,
        )

        print(
            "characters:",
            len(
                result.text
                or ""
            ),
        )

        print(
            "confidence:",
            result.confidence,
        )

        print(
            "width:",
            result.width,
        )

        print(
            "height:",
            result.height,
        )

        print(
            "elapsed_seconds:",
            result.elapsed_seconds,
        )

        print(
            "error:",
            result.error,
        )

        print()
        print(
            "preview:"
        )

        print(
            (
                result.text
                or "[NO TEXT]"
            )[:1500]
        )

    except Exception as error:
        print(
            "OCR SERVICE EXCEPTION"
        )

        print(
            "type:",
            type(error).__name__,
        )

        print(
            "error:",
            repr(error),
        )

finally:
    db.close()