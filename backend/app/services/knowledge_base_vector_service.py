from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models
from sqlalchemy.orm import Session

from app.ai.clients.ollama_embedding_client import OllamaEmbeddingClient
from app.core.config import settings
from app.models.knowledge_base import KnowledgeBaseItem, KnowledgeBasePage


class KnowledgeBaseVectorGateError(RuntimeError): pass


@dataclass(frozen=True)
class KnowledgeBaseChunk:
    point_id: str
    page_id: int
    page_number: int
    chunk_index: int
    content: str


class KnowledgeBaseVectorService:
    CHUNK_CHARS = 1200
    OVERLAP_CHARS = 150
    NAMESPACE = uuid.UUID("2b14e9f4-eaaf-5eb9-89a9-c958837754a4")

    def __init__(self, db: Session, *, client: QdrantClient | None = None,
                 embedding_client=None, collection_name: str | None = None,
                 writes_enabled: bool | None = None) -> None:
        self.db = db
        self.client = client or QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=60)
        self.embedding = embedding_client or OllamaEmbeddingClient()
        self.collection = collection_name or settings.qdrant_knowledge_base_chunks_collection
        self.writes_enabled = settings.knowledge_base_vector_writes_enabled if writes_enabled is None else writes_enabled
        self.dimensions = settings.embedding_dimensions

    def _require_write(self) -> None:
        if not self.writes_enabled:
            raise KnowledgeBaseVectorGateError("knowledge_base_vector_write_approval_required")

    def ensure_collection(self) -> bool:
        self._require_write()
        if self.client.collection_exists(self.collection):
            info = self.client.get_collection(self.collection)
            vectors = info.config.params.vectors
            if getattr(vectors, "size", None) != self.dimensions or getattr(vectors, "distance", None) != models.Distance.COSINE:
                raise KnowledgeBaseVectorGateError("knowledge_base_vector_collection_incompatible")
            return False
        self.client.create_collection(self.collection, vectors_config=models.VectorParams(size=self.dimensions, distance=models.Distance.COSINE))
        return True

    def chunks(self, item: KnowledgeBaseItem) -> list[KnowledgeBaseChunk]:
        result: list[KnowledgeBaseChunk] = []
        pages = self.db.query(KnowledgeBasePage).filter(KnowledgeBasePage.item_id == item.id).order_by(KnowledgeBasePage.page_number).all()
        for page in pages:
            text = " ".join((page.text or "").split())
            start = 0; index = 0
            while start < len(text):
                content = text[start:start + self.CHUNK_CHARS].strip()
                if content:
                    key = f"{item.id}:{page.id}:{index}:{item.checksum_sha256}"
                    result.append(KnowledgeBaseChunk(str(uuid.uuid5(self.NAMESPACE, key)), page.id, page.page_number, index, content))
                if start + self.CHUNK_CHARS >= len(text): break
                start += self.CHUNK_CHARS - self.OVERLAP_CHARS; index += 1
        return result

    def index_item(self, item: KnowledgeBaseItem) -> int:
        self._require_write(); self.ensure_collection()
        chunks = self.chunks(item)
        vectors = self.embedding.embed([chunk.content for chunk in chunks]).embeddings if chunks else []
        self.delete_item(item.id)
        points = [models.PointStruct(id=chunk.point_id, vector=vector, payload={
            "source_type": "knowledge_base", "content_kind": "source",
            "knowledge_base_item_id": item.id, "knowledge_base_page_id": chunk.page_id,
            "source_file": item.original_filename, "page": chunk.page_number,
            "chunk_index": chunk.chunk_index, "status": item.status, "version": item.version,
            "category": item.category, "checksum_sha256": item.checksum_sha256,
            "embedding_model": settings.embedding_model, "embedding_version": settings.embedding_version,
            "content": chunk.content,
        }) for chunk, vector in zip(chunks, vectors, strict=True)]
        if points: self.client.upsert(self.collection, points=points, wait=True)
        return len(points)

    def delete_item(self, item_id: int) -> None:
        self._require_write()
        if not self.client.collection_exists(self.collection): return
        self.client.delete(self.collection, points_selector=models.FilterSelector(filter=models.Filter(must=[
            models.FieldCondition(key="source_type", match=models.MatchValue(value="knowledge_base")),
            models.FieldCondition(key="knowledge_base_item_id", match=models.MatchValue(value=item_id)),
        ])), wait=True)

    def update_metadata(self, item: KnowledgeBaseItem) -> None:
        self._require_write()
        if not self.client.collection_exists(self.collection): return
        selector = models.Filter(must=[
            models.FieldCondition(key="source_type", match=models.MatchValue(value="knowledge_base")),
            models.FieldCondition(key="knowledge_base_item_id", match=models.MatchValue(value=item.id)),
        ])
        self.client.set_payload(self.collection, payload={"status": item.status, "version": item.version, "category": item.category}, points=selector, wait=True)

    def search(self, query: str, *, limit: int = 20, include_superseded: bool = False,
               item_id: int | None = None) -> list[dict]:
        if not self.client.collection_exists(self.collection): return []
        vector = self.embedding.embed_one(query)
        must = [models.FieldCondition(key="source_type", match=models.MatchValue(value="knowledge_base")),
                models.FieldCondition(key="content_kind", match=models.MatchValue(value="source"))]
        if item_id is not None:
            must.append(models.FieldCondition(
                key="knowledge_base_item_id", match=models.MatchValue(value=item_id)
            ))
        if not include_superseded: must.append(models.FieldCondition(key="status", match=models.MatchValue(value="current")))
        response = self.client.query_points(collection_name=self.collection, query=vector,
            query_filter=models.Filter(must=must), limit=limit, with_payload=True)
        rows = []
        for point in response.points:
            payload = point.payload or {}
            item = self.db.get(KnowledgeBaseItem, int(payload["knowledge_base_item_id"]))
            if item is None or item.archived_at is not None: continue
            rows.append({"knowledge_base_item_id": item.id, "title": item.title, "publisher": item.publisher,
                "version": item.version, "effective_date": item.effective_date, "category": item.category,
                "status": item.status, "source_file": item.original_filename, "page": payload.get("page"),
                "excerpt": str(payload.get("content") or "")[:500], "retrieval_method": "vector"})
        return rows
