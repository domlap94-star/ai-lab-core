from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from qdrant_client import models
from sqlalchemy.orm import Session

from app.ai.clients.ollama_embedding_client import (
    OllamaEmbeddingClient,
)
from app.core.config import settings
from app.models.document_chunk import (
    DocumentChunk,
)
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.qdrant_vector_store import (
    QdrantVectorStore,
)


@dataclass(frozen=True)
class EmbeddingProcessingResult:
    status: str
    selected_count: int
    embedded_count: int
    failed_count: int
    qdrant_points: int
    model: str
    dimensions: int
    error: str | None = None


class EmbeddingService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.repository = (
            DocumentChunkRepository(
                db
            )
        )

        self.embedding_client = (
            OllamaEmbeddingClient()
        )

        self.vector_store = (
            QdrantVectorStore()
        )

        self.batch_size = (
            settings.embedding_batch_size
        )

        self.model = (
            settings.embedding_model
        )

        self.embedding_version = (
            settings.embedding_version
        )

        self.dimensions = (
            settings.embedding_dimensions
        )

    def embed_pending(
        self,
        *,
        limit: int | None = None,
        include_failed: bool = False,
    ) -> EmbeddingProcessingResult:
        try:
            self.vector_store.ensure_collection()

            chunks = (
                self.repository
                .get_for_embedding(
                    limit=limit,
                    include_failed=(
                        include_failed
                    ),
                )
            )

            if not chunks:
                return EmbeddingProcessingResult(
                    status="existing",
                    selected_count=0,
                    embedded_count=0,
                    failed_count=0,
                    qdrant_points=(
                        self.vector_store.count()
                    ),
                    model=self.model,
                    dimensions=self.dimensions,
                    error=None,
                )

            embedded_count = 0
            failed_count = 0

            for start in range(
                0,
                len(chunks),
                self.batch_size,
            ):
                batch = chunks[
                    start:
                    start + self.batch_size
                ]

                try:
                    self._embed_batch(
                        batch
                    )

                    embedded_count += len(
                        batch
                    )

                except Exception as error:
                    self.db.rollback()

                    failed_count += len(
                        batch
                    )

                    error_message = str(
                        error
                    )

                    for chunk in batch:
                        db_chunk = (
                            self.repository.get(
                                chunk.id
                            )
                        )

                        if db_chunk is None:
                            continue

                        db_chunk.embedding_status = (
                            "failed"
                        )

                        db_chunk.embedding_error = (
                            error_message
                        )

                        self.repository.save(
                            db_chunk
                        )

                    self.repository.commit()

            status = (
                "embedded"
                if failed_count == 0
                else "partial"
            )

            return EmbeddingProcessingResult(
                status=status,
                selected_count=len(
                    chunks
                ),
                embedded_count=(
                    embedded_count
                ),
                failed_count=(
                    failed_count
                ),
                qdrant_points=(
                    self.vector_store.count()
                ),
                model=self.model,
                dimensions=self.dimensions,
                error=None,
            )

        except Exception as error:
            self.db.rollback()

            return EmbeddingProcessingResult(
                status="failed",
                selected_count=0,
                embedded_count=0,
                failed_count=0,
                qdrant_points=0,
                model=self.model,
                dimensions=self.dimensions,
                error=str(error),
            )

    def _embed_batch(
        self,
        chunks: list[
            DocumentChunk
        ],
    ) -> None:
        texts = [
            chunk.content
            for chunk in chunks
        ]

        response = (
            self.embedding_client.embed(
                texts
            )
        )

        points: list[
            models.PointStruct
        ] = []

        for chunk, vector in zip(
            chunks,
            response.embeddings,
            strict=True,
        ):
            document = (
                chunk.document
            )

            filename = (
                document.original_filename
                or document.filename
            )

            payload = {
                "chunk_id": chunk.id,
                "document_id": (
                    chunk.document_id
                ),
                "chunk_index": (
                    chunk.chunk_index
                ),
                "page_from": (
                    chunk.page_from
                ),
                "page_to": (
                    chunk.page_to
                ),
                "source_type": (
                    chunk.source_type
                ),
                "content_source": (
                    chunk.content_source
                ),
                "content_hash": (
                    chunk.content_hash
                ),
                "chunking_version": (
                    chunk.chunking_version
                ),
                "embedding_version": (
                    self.embedding_version
                ),
                "client_id": (
                    document.client_id
                ),
                "candidate_id": (
                    document.candidate_id
                ),
                "filename": filename,
                "content_type": (
                    document.content_type
                ),
                "content": (
                    chunk.content
                ),
            }

            points.append(
                models.PointStruct(
                    id=chunk.id,
                    vector=vector,
                    payload=payload,
                )
            )

        self.vector_store.upsert(
            points=points
        )

        now = datetime.now(
            UTC
        )

        for chunk in chunks:
            chunk.embedding_status = (
                "embedded"
            )

            chunk.embedding_model = (
                self.model
            )

            chunk.embedding_version = (
                self.embedding_version
            )

            chunk.vector_id = str(
                chunk.id
            )

            chunk.embedding_error = None

            chunk.embedded_at = now

            self.repository.save(
                chunk
            )

        self.repository.commit()
