from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_service import (
    DocumentContentUnavailableError,
    UnsafeDocumentStoragePathError,
    resolve_document_storage_path,
)


FILE_FOUND_NATIVE_TEXT_AVAILABLE = "FILE_FOUND_NATIVE_TEXT_AVAILABLE"
FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE = "FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE"
FILE_FOUND_REQUIRES_OCR = "FILE_FOUND_REQUIRES_OCR"
FILE_FOUND_PROCESSING_PENDING = "FILE_FOUND_PROCESSING_PENDING"
FILE_FOUND_UNSUPPORTED = "FILE_FOUND_UNSUPPORTED"
FILE_NOT_FOUND = "FILE_NOT_FOUND"
FILE_READ_FAILED = "FILE_READ_FAILED"
INTEGRITY_MISMATCH = "INTEGRITY_MISMATCH"

MAX_SELECTED_PAGES = 8
MAX_PAGE_CHARACTERS = 800
MAX_TOTAL_CHARACTERS = 12_000


@dataclass(frozen=True)
class UnifiedDocumentPage:
    page_number: int | None
    text: str
    origin: str


@dataclass(frozen=True)
class UnifiedDocumentContent:
    state: str
    pages: tuple[UnifiedDocumentPage, ...] = ()
    extractor: str | None = None
    character_count: int = 0
    error_code: str | None = None


class UnifiedDocumentContentService:
    """Read-only document content access for bounded Assistant evidence.

    The service never changes Document/DocumentPage state. Persisted extraction is
    preferred; authoritative originals are read only when the cache is empty.
    """

    _STOP_WORDS = {
        "tego", "klienta", "przeanalizuj", "przedstaw", "plik", "pdf",
        "dokument", "dokumentacja", "mowi", "oraz", "jest", "jakie",
    }

    def __init__(
        self,
        db: Session,
        *,
        data_root: Path | None = None,
        extractor: DocumentExtractionService | None = None,
    ) -> None:
        self.db = db
        self.data_root = data_root or Path(settings.data_dir)
        self.extractor = extractor or DocumentExtractionService()
        self._cache: dict[int, UnifiedDocumentContent] = {}

    def access(self, document: Document, *, query: str = "") -> UnifiedDocumentContent:
        content = self._cache.get(document.id)
        if content is None:
            content = self._load(document)
            self._cache[document.id] = content
        if not content.pages:
            return content
        return UnifiedDocumentContent(
            state=content.state,
            pages=self._select_pages(content.pages, query),
            extractor=content.extractor,
            character_count=content.character_count,
            error_code=content.error_code,
        )

    def _load(self, document: Document) -> UnifiedDocumentContent:
        persisted = self.db.query(DocumentPage).filter(
            DocumentPage.document_id == document.id
        ).order_by(DocumentPage.page_number.asc()).all()
        persisted_pages = tuple(
            UnifiedDocumentPage(
                page_number=page.page_number,
                text=self._normalize(page.extracted_text or page.ocr_text or ""),
                origin="persisted_page",
            )
            for page in persisted
            if self._normalize(page.extracted_text or page.ocr_text or "")
        )
        if persisted_pages:
            return UnifiedDocumentContent(
                state=FILE_FOUND_NATIVE_TEXT_AVAILABLE,
                pages=persisted_pages,
                extractor="persisted_page_text",
                character_count=sum(len(page.text) for page in persisted_pages),
            )

        document_text = self._normalize(document.extracted_text or "")
        if document_text:
            return UnifiedDocumentContent(
                state=FILE_FOUND_NATIVE_TEXT_AVAILABLE,
                pages=(UnifiedDocumentPage(None, document_text, "persisted_document"),),
                extractor="persisted_document_text",
                character_count=len(document_text),
            )

        if not document.storage_path:
            state = (
                FILE_FOUND_PROCESSING_PENDING
                if document.processing_status in {"pending", "extracting"}
                else FILE_NOT_FOUND
            )
            return UnifiedDocumentContent(state=state, error_code=state)

        try:
            path = resolve_document_storage_path(
                storage_path=document.storage_path,
                data_root=self.data_root,
            )
        except UnsafeDocumentStoragePathError:
            return UnifiedDocumentContent(
                state=FILE_READ_FAILED,
                error_code="DOCUMENT_STORAGE_PATH_REJECTED",
            )
        except DocumentContentUnavailableError:
            return UnifiedDocumentContent(state=FILE_NOT_FOUND, error_code=FILE_NOT_FOUND)

        if document.checksum_sha256:
            actual = self._sha256(path)
            if actual.casefold() != document.checksum_sha256.strip().casefold():
                return UnifiedDocumentContent(
                    state=INTEGRITY_MISMATCH,
                    error_code="DOCUMENT_STORAGE_INTEGRITY_MISMATCH",
                )

        result = self.extractor.extract(
            path=path,
            content_type=document.content_type,
            original_filename=document.original_filename or document.filename,
        )
        if result.status == "extracted" and result.text:
            pages = tuple(
                UnifiedDocumentPage(page.page_number, self._normalize(page.text), "ephemeral_native")
                for page in result.pages
                if self._normalize(page.text)
            )
            if not pages:
                pages = (
                    UnifiedDocumentPage(None, self._normalize(result.text), "ephemeral_native"),
                )
            return UnifiedDocumentContent(
                state=FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE,
                pages=pages,
                extractor=result.extractor,
                character_count=result.character_count,
            )
        if result.status == "requires_ocr":
            return UnifiedDocumentContent(
                state=FILE_FOUND_REQUIRES_OCR,
                extractor=result.extractor,
                character_count=result.character_count,
                error_code="DOCUMENT_REQUIRES_OCR",
            )
        if result.status == "unsupported":
            return UnifiedDocumentContent(
                state=FILE_FOUND_UNSUPPORTED,
                error_code="DOCUMENT_FORMAT_UNSUPPORTED",
            )
        return UnifiedDocumentContent(
            state=FILE_READ_FAILED,
            error_code="DOCUMENT_NATIVE_EXTRACTION_FAILED",
        )

    def _select_pages(
        self, pages: tuple[UnifiedDocumentPage, ...], query: str
    ) -> tuple[UnifiedDocumentPage, ...]:
        terms = {
            token.casefold()
            for token in re.findall(r"[\wąćęłńóśźż-]{3,}", query or "", re.UNICODE)
            if token.casefold() not in self._STOP_WORDS
        }

        def relevance(page: UnifiedDocumentPage) -> tuple[int, int]:
            folded = page.text.casefold()
            return (-sum(1 for term in terms if term in folded), page.page_number or 0)

        selected = sorted(pages, key=relevance)[:MAX_SELECTED_PAGES]
        remaining = MAX_TOTAL_CHARACTERS
        bounded: list[UnifiedDocumentPage] = []
        for page in selected:
            text = page.text[: min(MAX_PAGE_CHARACTERS, remaining)]
            if not text:
                continue
            bounded.append(UnifiedDocumentPage(page.page_number, text, page.origin))
            remaining -= len(text)
            if remaining <= 0:
                break
        return tuple(bounded)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").split())

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
