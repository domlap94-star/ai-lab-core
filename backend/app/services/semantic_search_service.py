from __future__ import annotations

from dataclasses import dataclass

from app.ai.clients.ollama_embedding_client import (
    OllamaEmbeddingClient,
)
from app.services.qdrant_vector_store import (
    QdrantVectorStore,
)


@dataclass(frozen=True)
class SemanticSearchResult:
    score: float

    chunk_id: int
    document_id: int
    chunk_index: int

    page_from: int | None
    page_to: int | None

    client_id: int | None

    filename: str | None
    content_type: str | None

    content_source: str | None
    content: str


class SemanticSearchService:
    def __init__(self) -> None:
        self.embedding_client = (
            OllamaEmbeddingClient()
        )

        self.vector_store = (
            QdrantVectorStore()
        )

    def search(
        self,
        *,
        query: str,
        limit: int = 10,
        client_id: int | None = None,
        document_id: int | None = None,
        content_type: str | None = None,
        score_threshold: float | None = None,
    ) -> list[
        SemanticSearchResult
    ]:
        query = query.strip()

        if not query:
            return []

        self.vector_store.ensure_collection()

        vector = (
            self.embedding_client
            .embed_one(
                query
            )
        )

        hits = self.vector_store.search(
            vector=vector,
            limit=limit,
            client_id=client_id,
            document_id=document_id,
            content_type=content_type,
            score_threshold=(
                score_threshold
            ),
        )

        results: list[
            SemanticSearchResult
        ] = []

        for hit in hits:
            payload = hit.payload

            results.append(
                SemanticSearchResult(
                    score=hit.score,
                    chunk_id=int(
                        payload["chunk_id"]
                    ),
                    document_id=int(
                        payload[
                            "document_id"
                        ]
                    ),
                    chunk_index=int(
                        payload[
                            "chunk_index"
                        ]
                    ),
                    page_from=(
                        payload.get(
                            "page_from"
                        )
                    ),
                    page_to=(
                        payload.get(
                            "page_to"
                        )
                    ),
                    client_id=(
                        payload.get(
                            "client_id"
                        )
                    ),
                    filename=(
                        payload.get(
                            "filename"
                        )
                    ),
                    content_type=(
                        payload.get(
                            "content_type"
                        )
                    ),
                    content_source=(
                        payload.get(
                            "content_source"
                        )
                    ),
                    content=str(
                        payload.get(
                            "content",
                            "",
                        )
                    ),
                )
            )

        return results