from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

from qdrant_client import QdrantClient

from test.support.database_safety import assert_isolated_database, require_test_database_environment
from test.support.qdrant_safety import assert_test_qdrant_target


TEST_DATABASE_NAME = require_test_database_environment()

from app.database.session import SessionLocal
from app.models.knowledge_base import KnowledgeBaseItem, KnowledgeBasePage
from app.models.user import User
from app.services.knowledge_base_vector_service import KnowledgeBaseVectorService


class SyntheticEmbedding:
    def embed(self, texts: list[str]):
        return SimpleNamespace(embeddings=[self.embed_one(text) for text in texts])

    def embed_one(self, text: str) -> list[float]:
        value = min(1.0, max(0.001, len(text) / 1000.0))
        return [value] + [0.0] * 1023


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    host = os.environ.get("QDRANT_TEST_HOST", "host.docker.internal")
    port = int(os.environ.get("QDRANT_TEST_PORT", "16333"))
    host, port, collection = assert_test_qdrant_target(
        host,
        port,
        f"ai_lab_test_kb_analysis_{uuid4().hex[:8]}",
    )
    client = QdrantClient(host=host, port=port, timeout=30)
    db = SessionLocal()
    item_id = None
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        actor = db.query(User).order_by(User.id).first()
        require(actor is not None, "isolated test actor missing")
        item = KnowledgeBaseItem(
            title="Synthetic vector reference", source="Public fixture", publisher="Fixture",
            version="v1", category="formulas", tags=["synthetic"], status="current",
            original_filename="synthetic.txt", stored_filename=f"{uuid4().hex}.txt",
            content_type="text/plain", file_size=28, storage_path="/tmp/synthetic.txt",
            checksum_sha256="a" * 64, processing_status="processed", processing_method="native_text",
            analysis_status="local_accepted", indexing_status="pending",
            extracted_text="R = U / I. Voltage and current.",
            created_by_user_id=actor.id, updated_by_user_id=actor.id,
        )
        db.add(item); db.flush(); item_id = item.id
        db.add(KnowledgeBasePage(item_id=item.id, page_number=1,
                                 text="R = U / I. Voltage and current.", extraction_method="native_text", confidence=100))
        db.commit(); db.refresh(item)
        service = KnowledgeBaseVectorService(
            db, client=client, embedding_client=SyntheticEmbedding(),
            collection_name=collection, writes_enabled=True,
        )
        require(service.index_item(item) == 1, "source chunk was not indexed")
        require(service.index_item(item) == 1, "idempotent reindex did not replace exact ownership")
        require(client.count(collection, exact=True).count == 1, "reindex created duplicate point")
        rows = service.search("voltage", include_superseded=False)
        require(len(rows) == 1 and rows[0]["knowledge_base_item_id"] == item.id, "isolated vector retrieval failed")
        point = client.scroll(collection, limit=10, with_payload=True)[0][0]
        require(point.payload["source_type"] == "knowledge_base", "source namespace missing")
        require(point.payload["content_kind"] == "source", "derived content was indexed")
        require(point.payload["knowledge_base_item_id"] == item.id, "ownership payload mismatch")
        item.status = "superseded"; db.commit(); service.update_metadata(item)
        require(service.search("voltage", include_superseded=False) == [], "superseded item leaked into default search")
        require(len(service.search("voltage", include_superseded=True)) == 1, "superseded explicit search failed")
        service.delete_item(item.id)
        require(client.count(collection, exact=True).count == 0, "exact ownership delete failed")
        print("KNOWLEDGE_BASE_VECTOR_ISOLATED=PASS")
        print("SOURCE_TYPE_ISOLATION=PASS")
        print("REINDEX_DUPLICATES=0")
    finally:
        if client.collection_exists(collection):
            client.delete_collection(collection)
        if item_id is not None:
            db.query(KnowledgeBasePage).filter(KnowledgeBasePage.item_id == item_id).delete()
            db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.id == item_id).delete()
            db.commit()
        db.close()


if __name__ == "__main__":
    main()
