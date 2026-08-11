from __future__ import annotations

import subprocess
import tempfile
import zipfile

from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document


DOCUMENT_ID = 770

# Celowo testujemy:
# - największy WMF,
# - średni WMF,
# - bardzo mały WMF.
TEST_MEDIA = [
    "word/media/image1.wmf",
    "word/media/image19.wmf",
    "word/media/image29.wmf",
]


def run_command(
    command: list[str],
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


db = SessionLocal()

try:
    document = (
        db.query(Document)
        .filter(Document.id == DOCUMENT_ID)
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

    print("document_id:", document.id)
    print("filename:", document.original_filename)
    print("path:", source_path)
    print("exists:", source_path.exists())

    with tempfile.TemporaryDirectory(
        prefix="ai-lab-wmf-test-"
    ) as temp_dir:
        temp_path = Path(temp_dir)

        docx_dir = temp_path / "docx"
        source_media_dir = temp_path / "wmf"
        output_dir = temp_path / "png"

        docx_dir.mkdir()
        source_media_dir.mkdir()
        output_dir.mkdir()

        print()
        print("=" * 120)
        print("CONVERT DOC -> DOCX")
        print("=" * 120)

        conversion = run_command(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(docx_dir),
                str(source_path),
            ]
        )

        print(
            "return_code:",
            conversion.returncode,
        )

        print(
            "stdout:",
            conversion.stdout.strip(),
        )

        print(
            "stderr:",
            conversion.stderr.strip(),
        )

        if conversion.returncode != 0:
            raise RuntimeError(
                "DOC -> DOCX conversion failed."
            )

        converted_files = list(
            docx_dir.glob("*.docx")
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
        print("EXTRACT TEST WMF")
        print("=" * 120)

        extracted_wmf_files: list[Path] = []

        with zipfile.ZipFile(
            docx_path,
            "r",
        ) as archive:
            names = set(
                archive.namelist()
            )

            for media_name in TEST_MEDIA:
                print()
                print(
                    "media:",
                    media_name,
                )

                if media_name not in names:
                    print(
                        "status: NOT FOUND"
                    )
                    continue

                content = archive.read(
                    media_name
                )

                output_path = (
                    source_media_dir
                    / Path(media_name).name
                )

                output_path.write_bytes(
                    content
                )

                extracted_wmf_files.append(
                    output_path
                )

                print(
                    "status: extracted"
                )

                print(
                    "size:",
                    len(content),
                )

                print(
                    "path:",
                    output_path,
                )

        print()
        print("=" * 120)
        print("CONVERT WMF -> PNG")
        print("=" * 120)

        successful = 0
        failed = 0

        for wmf_path in extracted_wmf_files:
            print()
            print("-" * 120)

            print(
                "source:",
                wmf_path.name,
            )

            process = run_command(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "png",
                    "--outdir",
                    str(output_dir),
                    str(wmf_path),
                ]
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

            expected_png = (
                output_dir
                / f"{wmf_path.stem}.png"
            )

            if not expected_png.exists():
                print(
                    "status: FAILED"
                )

                failed += 1
                continue

            try:
                with Image.open(
                    expected_png
                ) as image:
                    image.load()

                    width = image.width
                    height = image.height
                    image_format = image.format

            except Exception as error:
                print(
                    "status: INVALID PNG"
                )

                print(
                    "error:",
                    error,
                )

                failed += 1
                continue

            print(
                "status: CONVERTED"
            )

            print(
                "output:",
                expected_png,
            )

            print(
                "format:",
                image_format,
            )

            print(
                "dimensions:",
                width,
                "x",
                height,
            )

            print(
                "file_size:",
                expected_png.stat().st_size,
            )

            successful += 1

        print()
        print("=" * 120)
        print("SUMMARY")
        print("=" * 120)

        print(
            "tested:",
            len(extracted_wmf_files),
        )

        print(
            "successful:",
            successful,
        )

        print(
            "failed:",
            failed,
        )

        if successful == len(
            extracted_wmf_files
        ):
            print(
                "WMF CONVERSION TEST: OK"
            )
        else:
            print(
                "WMF CONVERSION TEST: INCOMPLETE"
            )

finally:
    db.close()