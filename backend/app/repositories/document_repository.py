from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.document_page import DocumentPage


class DocumentRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def create(
        self,
        document: Document,
    ) -> Document:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)

        return document

    def get(
        self,
        document_id: int,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.id == document_id,
            )
            .first()
        )

    def get_by_external_id(
        self,
        *,
        source_type: str,
        external_id: str,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.source_type == source_type,
                Document.external_id == external_id,
            )
            .first()
        )

    def get_by_checksum(
        self,
        checksum_sha256: str,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.checksum_sha256
                == checksum_sha256,
            )
            .first()
        )

    def get_archive_child(
        self,
        *,
        parent_document_id: int,
        archive_member_path: str,
    ) -> Document | None:
        return (
            self.db.query(Document)
            .filter(
                Document.parent_document_id
                == parent_document_id,
                Document.archive_member_path
                == archive_member_path,
            )
            .first()
        )

    def get_archive_children(
        self,
        parent_document_id: int,
    ) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(
                Document.parent_document_id
                == parent_document_id,
            )
            .order_by(
                Document.id.asc(),
            )
            .all()
        )

    def find_candidate_by_gmail_message_id(
        self,
        gmail_message_id: str,
    ) -> ClientCandidate | None:
        return (
            self.db.query(ClientCandidate)
            .join(
                CandidateSource,
                CandidateSource.candidate_id
                == ClientCandidate.id,
            )
            .filter(
                CandidateSource.source_type
                == "gmail_message",
                CandidateSource.external_id
                == gmail_message_id,
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
            )
            .first()
        )

    def update(
        self,
        document: Document,
    ) -> Document:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)

        return document

    def update_metadata(
        self,
        *,
        document: Document,
        status: str,
        raw_metadata: dict[str, Any] | None,
        normalized_metadata: dict[str, Any] | None,
        error: str | None,
    ) -> Document:
        document.metadata_status = status
        document.metadata_raw = raw_metadata
        document.metadata_normalized = normalized_metadata
        document.metadata_error = error
        document.metadata_extracted_at = datetime.now(
            UTC
        )

        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)

        return document

    def get_page(
        self,
        *,
        document_id: int,
        page_number: int,
    ) -> DocumentPage | None:
        return (
            self.db.query(DocumentPage)
            .filter(
                DocumentPage.document_id
                == document_id,
                DocumentPage.page_number
                == page_number,
            )
            .first()
        )

    def get_pages(
        self,
        document_id: int,
    ) -> list[DocumentPage]:
        return (
            self.db.query(DocumentPage)
            .filter(
                DocumentPage.document_id
                == document_id,
            )
            .order_by(
                DocumentPage.page_number.asc(),
            )
            .all()
        )

    def upsert_page(
        self,
        *,
        document_id: int,
        page_number: int,
        extracted_text: str | None,
        ocr_text: str | None,
        ocr_confidence: float | None,
        width: int | None,
        height: int | None,
        processing_status: str,
        processing_error: str | None,
        page_type: str | None = None,
        vision_analysis: str | None = None,
        render_path: str | None = None,
        render_dpi: int | None = None,
    ) -> DocumentPage:
        page = self.get_page(
            document_id=document_id,
            page_number=page_number,
        )

        if page is None:
            page = DocumentPage(
                document_id=document_id,
                page_number=page_number,
            )

            self.db.add(page)

        page.extracted_text = extracted_text
        page.ocr_text = ocr_text
        page.ocr_confidence = ocr_confidence
        page.width = width
        page.height = height
        page.processing_status = (
            processing_status
        )
        page.processing_error = (
            processing_error
        )

        if page_type is not None:
            page.page_type = page_type

        if vision_analysis is not None:
            page.vision_analysis = (
                vision_analysis
            )

        if render_path is not None:
            page.render_path = render_path

        if render_dpi is not None:
            page.render_dpi = render_dpi

        self.db.flush()

        return page

    def update_page_render(
        self,
        *,
        document_id: int,
        page_number: int,
        render_path: str,
        render_dpi: int,
        width: int,
        height: int,
    ) -> DocumentPage:
        page = self.get_page(
            document_id=document_id,
            page_number=page_number,
        )

        if page is None:
            page = DocumentPage(
                document_id=document_id,
                page_number=page_number,
                processing_status="pending",
            )

            self.db.add(page)

        page.render_path = render_path
        page.render_dpi = render_dpi
        page.width = width
        page.height = height

        self.db.flush()

        return page

    def update_page_vision(
        self,
        *,
        document_id: int,
        page_number: int,
        page_type: str | None,
        vision_analysis: str | None,
    ) -> DocumentPage:
        page = self.get_page(
            document_id=document_id,
            page_number=page_number,
        )

        if page is None:
            page = DocumentPage(
                document_id=document_id,
                page_number=page_number,
                processing_status="pending",
            )

            self.db.add(page)

        page.page_type = page_type
        page.vision_analysis = vision_analysis

        self.db.flush()

        return page

    def delete_pages(
        self,
        document_id: int,
    ) -> int:
        return (
            self.db.query(DocumentPage)
            .filter(
                DocumentPage.document_id
                == document_id,
            )
            .delete(
                synchronize_session=False,
            )
        )

    def commit(
        self,
    ) -> None:
        self.db.commit()

    def rollback(
        self,
    ) -> None:
        self.db.rollback()