from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.services.document_asset_extraction_service import (
    DocumentAssetExtractionService,
)
from app.services.document_extraction_service import (
    DocumentExtractionService,
)
from app.services.document_legacy_office_service import (
    DocumentLegacyOfficeService,
)
from app.services.document_metadata_service import (
    DocumentMetadataService,
)
from app.services.document_ocr_service import (
    DocumentOCRService,
)
from app.services.document_office_ocr_service import (
    DocumentOfficeOCRService,
)
from app.services.document_office_page_service import (
    DocumentOfficePageService,
)
from app.services.document_page_render_service import (
    DocumentPageRenderService,
)


@dataclass(frozen=True)
class DocumentProcessingResult:
    document_id: int
    status: str
    page_count: int
    native_character_count: int
    ocr_character_count: int
    combined_character_count: int
    metadata_status: str | None = None
    render_status: str | None = None
    error: str | None = None


class DocumentProcessingService:
    MIN_NATIVE_PAGE_TEXT = 40

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

    LEGACY_OFFICE_EXTENSIONS = {
        ".doc",
        ".xls",
    }

    LEGACY_OFFICE_CONTENT_TYPES = {
        "application/msword",
        "application/vnd.ms-excel",
    }

    ASSET_CAPABLE_TEXT_EXTENSIONS = {
        ".xlsx",
    }

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.repository = DocumentRepository(
            db
        )

        self.extraction_service = (
            DocumentExtractionService()
        )

        self.legacy_office_service = (
            DocumentLegacyOfficeService()
        )

        self.ocr_service = (
            DocumentOCRService()
        )

        self.metadata_service = (
            DocumentMetadataService()
        )

        self.render_service = (
            DocumentPageRenderService()
        )

        self.office_page_service = (
            DocumentOfficePageService(
                db
            )
        )

        self.office_ocr_service = (
            DocumentOfficeOCRService(
                db
            )
        )

        self.asset_service = (
            DocumentAssetExtractionService(
                db
            )
        )

    def process_document(
        self,
        *,
        document_id: int,
        ocr_dpi: int = 150,
        render_dpi: int = 150,
        force: bool = False,
    ) -> DocumentProcessingResult:
        document = self.repository.get(
            document_id
        )

        if document is None:
            return self._failed_result(
                document_id=document_id,
                error="Document not found.",
            )

        if not document.storage_path:
            return self._failed_result(
                document_id=document.id,
                error=(
                    "Document has no "
                    "storage path."
                ),
            )

        path = (
            Path(settings.data_dir)
            / document.storage_path
        )

        if not path.exists():
            return self._failed_result(
                document_id=document.id,
                error=(
                    f"File not found: {path}"
                ),
            )

        try:
            self._process_metadata(
                document=document,
                path=path,
                force=force,
            )

            extension = Path(
                document.original_filename
                or document.filename
                or path.name
            ).suffix.lower()

            content_type = (
                document.content_type
                or ""
            ).strip().lower()

            is_pdf = (
                content_type
                == "application/pdf"
                or extension == ".pdf"
            )

            is_image = (
                content_type
                in self.IMAGE_CONTENT_TYPES
                or extension
                in self.IMAGE_EXTENSIONS
            )

            is_legacy_office = (
                extension
                in self.LEGACY_OFFICE_EXTENSIONS
                or content_type
                in self.LEGACY_OFFICE_CONTENT_TYPES
            )

            is_office_renderable = (
                self.office_page_service
                .render_service
                .supports(
                    content_type=(
                        document.content_type
                    ),
                    original_filename=(
                        document.original_filename
                        or document.filename
                    ),
                )
            )

            if (
                not force
                and document.processing_status
                == "processed"
            ):
                if is_pdf:
                    pages = (
                        self.repository
                        .get_pages(
                            document.id
                        )
                    )

                    missing_render = any(
                        not page.render_path
                        for page in pages
                    )

                    if (
                        not pages
                        or missing_render
                    ):
                        return self._process_pdf(
                            document=document,
                            path=path,
                            ocr_dpi=ocr_dpi,
                            render_dpi=render_dpi,
                            force=False,
                        )

                    return self._existing_result(
                        document=document,
                        metadata_status=(
                            document.metadata_status
                        ),
                        render_status="existing",
                    )

                if is_office_renderable:
                    pages = (
                        self.repository
                        .get_pages(
                            document.id
                        )
                    )

                    missing_render = (
                        not pages
                        or any(
                            not page.render_path
                            for page in pages
                        )
                    )

                    incomplete_ocr = (
                        not pages
                        or any(
                            page.processing_status
                            not in {
                                "processed",
                                "no_text",
                            }
                            for page in pages
                        )
                    )

                    if (
                        missing_render
                        or incomplete_ocr
                    ):
                        return (
                            self._process_office_document(
                                document=document,
                                path=path,
                                render_dpi=(
                                    max(
                                        render_dpi,
                                        ocr_dpi,
                                    )
                                ),
                                force=False,
                            )
                        )

                    return self._existing_result(
                        document=document,
                        metadata_status=(
                            document.metadata_status
                        ),
                        render_status="existing",
                    )

                return self._existing_result(
                    document=document,
                    metadata_status=(
                        document.metadata_status
                    ),
                    render_status=None,
                )

            document.processing_status = (
                "extracting"
            )

            document.processing_error = None

            self.repository.update(
                document
            )

            self.repository.commit()

            if is_pdf:
                return self._process_pdf(
                    document=document,
                    path=path,
                    ocr_dpi=ocr_dpi,
                    render_dpi=render_dpi,
                    force=force,
                )

            if is_image:
                return self._process_image(
                    document=document,
                    path=path,
                    force=force,
                )

            if is_office_renderable:
                return (
                    self._process_office_document(
                        document=document,
                        path=path,
                        render_dpi=(
                            max(
                                render_dpi,
                                ocr_dpi,
                            )
                        ),
                        force=force,
                    )
                )

            if is_legacy_office:
                return (
                    self._process_legacy_office_document(
                        document=document,
                        path=path,
                    )
                )

            if (
                extension
                in self.ASSET_CAPABLE_TEXT_EXTENSIONS
            ):
                return (
                    self._process_asset_text_document(
                        document=document,
                        path=path,
                        force=force,
                    )
                )

            return self._process_text_document(
                document=document,
                path=path,
            )

        except Exception as error:
            self.repository.rollback()

            failed_document = (
                self.repository.get(
                    document_id
                )
            )

            if failed_document is not None:
                failed_document.processing_status = (
                    "failed"
                )

                failed_document.processing_error = (
                    str(error)
                )

                self.repository.update(
                    failed_document
                )

                self.repository.commit()

            return self._failed_result(
                document_id=document_id,
                error=str(error),
            )

    def _process_metadata(
        self,
        *,
        document: Document,
        path: Path,
        force: bool,
    ) -> None:
        if (
            not force
            and document.metadata_status
            in {
                "processed",
                "unsupported",
            }
        ):
            return

        result = (
            self.metadata_service.extract(
                path=path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
            )
        )

        document.metadata_status = (
            result.status
        )

        intake_metadata = (
            document.metadata_raw.get("intake")
            if isinstance(document.metadata_raw, dict)
            else None
        )
        document.metadata_raw = dict(result.raw_metadata or {})
        if intake_metadata is not None:
            document.metadata_raw["intake"] = intake_metadata

        document.metadata_normalized = (
            result.normalized_metadata
        )

        document.metadata_error = (
            result.error
        )

        document.metadata_extracted_at = (
            datetime.now(
                timezone.utc
            )
        )

        self.repository.update(
            document
        )

        self.repository.commit()

    def _process_pdf(
        self,
        *,
        document: Document,
        path: Path,
        ocr_dpi: int,
        render_dpi: int,
        force: bool,
    ) -> DocumentProcessingResult:
        if force:
            self.repository.delete_pages(
                document.id
            )

            self.repository.commit()

        render_result = (
            self.render_service.render_pdf(
                document_id=document.id,
                path=path,
                dpi=render_dpi,
                force=force,
            )
        )

        render_pages_by_number = {
            page.page_number: page
            for page in render_result.pages
        }

        native_pages = (
            self._extract_pdf_native_pages(
                path
            )
        )

        ocr_result = (
            self.ocr_service.ocr_document(
                path=path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
                dpi=ocr_dpi,
                max_pages=None,
            )
        )

        ocr_pages_by_number = {
            page.page_number: page
            for page in ocr_result.pages
        }

        total_pages = max(
            len(native_pages),
            len(ocr_result.pages),
            len(render_result.pages),
        )

        combined_document_parts: list[
            str
        ] = []

        native_character_count = 0
        ocr_character_count = 0

        for page_number in range(
            1,
            total_pages + 1,
        ):
            native_text = (
                native_pages[
                    page_number - 1
                ]
                if page_number
                <= len(native_pages)
                else None
            )

            native_text = self._clean_text(
                native_text
            )

            ocr_page = (
                ocr_pages_by_number.get(
                    page_number
                )
            )

            render_page = (
                render_pages_by_number.get(
                    page_number
                )
            )

            ocr_text = self._clean_text(
                ocr_page.text
                if ocr_page is not None
                else None
            )

            native_character_count += len(
                native_text or ""
            )

            ocr_character_count += len(
                ocr_text or ""
            )

            page_errors: list[str] = []

            if (
                ocr_page is not None
                and ocr_page.error
            ):
                page_errors.append(
                    f"OCR: {ocr_page.error}"
                )

            if (
                render_page is not None
                and render_page.error
            ):
                page_errors.append(
                    f"RENDER: "
                    f"{render_page.error}"
                )

            page_processing_status = (
                "failed"
                if (
                    not native_text
                    and not ocr_text
                    and (
                        (
                            ocr_page is not None
                            and ocr_page.status
                            == "failed"
                        )
                        or (
                            render_page
                            is not None
                            and render_page.status
                            == "failed"
                        )
                    )
                )
                else "processed"
            )

            width = None
            height = None

            if render_page is not None:
                width = render_page.width
                height = render_page.height

            elif ocr_page is not None:
                width = ocr_page.width
                height = ocr_page.height

            page = (
                self.repository.upsert_page(
                    document_id=document.id,
                    page_number=page_number,
                    extracted_text=native_text,
                    ocr_text=ocr_text,
                    ocr_confidence=(
                        ocr_page.confidence
                        if ocr_page
                        is not None
                        else None
                    ),
                    width=width,
                    height=height,
                    processing_status=(
                        page_processing_status
                    ),
                    processing_error=(
                        " | ".join(
                            page_errors
                        )
                        if page_errors
                        else None
                    ),
                )
            )

            if render_page is not None:
                page.render_path = (
                    render_page.render_path
                )

                page.render_dpi = (
                    render_page.dpi
                )

            self.repository.db.flush()

            page_block = (
                self._build_page_text(
                    page_number=page_number,
                    native_text=native_text,
                    ocr_text=ocr_text,
                )
            )

            if page_block:
                combined_document_parts.append(
                    page_block
                )

        combined_text = "\n\n".join(
            combined_document_parts
        ).strip()

        if total_pages == 0:
            document.processing_status = (
                "failed"
            )

            document.processing_error = (
                ocr_result.error
                or render_result.error
                or (
                    "No PDF pages could "
                    "be processed."
                )
            )

        else:
            document.processing_status = (
                "processed"
            )

            errors: list[str] = []

            if (
                ocr_result.status
                == "failed"
                and ocr_result.error
            ):
                errors.append(
                    f"OCR: "
                    f"{ocr_result.error}"
                )

            if (
                render_result.status
                in {
                    "failed",
                    "partial",
                }
                and render_result.error
            ):
                errors.append(
                    f"RENDER: "
                    f"{render_result.error}"
                )

            document.processing_error = (
                " | ".join(
                    errors
                )
                if errors
                else None
            )

        document.extracted_text = (
            combined_text
            if combined_text
            else None
        )

        self.repository.update(
            document
        )

        self.repository.commit()

        return DocumentProcessingResult(
            document_id=document.id,
            status=(
                document.processing_status
            ),
            page_count=total_pages,
            native_character_count=(
                native_character_count
            ),
            ocr_character_count=(
                ocr_character_count
            ),
            combined_character_count=len(
                combined_text
            ),
            metadata_status=(
                document.metadata_status
            ),
            render_status=(
                render_result.status
            ),
            error=(
                document.processing_error
            ),
        )

    def _process_office_document(
        self,
        *,
        document: Document,
        path: Path,
        render_dpi: int,
        force: bool,
    ) -> DocumentProcessingResult:
        extension = Path(
            document.original_filename
            or document.filename
            or path.name
        ).suffix.lower()

        content_type = (
            document.content_type
            or ""
        ).strip().lower()

        if force:
            self.repository.delete_pages(
                document.id
            )

            self.repository.commit()

        native_text: str | None = None
        native_status: str | None = None
        native_error: str | None = None

        if (
            extension == ".doc"
            or content_type
            == "application/msword"
        ):
            native_result = (
                self.legacy_office_service
                .extract(
                    path=path,
                    content_type=(
                        document.content_type
                    ),
                    original_filename=(
                        document.original_filename
                    ),
                )
            )

            native_text = self._clean_text(
                native_result.text
            )

            native_status = (
                native_result.status
            )

            native_error = (
                native_result.error
            )

        else:
            native_result = (
                self.extraction_service.extract(
                    path=path,
                    content_type=(
                        document.content_type
                    ),
                    original_filename=(
                        document.original_filename
                    ),
                )
            )

            native_text = self._clean_text(
                native_result.text
            )

            native_status = (
                native_result.status
            )

            native_error = (
                native_result.error
            )

        page_result = (
            self.office_page_service
            .process_document(
                document_id=document.id,
                dpi=render_dpi,
                force=force,
            )
        )

        ocr_result = None

        if (
            page_result.stored_page_count > 0
            and page_result.status
            in {
                "processed",
                "partial",
            }
        ):
            ocr_result = (
                self.office_ocr_service
                .process_document(
                    document_id=document.id,
                    force=force,
                )
            )

        asset_result = (
            self.asset_service
            .extract_document_assets(
                document_id=document.id,
                force=force,
            )
        )

        pages = self.repository.get_pages(
            document.id
        )

        ocr_character_count = sum(
            len(
                page.ocr_text
                or ""
            )
            for page in pages
        )

        native_character_count = len(
            native_text
            or ""
        )

        page_ocr_text = (
            self._build_office_ocr_fallback(
                pages
            )
        )

        final_text = (
            native_text
            or page_ocr_text
        )

        errors: list[str] = []

        if (
            native_status == "failed"
            and native_error
        ):
            errors.append(
                f"NATIVE: {native_error}"
            )

        if (
            page_result.status
            in {
                "failed",
                "partial",
            }
            and page_result.error
        ):
            errors.append(
                f"RENDER: "
                f"{page_result.error}"
            )

        if (
            ocr_result is not None
            and ocr_result.status
            in {
                "failed",
                "partial",
            }
        ):
            if ocr_result.error:
                errors.append(
                    f"OCR: "
                    f"{ocr_result.error}"
                )

            elif (
                ocr_result.failed_count
                > 0
            ):
                errors.append(
                    "OCR: "
                    f"{ocr_result.failed_count} "
                    "page(s) failed."
                )

        if (
            asset_result.status
            in {
                "failed",
                "partial",
            }
        ):
            if asset_result.error:
                errors.append(
                    f"ASSETS: "
                    f"{asset_result.error}"
                )

            elif (
                asset_result.failed_count
                > 0
            ):
                errors.append(
                    "ASSETS: "
                    f"{asset_result.failed_count} "
                    "asset(s) failed."
                )

        has_useful_result = bool(
            final_text
            or pages
            or (
                asset_result.extracted_count
                > 0
            )
            or (
                asset_result.existing_count
                > 0
            )
        )

        if has_useful_result:
            document.processing_status = (
                "processed"
            )
        else:
            document.processing_status = (
                "failed"
            )

        document.processing_error = (
            " | ".join(
                errors
            )
            if errors
            else None
        )

        if (
            document.processing_status
            == "failed"
            and not document.processing_error
        ):
            document.processing_error = (
                "Office document produced "
                "no usable text, pages, "
                "or assets."
            )

        document.extracted_text = (
            final_text
        )

        self.repository.update(
            document
        )

        self.repository.commit()

        return DocumentProcessingResult(
            document_id=document.id,
            status=(
                document.processing_status
            ),
            page_count=len(
                pages
            ),
            native_character_count=(
                native_character_count
            ),
            ocr_character_count=(
                ocr_character_count
            ),
            combined_character_count=len(
                final_text
                or ""
            ),
            metadata_status=(
                document.metadata_status
            ),
            render_status=(
                page_result.status
            ),
            error=(
                document.processing_error
            ),
        )

    def _process_legacy_office_document(
        self,
        *,
        document: Document,
        path: Path,
    ) -> DocumentProcessingResult:
        result = (
            self.legacy_office_service.extract(
                path=path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
            )
        )

        text = self._clean_text(
            result.text
        )

        if result.status == "extracted":
            document.extracted_text = text

            document.processing_status = (
                "processed"
            )

            document.processing_error = None

        elif result.status == "unsupported":
            document.processing_status = (
                "stored"
            )

            document.processing_error = (
                "Unsupported by legacy "
                "Office processor."
            )

        else:
            document.processing_status = (
                "failed"
            )

            document.processing_error = (
                result.error
            )

        self.repository.update(
            document
        )

        self.repository.commit()

        return DocumentProcessingResult(
            document_id=document.id,
            status=(
                document.processing_status
            ),
            page_count=0,
            native_character_count=len(
                text
                or ""
            ),
            ocr_character_count=0,
            combined_character_count=len(
                text
                or ""
            ),
            metadata_status=(
                document.metadata_status
            ),
            render_status=None,
            error=(
                document.processing_error
            ),
        )

    def _process_asset_text_document(
        self,
        *,
        document: Document,
        path: Path,
        force: bool,
    ) -> DocumentProcessingResult:
        result = (
            self.extraction_service.extract(
                path=path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
            )
        )

        text = self._clean_text(
            result.text
        )

        asset_result = (
            self.asset_service
            .extract_document_assets(
                document_id=document.id,
                force=force,
            )
        )

        errors: list[str] = []

        if (
            result.status == "failed"
            and result.error
        ):
            errors.append(
                f"TEXT: {result.error}"
            )

        if (
            asset_result.status
            in {
                "failed",
                "partial",
            }
        ):
            if asset_result.error:
                errors.append(
                    f"ASSETS: "
                    f"{asset_result.error}"
                )

            elif (
                asset_result.failed_count
                > 0
            ):
                errors.append(
                    "ASSETS: "
                    f"{asset_result.failed_count} "
                    "asset(s) failed."
                )

        if (
            result.status == "extracted"
            or text
        ):
            document.processing_status = (
                "processed"
            )

            document.extracted_text = (
                text
            )

        elif (
            asset_result.extracted_count
            > 0
            or asset_result.existing_count
            > 0
        ):
            document.processing_status = (
                "processed"
            )

            document.extracted_text = None

        elif result.status == "unsupported":
            document.processing_status = (
                "stored"
            )

        else:
            document.processing_status = (
                "failed"
            )

        document.processing_error = (
            " | ".join(
                errors
            )
            if errors
            else None
        )

        self.repository.update(
            document
        )

        self.repository.commit()

        return DocumentProcessingResult(
            document_id=document.id,
            status=(
                document.processing_status
            ),
            page_count=0,
            native_character_count=len(
                text
                or ""
            ),
            ocr_character_count=0,
            combined_character_count=len(
                text
                or ""
            ),
            metadata_status=(
                document.metadata_status
            ),
            render_status=None,
            error=(
                document.processing_error
            ),
        )

    def _process_image(
        self,
        *,
        document: Document,
        path: Path,
        force: bool,
    ) -> DocumentProcessingResult:
        if force:
            self.repository.delete_pages(
                document.id
            )

            self.repository.commit()

        result = (
            self.ocr_service.ocr_document(
                path=path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
            )
        )

        page_result = (
            result.pages[0]
            if result.pages
            else None
        )

        ocr_text = self._clean_text(
            page_result.text
            if page_result is not None
            else None
        )

        if page_result is not None:
            self.repository.upsert_page(
                document_id=document.id,
                page_number=1,
                extracted_text=None,
                ocr_text=ocr_text,
                ocr_confidence=(
                    page_result.confidence
                ),
                width=(
                    page_result.width
                ),
                height=(
                    page_result.height
                ),
                processing_status=(
                    "failed"
                    if (
                        page_result.status
                        == "failed"
                    )
                    else "processed"
                ),
                processing_error=(
                    page_result.error
                ),
            )

        document.extracted_text = (
            ocr_text
        )

        if result.status == "failed":
            document.processing_status = (
                "failed"
            )

            document.processing_error = (
                result.error
            )

        else:
            document.processing_status = (
                "processed"
            )

            document.processing_error = None

        self.repository.update(
            document
        )

        self.repository.commit()

        return DocumentProcessingResult(
            document_id=document.id,
            status=(
                document.processing_status
            ),
            page_count=len(
                result.pages
            ),
            native_character_count=0,
            ocr_character_count=len(
                ocr_text
                or ""
            ),
            combined_character_count=len(
                ocr_text
                or ""
            ),
            metadata_status=(
                document.metadata_status
            ),
            render_status=None,
            error=(
                document.processing_error
            ),
        )

    def _process_text_document(
        self,
        *,
        document: Document,
        path: Path,
    ) -> DocumentProcessingResult:
        result = (
            self.extraction_service.extract(
                path=path,
                content_type=(
                    document.content_type
                ),
                original_filename=(
                    document.original_filename
                ),
            )
        )

        text = self._clean_text(
            result.text
        )

        if result.status == "extracted":
            document.extracted_text = text

            document.processing_status = (
                "processed"
            )

            document.processing_error = None

        elif result.status == "requires_ocr":
            document.extracted_text = text

            document.processing_status = (
                "stored"
            )

            document.processing_error = (
                "Current extractor "
                "requires OCR."
            )

        elif result.status == "unsupported":
            document.processing_status = (
                "stored"
            )

            document.processing_error = (
                "Unsupported by current "
                "document processor."
            )

        else:
            document.processing_status = (
                "failed"
            )

            document.processing_error = (
                result.error
            )

        self.repository.update(
            document
        )

        self.repository.commit()

        return DocumentProcessingResult(
            document_id=document.id,
            status=(
                document.processing_status
            ),
            page_count=0,
            native_character_count=len(
                text
                or ""
            ),
            ocr_character_count=0,
            combined_character_count=len(
                text
                or ""
            ),
            metadata_status=(
                document.metadata_status
            ),
            render_status=None,
            error=(
                document.processing_error
            ),
        )

    def _extract_pdf_native_pages(
        self,
        path: Path,
    ) -> list[str | None]:
        try:
            reader = PdfReader(
                str(path)
            )

            if reader.is_encrypted:
                try:
                    result = reader.decrypt(
                        ""
                    )

                    if result == 0:
                        return []

                except Exception:
                    return []

            pages: list[
                str | None
            ] = []

            for page in reader.pages:
                try:
                    text = (
                        page.extract_text()
                        or ""
                    ).strip()

                    pages.append(
                        text
                        if text
                        else None
                    )

                except Exception:
                    pages.append(
                        None
                    )

            return pages

        except Exception:
            return []

    def _build_office_ocr_fallback(
        self,
        pages: list,
    ) -> str | None:
        parts: list[str] = []

        for page in pages:
            text = self._clean_text(
                page.ocr_text
            )

            if not text:
                continue

            parts.append(
                f"[PAGE {page.page_number}]"
            )

            parts.append(
                text
            )

        combined = "\n\n".join(
            parts
        ).strip()

        return (
            combined
            if combined
            else None
        )

    def _build_page_text(
        self,
        *,
        page_number: int,
        native_text: str | None,
        ocr_text: str | None,
    ) -> str | None:
        if (
            not native_text
            and not ocr_text
        ):
            return None

        parts = [
            f"[PAGE {page_number}]"
        ]

        if native_text:
            parts.append(
                "[NATIVE TEXT]"
            )

            parts.append(
                native_text
            )

        if (
            ocr_text
            and self._should_include_ocr_text(
                native_text=native_text,
                ocr_text=ocr_text,
            )
        ):
            parts.append(
                "[OCR TEXT]"
            )

            parts.append(
                ocr_text
            )

        return "\n".join(
            parts
        ).strip()

    def _should_include_ocr_text(
        self,
        *,
        native_text: str | None,
        ocr_text: str,
    ) -> bool:
        if not native_text:
            return True

        if (
            len(native_text)
            < self.MIN_NATIVE_PAGE_TEXT
        ):
            return True

        normalized_native = (
            self._normalize_comparison_text(
                native_text
            )
        )

        normalized_ocr = (
            self._normalize_comparison_text(
                ocr_text
            )
        )

        if not normalized_ocr:
            return False

        if (
            normalized_ocr
            in normalized_native
        ):
            return False

        return True

    def _existing_result(
        self,
        *,
        document: Document,
        metadata_status: str | None,
        render_status: str | None,
    ) -> DocumentProcessingResult:
        pages = (
            self.repository.get_pages(
                document.id
            )
        )

        return DocumentProcessingResult(
            document_id=document.id,
            status="already_processed",
            page_count=len(
                pages
            ),
            native_character_count=sum(
                len(
                    page.extracted_text
                    or ""
                )
                for page in pages
            ),
            ocr_character_count=sum(
                len(
                    page.ocr_text
                    or ""
                )
                for page in pages
            ),
            combined_character_count=len(
                document.extracted_text
                or ""
            ),
            metadata_status=(
                metadata_status
            ),
            render_status=(
                render_status
            ),
            error=None,
        )

    @staticmethod
    def _failed_result(
        *,
        document_id: int,
        error: str,
    ) -> DocumentProcessingResult:
        return DocumentProcessingResult(
            document_id=document_id,
            status="failed",
            page_count=0,
            native_character_count=0,
            ocr_character_count=0,
            combined_character_count=0,
            metadata_status=None,
            render_status=None,
            error=error,
        )

    @staticmethod
    def _normalize_comparison_text(
        value: str,
    ) -> str:
        return "".join(
            value.lower().split()
        )

    @staticmethod
    def _clean_text(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return (
            normalized
            if normalized
            else None
        )
