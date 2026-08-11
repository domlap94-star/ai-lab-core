from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.document_repository import DocumentRepository
from app.services.document_office_render_service import (
    DocumentOfficeRenderService,
)


@dataclass(frozen=True)
class OfficePageProcessingResult:
    document_id: int
    status: str
    page_count: int
    rendered_count: int
    existing_count: int
    stored_page_count: int
    failed_count: int
    error: str | None = None


class DocumentOfficePageService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.repository = DocumentRepository(
            db
        )

        self.render_service = (
            DocumentOfficeRenderService()
        )

        self.data_directory = Path(
            settings.data_dir
        )

    def process_document(
        self,
        *,
        document_id: int,
        dpi: int = 150,
        force: bool = False,
    ) -> OfficePageProcessingResult:
        document = self.repository.get(
            document_id
        )

        if document is None:
            return OfficePageProcessingResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                rendered_count=0,
                existing_count=0,
                stored_page_count=0,
                failed_count=1,
                error="Document not found.",
            )

        if not document.storage_path:
            return OfficePageProcessingResult(
                document_id=document.id,
                status="failed",
                page_count=0,
                rendered_count=0,
                existing_count=0,
                stored_page_count=0,
                failed_count=1,
                error=(
                    "Document has no storage path."
                ),
            )

        source_path = (
            self.data_directory
            / document.storage_path
        )

        if not source_path.exists():
            return OfficePageProcessingResult(
                document_id=document.id,
                status="failed",
                page_count=0,
                rendered_count=0,
                existing_count=0,
                stored_page_count=0,
                failed_count=1,
                error=(
                    f"Source file does not exist: "
                    f"{source_path}"
                ),
            )

        if not self.render_service.supports(
            content_type=document.content_type,
            original_filename=(
                document.original_filename
            ),
        ):
            return OfficePageProcessingResult(
                document_id=document.id,
                status="unsupported",
                page_count=0,
                rendered_count=0,
                existing_count=0,
                stored_page_count=0,
                failed_count=0,
                error=None,
            )

        render_result = (
            self.render_service.render_document(
                document_id=document.id,
                path=source_path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
                dpi=dpi,
                force=force,
            )
        )

        if render_result.status in {
            "failed",
            "unsupported",
        }:
            return OfficePageProcessingResult(
                document_id=document.id,
                status=render_result.status,
                page_count=(
                    render_result.page_count
                ),
                rendered_count=(
                    render_result.rendered_count
                ),
                existing_count=(
                    render_result.existing_count
                ),
                stored_page_count=0,
                failed_count=(
                    render_result.failed_count
                ),
                error=render_result.error,
            )

        stored_page_count = 0
        failed_count = (
            render_result.failed_count
        )

        try:
            for rendered_page in (
                render_result.pages
            ):
                if (
                    rendered_page.status
                    not in {
                        "rendered",
                        "existing",
                    }
                ):
                    continue

                if not rendered_page.render_path:
                    failed_count += 1
                    continue

                if (
                    rendered_page.width
                    is None
                    or rendered_page.height
                    is None
                ):
                    failed_count += 1
                    continue

                existing_page = (
                    self.repository.get_page(
                        document_id=(
                            document.id
                        ),
                        page_number=(
                            rendered_page.page_number
                        ),
                    )
                )

                if existing_page is None:
                    self.repository.upsert_page(
                        document_id=document.id,
                        page_number=(
                            rendered_page.page_number
                        ),
                        extracted_text=None,
                        ocr_text=None,
                        ocr_confidence=None,
                        width=(
                            rendered_page.width
                        ),
                        height=(
                            rendered_page.height
                        ),
                        processing_status="pending",
                        processing_error=None,
                        page_type=None,
                        vision_analysis=None,
                        render_path=(
                            rendered_page.render_path
                        ),
                        render_dpi=(
                            rendered_page.dpi
                        ),
                    )

                else:
                    self.repository.update_page_render(
                        document_id=document.id,
                        page_number=(
                            rendered_page.page_number
                        ),
                        render_path=(
                            rendered_page.render_path
                        ),
                        render_dpi=(
                            rendered_page.dpi
                        ),
                        width=(
                            rendered_page.width
                        ),
                        height=(
                            rendered_page.height
                        ),
                    )

                stored_page_count += 1

            self.repository.commit()

        except Exception as error:
            self.repository.rollback()

            return OfficePageProcessingResult(
                document_id=document.id,
                status="failed",
                page_count=(
                    render_result.page_count
                ),
                rendered_count=(
                    render_result.rendered_count
                ),
                existing_count=(
                    render_result.existing_count
                ),
                stored_page_count=(
                    stored_page_count
                ),
                failed_count=(
                    failed_count + 1
                ),
                error=str(error),
            )

        if failed_count > 0:
            status = "partial"

        elif (
            stored_page_count
            == render_result.page_count
            and stored_page_count > 0
        ):
            status = "processed"

        else:
            status = "partial"

        return OfficePageProcessingResult(
            document_id=document.id,
            status=status,
            page_count=(
                render_result.page_count
            ),
            rendered_count=(
                render_result.rendered_count
            ),
            existing_count=(
                render_result.existing_count
            ),
            stored_page_count=(
                stored_page_count
            ),
            failed_count=(
                failed_count
            ),
            error=None,
        )