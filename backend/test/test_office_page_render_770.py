from __future__ import annotations

import subprocess
import tempfile

from pathlib import Path

import fitz
from PIL import Image

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document


DOCUMENT_ID = 770
RENDER_DPI = 150


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
            "Document has no storage_path."
        )

    source_path = (
        Path(settings.data_dir)
        / document.storage_path
    )

    if not source_path.exists():
        raise RuntimeError(
            f"Source file does not exist: {source_path}"
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
        "content_type:",
        document.content_type,
    )

    print(
        "file_size:",
        document.file_size,
    )

    print(
        "source_path:",
        source_path,
    )

    print(
        "exists:",
        source_path.exists(),
    )

    with tempfile.TemporaryDirectory(
        prefix="ai-lab-office-render-"
    ) as temp_dir:
        temp_path = Path(
            temp_dir
        )

        pdf_dir = (
            temp_path
            / "pdf"
        )

        render_dir = (
            temp_path
            / "renders"
        )

        pdf_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        render_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print()
        print("=" * 120)
        print("CONVERT OFFICE -> PDF")
        print("=" * 120)

        process = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_dir),
                str(source_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
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

        pdf_files = list(
            pdf_dir.glob(
                "*.pdf"
            )
        )

        if not pdf_files:
            raise RuntimeError(
                "LibreOffice did not produce PDF."
            )

        pdf_path = pdf_files[0]

        print(
            "pdf_path:",
            pdf_path,
        )

        print(
            "pdf_exists:",
            pdf_path.exists(),
        )

        print(
            "pdf_size:",
            pdf_path.stat().st_size,
        )

        print()
        print("=" * 120)
        print("PDF INSPECTION")
        print("=" * 120)

        pdf = fitz.open(
            str(pdf_path)
        )

        try:
            print(
                "page_count:",
                len(pdf),
            )

            zoom = (
                RENDER_DPI
                / 72.0
            )

            matrix = fitz.Matrix(
                zoom,
                zoom,
            )

            rendered_pages = 0
            total_pixels = 0

            for page_index in range(
                len(pdf)
            ):
                page_number = (
                    page_index + 1
                )

                page = pdf.load_page(
                    page_index
                )

                pixmap = page.get_pixmap(
                    matrix=matrix,
                    alpha=False,
                )

                render_path = (
                    render_dir
                    / (
                        f"page_"
                        f"{page_number:04d}"
                        f".png"
                    )
                )

                pixmap.save(
                    str(render_path)
                )

                print()
                print("-" * 120)

                print(
                    "page:",
                    page_number,
                )

                print(
                    "render:",
                    render_path,
                )

                print(
                    "dimensions:",
                    pixmap.width,
                    "x",
                    pixmap.height,
                )

                print(
                    "file_size:",
                    render_path.stat().st_size,
                )

                try:
                    with Image.open(
                        render_path
                    ) as image:
                        image.verify()

                    print(
                        "image_verify: OK"
                    )

                except Exception as error:
                    print(
                        "image_verify: FAILED"
                    )

                    print(
                        "error:",
                        error,
                    )

                rendered_pages += 1

                total_pixels += (
                    pixmap.width
                    * pixmap.height
                )

            print()
            print("=" * 120)
            print("SUMMARY")
            print("=" * 120)

            print(
                "pdf_pages:",
                len(pdf),
            )

            print(
                "rendered_pages:",
                rendered_pages,
            )

            print(
                "dpi:",
                RENDER_DPI,
            )

            print(
                "total_pixels:",
                total_pixels,
            )

            if (
                rendered_pages
                == len(pdf)
                and rendered_pages > 0
            ):
                print(
                    "OFFICE PAGE RENDER TEST: OK"
                )

            else:
                print(
                    "OFFICE PAGE RENDER TEST: INCOMPLETE"
                )

        finally:
            pdf.close()

finally:
    db.close()