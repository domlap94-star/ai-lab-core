from __future__ import annotations

import shutil

from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.config import settings


@dataclass(frozen=True)
class PageRenderResult:
    page_number: int
    status: str

    render_path: str | None

    width: int | None
    height: int | None

    dpi: int

    error: str | None = None


@dataclass(frozen=True)
class DocumentRenderResult:
    document_id: int
    status: str

    page_count: int

    pages: list[PageRenderResult]

    error: str | None = None


class DocumentPageRenderService:
    DEFAULT_DPI = 150
    MIN_DPI = 72
    MAX_DPI = 300
    MAX_PAGES = 250

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

    def render_pdf(
        self,
        *,
        document_id: int,
        path: Path,
        dpi: int | None = None,
        max_pages: int | None = None,
        force: bool = False,
    ) -> DocumentRenderResult:
        selected_dpi = (
            dpi
            if dpi is not None
            else self.DEFAULT_DPI
        )

        if not self.MIN_DPI <= selected_dpi <= self.MAX_DPI:
            return DocumentRenderResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                pages=[],
                error=(
                    f"Render DPI must be between {self.MIN_DPI} "
                    f"and {self.MAX_DPI}."
                ),
            )

        selected_page_limit = (
            self.MAX_PAGES
            if max_pages is None
            else min(max_pages, self.MAX_PAGES)
        )
        if selected_page_limit < 1:
            return DocumentRenderResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                pages=[],
                error="Render page limit must be positive.",
            )

        if not path.exists():
            return DocumentRenderResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                pages=[],
                error=(
                    f"File does not exist: {path}"
                ),
            )

        document_directory = (
            self.render_root
            / str(document_id)
        )

        try:
            if (
                force
                and document_directory.exists()
            ):
                shutil.rmtree(
                    document_directory
                )

            document_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            pdf = fitz.open(
                str(path)
            )

            try:
                total_pages = len(pdf)
                pages_to_render = min(
                    total_pages,
                    selected_page_limit,
                )

                page_results: list[
                    PageRenderResult
                ] = []

                zoom = (
                    selected_dpi
                    / 72.0
                )

                matrix = fitz.Matrix(
                    zoom,
                    zoom,
                )

                for page_index in range(
                    pages_to_render
                ):
                    page_number = (
                        page_index + 1
                    )

                    page_path = (
                        document_directory
                        / (
                            f"page_"
                            f"{page_number:04d}"
                            f".png"
                        )
                    )

                    relative_path = (
                        page_path.relative_to(
                            self.data_directory
                        )
                    )

                    if (
                        page_path.exists()
                        and not force
                    ):
                        try:
                            existing = fitz.Pixmap(
                                str(page_path)
                            )

                            width = (
                                existing.width
                            )

                            height = (
                                existing.height
                            )

                            existing = None

                            page_results.append(
                                PageRenderResult(
                                    page_number=(
                                        page_number
                                    ),
                                    status="existing",
                                    render_path=(
                                        relative_path
                                        .as_posix()
                                    ),
                                    width=width,
                                    height=height,
                                    dpi=(
                                        selected_dpi
                                    ),
                                    error=None,
                                )
                            )

                            continue

                        except Exception:
                            page_path.unlink(
                                missing_ok=True
                            )

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
                            str(page_path)
                        )

                        page_results.append(
                            PageRenderResult(
                                page_number=(
                                    page_number
                                ),
                                status="rendered",
                                render_path=(
                                    relative_path
                                    .as_posix()
                                ),
                                width=(
                                    pixmap.width
                                ),
                                height=(
                                    pixmap.height
                                ),
                                dpi=(
                                    selected_dpi
                                ),
                                error=None,
                            )
                        )

                    except Exception as error:
                        page_results.append(
                            PageRenderResult(
                                page_number=(
                                    page_number
                                ),
                                status="failed",
                                render_path=None,
                                width=None,
                                height=None,
                                dpi=(
                                    selected_dpi
                                ),
                                error=str(
                                    error
                                ),
                            )
                        )

                failed_pages = [
                    page
                    for page in page_results
                    if page.status
                    == "failed"
                ]

                if not page_results:
                    status = "failed"
                    error = (
                        "PDF contains no pages."
                    )

                elif (
                    len(failed_pages)
                    == len(page_results)
                ):
                    status = "failed"
                    error = (
                        "All PDF pages "
                        "failed to render."
                    )

                elif failed_pages or total_pages > pages_to_render:
                    status = "partial"
                    reasons: list[str] = []
                    if failed_pages:
                        reasons.append(
                            f"{len(failed_pages)} page(s) failed to render."
                        )
                    if total_pages > pages_to_render:
                        reasons.append(
                            f"Rendered first {pages_to_render} of "
                            f"{total_pages} pages due to the safety limit."
                        )
                    error = " ".join(reasons)

                else:
                    status = "rendered"
                    error = None

                return DocumentRenderResult(
                    document_id=document_id,
                    status=status,
                    page_count=len(
                        page_results
                    ),
                    pages=page_results,
                    error=error,
                )

            finally:
                pdf.close()

        except Exception as error:
            return DocumentRenderResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                pages=[],
                error=str(error),
            )
