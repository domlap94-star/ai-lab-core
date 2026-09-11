from __future__ import annotations

import hashlib
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from PIL import Image
from sqlalchemy.orm import sessionmaker

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.config import settings  # noqa: E402
from app.database.engine import engine  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.visual_v2_service import VisualV2Service  # noqa: E402


class _Supervisor:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.lock = threading.Lock()

    def create_job(self, payload: dict) -> dict:
        with self.lock:
            self.created.append(payload)
            sequence = len(self.created)
        return {
            "job_id": f"00000000-0000-0000-0000-{sequence:012d}",
            "state": "QUEUED",
            "attempt_count": 0,
        }

    def get_job(self, job_id: str) -> dict:
        return {"job_id": job_id, "state": "QUEUED", "attempt_count": 0}

    def cancel_job(self, job_id: str) -> dict:
        return {"job_id": job_id, "state": "CANCELLED"}


def test_r05_a1_concurrent_v1_v2_claims_create_one_handoff(request) -> None:
    assert_isolated_database(engine, TEST_DATABASE_NAME)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    supervisor = _Supervisor()
    original_data_dir = settings.data_dir
    original_stage = VisualV2Service._stage_export
    barrier = threading.Barrier(2, timeout=10)
    local = threading.local()
    document_id: int | None = None
    job_id: str | None = None
    created_user_id: int | None = None
    created_role_id: int | None = None

    def cleanup() -> None:
        settings.data_dir = original_data_dir
        if document_id is None:
            return
        cleanup_db = Session()
        try:
            if job_id is not None:
                cleanup_db.query(AnalysisJobSource).filter(
                    AnalysisJobSource.analysis_job_id == job_id
                ).delete(synchronize_session=False)
                cleanup_db.query(AnalysisJob).filter(AnalysisJob.id == job_id).delete(
                    synchronize_session=False
                )
            cleanup_db.query(DocumentPage).filter(
                DocumentPage.document_id == document_id
            ).delete(synchronize_session=False)
            cleanup_db.query(Document).filter(Document.id == document_id).delete(
                synchronize_session=False
            )
            if created_user_id is not None:
                cleanup_db.query(User).filter(User.id == created_user_id).delete(
                    synchronize_session=False
                )
            if created_role_id is not None:
                cleanup_db.query(Role).filter(Role.id == created_role_id).delete(
                    synchronize_session=False
                )
            cleanup_db.commit()
        finally:
            cleanup_db.close()

    request.addfinalizer(cleanup)

    with tempfile.TemporaryDirectory(prefix="r05-shared-handoff-") as temporary:
        root = Path(temporary)
        settings.data_dir = str(root)
        image_path = root / "documents" / "shared.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (160, 120), color=(30, 80, 130)).save(
            image_path,
            "JPEG",
        )
        checksum = hashlib.sha256(image_path.read_bytes()).hexdigest()
        setup = Session()
        try:
            actor = (
                setup.query(User)
                .join(Role, User.role_id == Role.id)
                .filter(User.is_active.is_(True), Role.name == "Administrator")
                .order_by(User.id)
                .first()
            )
            if actor is None:
                role = setup.query(Role).filter(Role.name == "Administrator").first()
                if role is None:
                    role = Role(
                        name="Administrator",
                        description="Synthetic R05 concurrency operator",
                    )
                    setup.add(role)
                    setup.flush()
                    created_role_id = role.id
                suffix = uuid4().hex[:12]
                actor = User(
                    username=f"r05-concurrency-{suffix}",
                    email=f"r05-concurrency-{suffix}@example.invalid",
                    password_hash="synthetic-not-a-real-password-hash",
                    role_id=role.id,
                    is_active=True,
                )
                setup.add(actor)
                setup.flush()
                created_user_id = actor.id
            document = Document(
                filename="shared.jpg",
                original_filename="synthetic-shared.jpg",
                content_type="image/jpeg",
                file_size=image_path.stat().st_size,
                storage_path="documents/shared.jpg",
                checksum_sha256=checksum,
                source_type="manual_upload",
                processing_status="processed",
                vision_auto_eligible=True,
                vision_status="not_evaluated",
            )
            setup.add(document)
            setup.flush()
            document_id = document.id
            setup.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=1,
                    width=160,
                    height=120,
                    render_path="documents/shared.jpg",
                    processing_status="processed",
                )
            )
            setup.commit()
            gate = VisualV2Service(setup, supervisor=supervisor, enabled=True)
            resolution = gate.ensure(
                document=document,
                explicit=True,
                created_by_user_id=actor.id,
            )
            job_id = resolution.analysis_job_id
            candidate = gate.approval_candidate(job_id, actor_user_id=actor.id)
            gate.approve_export(
                job_id,
                actor_user_id=actor.id,
                expected_package_sha256=candidate["package_sha256"],
                expected_source_sha256={
                    row["source_ref"]: row["final_sha256"]
                    for row in candidate["sources"]
                },
                approval_kind="locally_redacted",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        finally:
            setup.close()

        def synchronized_stage(service: VisualV2Service, current_job_id: str):
            staged = original_stage(service, current_job_id)
            calls = getattr(local, "calls", 0) + 1
            local.calls = calls
            if calls == 1:
                barrier.wait()
            return staged

        def advance_once():
            db = Session()
            try:
                return VisualV2Service(
                    db,
                    supervisor=supervisor,
                    enabled=True,
                ).advance(job_id)
            finally:
                db.close()

        VisualV2Service._stage_export = synchronized_stage
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _index: advance_once(), range(2)))
        finally:
            VisualV2Service._stage_export = original_stage

        verify = Session()
        try:
            job = verify.get(AnalysisJob, job_id)
            assert all(result.waiting for result in results)
            assert len(supervisor.created) == 1
            assert job.external_job_id == "00000000-0000-0000-0000-000000000001"
        finally:
            verify.close()
