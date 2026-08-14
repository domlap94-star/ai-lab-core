from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentPublicPage, DocumentPublicRead
from app.services.document_service import (
    DocumentContentUnavailableError,
    DocumentService,
)


class DocumentNotFoundError(Exception):
    pass


class DocumentReadService:
    def __init__(self, db: Session) -> None:
        self.repository = DocumentRepository(db)
        self.storage_service = DocumentService(db)

    def get_page(self, **filters) -> DocumentPublicPage:
        items, total = self.repository.get_read_page(**filters)
        return DocumentPublicPage(
            items=[self._to_public(item) for item in items],
            total=total,
            skip=filters["skip"],
            limit=filters["limit"],
        )

    def get_document(self, document_id: int) -> DocumentPublicRead:
        item = self.repository.get_read(document_id)
        if item is None:
            raise DocumentNotFoundError
        return self._to_public(item)

    def get_content(self, document_id: int) -> tuple[Document, Path, str]:
        document = self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError

        path = self.storage_service.get_absolute_storage_path(document)
        if path is None:
            raise DocumentContentUnavailableError(
                "Document content is unavailable."
            )

        filename = DocumentService._sanitize_filename(
            document.original_filename or document.filename or "document.bin"
        )
        return document, path, filename

    @staticmethod
    def _to_public(item) -> DocumentPublicRead:
        return DocumentPublicRead.model_validate(
            dict(item._mapping)
        )
