from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


class DocumentChunkRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get_by_document(
        self,
        document_id: int,
    ) -> list[DocumentChunk]:
        return (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id
                == document_id
            )
            .order_by(
                DocumentChunk.chunk_index.asc()
            )
            .all()
        )

    def delete_by_document(
        self,
        document_id: int,
    ) -> int:
        return (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id
                == document_id
            )
            .delete(
                synchronize_session=False
            )
        )

    def add(
        self,
        chunk: DocumentChunk,
    ) -> DocumentChunk:
        self.db.add(chunk)
        self.db.flush()

        return chunk

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
