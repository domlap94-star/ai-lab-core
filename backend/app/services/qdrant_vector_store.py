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


@dataclass(frozen=True)
class DocumentVectorReference:
    vector_id: str
    chunk_id: int
    embedding_version: str | None


@dataclass(frozen=True)
class DocumentVectorPurgePlan:
    document_id: int
    expected_vector_ids: tuple[str, ...]
    present_vector_ids: tuple[str, ...]
    missing_vector_ids: tuple[str, ...]


class QdrantDocumentPurgeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class QdrantVectorStore:
    MAX_DOCUMENT_PURGE_POINTS = 10_000

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

    def collection_exists(self) -> bool:
        return self.client.collection_exists(
            self.collection_name
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

    def has_document_points(self, document_id: int) -> bool:
        """Read-only exact ownership check used by fail-closed retention purge."""
        if not self.client.collection_exists(self.collection_name):
            return False
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return bool(points)

    @staticmethod
    def _point_id(value: str) -> int | str:
        normalized = str(value).strip()
        return int(normalized) if normalized.isdecimal() else normalized

    def prepare_document_purge(
        self,
        *,
        document_id: int,
        references: list[DocumentVectorReference],
    ) -> DocumentVectorPurgePlan:
        """Verify the exact DB/Qdrant ownership set without mutating Qdrant."""
        if len(references) > self.MAX_DOCUMENT_PURGE_POINTS:
            raise QdrantDocumentPurgeError("qdrant_point_set_too_large")
        by_vector_id: dict[str, DocumentVectorReference] = {}
        for reference in references:
            vector_id = str(reference.vector_id).strip()
            if not vector_id:
                raise QdrantDocumentPurgeError("qdrant_invalid_vector_id")
            if vector_id in by_vector_id:
                raise QdrantDocumentPurgeError("qdrant_duplicate_vector_id")
            by_vector_id[vector_id] = reference

        if not self.client.collection_exists(self.collection_name):
            raise QdrantDocumentPurgeError("qdrant_collection_unavailable")

        expected_ids = tuple(sorted(by_vector_id, key=lambda value: (len(value), value)))
        present_by_id: dict[str, Any] = {}
        if expected_ids:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[self._point_id(value) for value in expected_ids],
                with_payload=True,
                with_vectors=False,
            )
            present_by_id = {str(point.id): point for point in points}
            for vector_id, point in present_by_id.items():
                reference = by_vector_id.get(vector_id)
                payload = dict(point.payload or {})
                if reference is None:
                    raise QdrantDocumentPurgeError("qdrant_ownership_mismatch")
                try:
                    payload_document_id = int(payload.get("document_id"))
                    payload_chunk_id = int(payload.get("chunk_id"))
                except (TypeError, ValueError):
                    raise QdrantDocumentPurgeError("qdrant_ownership_mismatch") from None
                if payload_document_id != document_id or payload_chunk_id != reference.chunk_id:
                    raise QdrantDocumentPurgeError("qdrant_ownership_mismatch")
                payload_version = payload.get("embedding_version")
                if payload_version is not None and reference.embedding_version is not None:
                    if str(payload_version) != reference.embedding_version:
                        raise QdrantDocumentPurgeError("qdrant_ownership_mismatch")

        owned_point_ids: set[str] = set()
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                ),
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            owned_point_ids.update(str(point.id) for point in points)
            if len(owned_point_ids) > self.MAX_DOCUMENT_PURGE_POINTS:
                raise QdrantDocumentPurgeError("qdrant_point_set_too_large")
            if offset is None:
                break

        untracked = owned_point_ids - set(expected_ids)
        if untracked:
            raise QdrantDocumentPurgeError("qdrant_untracked_points_detected")

        present_ids = tuple(value for value in expected_ids if value in present_by_id)
        missing_ids = tuple(value for value in expected_ids if value not in present_by_id)
        return DocumentVectorPurgePlan(
            document_id=document_id,
            expected_vector_ids=expected_ids,
            present_vector_ids=present_ids,
            missing_vector_ids=missing_ids,
        )

    def delete_document_points(self, plan: DocumentVectorPurgePlan) -> int:
        """Delete and verify only the exact IDs approved by a purge plan."""
        if not plan.present_vector_ids:
            return 0
        point_ids = [self._point_id(value) for value in plan.present_vector_ids]
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )
        remaining = self.client.retrieve(
            collection_name=self.collection_name,
            ids=point_ids,
            with_payload=False,
            with_vectors=False,
        )
        if remaining:
            raise QdrantDocumentPurgeError("qdrant_delete_verification_failed")
        return len(point_ids)

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
