from __future__ import annotations

import time

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import fitz
import pytesseract

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


register_heif_opener()


OCRStatus = Literal[
    "ocr_extracted",
    "no_text",
    "unsupported",
    "failed",
]


@dataclass(frozen=True)
class OCRPageResult:
    page_number: int
    status: OCRStatus
    text: str | None
    confidence: float | None
    width: int | None
    height: int | None
    elapsed_seconds: float
    error: str | None = None


@dataclass(frozen=True)
class OCRDocumentResult:
    status: OCRStatus
    text: str | None
    pages: list[OCRPageResult]
    page_count: int
    character_count: int
    average_confidence: float | None
    elapsed_seconds: float
    error: str | None = None


class DocumentOCRService:
    OCR_LANGUAGES = "pol+eng"

    # Lekki tryb do pierwszego przejĹ›cia wszystkich PDF.
    DEFAULT_DPI = 150

    # Docelowo wykorzystamy ten poziom dla stron technicznych.
    DEEP_DPI = 300

    MIN_TEXT_CHARACTERS = 20

    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".webp",
    }

    IMAGE_CONTENT_TYPES = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/bmp",
        "image/tiff",
        "image/heic",
        "image/heif",
        "image/webp",
    }

    def ocr_document(
        self,
        *,
        path: Path,
        content_type: str | None,
        original_filename: str | None,
        dpi: int | None = None,
        max_pages: int | None = None,
    ) -> OCRDocumentResult:
        started = time.perf_counter()

        if not path.exists():
            return OCRDocumentResult(
                status="failed",
                text=None,
                pages=[],
                page_count=0,
                character_count=0,
                average_confidence=None,
                elapsed_seconds=time.perf_counter() - started,
                error=f"File does not exist: {path}",
            )

        normalized_content_type = (
            content_type or ""
        ).strip().lower()

        extension = Path(
            original_filename or path.name
        ).suffix.lower()

        selected_dpi = dpi or self.DEFAULT_DPI

        try:
            if (
                normalized_content_type == "application/pdf"
                or extension == ".pdf"
            ):
                return self._ocr_pdf(
                    path=path,
                    dpi=selected_dpi,
                    max_pages=max_pages,
                )

            if (
                normalized_content_type
                in self.IMAGE_CONTENT_TYPES
                or extension in self.IMAGE_EXTENSIONS
            ):
                return self._ocr_image_document(
                    path=path,
                )

            return OCRDocumentResult(
                status="unsupported",
                text=None,
                pages=[],
                page_count=0,
                character_count=0,
                average_confidence=None,
                elapsed_seconds=time.perf_counter() - started,
                error=None,
            )

        except Exception as error:
            return OCRDocumentResult(
                status="failed",
                text=None,
                pages=[],
                page_count=0,
                character_count=0,
                average_confidence=None,
                elapsed_seconds=time.perf_counter() - started,
                error=str(error),
            )

    def ocr_image(
        self,
        *,
        path: Path,
        page_number: int = 1,
    ) -> OCRPageResult:
        started = time.perf_counter()

        if not path.exists():
            return OCRPageResult(
                page_number=page_number,
                status="failed",
                text=None,
                confidence=None,
                width=None,
                height=None,
                elapsed_seconds=(
                    time.perf_counter()
                    - started
                ),
                error=f"File does not exist: {path}",
            )

        try:
            with Image.open(path) as image:
                image.load()

                prepared = self._prepare_image(
                    image
                )

                return self._ocr_pil_image(
                    image=prepared,
                    page_number=page_number,
                    started=started,
                )

        except Exception as error:
            return OCRPageResult(
                page_number=page_number,
                status="failed",
                text=None,
                confidence=None,
                width=None,
                height=None,
                elapsed_seconds=(
                    time.perf_counter()
                    - started
                ),
                error=str(error),
            )
    def _ocr_pdf(
        self,
        *,
        path: Path,
        dpi: int,
        max_pages: int | None,
    ) -> OCRDocumentResult:
        started = time.perf_counter()

        pages: list[OCRPageResult] = []

        try:
            pdf = fitz.open(str(path))

            total_pages = len(pdf)

            selected_pages = total_pages

            if max_pages is not None:
                selected_pages = min(
                    total_pages,
                    max_pages,
                )

            zoom = dpi / 72.0

            matrix = fitz.Matrix(
                zoom,
                zoom,
            )

            for page_index in range(selected_pages):
                page_started = time.perf_counter()

                try:
                    page = pdf.load_page(
                        page_index
                    )

                    pixmap = page.get_pixmap(
                        matrix=matrix,
                        alpha=False,
                    )

                    image = Image.frombytes(
                        "RGB",
                        [
                            pixmap.width,
                            pixmap.height,
                        ],
                        pixmap.samples,
                    )

                    image = self._prepare_image(
                        image
                    )

                    page_result = self._ocr_pil_image(
                        image=image,
                        page_number=page_index + 1,
                        started=page_started,
                    )

                    pages.append(page_result)

                except Exception as error:
                    pages.append(
                        OCRPageResult(
                            page_number=page_index + 1,
                            status="failed",
                            text=None,
                            confidence=None,
                            width=None,
                            height=None,
                            elapsed_seconds=(
                                time.perf_counter()
                                - page_started
                            ),
                            error=str(error),
                        )
                    )

            pdf.close()

            return self._build_document_result(
                pages=pages,
                started=started,
            )

        except Exception as error:
            return OCRDocumentResult(
                status="failed",
                text=None,
                pages=pages,
                page_count=len(pages),
                character_count=0,
                average_confidence=None,
                elapsed_seconds=(
                    time.perf_counter()
                    - started
                ),
                error=str(error),
            )

    def _ocr_image_document(
        self,
        *,
        path: Path,
    ) -> OCRDocumentResult:
        started = time.perf_counter()

        try:
            with Image.open(path) as image:
                image.load()

                prepared = self._prepare_image(
                    image
                )

                page_result = self._ocr_pil_image(
                    image=prepared,
                    page_number=1,
                    started=started,
                )

            return self._build_document_result(
                pages=[page_result],
                started=started,
            )

        except Exception as error:
            return OCRDocumentResult(
                status="failed",
                text=None,
                pages=[],
                page_count=0,
                character_count=0,
                average_confidence=None,
                elapsed_seconds=(
                    time.perf_counter()
                    - started
                ),
                error=str(error),
            )

    def _ocr_pil_image(
        self,
        *,
        image: Image.Image,
        page_number: int,
        started: float,
    ) -> OCRPageResult:
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.OCR_LANGUAGES,
                config="--psm 3",
                output_type=(
                    pytesseract.Output.DICT
                ),
            )

            words: list[str] = []
            confidences: list[float] = []

            texts = data.get(
                "text",
                [],
            )

            confidence_values = data.get(
                "conf",
                [],
            )

            for text_value, confidence_value in zip(
                texts,
                confidence_values,
            ):
                text_value = str(
                    text_value
                ).strip()

                if not text_value:
                    continue

                try:
                    confidence = float(
                        confidence_value
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    confidence = -1.0

                words.append(
                    text_value
                )

                if confidence >= 0:
                    confidences.append(
                        confidence
                    )

            text = self._normalize_text(
                " ".join(words)
            )

            confidence = (
                sum(confidences)
                / len(confidences)
                if confidences
                else None
            )

            status: OCRStatus = (
                "ocr_extracted"
                if len(text)
                >= self.MIN_TEXT_CHARACTERS
                else "no_text"
            )

            return OCRPageResult(
                page_number=page_number,
                status=status,
                text=(
                    text
                    if text
                    else None
                ),
                confidence=confidence,
                width=image.width,
                height=image.height,
                elapsed_seconds=(
                    time.perf_counter()
                    - started
                ),
                error=None,
            )

        except Exception as error:
            return OCRPageResult(
                page_number=page_number,
                status="failed",
                text=None,
                confidence=None,
                width=image.width,
                height=image.height,
                elapsed_seconds=(
                    time.perf_counter()
                    - started
                ),
                error=str(error),
            )

    def _build_document_result(
        self,
        *,
        pages: list[OCRPageResult],
        started: float,
    ) -> OCRDocumentResult:
        successful_texts = [
            page.text
            for page in pages
            if (
                page.status == "ocr_extracted"
                and page.text
            )
        ]

        combined_parts: list[str] = []

        for page in pages:
            if not page.text:
                continue

            combined_parts.append(
                f"[PAGE {page.page_number}]"
            )

            combined_parts.append(
                page.text
            )

        combined_text = self._normalize_text(
            "\n".join(
                combined_parts
            )
        )

        confidence_values = [
            page.confidence
            for page in pages
            if page.confidence is not None
        ]

        average_confidence = (
            sum(confidence_values)
            / len(confidence_values)
            if confidence_values
            else None
        )

        if successful_texts:
            status: OCRStatus = (
                "ocr_extracted"
            )

        elif any(
            page.status == "failed"
            for page in pages
        ):
            status = "failed"

        else:
            status = "no_text"

        errors = [
            page.error
            for page in pages
            if page.error
        ]

        return OCRDocumentResult(
            status=status,
            text=(
                combined_text
                if combined_text
                else None
            ),
            pages=pages,
            page_count=len(pages),
            character_count=len(
                combined_text
            ),
            average_confidence=(
                average_confidence
            ),
            elapsed_seconds=(
                time.perf_counter()
                - started
            ),
            error=(
                " | ".join(errors)
                if errors
                else None
            ),
        )

    @staticmethod
    def _prepare_image(
        image: Image.Image,
    ) -> Image.Image:
        image = ImageOps.exif_transpose(
            image
        )

        if image.mode not in {
            "RGB",
            "L",
        }:
            image = image.convert(
                "RGB"
            )

        return image

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        return " ".join(
            value.split()
        ).strip()
