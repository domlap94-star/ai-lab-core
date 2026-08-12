from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.document_chunk import (
    DocumentChunk,
)


class DocumentChunkRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get(
        self,
        chunk_id: int,
    ) -> DocumentChunk | None:
        return (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.id
                == chunk_id
            )
            .first()
        )

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

    def get_for_embedding(
        self,
        *,
        limit: int | None = None,
        include_failed: bool = False,
    ) -> list[DocumentChunk]:
        statuses = [
            "pending",
            "stale",
        ]

        if include_failed:
            statuses.append(
                "failed"
            )

        query = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.embedding_status.in_(
                    statuses
                )
            )
            .order_by(
                DocumentChunk.id.asc()
            )
        )

        if limit is not None:
            query = query.limit(
                limit
            )

        return query.all()

    def count_by_embedding_status(
        self,
        status: str,
    ) -> int:
        return (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.embedding_status
                == status
            )
            .count()
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
        self.db.add(
            chunk
        )

        self.db.flush()

        return chunk

    def save(
        self,
        chunk: DocumentChunk,
    ) -> DocumentChunk:
        self.db.add(
            chunk
        )

        self.db.flush()

        return chunk

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()