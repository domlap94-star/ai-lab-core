from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.client import Client


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

    def get_read(
        self,
        document_id: int,
    ):
        return (
            self._read_query()
            .filter(Document.id == document_id)
            .first()
        )

    def get_read_page(
        self,
        *,
        search: str | None = None,
        client_id: int | None = None,
        project_id: int | None = None,
        source_type: str | None = None,
        match_status: str | None = None,
        processing_status: str | None = None,
        link_state: str = "ALL",
        content_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list, int]:
        query = self._read_query()
        query = self._apply_read_filters(
            query,
            search=search,
            client_id=client_id,
            project_id=project_id,
            source_type=source_type,
            match_status=match_status,
            processing_status=processing_status,
            link_state=link_state,
            content_type=content_type,
        )

        total = query.order_by(None).count()
        items = (
            query.order_by(
                Document.created_at.desc(),
                Document.id.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, total

    def _read_query(self) -> Query:
        return (
            self.db.query(
                Document.id,
                Document.original_filename,
                Document.content_type,
                Document.file_size,
                Document.source_type,
                Document.client_id,
                Document.project_id,
                Client.name.label("client_name"),
                Document.candidate_id,
                ClientCandidate.name.label("candidate_name"),
                Document.processing_status,
                Document.metadata_status,
                Document.match_status,
                Document.match_confidence,
                Document.captured_at,
                Document.parent_document_id,
                Document.archive_member_path,
                Document.archive_depth,
                Document.created_at,
                Document.updated_at,
            )
            .outerjoin(Client, Client.id == Document.client_id)
            .outerjoin(
                ClientCandidate,
                ClientCandidate.id == Document.candidate_id,
            )
        )

    @staticmethod
    def _apply_read_filters(
        query: Query,
        *,
        search: str | None,
        client_id: int | None,
        project_id: int | None,
        source_type: str | None,
        match_status: str | None,
        processing_status: str | None,
        link_state: str,
        content_type: str | None,
    ) -> Query:
        normalized_search = search.strip() if search else ""

        if normalized_search:
            pattern = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    Document.original_filename.ilike(pattern),
                    Document.archive_member_path.ilike(pattern),
                    Document.content_type.ilike(pattern),
                    Client.name.ilike(pattern),
                    ClientCandidate.name.ilike(pattern),
                )
            )

        if client_id is not None:
            query = query.filter(Document.client_id == client_id)
        if project_id is not None:
            query = query.filter(Document.project_id == project_id)
        if source_type is not None:
            query = query.filter(Document.source_type == source_type)
        if match_status is not None:
            query = query.filter(Document.match_status == match_status)
        if processing_status is not None:
            query = query.filter(
                Document.processing_status == processing_status
            )
        if content_type is not None:
            query = query.filter(Document.content_type == content_type)

        if link_state == "LINKED":
            query = query.filter(Document.client_id.is_not(None))
        elif link_state == "CANDIDATE_ONLY":
            query = query.filter(
                Document.client_id.is_(None),
                Document.candidate_id.is_not(None),
            )
        elif link_state == "UNLINKED":
            query = query.filter(
                Document.client_id.is_(None),
                Document.candidate_id.is_(None),
            )

        return query

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
