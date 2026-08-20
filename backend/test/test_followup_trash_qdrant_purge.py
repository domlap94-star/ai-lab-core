from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4

from qdrant_client import models

from test.support.database_safety import assert_isolated_database, require_test_database_environment
from test.support.qdrant_safety import (
    UnsafeTestQdrantCollectionError,
    assert_test_qdrant_collection,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.change_history_event import ChangeHistoryEvent
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.trash_entry import TrashEntry
from app.services.qdrant_vector_store import (
    DocumentVectorReference,
    QdrantDocumentPurgeError,
    QdrantVectorStore,
)
from app.services.trash_lifecycle_service import TrashLifecycleService, TrashPurgeBlockedError


TEST_ROOT = Path("/tmp/ai-lab-trash-qdrant")


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def point(point_id: str, *, document_id: int, chunk_id: int) -> models.PointStruct:
    return models.PointStruct(
        id=int(point_id) if point_id.isdecimal() else point_id,
        vector=[0.01] * settings.embedding_dimensions,
        payload={
            "document_id": document_id,
            "chunk_id": chunk_id,
            "embedding_version": "test-v1",
            "content": "synthetic only",
        },
    )


def reference(point_id: str, chunk_id: int) -> DocumentVectorReference:
    return DocumentVectorReference(
        vector_id=point_id,
        chunk_id=chunk_id,
        embedding_version="test-v1",
    )


def expect_code(code: str, callback) -> None:
    try:
        callback()
    except QdrantDocumentPurgeError as error:
        require(error.code == code, f"Expected {code}, got {error.code}")
    else:
        raise AssertionError(f"Expected Qdrant blocker {code}")


def main() -> None:
    db = SessionLocal()
    assert_isolated_database(db, TEST_DATABASE_NAME)
    try:
        assert_test_qdrant_collection("ai_lab_document_chunks")
    except UnsafeTestQdrantCollectionError:
        pass
    else:
        raise AssertionError("Production Qdrant collection was accepted by test guard")

    suffix = uuid4().hex[:12]
    collection = assert_test_qdrant_collection(f"ai_lab_test_trash_qdrant_{suffix}")
    original_collection = settings.qdrant_document_chunks_collection
    settings.qdrant_document_chunks_collection = collection
    store = QdrantVectorStore()
    require(store.collection_name == collection, "Test collection selection failed")
    created_document_id: int | None = None
    try:
        store.ensure_collection()

        # Exact owner: A is deleted, B is unchanged.
        a_ids = [str(uuid4()), str(uuid4())]
        b_ids = [str(uuid4()), str(uuid4())]
        a_refs = [reference(a_ids[0], 101), reference(a_ids[1], 102)]
        store.upsert(points=[
            point(a_ids[0], document_id=1001, chunk_id=101),
            point(a_ids[1], document_id=1001, chunk_id=102),
            point(b_ids[0], document_id=2002, chunk_id=201),
            point(b_ids[1], document_id=2002, chunk_id=202),
        ])
        before_b = store.client.retrieve(
            collection_name=collection, ids=b_ids, with_payload=True, with_vectors=True
        )
        plan = store.prepare_document_purge(document_id=1001, references=a_refs)
        require(plan.present_vector_ids == tuple(a_ids), "Exact plan is not deterministic")
        require(store.delete_document_points(plan) == 2, "Exact deletion count mismatch")
        require(not store.client.retrieve(collection_name=collection, ids=a_ids), "A points remain")
        retry_plan = store.prepare_document_purge(document_id=1001, references=a_refs)
        require(retry_plan.missing_vector_ids == tuple(a_ids), "Retry did not accept prior exact deletion")
        require(store.delete_document_points(retry_plan) == 0, "Retry repeated external deletion")
        after_b = store.client.retrieve(
            collection_name=collection, ids=b_ids, with_payload=True, with_vectors=True
        )
        require(repr(before_b) == repr(after_b), "Foreign Document B changed")

        # A DB reference pointing at B must fail before any deletion.
        expect_code(
            "qdrant_ownership_mismatch",
            lambda: store.prepare_document_purge(
                document_id=1001,
                references=[reference(b_ids[0], 201)],
            ),
        )
        require(len(store.client.retrieve(collection_name=collection, ids=b_ids)) == 2, "B points deleted")

        # Missing exact IDs are an idempotent prior-delete state; they are never recreated.
        missing_id = str(uuid4())
        missing_plan = store.prepare_document_purge(
            document_id=3003,
            references=[reference(missing_id, 301)],
        )
        require(missing_plan.missing_vector_ids == (missing_id,), "Missing point not classified")
        require(store.delete_document_points(missing_plan) == 0, "Missing point caused a delete")

        # Extra payload-owned points not represented by DB chunks block the whole operation.
        tracked_id, extra_id = str(uuid4()), str(uuid4())
        store.upsert(points=[
            point(tracked_id, document_id=4004, chunk_id=401),
            point(extra_id, document_id=4004, chunk_id=402),
        ])
        expect_code(
            "qdrant_untracked_points_detected",
            lambda: store.prepare_document_purge(
                document_id=4004,
                references=[reference(tracked_id, 401)],
            ),
        )
        require(
            len(store.client.retrieve(collection_name=collection, ids=[tracked_id, extra_id])) == 2,
            "Extra-point blocker deleted data",
        )

        duplicate_id = str(uuid4())
        expect_code(
            "qdrant_duplicate_vector_id",
            lambda: store.prepare_document_purge(
                document_id=5005,
                references=[reference(duplicate_id, 501), reference(duplicate_id, 502)],
            ),
        )

        # Qdrant outage is converted into a typed Trash blocker before bytes or DB chunks change.
        outage_id = str(uuid4())
        store.upsert(points=[point(outage_id, document_id=6006, chunk_id=601)])
        with patch.object(store.client, "retrieve", side_effect=TimeoutError("synthetic timeout")):
            try:
                store.prepare_document_purge(
                    document_id=6006,
                    references=[reference(outage_id, 601)],
                )
            except TimeoutError:
                pass
            else:
                raise AssertionError("Synthetic Qdrant outage did not fail")

        # Full Trash path: exact point deletion precedes content/chunk purge and leaves a tombstone.
        content = b"synthetic vector document"
        relative = Path("documents") / f"trash-qdrant-{suffix}.bin"
        source = TEST_ROOT / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(content)
        document = Document(
            filename=source.name,
            original_filename="synthetic.bin",
            content_type="application/octet-stream",
            file_size=len(content),
            storage_path=str(relative),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            source_type="manual_upload",
            processing_status="processed",
            metadata_status="processed",
            match_status="unmatched",
            extracted_text="synthetic sensitive content",
        )
        db.add(document)
        db.flush()
        created_document_id = document.id
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="synthetic",
            token_count=1,
            character_count=9,
            embedding_status="embedded",
            embedding_version="test-v1",
        )
        db.add(chunk)
        db.flush()
        vector_id = str(chunk.id)
        chunk.vector_id = vector_id
        old = datetime.now(timezone.utc) - timedelta(days=8)
        document.trashed_at = old
        entry = TrashEntry(
            entity_type="document",
            entity_id=document.id,
            state="trashed",
            safe_display_label=f"Dokument #{document.id}",
            trashed_at=old,
            purge_after=old + timedelta(days=7),
            trashed_by_user_id=1,
        )
        db.add(entry)
        db.commit()
        store.upsert(points=[point(vector_id, document_id=document.id, chunk_id=chunk.id)])
        service = TrashLifecycleService(db, data_root=TEST_ROOT, vector_store=store)
        result, moved = service.purge_locked(entry)
        require(result == "purged", "End-to-end purge did not complete")
        db.commit()
        require(not store.client.retrieve(collection_name=collection, ids=[int(vector_id)]), "Vector remains")
        db.expire_all()
        tombstone = db.get(Document, document.id)
        require(tombstone.purged_at is not None and tombstone.extracted_text is None, "Tombstone failed")
        require(db.query(DocumentChunk).filter_by(document_id=document.id).count() == 0, "Chunks remain")
        require(not source.exists(), "Document bytes remain in serving storage")
        if moved:
            shutil.rmtree(moved[0].quarantine.parent, ignore_errors=True)

        print("FOLLOWUP_TRASH_QDRANT_PURGE=PASS")
        print("exact_owner=PASS")
        print("foreign_payload=PASS")
        print("missing_point_idempotency=PASS")
        print("extra_untracked=PASS")
        print("duplicate_vector_id=PASS")
        print("cross_document_protection=PASS")
        print("outage_fail_closed=PASS")
        print("end_to_end_tombstone=PASS")
    finally:
        db.rollback()
        if created_document_id is not None:
            db.query(ChangeHistoryEvent).filter(
                ChangeHistoryEvent.entity_type == "document",
                ChangeHistoryEvent.entity_id == created_document_id,
            ).delete(synchronize_session=False)
            db.query(TrashEntry).filter(
                TrashEntry.entity_type == "document",
                TrashEntry.entity_id == created_document_id,
            ).delete(synchronize_session=False)
            db.query(DocumentChunk).filter(DocumentChunk.document_id == created_document_id).delete(synchronize_session=False)
            db.query(Document).filter(Document.id == created_document_id).delete(synchronize_session=False)
            db.commit()
        db.close()
        assert_test_qdrant_collection(collection)
        if store.client.collection_exists(collection):
            store.client.delete_collection(collection_name=collection)
        settings.qdrant_document_chunks_collection = original_collection
        shutil.rmtree(TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    main()
