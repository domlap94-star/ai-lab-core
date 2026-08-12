from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import (
    QdrantClient,
    models,
)

from app.core.config import settings


@dataclass(frozen=True)
class VectorSearchHit:
    vector_id: str
    score: float
    payload: dict[str, Any]


class QdrantVectorStore:
    def __init__(self) -> None:
        self.collection_name = (
            settings
            .qdrant_document_chunks_collection
        )

        self.dimensions = (
            settings.embedding_dimensions
        )

        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=60,
        )

    def ensure_collection(
        self,
    ) -> bool:
        if self.client.collection_exists(
            self.collection_name
        ):
            info = self.client.get_collection(
                self.collection_name
            )

            vectors = (
                info.config.params.vectors
            )

            size = getattr(
                vectors,
                "size",
                None,
            )

            if (
                size is not None
                and size != self.dimensions
            ):
                raise RuntimeError(
                    "Existing Qdrant collection "
                    "has incompatible vector size: "
                    f"expected={self.dimensions}, "
                    f"actual={size}."
                )

            return False

        self.client.create_collection(
            collection_name=(
                self.collection_name
            ),
            vectors_config=(
                models.VectorParams(
                    size=self.dimensions,
                    distance=(
                        models.Distance.COSINE
                    ),
                )
            ),
        )

        return True

    def count(
        self,
    ) -> int:
        result = self.client.count(
            collection_name=(
                self.collection_name
            ),
            exact=True,
        )

        return result.count

    def upsert(
        self,
        *,
        points: list[
            models.PointStruct
        ],
    ) -> None:
        if not points:
            return

        self.client.upsert(
            collection_name=(
                self.collection_name
            ),
            points=points,
            wait=True,
        )

    def delete_all(
        self,
    ) -> None:
        if self.client.collection_exists(
            self.collection_name
        ):
            self.client.delete_collection(
                collection_name=(
                    self.collection_name
                )
            )

    def search(
        self,
        *,
        vector: list[float],
        limit: int = 10,
        client_id: int | None = None,
        document_id: int | None = None,
        content_type: str | None = None,
        score_threshold: float | None = None,
    ) -> list[VectorSearchHit]:
        must_conditions: list[
            models.Condition
        ] = []

        if client_id is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="client_id",
                    match=models.MatchValue(
                        value=client_id
                    ),
                )
            )

        if document_id is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(
                        value=document_id
                    ),
                )
            )

        if content_type is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="content_type",
                    match=models.MatchValue(
                        value=content_type
                    ),
                )
            )

        query_filter = None

        if must_conditions:
            query_filter = models.Filter(
                must=must_conditions
            )

        response = self.client.query_points(
            collection_name=(
                self.collection_name
            ),
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
            score_threshold=(
                score_threshold
            ),
        )

        return [
            VectorSearchHit(
                vector_id=str(
                    point.id
                ),
                score=float(
                    point.score
                ),
                payload=dict(
                    point.payload
                    or {}
                ),
            )
            for point in response.points
        ]