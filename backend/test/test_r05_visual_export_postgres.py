from __future__ import annotations

import copy
import hashlib
import importlib
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.database.engine import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.inspection import Inspection  # noqa: E402
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.vision_processing_service import VisionProcessingService  # noqa: E402
from app.services.visual_v2_service import (  # noqa: E402
    VisualV2ContractError,
    VisualV2Service,
)


documents_router = importlib.import_module("app.api.documents.router")
DOCUMENTS_PATH = "/api/v1/documents"


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


@pytest.fixture
def postgres_scoped_approval_case():
    """A real-FK PostgreSQL case A/B with unchanged source bytes."""
    assert_isolated_database(engine, TEST_DATABASE_NAME)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    original_data_dir = settings.data_dir
    created: dict[str, list[int] | int | str | bool] = {
        "clients": [],
        "projects": [],
        "inspections": [],
        "role_created": False,
    }
    with tempfile.TemporaryDirectory(prefix="r05-scope-postgres-") as temporary:
        root = Path(temporary)
        settings.data_dir = str(root)
        image_path = root / "documents" / "scope.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (160, 120), color=(100, 80, 60)).save(image_path, "JPEG")
        checksum = hashlib.sha256(image_path.read_bytes()).hexdigest()
        db = Session()
        supervisor = _Supervisor()
        try:
            role = db.query(Role).filter(Role.name == "Administrator").first()
            if role is None:
                role = Role(name="Administrator", description="Synthetic R05 operator")
                db.add(role)
                db.flush()
                created["role_created"] = True
            created["role_id"] = role.id
            suffix = uuid4().hex[:12]
            actor = User(
                username=f"r05-scope-{suffix}",
                email=f"r05-scope-{suffix}@example.invalid",
                password_hash="synthetic-not-a-real-password-hash",
                role_id=role.id,
                is_active=True,
            )
            db.add(actor)
            clients = [
                Client(client_type="company", name=f"Synthetic Scope {label} {suffix}")
                for label in ("A", "B")
            ]
            db.add_all(clients)
            db.flush()
            created["clients"] = [row.id for row in clients]
            projects = [
                Project(
                    client_id=client.id,
                    name=f"Synthetic Project {label} {suffix}",
                    status="active",
                )
                for client, label in zip(clients, ("A", "B"), strict=True)
            ]
            db.add_all(projects)
            db.flush()
            created["projects"] = [row.id for row in projects]
            inspections = [
                Inspection(
                    client_id=client.id,
                    project_id=project.id,
                    title=f"Synthetic Inspection {label} {suffix}",
                    status="planned",
                )
                for client, project, label in zip(
                    clients, projects, ("A", "B"), strict=True
                )
            ]
            db.add_all(inspections)
            db.flush()
            created["inspections"] = [row.id for row in inspections]
            document = Document(
                filename="scope.jpg",
                original_filename="synthetic-scope.jpg",
                content_type="image/jpeg",
                file_size=image_path.stat().st_size,
                storage_path="documents/scope.jpg",
                checksum_sha256=checksum,
                source_type="manual_upload",
                processing_status="processed",
                vision_auto_eligible=True,
                vision_status="not_evaluated",
                client_id=clients[0].id,
                project_id=projects[0].id,
                inspection_id=inspections[0].id,
            )
            db.add(document)
            db.flush()
            created["document_id"] = document.id
            page = DocumentPage(
                document_id=document.id,
                page_number=1,
                width=160,
                height=120,
                render_path="documents/scope.jpg",
                processing_status="processed",
            )
            db.add(page)
            db.commit()
            created["user_id"] = actor.id
            created["page_id"] = page.id
            service = VisualV2Service(db, supervisor=supervisor, enabled=True)
            resolution = service.ensure(document=document, explicit=True)
            candidate = service.approval_candidate(
                resolution.analysis_job_id,
                actor_user_id=actor.id,
            )
            service.approve_export(
                resolution.analysis_job_id,
                actor_user_id=actor.id,
                expected_package_sha256=candidate["package_sha256"],
                expected_source_sha256={
                    row["source_ref"]: row["final_sha256"]
                    for row in candidate["sources"]
                },
                approval_kind="locally_redacted",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            created["job_id"] = resolution.analysis_job_id
            yield {
                "Session": Session,
                "db": db,
                "service": service,
                "supervisor": supervisor,
                "job_id": resolution.analysis_job_id,
                "document_id": document.id,
                "target_scope": {
                    "client_id": clients[1].id,
                    "project_id": projects[1].id,
                    "inspection_id": inspections[1].id,
                },
            }
        finally:
            settings.data_dir = original_data_dir
            db.rollback()
            cleanup = Session()
            try:
                job_id = created.get("job_id")
                if isinstance(job_id, str):
                    cleanup.query(AnalysisJobSource).filter(
                        AnalysisJobSource.analysis_job_id == job_id
                    ).delete(synchronize_session=False)
                    cleanup.query(AnalysisJob).filter(AnalysisJob.id == job_id).delete(
                        synchronize_session=False
                    )
                page_id = created.get("page_id")
                if isinstance(page_id, int):
                    cleanup.query(DocumentPage).filter(DocumentPage.id == page_id).delete(
                        synchronize_session=False
                    )
                document_id = created.get("document_id")
                if isinstance(document_id, int):
                    cleanup.query(Document).filter(Document.id == document_id).delete(
                        synchronize_session=False
                    )
                inspections = created.get("inspections")
                if isinstance(inspections, list):
                    cleanup.query(Inspection).filter(Inspection.id.in_(inspections)).delete(
                        synchronize_session=False
                    )
                projects = created.get("projects")
                if isinstance(projects, list):
                    cleanup.query(Project).filter(Project.id.in_(projects)).delete(
                        synchronize_session=False
                    )
                clients = created.get("clients")
                if isinstance(clients, list):
                    cleanup.query(Client).filter(Client.id.in_(clients)).delete(
                        synchronize_session=False
                    )
                user_id = created.get("user_id")
                if isinstance(user_id, int):
                    cleanup.query(User).filter(User.id == user_id).delete(
                        synchronize_session=False
                    )
                if created.get("role_created") is True:
                    role_id = created.get("role_id")
                    if isinstance(role_id, int):
                        cleanup.query(Role).filter(Role.id == role_id).delete(
                            synchronize_session=False
                        )
                cleanup.commit()
            finally:
                cleanup.close()
                db.close()


@pytest.mark.parametrize("phase", ["before_claim", "after_claim"])
@pytest.mark.parametrize("field_name", ["client_id", "project_id", "inspection_id"])
def test_r05_a1_real_postgres_scope_change_blocks_old_approval(
    postgres_scoped_approval_case,
    phase: str,
    field_name: str,
) -> None:
    case = postgres_scoped_approval_case
    claimed = None
    if phase == "after_claim":
        claimed = case["service"].claim_approved_export(case["job_id"])
        assert claimed is not None

    other = case["Session"]()
    try:
        document = other.get(Document, case["document_id"])
        setattr(document, field_name, case["target_scope"][field_name])
        other.commit()
    finally:
        other.close()

    if phase == "before_claim":
        assert case["service"].claim_approved_export(case["job_id"]) is None
    else:
        with pytest.raises(
            VisualV2ContractError,
            match="VISUAL_V2_EXPORT_APPROVAL_STALE",
        ):
            case["service"].submit_claimed_export(case["job_id"], claimed)
    assert case["supervisor"].created == []


@pytest.mark.parametrize(
    ("callers", "approval_state"),
    [
        pytest.param(("v2", "v2"), "valid", id="v2-v2-valid"),
        pytest.param(("v1", "v2"), "valid", id="v1-v2-valid"),
        pytest.param(("v1", "v2"), "expired", id="v1-v2-expired"),
    ],
)
def test_r05_a1_concurrent_claims_create_one_handoff(
    request,
    callers,
    approval_state,
) -> None:
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
    actor_id: int | None = None

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
            actor_id = actor.id
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
            if approval_state == "expired":
                job = setup.get(AnalysisJob, job_id)
                signals = copy.deepcopy(job.quality_signals)
                signals["visual_export_approval"]["expires_at"] = (
                    datetime.now(UTC) - timedelta(seconds=1)
                ).isoformat()
                job.quality_signals = signals
                setup.commit()
        finally:
            setup.close()

        def synchronized_stage(service: VisualV2Service, current_job_id: str):
            staged = original_stage(service, current_job_id)
            calls = getattr(local, "calls", 0) + 1
            local.calls = calls
            if calls == 1:
                barrier.wait()
            return staged

        def advance_once(caller: str):
            db = Session()
            try:
                if caller == "v1":
                    return VisionProcessingService(
                        db,
                        supervisor=supervisor,
                    ).advance(
                        document_id,
                        explicit=True,
                        actor_user_id=actor_id,
                    )
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
                results = list(executor.map(advance_once, callers))
        finally:
            VisualV2Service._stage_export = original_stage

        verify = Session()
        try:
            job = verify.get(AnalysisJob, job_id)
            assert len(results) == 2
            for caller, result in zip(callers, results, strict=True):
                if caller == "v1":
                    assert result.document_id == document_id
                else:
                    assert result.analysis_job_id == job_id
            if approval_state == "valid":
                assert len(supervisor.created) == 1
                assert job.external_job_id == "00000000-0000-0000-0000-000000000001"
            else:
                assert supervisor.created == []
                assert job.external_job_id is None
                assert job.error_code == "VISUAL_V2_EXPORT_APPROVAL_EXPIRED"
        finally:
            verify.close()


def test_r05_a1_candidate_first_persists_across_postgres_requests(
    request,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert_isolated_database(engine, TEST_DATABASE_NAME)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    original_data_dir = settings.data_dir
    document_id: int | None = None
    page_id: int | None = None
    user_id: int | None = None
    role_id: int | None = None
    created_role = False
    job_ids: set[str] = set()

    def cleanup() -> None:
        settings.data_dir = original_data_dir
        app.dependency_overrides.pop(get_db, None)
        cleanup_db = Session()
        try:
            if page_id is not None:
                rows = cleanup_db.query(AnalysisJobSource.analysis_job_id).filter(
                    (
                        (AnalysisJobSource.source_entity_type == "Document")
                        & (AnalysisJobSource.source_entity_id == str(document_id))
                    )
                    | (
                        (AnalysisJobSource.source_entity_type == "DocumentPage")
                        & (AnalysisJobSource.source_entity_id == str(page_id))
                    )
                ).all()
                job_ids.update(row[0] for row in rows)
            if job_ids:
                cleanup_db.query(AnalysisJobSource).filter(
                    AnalysisJobSource.analysis_job_id.in_(job_ids)
                ).delete(synchronize_session=False)
                cleanup_db.query(AnalysisJob).filter(
                    AnalysisJob.id.in_(job_ids)
                ).delete(synchronize_session=False)
            if page_id is not None:
                cleanup_db.query(DocumentPage).filter(
                    DocumentPage.id == page_id
                ).delete(synchronize_session=False)
            if document_id is not None:
                cleanup_db.query(Document).filter(
                    Document.id == document_id
                ).delete(synchronize_session=False)
            if user_id is not None:
                cleanup_db.query(User).filter(User.id == user_id).delete(
                    synchronize_session=False
                )
            if created_role and role_id is not None:
                cleanup_db.query(Role).filter(Role.id == role_id).delete(
                    synchronize_session=False
                )
            cleanup_db.commit()
        finally:
            cleanup_db.close()

    request.addfinalizer(cleanup)

    with tempfile.TemporaryDirectory(prefix="r05-candidate-request-") as temporary:
        root = Path(temporary)
        settings.data_dir = str(root)
        image_path = root / "documents" / "candidate-first.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (160, 120), color=(60, 100, 140)).save(
            image_path,
            "JPEG",
        )
        checksum = hashlib.sha256(image_path.read_bytes()).hexdigest()
        setup = Session()
        try:
            role = setup.query(Role).filter(Role.name == "Administrator").first()
            if role is None:
                role = Role(
                    name="Administrator",
                    description="Synthetic R05 candidate operator",
                )
                setup.add(role)
                setup.flush()
                created_role = True
            role_id = role.id
            suffix = uuid4().hex[:12]
            actor = User(
                username=f"r05-candidate-{suffix}",
                email=f"r05-candidate-{suffix}@example.invalid",
                password_hash="synthetic-not-a-real-password-hash",
                role_id=role.id,
                is_active=True,
            )
            setup.add(actor)
            setup.flush()
            user_id = actor.id
            document = Document(
                filename="candidate-first.jpg",
                original_filename="synthetic-candidate-first.jpg",
                content_type="image/jpeg",
                file_size=image_path.stat().st_size,
                storage_path="documents/candidate-first.jpg",
                checksum_sha256=checksum,
                source_type="manual_upload",
                processing_status="processed",
                vision_auto_eligible=True,
                vision_status="not_evaluated",
            )
            setup.add(document)
            setup.flush()
            document_id = document.id
            page = DocumentPage(
                document_id=document.id,
                page_number=1,
                width=160,
                height=120,
                render_path="documents/candidate-first.jpg",
                processing_status="processed",
            )
            setup.add(page)
            setup.flush()
            page_id = page.id
            setup.commit()
            username = actor.username
        finally:
            setup.close()

        request_session_ids: list[int] = []

        def override_db():
            request_db = Session()
            request_session_ids.append(id(request_db))
            try:
                yield request_db
            finally:
                request_db.close()

        app.dependency_overrides[get_db] = override_db
        monkeypatch.setattr(
            documents_router,
            "process_explicit_vision_document",
            lambda _document_id, _actor_user_id=None: None,
        )
        token = create_access_token({"sub": username, "auth_version": 0})
        headers = {"Authorization": f"Bearer {token}"}
        http = TestClient(app)
        try:
            candidate_response = http.post(
                f"{DOCUMENTS_PATH}/{document_id}/vision/export-approval/candidate",
                headers=headers,
            )
            assert candidate_response.status_code == 200
            candidate = candidate_response.json()
            job_ids.add(candidate["analysis_job_id"])

            verify = Session()
            try:
                assert verify.get(AnalysisJob, candidate["analysis_job_id"]) is not None
                assert verify.query(AnalysisJobSource).filter(
                    AnalysisJobSource.analysis_job_id == candidate["analysis_job_id"]
                ).count() == len(candidate["sources"])
            finally:
                verify.close()

            approval_response = http.post(
                f"{DOCUMENTS_PATH}/{document_id}/vision/export-approval",
                headers=headers,
                json={
                    "analysis_job_id": candidate["analysis_job_id"],
                    "package_sha256": candidate["package_sha256"],
                    "source_sha256": {
                        row["source_ref"]: row["final_sha256"]
                        for row in candidate["sources"]
                    },
                    "approval_kind": "locally_redacted",
                    "expires_at": (
                        datetime.now(UTC) + timedelta(hours=1)
                    ).isoformat(),
                },
            )
            assert approval_response.status_code == 200
            assert approval_response.json()["analysis_job_id"] == (
                candidate["analysis_job_id"]
            )
            assert len(request_session_ids) >= 2
            assert request_session_ids[0] != request_session_ids[1]
        finally:
            http.close()
