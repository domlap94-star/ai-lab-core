from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_ocr_service import (
    DocumentOCRService,
)


@dataclass(frozen=True)
class OfficeOCRPageResult:
    page_number: int
    status: str
    character_count: int
    confidence: float | None
    render_path: str | None
    error: str | None = None


@dataclass(frozen=True)
class OfficeOCRDocumentResult:
    document_id: int
    status: str
    page_count: int
    processed_count: int
    no_text_count: int
    failed_count: int
    total_character_count: int
    average_confidence: float | None
    pages: list[OfficeOCRPageResult]
    error: str | None = None


class DocumentOfficeOCRService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.repository = (
            DocumentRepository(
                db
            )
        )

        self.ocr_service = (
            DocumentOCRService()
        )

        self.data_directory = Path(
            settings.data_dir
        )

    def process_document(
        self,
        *,
        document_id: int,
        force: bool = False,
    ) -> OfficeOCRDocumentResult:
        document = self.repository.get(
            document_id
        )

        if document is None:
            return OfficeOCRDocumentResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                processed_count=0,
                no_text_count=0,
                failed_count=1,
                total_character_count=0,
                average_confidence=None,
                pages=[],
                error="Document not found.",
            )

        pages = self.repository.get_pages(
            document_id
        )

        if not pages:
            return OfficeOCRDocumentResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                processed_count=0,
                no_text_count=0,
                failed_count=1,
                total_character_count=0,
                average_confidence=None,
                pages=[],
                error=(
                    "Document has no pages "
                    "available for OCR."
                ),
            )

        results: list[
            OfficeOCRPageResult
        ] = []

        processed_count = 0
        no_text_count = 0
        failed_count = 0
        total_character_count = 0

        confidence_values: list[
            float
        ] = []

        try:
            for page in pages:
                if not page.render_path:
                    failed_count += 1

                    results.append(
                        OfficeOCRPageResult(
                            page_number=(
                                page.page_number
                            ),
                            status="failed",
                            character_count=0,
                            confidence=None,
                            render_path=None,
                            error=(
                                "Page has no "
                                "render_path."
                            ),
                        )
                    )

                    continue

                if (
                    not force
                    and page.ocr_text
                    and page.processing_status
                    in {
                        "processed",
                        "no_text",
                    }
                ):
                    character_count = len(
                        page.ocr_text
                        or ""
                    )

                    total_character_count += (
                        character_count
                    )

                    if (
                        page.ocr_confidence
                        is not None
                    ):
                        confidence_values.append(
                            page.ocr_confidence
                        )

                    if (
                        page.processing_status
                        == "no_text"
                    ):
                        no_text_count += 1
                    else:
                        processed_count += 1

                    results.append(
                        OfficeOCRPageResult(
                            page_number=(
                                page.page_number
                            ),
                            status=(
                                page.processing_status
                            ),
                            character_count=(
                                character_count
                            ),
                            confidence=(
                                page.ocr_confidence
                            ),
                            render_path=(
                                page.render_path
                            ),
                            error=(
                                page.processing_error
                            ),
                        )
                    )

                    continue

                render_path = (
                    self.data_directory
                    / page.render_path
                )

                if not render_path.exists():
                    failed_count += 1

                    page.processing_status = (
                        "failed"
                    )

                    page.processing_error = (
                        f"Render file does not "
                        f"exist: {render_path}"
                    )

                    self.db.add(
                        page
                    )

                    results.append(
                        OfficeOCRPageResult(
                            page_number=(
                                page.page_number
                            ),
                            status="failed",
                            character_count=0,
                            confidence=None,
                            render_path=(
                                page.render_path
                            ),
                            error=(
                                page.processing_error
                            ),
                        )
                    )

                    continue

                ocr_result = (
                    self.ocr_service.ocr_image(
                        path=render_path,
                        page_number=(
                            page.page_number
                        ),
                    )
                )

                text = (
                    ocr_result.text
                    or None
                )

                character_count = len(
                    text
                    or ""
                )

                page.ocr_text = text
                page.ocr_confidence = (
                    ocr_result.confidence
                )

                if (
                    ocr_result.status
                    == "ocr_extracted"
                ):
                    page.processing_status = (
                        "processed"
                    )

                    page.processing_error = None

                    processed_count += 1

                elif (
                    ocr_result.status
                    == "no_text"
                ):
                    page.processing_status = (
                        "no_text"
                    )

                    page.processing_error = None

                    no_text_count += 1

                else:
                    page.processing_status = (
                        "failed"
                    )

                    page.processing_error = (
                        ocr_result.error
                    )

                    failed_count += 1

                total_character_count += (
                    character_count
                )

                if (
                    ocr_result.confidence
                    is not None
                ):
                    confidence_values.append(
                        ocr_result.confidence
                    )

                self.db.add(
                    page
                )

                results.append(
                    OfficeOCRPageResult(
                        page_number=(
                            page.page_number
                        ),
                        status=(
                            page.processing_status
                        ),
                        character_count=(
                            character_count
                        ),
                        confidence=(
                            ocr_result.confidence
                        ),
                        render_path=(
                            page.render_path
                        ),
                        error=(
                            page.processing_error
                        ),
                    )
                )

            self.db.commit()

        except Exception as error:
            self.db.rollback()

            return OfficeOCRDocumentResult(
                document_id=document_id,
                status="failed",
                page_count=len(
                    pages
                ),
                processed_count=(
                    processed_count
                ),
                no_text_count=(
                    no_text_count
                ),
                failed_count=(
                    failed_count + 1
                ),
                total_character_count=(
                    total_character_count
                ),
                average_confidence=(
                    self._average(
                        confidence_values
                    )
                ),
                pages=results,
                error=str(error),
            )

        if failed_count > 0:
            if (
                processed_count > 0
                or no_text_count > 0
            ):
                status = "partial"
            else:
                status = "failed"

        elif (
            processed_count > 0
            or no_text_count > 0
        ):
            status = "processed"

        else:
            status = "failed"

        return OfficeOCRDocumentResult(
            document_id=document_id,
            status=status,
            page_count=len(
                pages
            ),
            processed_count=(
                processed_count
            ),
            no_text_count=(
                no_text_count
            ),
            failed_count=(
                failed_count
            ),
            total_character_count=(
                total_character_count
            ),
            average_confidence=(
                self._average(
                    confidence_values
                )
            ),
            pages=results,
            error=None,
        )

    @staticmethod
    def _average(
        values: list[float],
    ) -> float | None:
        if not values:
            return None

        return (
            sum(values)
            / len(values)
        )