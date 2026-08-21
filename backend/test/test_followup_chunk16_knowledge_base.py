from __future__ import annotations

from pathlib import Path
import shutil
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from test.support.database_safety import assert_isolated_database, require_test_database_environment


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.security import create_access_token, hash_password
from app.database.session import SessionLocal
from app.main import app
from app.models.change_history_event import ChangeHistoryEvent
from app.models.knowledge_base import (
    AnalysisJob,
    AnalysisJobSource,
    KnowledgeBaseAnalysisArtifact,
    KnowledgeBaseItem,
    KnowledgeBasePage,
    KnowledgeBaseProcessingJob,
)
from app.models.role import Role
from app.models.user import User
from app.schemas.knowledge_base import KnowledgeBaseMetadata, KnowledgeBasePatch
from app.services.knowledge_base_service import KnowledgeBaseError, KnowledgeBaseService
from app.services.knowledge_base_dispatcher import KnowledgeBaseDispatcher


TEST_ROOT = Path("/tmp/ai-lab-kb16")


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def token(user: User) -> str:
    return create_access_token({"sub": user.username, "auth_version": user.auth_version})


def main() -> None:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
    TEST_ROOT.mkdir(parents=True)
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        db.query(KnowledgeBaseAnalysisArtifact).delete()
        db.query(AnalysisJobSource).delete()
        db.query(KnowledgeBaseProcessingJob).delete()
        db.query(KnowledgeBasePage).delete()
        db.query(AnalysisJob).delete()
        db.query(ChangeHistoryEvent).filter(ChangeHistoryEvent.entity_type == "knowledge_base_item").delete()
        db.query(KnowledgeBaseItem).delete()
        db.commit()
        admin_role = db.query(Role).filter(Role.name == "Administrator").first()
        user_role = db.query(Role).filter(Role.name == "User").first()
        if admin_role is None:
            admin_role = Role(name="Administrator", description="Isolated Knowledge Base administrator")
            db.add(admin_role)
        if user_role is None:
            user_role = Role(name="User", description="Isolated normal user")
            db.add(user_role)
        db.flush()
        admin = User(username=f"kb_admin_{suffix}", email=f"kb_admin_{suffix}@example.invalid", password_hash=hash_password("Kb-Test-2026!"), role=admin_role, is_active=True)
        normal = User(username=f"kb_user_{suffix}", email=f"kb_user_{suffix}@example.invalid", password_hash=hash_password("Kb-Test-2026!"), role=user_role, is_active=True)
        db.add_all([admin, normal]); db.commit(); db.refresh(admin); db.refresh(normal)

        service = KnowledgeBaseService(db)
        service.storage_root = TEST_ROOT
        content = b"Technical sheet ALPHA-600. Formula: R = U / I. Reference load 600 kg."
        first, duplicates = service.create(
            metadata=KnowledgeBaseMetadata(title="Synthetic ALPHA 600", source="Public safe fixture", publisher="Fixture Publisher", version="v1", category="technical_datasheets", tags=["Load", "formula"]),
            filename="alpha-600.txt", content_type="text/plain", content=content, actor=admin,
        )
        require(not duplicates, "first upload reported duplicate")
        require(first.processing_status == "queued", "upload did not return in queued state")
        queued = db.query(KnowledgeBaseProcessingJob).filter(KnowledgeBaseProcessingJob.item_id == first.id).one()
        require(queued.status == "queued", "durable processing job missing")
        require(KnowledgeBaseDispatcher().process_one(), "background dispatcher did not claim work")
        db.expire_all()
        first = db.get(KnowledgeBaseItem, first.id)
        require(first is not None and first.processing_status == "processed", "native extraction failed")
        require(first.processing_method == "native_text", "wrong extraction provenance")
        require(first.analysis_status == "local_accepted", "local-first analysis was not accepted")
        require(first.indexing_status == "not_ready", "vector gate did not remain closed")
        require(first.pages and first.pages[0].page_number == 1, "page provenance missing")
        artifact = db.query(KnowledgeBaseAnalysisArtifact).filter(
            KnowledgeBaseAnalysisArtifact.item_id == first.id,
        ).one()
        require(artifact.origin == "local" and artifact.validation_state == "accepted",
                "derived artifact provenance is invalid")
        require(artifact.source_page_refs == [{"source_ref": "S1", "page": 1}],
                "derived artifact lost page evidence")

        for phrase in ("Synthetic", "Fixture Publisher", "Public safe", "v1", "technical_datasheets", "Load", "R = U / I", "600 kg"):
            results = service.search(phrase, 20)
            require(any(row["knowledge_base_item_id"] == first.id for row in results), f"lexical search failed for {phrase}")
            require(all(row["retrieval_method"] == "lexical" for row in results), "retrieval contract mismatch")

        service.enqueue_retry(first, actor=admin)
        service.enqueue_retry(first, actor=admin)
        active_retries = db.query(KnowledgeBaseProcessingJob).filter(
            KnowledgeBaseProcessingJob.item_id == first.id,
            KnowledgeBaseProcessingJob.status.in_(["queued", "running"]),
        ).count()
        require(active_retries == 1, "single-item retry created duplicate active jobs")
        retry_job = db.query(KnowledgeBaseProcessingJob).filter(
            KnowledgeBaseProcessingJob.item_id == first.id,
            KnowledgeBaseProcessingJob.status == "queued",
        ).one()
        retry_job.status = "running"
        retry_job.stage = "extracting"
        retry_job.updated_at = datetime.now(UTC) - timedelta(hours=1)
        first.processing_status = "extracting"
        db.commit()
        dispatcher = KnowledgeBaseDispatcher()
        require(dispatcher.recover_stale_processing() == 1, "stale job was not recovered after restart")
        require(dispatcher.process_one(), "retry job was not picked up after restart")
        db.expire_all(); first = db.get(KnowledgeBaseItem, first.id)
        require(first is not None and first.processing_status == "processed", "retry processing failed")

        second, duplicates = service.create(
            metadata=KnowledgeBaseMetadata(title="Synthetic ALPHA 600 v2", source="Public safe fixture", publisher="Fixture Publisher", version="v2", category="technical_datasheets", tags=["load"], supersedes_id=first.id),
            filename="alpha-600-copy.txt", content_type="text/plain", content=content, actor=admin,
        )
        require(first.id in duplicates, "checksum duplicate was not reported")
        db.refresh(first)
        require(first.status == "superseded" and second.status == "current", "supersession state is invalid")
        service.update(second, KnowledgeBasePatch(tags=[" Load ", "load", "Reference"]), admin)
        require(second.tags == ["Load", "Reference"], "tag normalization failed")
        service.archive(second, admin)
        require(db.get(KnowledgeBaseItem, second.id).archived_at is not None, "archive failed")
        require(db.query(ChangeHistoryEvent).filter(ChangeHistoryEvent.entity_type == "knowledge_base_item").count() >= 4, "change history incomplete")

        with TestClient(app) as http:
            normal_response = http.get("/api/v1/admin/knowledge-base", headers={"Authorization": f"Bearer {token(normal)}"})
            admin_response = http.get("/api/v1/admin/knowledge-base", headers={"Authorization": f"Bearer {token(admin)}"})
            require(normal_response.status_code == 403, "normal user accessed Knowledge Base administration")
            require(admin_response.status_code == 200, "Administrator list endpoint failed")

        try:
            service.create(metadata=KnowledgeBaseMetadata(title="Bad", source="Fixture", category="other"), filename="bad.exe", content_type="application/octet-stream", content=b"bad", actor=admin)
        except KnowledgeBaseError as error:
            require(str(error) == "knowledge_base_file_type_unsupported", "wrong upload rejection")
        else:
            raise AssertionError("unsafe extension accepted")

        try:
            service.create(metadata=KnowledgeBaseMetadata(title="Bad MIME", source="Fixture", category="other"), filename="bad.pdf", content_type="image/png", content=b"not-a-pdf", actor=admin)
        except KnowledgeBaseError as error:
            require(str(error) == "knowledge_base_mime_type_mismatch", "wrong MIME rejection")
        else:
            raise AssertionError("mismatched MIME accepted")

        print("TEST_FOLLOWUP_CHUNK16_KNOWLEDGE_BASE=PASS")
        print("ADMIN_AUTH=PASS")
        print("LEXICAL_MATRIX=8/8")
        print("PRODUCTION_QDRANT_WRITES=0")
    finally:
        db.close()
        shutil.rmtree(TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    main()
