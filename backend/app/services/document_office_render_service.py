from __future__ import annotations

import shutil
import subprocess
import tempfile

from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.config import settings


@dataclass(frozen=True)
class OfficeRenderedPage:
    page_number: int
    render_path: str | None
    dpi: int
    width: int | None
    height: int | None
    file_size: int | None
    status: str
    error: str | None = None


@dataclass(frozen=True)
class OfficeRenderResult:
    document_id: int
    status: str
    source_format: str | None
    page_count: int
    rendered_count: int
    existing_count: int
    failed_count: int
    pages: list[OfficeRenderedPage]
    conversion_stdout: str | None = None
    conversion_stderr: str | None = None
    error: str | None = None


class DocumentOfficeRenderService:
    SUPPORTED_EXTENSIONS = {
        ".doc",
        ".docx",
        ".odt",
        ".ppt",
        ".pptx",
        ".odp",
        ".rtf",
    }

    SUPPORTED_CONTENT_TYPES = {
        "application/msword",
        (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        "application/vnd.oasis.opendocument.text",
        "application/vnd.ms-powerpoint",
        (
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
        "application/vnd.oasis.opendocument.presentation",
        "application/rtf",
        "text/rtf",
    }

    def __init__(
        self,
    ) -> None:
        self.data_directory = Path(
            settings.data_dir
        )

        self.render_root = (
            self.data_directory
            / "document-pages"
        )

    def supports(
        self,
        *,
        content_type: str | None,
        original_filename: str | None,
    ) -> bool:
        normalized_content_type = (
            content_type
            or ""
        ).strip().lower()

        extension = Path(
            original_filename
            or ""
        ).suffix.lower()

        return (
            extension
            in self.SUPPORTED_EXTENSIONS
            or normalized_content_type
            in self.SUPPORTED_CONTENT_TYPES
        )

    def render_document(
        self,
        *,
        document_id: int,
        path: Path,
        content_type: str | None,
        original_filename: str | None,
        dpi: int = 150,
        force: bool = False,
    ) -> OfficeRenderResult:
        path = Path(
            path
        )

        if not path.exists():
            return self._failed_result(
                document_id=document_id,
                source_format=None,
                error=(
                    f"Source file does not exist: "
                    f"{path}"
                ),
            )

        if dpi < 72:
            return self._failed_result(
                document_id=document_id,
                source_format=None,
                error=(
                    "Render DPI must be at "
                    "least 72."
                ),
            )

        extension = Path(
            original_filename
            or path.name
        ).suffix.lower()

        source_format = (
            extension.lstrip(".")
            if extension
            else None
        )

        if not self.supports(
            content_type=content_type,
            original_filename=(
                original_filename
                or path.name
            ),
        ):
            return OfficeRenderResult(
                document_id=document_id,
                status="unsupported",
                source_format=source_format,
                page_count=0,
                rendered_count=0,
                existing_count=0,
                failed_count=0,
                pages=[],
                conversion_stdout=None,
                conversion_stderr=None,
                error=None,
            )

        output_directory = (
            self.render_root
            / str(document_id)
        )

        if force:
            self._clear_output_directory(
                output_directory
            )

        try:
            with tempfile.TemporaryDirectory(
                prefix=(
                    "ai-lab-office-render-"
                )
            ) as temp_dir:
                temp_path = Path(
                    temp_dir
                )

                pdf_directory = (
                    temp_path
                    / "pdf"
                )

                pdf_directory.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                conversion = (
                    self._convert_to_pdf(
                        source_path=path,
                        output_directory=(
                            pdf_directory
                        ),
                    )
                )

                if conversion[
                    "status"
                ] != "converted":
                    return OfficeRenderResult(
                        document_id=(
                            document_id
                        ),
                        status="failed",
                        source_format=(
                            source_format
                        ),
                        page_count=0,
                        rendered_count=0,
                        existing_count=0,
                        failed_count=1,
                        pages=[],
                        conversion_stdout=(
                            conversion[
                                "stdout"
                            ]
                        ),
                        conversion_stderr=(
                            conversion[
                                "stderr"
                            ]
                        ),
                        error=(
                            conversion[
                                "error"
                            ]
                        ),
                    )

                pdf_path = conversion[
                    "pdf_path"
                ]

                if pdf_path is None:
                    return OfficeRenderResult(
                        document_id=(
                            document_id
                        ),
                        status="failed",
                        source_format=(
                            source_format
                        ),
                        page_count=0,
                        rendered_count=0,
                        existing_count=0,
                        failed_count=1,
                        pages=[],
                        conversion_stdout=(
                            conversion[
                                "stdout"
                            ]
                        ),
                        conversion_stderr=(
                            conversion[
                                "stderr"
                            ]
                        ),
                        error=(
                            "Office conversion "
                            "returned no PDF path."
                        ),
                    )

                return self._render_pdf(
                    document_id=document_id,
                    pdf_path=pdf_path,
                    source_format=(
                        source_format
                    ),
                    output_directory=(
                        output_directory
                    ),
                    dpi=dpi,
                    force=force,
                    conversion_stdout=(
                        conversion["stdout"]
                    ),
                    conversion_stderr=(
                        conversion["stderr"]
                    ),
                )

        except Exception as error:
            return self._failed_result(
                document_id=document_id,
                source_format=(
                    source_format
                ),
                error=str(error),
            )

    def _convert_to_pdf(
        self,
        *,
        source_path: Path,
        output_directory: Path,
    ) -> dict:
        try:
            process = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(
                        output_directory
                    ),
                    str(
                        source_path
                    ),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "pdf_path": None,
                "stdout": None,
                "stderr": None,
                "error": (
                    "LibreOffice conversion "
                    "timed out."
                ),
            }

        except Exception as error:
            return {
                "status": "failed",
                "pdf_path": None,
                "stdout": None,
                "stderr": None,
                "error": str(error),
            }

        stdout = (
            process.stdout.strip()
            if process.stdout
            else None
        )

        stderr = (
            process.stderr.strip()
            if process.stderr
            else None
        )

        pdf_files = sorted(
            output_directory.glob(
                "*.pdf"
            )
        )

        if (
            process.returncode != 0
            or not pdf_files
        ):
            return {
                "status": "failed",
                "pdf_path": None,
                "stdout": stdout,
                "stderr": stderr,
                "error": (
                    stderr
                    or stdout
                    or (
                        "LibreOffice did not "
                        "produce a PDF."
                    )
                ),
            }

        pdf_path = (
            pdf_files[0]
        )

        if (
            not pdf_path.exists()
            or pdf_path.stat().st_size
            <= 0
        ):
            return {
                "status": "failed",
                "pdf_path": None,
                "stdout": stdout,
                "stderr": stderr,
                "error": (
                    "Converted PDF is empty "
                    "or missing."
                ),
            }

        return {
            "status": "converted",
            "pdf_path": pdf_path,
            "stdout": stdout,
            "stderr": stderr,
            "error": None,
        }

    def _render_pdf(
        self,
        *,
        document_id: int,
        pdf_path: Path,
        source_format: str | None,
        output_directory: Path,
        dpi: int,
        force: bool,
        conversion_stdout: str | None,
        conversion_stderr: str | None,
    ) -> OfficeRenderResult:
        pages: list[
            OfficeRenderedPage
        ] = []

        rendered_count = 0
        existing_count = 0
        failed_count = 0

        try:
            pdf = fitz.open(
                str(
                    pdf_path
                )
            )

        except Exception as error:
            return OfficeRenderResult(
                document_id=document_id,
                status="failed",
                source_format=source_format,
                page_count=0,
                rendered_count=0,
                existing_count=0,
                failed_count=1,
                pages=[],
                conversion_stdout=(
                    conversion_stdout
                ),
                conversion_stderr=(
                    conversion_stderr
                ),
                error=(
                    f"Cannot open converted "
                    f"PDF: {error}"
                ),
            )

        try:
            page_count = len(
                pdf
            )

            if page_count == 0:
                return OfficeRenderResult(
                    document_id=(
                        document_id
                    ),
                    status="failed",
                    source_format=(
                        source_format
                    ),
                    page_count=0,
                    rendered_count=0,
                    existing_count=0,
                    failed_count=1,
                    pages=[],
                    conversion_stdout=(
                        conversion_stdout
                    ),
                    conversion_stderr=(
                        conversion_stderr
                    ),
                    error=(
                        "Converted PDF has "
                        "no pages."
                    ),
                )

            output_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            zoom = (
                dpi
                / 72.0
            )

            matrix = fitz.Matrix(
                zoom,
                zoom,
            )

            for page_index in range(
                page_count
            ):
                page_number = (
                    page_index + 1
                )

                render_name = (
                    f"page_"
                    f"{page_number:04d}"
                    f".png"
                )

                render_path = (
                    output_directory
                    / render_name
                )

                relative_render_path = (
                    render_path
                    .relative_to(
                        self.data_directory
                    )
                    .as_posix()
                )

                if (
                    render_path.exists()
                    and not force
                ):
                    try:
                        pix = fitz.Pixmap(
                            str(
                                render_path
                            )
                        )

                        width = (
                            pix.width
                        )

                        height = (
                            pix.height
                        )

                        pix = None

                        pages.append(
                            OfficeRenderedPage(
                                page_number=(
                                    page_number
                                ),
                                render_path=(
                                    relative_render_path
                                ),
                                dpi=dpi,
                                width=width,
                                height=height,
                                file_size=(
                                    render_path
                                    .stat()
                                    .st_size
                                ),
                                status=(
                                    "existing"
                                ),
                                error=None,
                            )
                        )

                        existing_count += 1

                        continue

                    except Exception:
                        try:
                            render_path.unlink(
                                missing_ok=True
                            )
                        except Exception:
                            pass

                try:
                    page = pdf.load_page(
                        page_index
                    )

                    pixmap = (
                        page.get_pixmap(
                            matrix=matrix,
                            alpha=False,
                        )
                    )

                    pixmap.save(
                        str(
                            render_path
                        )
                    )

                    pages.append(
                        OfficeRenderedPage(
                            page_number=(
                                page_number
                            ),
                            render_path=(
                                relative_render_path
                            ),
                            dpi=dpi,
                            width=(
                                pixmap.width
                            ),
                            height=(
                                pixmap.height
                            ),
                            file_size=(
                                render_path
                                .stat()
                                .st_size
                            ),
                            status="rendered",
                            error=None,
                        )
                    )

                    rendered_count += 1

                except Exception as error:
                    failed_count += 1

                    pages.append(
                        OfficeRenderedPage(
                            page_number=(
                                page_number
                            ),
                            render_path=None,
                            dpi=dpi,
                            width=None,
                            height=None,
                            file_size=None,
                            status="failed",
                            error=str(error),
                        )
                    )

        finally:
            pdf.close()

        if failed_count > 0:
            if (
                rendered_count > 0
                or existing_count > 0
            ):
                status = "partial"
            else:
                status = "failed"

        elif rendered_count > 0:
            status = "rendered"

        elif existing_count > 0:
            status = "existing"

        else:
            status = "failed"

        return OfficeRenderResult(
            document_id=document_id,
            status=status,
            source_format=source_format,
            page_count=len(
                pages
            ),
            rendered_count=(
                rendered_count
            ),
            existing_count=(
                existing_count
            ),
            failed_count=(
                failed_count
            ),
            pages=pages,
            conversion_stdout=(
                conversion_stdout
            ),
            conversion_stderr=(
                conversion_stderr
            ),
            error=(
                None
                if status
                in {
                    "rendered",
                    "existing",
                }
                else (
                    "One or more Office "
                    "pages failed to render."
                )
            ),
        )

    def clear_document_renders(
        self,
        *,
        document_id: int,
    ) -> None:
        directory = (
            self.render_root
            / str(document_id)
        )

        self._clear_output_directory(
            directory
        )

    @staticmethod
    def _clear_output_directory(
        directory: Path,
    ) -> None:
        if directory.exists():
            shutil.rmtree(
                directory
            )

    @staticmethod
    def _failed_result(
        *,
        document_id: int,
        source_format: str | None,
        error: str,
    ) -> OfficeRenderResult:
        return OfficeRenderResult(
            document_id=document_id,
            status="failed",
            source_format=source_format,
            page_count=0,
            rendered_count=0,
            existing_count=0,
            failed_count=1,
            pages=[],
            conversion_stdout=None,
            conversion_stderr=None,
            error=error,
        )