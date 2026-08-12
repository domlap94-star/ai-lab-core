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
    """
    Semantic retrieval over DocumentChunk vectors.

    Retrieval Quality 1.0 currently applies:

    1. Qdrant semantic vector search.
    2. Candidate over-fetch.
    3. Explicit low-information filtering.
    4. Conservative document diversity.
    5. Final TOP K selection.

    Vector similarity scores are not modified.
    """

    LOW_INFORMATION_EXACT = {
        "----- message truncated -----",
    }

    CANDIDATE_MULTIPLIER = 3

    MAX_CHUNKS_PER_DOCUMENT = 2

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

        if limit <= 0:
            return []

        self.vector_store.ensure_collection()

        vector = (
            self.embedding_client
            .embed_one(
                query
            )
        )

        candidate_limit = max(
            limit,
            limit
            * self.CANDIDATE_MULTIPLIER,
        )

        hits = self.vector_store.search(
            vector=vector,
            limit=candidate_limit,
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

        document_counts: dict[
            int,
            int,
        ] = {}

        for hit in hits:
            payload = hit.payload

            content = str(
                payload.get(
                    "content",
                    "",
                )
            )

            if self._is_low_information(
                content
            ):
                continue

            document_id_value = int(
                payload[
                    "document_id"
                ]
            )

            current_document_count = (
                document_counts.get(
                    document_id_value,
                    0,
                )
            )

            if (
                current_document_count
                >= self.MAX_CHUNKS_PER_DOCUMENT
            ):
                continue

            results.append(
                SemanticSearchResult(
                    score=hit.score,
                    chunk_id=int(
                        payload[
                            "chunk_id"
                        ]
                    ),
                    document_id=(
                        document_id_value
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
                    content=content,
                )
            )

            document_counts[
                document_id_value
            ] = (
                current_document_count
                + 1
            )

            if len(results) >= limit:
                break

        return results

    @classmethod
    def _is_low_information(
        cls,
        content: str,
    ) -> bool:
        normalized = " ".join(
            content.lower().split()
        )

        if not normalized:
            return True

        if (
            normalized
            in cls.LOW_INFORMATION_EXACT
        ):
            return True

        return False
