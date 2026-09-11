from __future__ import annotations

import hashlib
import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource
from app.models.role import Role
from app.models.user import User
from app.services.vision_processing_service import VisionProcessingService


documents_router = importlib.import_module("app.api.documents.router")
PATH = "/api/v1/documents"


@compiles(BigInteger, "sqlite")
def _sqlite_bigint_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


class _Supervisor:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.jobs: dict[str, dict] = {}

    def create_job(self, payload: dict) -> dict:
        self.created.append(payload)
        value = {
            "job_id": f"00000000-0000-0000-0000-{len(self.created):012d}",
            "state": "QUEUED",
            "attempt_count": 0,
        }
        self.jobs[value["job_id"]] = value
        return value

    def get_job(self, job_id: str) -> dict:
        return self.jobs[job_id]

    def cancel_job(self, job_id: str) -> dict:
        return {"job_id": job_id, "state": "CANCELLED"}

    def health(self) -> dict:
        return {"status": "SYNTHETIC_READY"}


@pytest.fixture()
def api_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'r05-api.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Document.__table__,
            DocumentPage.__table__,
            DocumentAsset.__table__,
            Role.__table__,
            User.__table__,
            AnalysisJob.__table__,
            AnalysisJobSource.__table__,
        ],
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "visual_v2_enabled", False)
    db.add_all([
        Role(id=1, name="Administrator", description="Synthetic R05 admin"),
        Role(id=2, name="Operator", description="Synthetic R05 user"),
        User(
            id=1,
            username="r05-api-admin",
            email="r05-api-admin@example.invalid",
            password_hash="synthetic-not-a-real-password-hash",
            role_id=1,
            is_active=True,
        ),
        User(
            id=2,
            username="r05-api-user",
            email="r05-api-user@example.invalid",
            password_hash="synthetic-not-a-real-password-hash",
            role_id=2,
            is_active=True,
        ),
    ])
    image_path = tmp_path / "documents" / "r05.jpg"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (160, 120), color=(40, 90, 130)).save(image_path, "JPEG")
    checksum = hashlib.sha256(image_path.read_bytes()).hexdigest()
    document = Document(
        id=501,
        filename="r05.jpg",
        original_filename="synthetic-r05.jpg",
        content_type="image/jpeg",
        file_size=image_path.stat().st_size,
        storage_path="documents/r05.jpg",
        checksum_sha256=checksum,
        source_type="manual_upload",
        processing_status="processed",
        vision_auto_eligible=True,
        vision_status="not_evaluated",
    )
    db.add(document)
    db.add(DocumentPage(
        id=50101,
        document_id=document.id,
        page_number=1,
        width=160,
        height=120,
        render_path="documents/r05.jpg",
        processing_status="processed",
    ))
    db.commit()

    def override_db():
        request_db = session_factory()
        try:
            yield request_db
        finally:
            request_db.close()

    app.dependency_overrides[get_db] = override_db
    supervisor = _Supervisor()
    monkeypatch.setattr(documents_router, "VisionSupervisorClient", lambda: supervisor)
    background_calls: list[tuple[int, int | None]] = []

    def controlled_background(document_id: int, actor_user_id: int | None = None) -> None:
        background_calls.append((document_id, actor_user_id))
        background_db = session_factory()
        try:
            VisionProcessingService(background_db, supervisor=supervisor).advance(
                document_id,
                explicit=True,
                actor_user_id=actor_user_id,
            )
        finally:
            background_db.close()

    monkeypatch.setattr(
        documents_router,
        "process_explicit_vision_document",
        controlled_background,
    )
    try:
        yield db, supervisor, background_calls
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def _headers(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username, "auth_version": 0})
    return {"Authorization": f"Bearer {token}"}


def test_r05_a1_export_approval_http_auth_scope_and_background(api_case) -> None:
    db, supervisor, background_calls = api_case
    http = TestClient(app)
    analyze_path = f"{PATH}/501/vision/analyze"
    candidate_path = f"{PATH}/501/vision/export-approval/candidate"
    approval_path = f"{PATH}/501/vision/export-approval"

    assert http.post(analyze_path).status_code == 401
    assert http.post(
        analyze_path,
        headers={"Authorization": "Bearer invalid-r05-token"},
    ).status_code == 401
    assert http.get(f"{PATH}/501/vision").status_code == 401
    assert http.post(f"{PATH}/501/analyze").status_code == 401
    requested = http.post(analyze_path, headers=_headers("r05-api-user"))
    assert requested.status_code == 202
    assert background_calls == [(501, 2)]
    assert supervisor.created == []
    db.expire_all()
    assert db.get(Document, 501).vision_status == "pending_auth"
    status_response = http.get(
        f"{PATH}/501/vision",
        headers=_headers("r05-api-user"),
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending_auth"

    assert http.post(candidate_path).status_code == 401
    assert http.post(candidate_path, headers=_headers("r05-api-user")).status_code == 403

    candidate_response = http.post(
        candidate_path,
        headers=_headers("r05-api-admin"),
    )
    assert candidate_response.status_code == 200
    candidate = candidate_response.json()
    assert candidate["sources"][0]["document_id"] == 501
    assert supervisor.created == []

    revoke_path = (
        f"{PATH}/501/vision/export-approval/{candidate['analysis_job_id']}"
    )
    assert http.delete(
        revoke_path,
        headers=_headers("r05-api-user"),
    ).status_code == 403
    revoked = http.delete(revoke_path, headers=_headers("r05-api-admin"))
    assert revoked.status_code == 200
    assert revoked.json()["reason"] == "VISUAL_V2_EXPORT_APPROVAL_REVOKED"
    assert background_calls == [(501, 2)]
    assert supervisor.created == []

    assert http.post(
        approval_path,
        headers=_headers("r05-api-user"),
        json={},
    ).status_code == 403

    forged = http.post(
        approval_path,
        headers=_headers("r05-api-admin"),
        json={
            "analysis_job_id": candidate["analysis_job_id"],
            "package_sha256": "0" * 64,
            "source_sha256": {
                row["source_ref"]: row["final_sha256"]
                for row in candidate["sources"]
            },
            "approval_kind": "locally_redacted",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert forged.status_code == 409
    assert background_calls == [(501, 2)]
    assert supervisor.created == []

    approved = http.post(
        approval_path,
        headers=_headers("r05-api-admin"),
        json={
            "analysis_job_id": candidate["analysis_job_id"],
            "package_sha256": candidate["package_sha256"],
            "source_sha256": {
                row["source_ref"]: row["final_sha256"]
                for row in candidate["sources"]
            },
            "approval_kind": "locally_redacted",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )

    assert approved.status_code == 200
    assert background_calls == [(501, 2), (501, 1)]
    assert len(supervisor.created) == 1
    db.expire_all()
    assert db.query(AnalysisJob).count() == 1
    assert db.get(Document, 501).vision_status == "queued"
    http.close()
