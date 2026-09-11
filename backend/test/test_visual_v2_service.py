from __future__ import annotations

import ast
import copy
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.api.documents.router import analyze_document
from app.database.base import Base
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource
from app.models.role import Role
from app.models.user import User
from app.schemas.vision import VISION_RESULT_SCHEMA
from app.services.visual_v2_service import (
    MAX_VISUAL_SOURCES,
    VISUAL_V2_ANALYSIS_TYPE,
    VISUAL_V2_RESULT_SCHEMA,
    VISUAL_V2_SOURCE_DOMAIN,
    VisualV2ContractError,
    VisualV2Resolution,
    VisualV2Service,
)
from app.services import visual_v2_service as visual_v2_module
from app.services import vision_dispatcher as vision_dispatcher_module
from app.services.vision_processing_service import VisionProcessingService


@compiles(BigInteger, "sqlite")
def _sqlite_bigint_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


class _Supervisor:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.cancelled: list[str] = []
        self.jobs: dict[str, dict] = {}

    def create_job(self, payload: dict) -> dict:
        self.created.append(payload)
        job_id = str(uuid.uuid4())
        value = {"job_id": job_id, "state": "QUEUED", "attempt_count": 0}
        self.jobs[job_id] = value
        return value

    def get_job(self, job_id: str) -> dict:
        return self.jobs[job_id]

    def cancel_job(self, job_id: str) -> dict:
        self.cancelled.append(job_id)
        return {"job_id": job_id, "state": "CANCELLED"}


class _UncertainSupervisor(_Supervisor):
    def create_job(self, payload: dict) -> dict:
        self.created.append(payload)
        raise visual_v2_module.VisionSupervisorUnavailable("synthetic uncertain handoff")


@pytest.fixture()
def visual_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Document.__table__,
            DocumentPage.__table__,
            DocumentAsset.__table__,
            DocumentPreparationJob.__table__,
            Role.__table__,
            User.__table__,
            AnalysisJob.__table__,
            AnalysisJobSource.__table__,
        ],
    )
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "visual_v2_enabled", True)
    db.add(Role(id=1, name="Administrator", description="Synthetic R05 operator"))
    db.add(User(
        id=1,
        username="r05-admin",
        email="r05-admin@example.invalid",
        password_hash="synthetic-not-a-real-password-hash",
        role_id=1,
        is_active=True,
    ))
    db.add(Role(id=2, name="Operator", description="Synthetic unprivileged user"))
    db.add(User(
        id=2,
        username="r05-operator",
        email="r05-operator@example.invalid",
        password_hash="synthetic-not-a-real-password-hash",
        role_id=2,
        is_active=True,
    ))
    db.commit()
    try:
        yield db, tmp_path
    finally:
        db.close()
        engine.dispose()


def _image(root: Path, relative: str, *, exif: bool = False) -> tuple[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 480), color=(20, 80, 120))
    metadata = Image.Exif()
    if exif:
        metadata[0x010E] = "private description"
    image.save(path, format="JPEG", exif=metadata)
    return relative, hashlib.sha256(path.read_bytes()).hexdigest()


def _document(db, root: Path, *, document_id: int = 1, visual: bool = True) -> Document:
    if visual:
        relative, checksum = _image(root, f"documents/{document_id}.jpg")
        document = Document(
            id=document_id,
            filename=f"{document_id}.jpg",
            original_filename=f"customer-original-{document_id}.jpg",
            content_type="image/jpeg",
            file_size=(root / relative).stat().st_size,
            storage_path=relative,
            checksum_sha256=checksum,
            source_type="manual_upload",
            client_id=1,
            processing_status="processed",
        )
        db.add(document)
        db.add(DocumentPage(
            id=document_id * 100,
            document_id=document_id,
            page_number=1,
            width=640,
            height=480,
            render_path=relative,
            processing_status="processed",
        ))
    else:
        relative = f"documents/{document_id}.txt"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("A" * 300, encoding="utf-8")
        document = Document(
            id=document_id,
            filename=f"{document_id}.txt",
            original_filename=f"{document_id}.txt",
            content_type="text/plain",
            file_size=path.stat().st_size,
            storage_path=relative,
            checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_type="manual_upload",
            processing_status="processed",
            extracted_text="A" * 300,
        )
        db.add(document)
    db.commit()
    return document


def _pdf_pages(db, root: Path, count: int = 6) -> Document:
    path = root / "documents/scan.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-synthetic")
    document = Document(
        id=8,
        filename="scan.pdf",
        original_filename="scan.pdf",
        content_type="application/pdf",
        file_size=path.stat().st_size,
        storage_path="documents/scan.pdf",
        checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_type="manual_upload",
        processing_status="processed",
        client_id=1,
    )
    db.add(document)
    for page_number in range(1, count + 1):
        relative, _ = _image(root, f"renders/{page_number}.jpg")
        db.add(DocumentPage(
            id=800 + page_number,
            document_id=8,
            page_number=page_number,
            render_path=relative,
            extracted_text="",
            page_type="scan",
            processing_status="processed",
        ))
    db.commit()
    return document


def _raw_result(job_id: str, *, source_ref: str = "S1", direct: str = "observation") -> dict:
    observations = []
    visible_text = []
    interpretations = []
    if direct == "observation":
        observations = [{"source_ref": source_ref, "text": "Widoczny przekrój warstw."}]
    elif direct == "visible_text":
        visible_text = [{"source_ref": source_ref, "text": "1,8 m"}]
    elif direct == "interpretation":
        interpretations = [{"source_ref": source_ref, "text": "Możliwe osiadanie."}]
    return {
        "schema_version": VISION_RESULT_SCHEMA,
        "job_id": job_id,
        "observations": observations,
        "possible_interpretations": interpretations,
        "uncertainties": [{"source_ref": source_ref, "text": "Skala częściowo zasłonięta."}],
        "visible_text": visible_text,
        "measurements": [{"source_ref": source_ref, "value": 1.8, "unit": "m", "basis": "visible_scale"}],
        "image_quality": [{"source_ref": source_ref, "quality": "good"}],
    }


def _write_output(
    service: VisualV2Service,
    job: AnalysisJob,
    raw: dict,
    source_sha: str | dict[str, str],
    *,
    output_sha256: str | None = None,
) -> None:
    source_hashes = (
        source_sha
        if isinstance(source_sha, dict)
        else {"S1": source_sha}
    )
    job_dir = service.spool_root / "jobs" / job.external_job_id
    (job_dir / "output").mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n"
    (job_dir / "output" / "vision.json").write_text(
        json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (job_dir / "manifest.json").write_text(json.dumps({
        "sources": [
            {"source_ref": ref, "sha256": checksum}
            for ref, checksum in source_hashes.items()
        ],
    }), encoding="utf-8")
    (job_dir / "output" / "result_manifest.json").write_text(json.dumps({
        "source_sha256": source_hashes,
        "output_sha256": (
            output_sha256
            or hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        ),
    }), encoding="utf-8")


def _submitted(service: VisualV2Service, db, document: Document) -> AnalysisJob:
    resolution = service.ensure(document=document)
    assert resolution.state == "queued"
    assert service.advance(resolution.analysis_job_id).state == "awaiting_auth"
    _approve(service, resolution.analysis_job_id)
    service.advance(resolution.analysis_job_id)
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    assert job.external_job_id
    return job


def _approve(service: VisualV2Service, job_id: str) -> None:
    candidate = service.approval_candidate(job_id, actor_user_id=1)
    service.approve_export(
        job_id,
        actor_user_id=1,
        expected_package_sha256=candidate["package_sha256"],
        expected_source_sha256={
            row["source_ref"]: row["final_sha256"]
            for row in candidate["sources"]
        },
        approval_kind="locally_redacted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def test_r05_a1_legacy_v1_unapproved_pixels_do_not_reach_supervisor(visual_db):
    db, root = visual_db
    document = _document(db, root, document_id=70)
    document.vision_auto_eligible = True
    document.vision_status = "not_evaluated"
    db.commit()
    supervisor = _Supervisor()
    service = VisionProcessingService(db, supervisor=supervisor)

    result = service.advance(document.id, explicit=True)

    assert result.status == "pending_auth"
    assert result.worker_status == "AUTH_REQUIRED"
    assert document.vision_error_code == "VISION_EXPORT_APPROVAL_REQUIRED"
    assert supervisor.created == []


def test_r05_a1_legacy_v1_uses_same_exact_byte_approval_and_handoff(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
):
    db, root = visual_db
    monkeypatch.setattr(settings, "visual_v2_enabled", False)
    document = _document(db, root, document_id=71)
    document.vision_auto_eligible = True
    document.vision_status = "not_evaluated"
    db.commit()
    supervisor = _Supervisor()
    legacy = VisionProcessingService(db, supervisor=supervisor)

    assert legacy.advance(document.id, explicit=True).status == "pending_auth"
    job = db.query(AnalysisJob).filter(
        AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
    ).one()
    gate = VisualV2Service(db, supervisor=supervisor, enabled=True)
    candidate = gate.approval_candidate(job.id, actor_user_id=1)
    gate.approve_export(
        job.id,
        actor_user_id=1,
        expected_package_sha256=candidate["package_sha256"],
        expected_source_sha256={
            row["source_ref"]: row["final_sha256"]
            for row in candidate["sources"]
        },
        approval_kind="locally_redacted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    result = legacy.advance(document.id, explicit=True)
    db.expire_all()
    job = db.get(AnalysisJob, job.id)
    _write_output(
        gate,
        job,
        _raw_result(job.external_job_id),
        candidate["sources"][0]["final_sha256"],
    )
    supervisor.jobs[job.external_job_id]["state"] = "COMPLETE"
    completed = legacy.advance(document.id, explicit=True)
    gate.advance(job.id)

    assert result.status == "queued"
    assert completed.status == "complete"
    assert len(supervisor.created) == 1
    assert supervisor.created[0]["sources"][0]["sha256"] == (
        candidate["sources"][0]["final_sha256"]
    )
    assert db.query(AnalysisJob).count() == 1
    page = db.query(DocumentPage).filter(DocumentPage.document_id == document.id).one()
    assert page.vision_status == "complete"
    assert "Widoczny przekrój" in page.vision_analysis


def test_r05_a1_historical_v1_document_requires_explicit_request_and_approval(visual_db):
    db, root = visual_db
    document = _document(db, root, document_id=75)
    document.vision_auto_eligible = False
    document.vision_status = "not_evaluated"
    db.commit()
    supervisor = _Supervisor()
    legacy = VisionProcessingService(db, supervisor=supervisor)

    assert legacy.advance(document.id).status == "not_evaluated"
    assert legacy.advance(document.id, explicit=True).status == "pending_auth"
    assert document.vision_error_code == "VISION_EXPORT_APPROVAL_REQUIRED"
    assert supervisor.created == []


def test_r05_a1_legacy_v1_uncertain_handoff_is_not_sent_twice(visual_db):
    db, root = visual_db
    document = _document(db, root, document_id=72)
    document.vision_auto_eligible = True
    document.vision_status = "not_evaluated"
    db.commit()
    supervisor = _UncertainSupervisor()
    legacy = VisionProcessingService(db, supervisor=supervisor)

    assert legacy.advance(document.id, explicit=True).status == "pending_auth"
    job = db.query(AnalysisJob).one()
    gate = VisualV2Service(db, supervisor=supervisor, enabled=True)
    candidate = gate.approval_candidate(job.id, actor_user_id=1)
    gate.approve_export(
        job.id,
        actor_user_id=1,
        expected_package_sha256=candidate["package_sha256"],
        expected_source_sha256={
            row["source_ref"]: row["final_sha256"]
            for row in candidate["sources"]
        },
        approval_kind="public_safe",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    first = legacy.advance(document.id, explicit=True)
    second = legacy.advance(document.id, explicit=True)

    assert first.status == second.status == "pending_auth"
    assert first.worker_status == second.worker_status == "AUTH_REQUIRED"
    assert document.vision_error_code == "VISION_EXPORT_HANDOFF_UNCERTAIN"
    assert len(supervisor.created) == 1


def test_r05_a1_legacy_v1_restricted_document_never_stages_or_exports(visual_db):
    db, root = visual_db
    document = _document(db, root, document_id=73)
    document.vision_auto_eligible = True
    document.metadata_normalized = {"sensitivity": "restricted_never_external"}
    db.commit()
    supervisor = _Supervisor()

    result = VisionProcessingService(db, supervisor=supervisor).advance(
        document.id,
        explicit=True,
    )

    assert result.status == "failed_permanent"
    assert document.vision_error_code == "VISION_RESTRICTED_NEVER_EXTERNAL"
    assert supervisor.created == []
    assert db.query(AnalysisJob).count() == 0


def test_r05_a1_legacy_dispatcher_does_not_spin_on_approval_wait(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=74)
    document.vision_auto_eligible = True
    document.vision_status = "pending_auth"
    document.vision_error_code = "VISION_EXPORT_APPROVAL_REQUIRED"
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(vision_dispatcher_module, "SessionLocal", factory)

    assert vision_dispatcher_module.VisionDispatcher().next_document_id() is None


def test_r05_a1_explicit_v1_helper_stops_at_approval_without_sleep(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=76)
    document.vision_auto_eligible = True
    document.vision_status = "not_evaluated"
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(vision_dispatcher_module, "SessionLocal", factory)
    monkeypatch.setattr(
        vision_dispatcher_module.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(
            AssertionError("approval wait must not poll for 240 seconds")
        ),
    )

    vision_dispatcher_module.process_explicit_vision_document(document.id, 2)

    db.expire_all()
    assert db.get(Document, document.id).vision_status == "pending_auth"
    assert db.get(Document, document.id).vision_error_code == (
        "VISION_EXPORT_APPROVAL_REQUIRED"
    )


def test_r05_a1_single_legacy_dispatch_iteration_pauses_until_approval(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=77)
    document.vision_auto_eligible = True
    document.vision_status = "not_evaluated"
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(vision_dispatcher_module, "SessionLocal", factory)
    dispatcher = vision_dispatcher_module.VisionDispatcher()

    selected = dispatcher.next_document_id()
    result = vision_dispatcher_module.process_one_vision_document(selected)

    assert selected == document.id
    assert result.status == "pending_auth"
    assert dispatcher.next_document_id() is None


def test_v01_text_only_document_does_not_enqueue_visual(visual_db):
    db, root = visual_db
    document = _document(db, root, visual=False)
    result = VisualV2Service(db, supervisor=_Supervisor()).ensure(document=document)
    assert result.state == "not_required"
    assert db.query(AnalysisJob).count() == 0


def test_v02_image_creates_exact_durable_job_and_binding(visual_db):
    db, root = visual_db
    document = _document(db, root)
    result = VisualV2Service(db, supervisor=_Supervisor()).ensure(document=document)
    assert result.state == "queued"
    job = db.get(AnalysisJob, result.analysis_job_id)
    assert (job.analysis_type, job.source_domain) == (
        VISUAL_V2_ANALYSIS_TYPE,
        VISUAL_V2_SOURCE_DOMAIN,
    )
    source = db.query(AnalysisJobSource).one()
    assert source.source_ref == "V01"
    assert source.checksum_sha256 == document.checksum_sha256


def test_v03_active_fingerprint_is_reused(visual_db):
    db, root = visual_db
    document = _document(db, root)
    service = VisualV2Service(db, supervisor=_Supervisor())
    first = service.ensure(document=document)
    second = service.ensure(document=document, question="Co widać na obrazie?")
    assert first.analysis_job_id == second.analysis_job_id
    assert db.query(AnalysisJob).count() == 1


def test_v03b_accepted_is_reused_but_terminal_failure_gets_new_job(visual_db):
    db, root = visual_db
    document = _document(db, root)
    service = VisualV2Service(db, supervisor=_Supervisor())
    failed = db.get(AnalysisJob, service.ensure(document=document).analysis_job_id)
    failed.status = "review_required"
    failed.decision = "review_required"
    failed.error_code = "VISUAL_V2_EXTERNAL_FAILED"
    db.commit()

    # The production PostgreSQL index is partial and permits a replacement
    # after a terminal row. SQLite omits postgresql_where and materializes a
    # full unique index in this compact unit fixture, so prove the selection
    # boundary first and then remove only the synthetic terminal row.
    assert service._current_job(failed.input_fingerprint) is None
    db.delete(failed)
    db.commit()
    replacement = service.ensure(document=document)
    assert replacement.state == "queued"
    current = db.get(AnalysisJob, replacement.analysis_job_id)
    current.status = "accepted_advanced"
    current.decision = "accepted"
    current.result_payload = {
        "schema_version": VISUAL_V2_RESULT_SCHEMA,
        "analysis_job_id": current.id,
        "input_fingerprint": current.input_fingerprint,
        "evidence": [{
            "kind": "observation",
            "source_ref": "V01",
            "page_number": 1,
            "text": "Widoczny przekrój.",
        }],
        "coverage": {
            "selected_source_count": 1,
            "covered_source_count": 1,
            "complete": True,
        },
    }
    db.commit()

    reused = service.ensure(document=document)
    assert reused.state == "accepted"
    assert reused.analysis_job_id == replacement.analysis_job_id
    assert db.query(AnalysisJob).count() == 1


def test_v04_explicit_page_is_first_and_plan_is_capped(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root)
    result = VisualV2Service(db, supervisor=_Supervisor()).ensure(
        document=document, question="Pokaż obraz na stronie 5"
    )
    job = db.get(AnalysisJob, result.analysis_job_id)
    assert job.request_payload["selected_count"] == MAX_VISUAL_SOURCES
    assert job.request_payload["omitted_count"] == 2
    assert job.request_payload["sources"][0]["page_number"] == 5


def test_v05_transport_uses_only_synthetic_identity_and_filenames(visual_db):
    db, root = visual_db
    document = _document(db, root)
    service = VisualV2Service(db, supervisor=_Supervisor())
    job = db.get(AnalysisJob, service.ensure(document=document).analysis_job_id)
    _, request, _, _ = service._stage(job.id)
    assert request["sources"][0]["source_ref"] == "S1"
    assert request["sources"][0]["document_id"] == 900001
    assert request["sources"][0]["page_number"] is None
    assert request["sources"][0]["asset_id"] is None
    assert request["sources"][0]["incoming_relative_path"].endswith("/S1.jpg")
    serialized = json.dumps(request)
    assert document.original_filename not in serialized


def test_v06_normalization_strips_exif(visual_db):
    db, root = visual_db
    document = _document(db, root)
    source = root / document.storage_path
    image = Image.open(source)
    exif = Image.Exif()
    exif[0x010E] = "private description"
    image.save(source, format="JPEG", exif=exif)
    document.checksum_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    db.commit()
    service = VisualV2Service(db, supervisor=_Supervisor())
    job = db.get(AnalysisJob, service.ensure(document=document).analysis_job_id)
    service._stage(job.id)
    prepared = next((service.spool_root / "incoming").rglob("S1.jpg"))
    with Image.open(prepared) as normalized:
        assert not normalized.getexif()


def test_v07_source_checksum_change_fails_closed(visual_db):
    db, root = visual_db
    document = _document(db, root)
    service = VisualV2Service(db, supervisor=_Supervisor())
    job = db.get(AnalysisJob, service.ensure(document=document).analysis_job_id)
    (root / document.storage_path).write_bytes(b"changed")
    with pytest.raises(VisualV2ContractError, match="SOURCE_SHA_MISMATCH"):
        service._stage(job.id)


@pytest.mark.parametrize("direct", ["observation", "visible_text"])
def test_v08_direct_evidence_is_strictly_validated_and_accepted(visual_db, direct):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    job = _submitted(service, db, document)
    staged = next((service.spool_root / "incoming").rglob("S1.jpg"), None)
    source_sha = (
        hashlib.sha256(staged.read_bytes()).hexdigest()
        if staged else supervisor.created[0]["sources"][0]["sha256"]
    )
    _write_output(service, job, _raw_result(job.external_job_id, direct=direct), source_sha)
    supervisor.jobs[job.external_job_id] = {"job_id": job.external_job_id, "state": "COMPLETE"}
    result = service.advance(job.id)
    assert result.state == "accepted"
    assert result.result_payload["schema_version"] == VISUAL_V2_RESULT_SCHEMA
    assert {item["kind"] for item in result.result_payload["evidence"]} >= {
        direct,
        "measurement",
        "uncertainty",
        "image_quality",
    }


def test_v09_interpretation_only_result_is_rejected(visual_db):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    job = _submitted(service, db, document)
    source_sha = supervisor.created[0]["sources"][0]["sha256"]
    _write_output(service, job, _raw_result(job.external_job_id, direct="interpretation"), source_sha)
    supervisor.jobs[job.external_job_id] = {"job_id": job.external_job_id, "state": "COMPLETE"}
    result = service.advance(job.id)
    assert result.state == "review_required"
    assert result.reason == "VISUAL_V2_SUBSTANTIVE_EVIDENCE_MISSING"


def test_v10_foreign_source_ref_and_output_hash_are_rejected(visual_db):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    job = _submitted(service, db, document)
    source_sha = supervisor.created[0]["sources"][0]["sha256"]
    raw = _raw_result(job.external_job_id, source_ref="S2")
    raw["image_quality"] = [{"source_ref": "S2", "quality": "good"}]
    _write_output(service, job, raw, source_sha)
    supervisor.jobs[job.external_job_id] = {"job_id": job.external_job_id, "state": "COMPLETE"}
    result = service.advance(job.id)
    assert result.state == "review_required"
    assert result.reason == "VISUAL_V2_FOREIGN_SOURCE_REF"


def test_v10b_output_hash_mismatch_is_rejected(visual_db):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    job = _submitted(service, db, document)
    source_sha = supervisor.created[0]["sources"][0]["sha256"]
    _write_output(
        service,
        job,
        _raw_result(job.external_job_id),
        source_sha,
        output_sha256="0" * 64,
    )
    supervisor.jobs[job.external_job_id] = {
        "job_id": job.external_job_id,
        "state": "COMPLETE",
    }
    result = service.advance(job.id)
    assert result.state == "review_required"
    assert result.reason == "VISUAL_V2_OUTPUT_SHA_MISMATCH"


def test_v10c_empty_output_is_rejected(visual_db):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    job = _submitted(service, db, document)
    source_sha = supervisor.created[0]["sources"][0]["sha256"]
    raw = _raw_result(job.external_job_id)
    raw["observations"] = []
    raw["visible_text"] = []
    raw["possible_interpretations"] = []
    raw["uncertainties"] = []
    raw["measurements"] = []
    _write_output(service, job, raw, source_sha)
    supervisor.jobs[job.external_job_id] = {
        "job_id": job.external_job_id,
        "state": "COMPLETE",
    }
    result = service.advance(job.id)
    assert result.state == "review_required"
    assert result.reason == "VISUAL_V2_SUBSTANTIVE_EVIDENCE_MISSING"


def test_v11_restart_poll_reuses_external_job_and_cancel_fences_late_result(visual_db):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    job = _submitted(service, db, document)
    external_id = job.external_job_id
    restarted = VisualV2Service(db, supervisor=supervisor)
    assert restarted.advance(job.id).waiting
    assert len(supervisor.created) == 1
    assert restarted.cancel(job.id)
    assert supervisor.cancelled == [external_id]
    supervisor.jobs[external_id] = {"job_id": external_id, "state": "COMPLETE"}
    assert restarted.advance(job.id).state == "cancelled"


def test_v12_restricted_and_no_raster_fail_without_job(visual_db):
    db, root = visual_db
    document = _document(db, root)
    document.metadata_normalized = {"sensitivity": "restricted_never_external"}
    db.commit()
    service = VisualV2Service(db, supervisor=_Supervisor())
    assert service.ensure(document=document).reason == "VISUAL_V2_RESTRICTED_NEVER_EXTERNAL"
    document.metadata_normalized = None
    document.storage_path = None
    db.query(DocumentPage).delete()
    db.commit()
    assert service.ensure(document=document, explicit=True).reason == "VISUAL_V2_NO_SAFE_RASTER"
    assert db.query(AnalysisJob).count() == 0


def test_v13_current_complete_v1_can_be_locally_reused_without_external_job(visual_db):
    db, root = visual_db
    document = _document(db, root)
    document.vision_status = "complete"
    document.vision_schema_version = VISION_RESULT_SCHEMA
    page = db.query(DocumentPage).one()
    page.vision_analysis = json.dumps({
        "observations": [{"source_ref": "S1", "text": "Widoczna rysa."}],
        "visible_text": [],
    })
    db.commit()
    supervisor = _Supervisor()
    result = VisualV2Service(db, supervisor=supervisor).ensure(document=document)
    assert result.state == "accepted"
    assert result.result_payload["schema_version"] == VISUAL_V2_RESULT_SCHEMA
    assert supervisor.created == []
    assert document.vision_status == "complete"


def test_v14_visual_v2_never_writes_legacy_vision_fields(visual_db):
    db, root = visual_db
    document = _document(db, root)
    before = (
        document.vision_status,
        document.vision_schema_version,
        document.vision_attempt_count,
    )
    VisualV2Service(db, supervisor=_Supervisor()).ensure(document=document)
    db.refresh(document)
    assert (
        document.vision_status,
        document.vision_schema_version,
        document.vision_attempt_count,
    ) == before


def test_h01_h02_h03_manual_full_analysis_is_fast_and_idempotent(visual_db):
    db, root = visual_db
    document = _document(db, root)
    actor = SimpleNamespace(id=None)

    first = analyze_document(document.id, actor=actor, db=db)
    second = analyze_document(document.id, actor=actor, db=db)

    assert first["document_id"] == document.id
    assert first["preparation_job_id"] == second["preparation_job_id"]
    assert first["visual_job_id"] == second["visual_job_id"]
    assert first["visual_state"] == second["visual_state"] == "queued"
    assert db.query(DocumentPreparationJob).count() == 1
    assert db.query(AnalysisJob).filter(
        AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
        AnalysisJob.source_domain == VISUAL_V2_SOURCE_DOMAIN,
    ).count() == 1


def test_visual_dispatcher_rotates_active_jobs_by_last_progress(
    visual_db, monkeypatch: pytest.MonkeyPatch
):
    db, root = visual_db
    first_document = _document(db, root, document_id=31)
    second_document = _document(db, root, document_id=32)
    service = VisualV2Service(db, supervisor=_Supervisor())
    first = service.ensure(document=first_document)
    second = service.ensure(document=second_document)
    first_job = db.get(AnalysisJob, first.analysis_job_id)
    second_job = db.get(AnalysisJob, second.analysis_job_id)
    first_job.last_progress_at = datetime.now(UTC) - timedelta(minutes=2)
    second_job.last_progress_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(visual_v2_module, "SessionLocal", factory)

    assert visual_v2_module._next_visual_job_id() == first.analysis_job_id
    assert visual_v2_module._next_visual_job_id() == second.analysis_job_id


def _complete_multisource(
    service: VisualV2Service,
    supervisor: _Supervisor,
    db,
    document: Document,
    *,
    question: str | None = None,
    observation_refs: tuple[str, ...] = ("S1", "S2", "S3", "S4"),
):
    resolution = service.ensure(document=document, question=question)
    assert service.advance(resolution.analysis_job_id).state == "awaiting_auth"
    _approve(service, resolution.analysis_job_id)
    service.advance(resolution.analysis_job_id)
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    source_hashes = {
        item["source_ref"]: item["sha256"]
        for item in supervisor.created[0]["sources"]
    }
    raw = {
        "schema_version": VISION_RESULT_SCHEMA,
        "job_id": job.external_job_id,
        "observations": [
            {"source_ref": ref, "text": f"Widoczny materiał {ref}."}
            for ref in observation_refs
        ],
        "possible_interpretations": [],
        "uncertainties": [],
        "visible_text": [],
        "measurements": [],
        "image_quality": [
            {"source_ref": ref, "quality": "good"}
            for ref in source_hashes
        ],
    }
    _write_output(service, job, raw, source_hashes)
    supervisor.jobs[job.external_job_id] = {
        "job_id": job.external_job_id,
        "state": "COMPLETE",
    }
    return service.advance(job.id)


def test_v21_multisource_omission_is_partial(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root, count=6)
    supervisor = _Supervisor()
    result = _complete_multisource(
        VisualV2Service(db, supervisor=supervisor), supervisor, db, document
    )

    assert result.state == "accepted"
    assert result.result_payload["coverage"] == {
        "selected_source_count": 4,
        "covered_source_count": 4,
        "omitted_source_count": 2,
        "required_page": None,
        "required_page_covered": False,
        "complete": False,
        "limitation_code": "VISUAL_V2_SOURCE_LIMIT_PARTIAL",
    }


def test_v23_explicit_page_covered_may_continue_with_partial_scope(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root, count=6)
    supervisor = _Supervisor()
    result = _complete_multisource(
        VisualV2Service(db, supervisor=supervisor),
        supervisor,
        db,
        document,
        question="Co widać na stronie 5?",
        observation_refs=("S1",),
    )

    assert result.state == "accepted"
    coverage = result.result_payload["coverage"]
    assert coverage["required_page"] == 5
    assert coverage["required_page_covered"] is True
    assert coverage["complete"] is False
    assert coverage["limitation_code"] == "VISUAL_V2_SOURCE_LIMIT_PARTIAL"


def test_v24_explicit_page_not_covered_fails_closed(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root, count=6)
    supervisor = _Supervisor()
    result = _complete_multisource(
        VisualV2Service(db, supervisor=supervisor),
        supervisor,
        db,
        document,
        question="Co widać na stronie 5?",
        observation_refs=("S2",),
    )

    assert result.state == "review_required"
    assert result.reason == "VISUAL_V2_REQUIRED_PAGE_NOT_COVERED"


def test_v25_single_image_remains_complete(visual_db):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    result = _complete_multisource(
        VisualV2Service(db, supervisor=supervisor),
        supervisor,
        db,
        document,
        observation_refs=("S1",),
    )

    assert result.state == "accepted"
    assert result.result_payload["coverage"] == {
        "selected_source_count": 1,
        "covered_source_count": 1,
        "omitted_source_count": 0,
        "required_page": None,
        "required_page_covered": False,
        "complete": True,
        "limitation_code": None,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"covered_source_count": -1},
        {"selected_source_count": 1, "covered_source_count": 2},
        {"omitted_source_count": 1, "complete": True},
    ],
)
def test_v26_malformed_coverage_is_rejected(visual_db, changes):
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    accepted = _complete_multisource(
        service, supervisor, db, document, observation_refs=("S1",)
    )
    payload = copy.deepcopy(accepted.result_payload)
    payload["coverage"].update(changes)
    malformed = VisualV2Resolution(
        "accepted",
        "VISUAL_V2_ACCEPTED",
        accepted.analysis_job_id,
        payload,
    )

    with pytest.raises(VisualV2ContractError, match="VISUAL_V2_COVERAGE_INVALID"):
        service.assistant_evidence(malformed, document_id=document.id)


def test_v27_explicit_then_broad_reuse_uses_broad_current_scope(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root, count=6)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    explicit = _complete_multisource(
        service,
        supervisor,
        db,
        document,
        question="Co widać na stronie 1?",
    )
    stored_payload = copy.deepcopy(explicit.result_payload)

    broad = service.ensure(document=document)

    assert broad.analysis_job_id == explicit.analysis_job_id
    assert len(supervisor.created) == 1
    assert service.validated_coverage(broad) == {
        "selected_source_count": 4,
        "covered_source_count": 4,
        "omitted_source_count": 2,
        "required_page": None,
        "required_page_covered": False,
        "complete": False,
        "limitation_code": "VISUAL_V2_SOURCE_LIMIT_PARTIAL",
    }
    assert broad.result_payload == stored_payload
    assert broad.result_payload["coverage"]["required_page"] == 1


def test_v28_broad_then_explicit_covered_reuse_uses_explicit_scope(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root, count=6)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    broad = _complete_multisource(service, supervisor, db, document)
    stored_payload = copy.deepcopy(broad.result_payload)

    explicit = service.ensure(document=document, question="Co widać na stronie 1?")
    coverage = service.validated_coverage(
        explicit,
        question="Co widać na stronie 1?",
    )

    assert explicit.analysis_job_id == broad.analysis_job_id
    assert len(supervisor.created) == 1
    assert coverage["required_page"] == 1
    assert coverage["required_page_covered"] is True
    assert coverage["complete"] is False
    assert explicit.result_payload == stored_payload
    assert explicit.result_payload["coverage"]["required_page"] is None


def test_v29_broad_then_explicit_uncovered_reuse_fails_scope_check(visual_db):
    db, root = visual_db
    document = _pdf_pages(db, root, count=6)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    broad = _complete_multisource(
        service,
        supervisor,
        db,
        document,
        observation_refs=("S2",),
    )

    explicit = service.ensure(document=document, question="Co widać na stronie 1?")
    coverage = service.validated_coverage(
        explicit,
        question="Co widać na stronie 1?",
    )

    assert explicit.analysis_job_id == broad.analysis_job_id
    assert len(supervisor.created) == 1
    assert coverage["required_page"] == 1
    assert coverage["required_page_covered"] is False


def test_r04_a3_fake_supervisor_and_spool_are_harness_boundaries(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
):
    db, root = visual_db

    class _ForbiddenRealSupervisor:
        def __init__(self) -> None:
            raise AssertionError("R04_A3_REAL_SUPERVISOR_FORBIDDEN")

    monkeypatch.setattr(
        visual_v2_module,
        "VisionSupervisorClient",
        _ForbiddenRealSupervisor,
    )
    with pytest.raises(AssertionError, match="R04_A3_REAL_SUPERVISOR_FORBIDDEN"):
        VisualV2Service(db)

    service = VisualV2Service(db, supervisor=_Supervisor())
    document = _document(db, root)
    resolution = service.ensure(document=document)
    service.advance(resolution.analysis_job_id)

    assert service.data_root == root.resolve()
    assert service.spool_root.is_relative_to(root.resolve())
    assert all(path.is_relative_to(root.resolve()) for path in service.spool_root.rglob("*"))


def test_r04_a3_visual_dispatcher_start_is_lifespan_only() -> None:
    main_path = Path(__file__).parents[1] / "app" / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    lifespan = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
    )
    lifespan_starts = [
        node
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "start_visual_v2_dispatcher"
    ]
    module_starts = [
        call
        for node in tree.body
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "start_visual_v2_dispatcher"
    ]

    assert len(lifespan_starts) == 1
    assert module_starts == []


def test_r05_a1_disabled_visual_dispatcher_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []

    def _forbidden_create_task(coroutine):
        coroutine.close()
        created.append(coroutine)
        raise AssertionError("R05_A1_DISABLED_DISPATCHER_STARTED")

    assert hasattr(settings, "visual_v2_enabled"), "R05_A1_ACTIVATION_FLAG_MISSING"
    monkeypatch.setattr(settings, "visual_v2_enabled", False)
    monkeypatch.setattr(visual_v2_module.asyncio, "create_task", _forbidden_create_task)

    assert visual_v2_module.start_visual_v2_dispatcher() is None
    assert created == []


def test_r05_a1_disabled_legacy_vision_dispatcher_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []

    def _forbidden_create_task(coroutine):
        coroutine.close()
        created.append(coroutine)
        raise AssertionError("R05_A1_DISABLED_V1_DISPATCHER_STARTED")

    monkeypatch.setattr(settings, "vision_automation_enabled", False)
    monkeypatch.setattr(
        vision_dispatcher_module.asyncio,
        "create_task",
        _forbidden_create_task,
    )

    assert vision_dispatcher_module.start_vision_dispatcher() is None
    assert created == []


@pytest.mark.parametrize(
    ("v1_enabled", "v2_enabled", "expected_tasks"),
    [
        (True, False, ["vision-dispatcher"]),
        (False, True, ["visual-v2-dispatcher"]),
    ],
)
def test_r05_a1_v1_v2_activation_flags_are_independent(
    monkeypatch: pytest.MonkeyPatch,
    v1_enabled: bool,
    v2_enabled: bool,
    expected_tasks: list[str],
) -> None:
    created: list[str] = []

    def _record_task(coroutine, *, name: str):
        coroutine.close()
        created.append(name)
        return object()

    monkeypatch.setattr(settings, "vision_automation_enabled", v1_enabled)
    monkeypatch.setattr(settings, "visual_v2_enabled", v2_enabled)
    monkeypatch.setattr(vision_dispatcher_module.asyncio, "create_task", _record_task)
    monkeypatch.setattr(visual_v2_module.asyncio, "create_task", _record_task)

    vision_dispatcher_module.start_vision_dispatcher()
    visual_v2_module.start_visual_v2_dispatcher()

    assert created == expected_tasks


def test_r05_a1_disabled_service_blocks_ensure_and_direct_advance(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    monkeypatch.setattr(settings, "visual_v2_enabled", False)
    service = VisualV2Service(db, supervisor=supervisor)

    resolution = service.ensure(document=document)

    assert resolution.state == "review_required"
    assert resolution.reason == "VISUAL_V2_RUNTIME_DISABLED"
    assert service.advance(resolution.analysis_job_id).reason == (
        "VISUAL_V2_RUNTIME_DISABLED"
    )
    assert supervisor.created == []


def test_r05_a1_unapproved_pixels_do_not_reach_supervisor(visual_db) -> None:
    db, root = visual_db
    document = _document(db, root)
    image_path = root / document.storage_path
    with Image.open(image_path) as original:
        rendered = original.copy()
    ImageDraw.Draw(rendered).text(
        (20, 20),
        "Jan Testowy, ul. Prywatna 12",
        fill=(255, 255, 255),
    )
    rendered.save(image_path, format="JPEG")
    document.checksum_sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()
    document.metadata_normalized = {"sensitivity": "customer_sanitizable"}
    db.commit()
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)

    resolution = service.ensure(document=document)
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    forged = dict(job.request_payload)
    forged["external_approval"] = {
        "state": "approved",
        "label": "sanitized",
        "actor_user_id": 1,
    }
    job.request_payload = forged
    db.commit()
    blocked = service.advance(resolution.analysis_job_id)

    assert blocked.state == "awaiting_auth"
    assert blocked.reason == "VISUAL_V2_EXPORT_APPROVAL_REQUIRED"
    assert supervisor.created == []


def test_r05_a1_dispatcher_does_not_spin_on_privacy_wait(visual_db, monkeypatch) -> None:
    db, root = visual_db
    document = _document(db, root)
    service = VisualV2Service(db, supervisor=_Supervisor())
    resolution = service.ensure(document=document)
    assert service.advance(resolution.analysis_job_id).reason == (
        "VISUAL_V2_EXPORT_APPROVAL_REQUIRED"
    )
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(visual_v2_module, "SessionLocal", factory)

    assert visual_v2_module._next_visual_job_id() is None


def test_r05_a1_approved_exact_raster_reaches_only_fake_supervisor(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root = visual_db
    monkeypatch.setattr(settings, "vision_automation_enabled", False)
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document, created_by_user_id=2)

    assert service.advance(resolution.analysis_job_id).reason == (
        "VISUAL_V2_EXPORT_APPROVAL_REQUIRED"
    )
    candidate = service.approval_candidate(
        resolution.analysis_job_id,
        actor_user_id=1,
    )
    expected = {
        row["source_ref"]: row["final_sha256"]
        for row in candidate["sources"]
    }
    approved = service.approve_export(
        resolution.analysis_job_id,
        actor_user_id=1,
        expected_package_sha256=candidate["package_sha256"],
        expected_source_sha256=expected,
        approval_kind="locally_redacted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert approved.state == "queued"

    submitted = service.advance(resolution.analysis_job_id)

    assert submitted.waiting
    assert len(supervisor.created) == 1
    request = supervisor.created[0]
    assert set(request) == {"request_key", "sources"}
    assert set(request["sources"][0]) == {
        "source_ref",
        "document_id",
        "page_number",
        "asset_id",
        "sha256",
        "incoming_relative_path",
    }
    assert request["sources"][0]["sha256"] == expected["S1"]
    serialized = json.dumps(request)
    assert document.original_filename not in serialized
    assert document.storage_path not in serialized
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    approval = job.quality_signals["visual_export_approval"]
    assert approval["approved_by_user_id"] == 1
    assert approval["binding"]["package_sha256"] == job.sanitized_package_hash


def test_r05_a1_unprivileged_actor_cannot_approve_or_forge_payload(visual_db) -> None:
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document, created_by_user_id=2)
    candidate = service.approval_candidate(
        resolution.analysis_job_id,
        actor_user_id=1,
    )

    with pytest.raises(VisualV2ContractError, match="VISUAL_V2_APPROVAL_FORBIDDEN"):
        service.approval_candidate(
            resolution.analysis_job_id,
            actor_user_id=2,
        )

    with pytest.raises(VisualV2ContractError, match="VISUAL_V2_APPROVAL_FORBIDDEN"):
        service.approve_export(
            resolution.analysis_job_id,
            actor_user_id=2,
            expected_package_sha256=candidate["package_sha256"],
            expected_source_sha256={
                row["source_ref"]: row["final_sha256"]
                for row in candidate["sources"]
            },
            approval_kind="public_safe",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    assert service.advance(resolution.analysis_job_id).reason == (
        "VISUAL_V2_EXPORT_APPROVAL_REQUIRED"
    )
    assert supervisor.created == []


def test_r05_a1_revoked_and_foreign_scope_approvals_fail_closed(visual_db) -> None:
    db, root = visual_db
    first_document = _document(db, root, document_id=41)
    second_document = _document(db, root, document_id=42)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    first = service.ensure(document=first_document)
    second = service.ensure(document=second_document)
    _approve(service, first.analysis_job_id)
    first_job = db.get(AnalysisJob, first.analysis_job_id)
    second_job = db.get(AnalysisJob, second.analysis_job_id)
    second_job.quality_signals = copy.deepcopy(first_job.quality_signals)
    db.commit()

    foreign = service.advance(second.analysis_job_id)
    assert foreign.reason == "VISUAL_V2_EXPORT_APPROVAL_STALE"
    assert supervisor.created == []

    revoked = service.revoke_export_approval(
        first.analysis_job_id,
        actor_user_id=1,
        expected_document_id=first_document.id,
    )
    assert revoked.reason == "VISUAL_V2_EXPORT_APPROVAL_REVOKED"
    assert service.advance(first.analysis_job_id).reason == (
        "VISUAL_V2_EXPORT_APPROVAL_REVOKED"
    )
    assert supervisor.created == []


@pytest.mark.parametrize(
    "mutation",
    ["staged_bytes", "source_bytes", "source_path", "source_symlink", "package"],
)
def test_r05_a1_changed_binding_after_approval_never_exports(visual_db, mutation) -> None:
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)
    job = db.get(AnalysisJob, resolution.analysis_job_id)

    if mutation == "staged_bytes":
        target = next((service.spool_root / "incoming").rglob("S1.jpg"))
        target.chmod(0o644)
        target.write_bytes(target.read_bytes() + b"changed")
    elif mutation == "source_bytes":
        source = root / document.storage_path
        source.write_bytes(source.read_bytes() + b"changed")
    elif mutation == "source_path":
        bound = db.query(AnalysisJobSource).filter(
            AnalysisJobSource.analysis_job_id == job.id
        ).one()
        entity = (
            db.get(Document, int(bound.source_entity_id))
            if bound.source_entity_type == "Document"
            else db.get(DocumentPage, int(bound.source_entity_id))
        )
        source_path = entity.storage_path if isinstance(entity, Document) else entity.render_path
        replacement = root / "documents" / "same-bytes-different-path.jpg"
        replacement.write_bytes((root / source_path).read_bytes())
        if isinstance(entity, Document):
            entity.storage_path = str(replacement.relative_to(root)).replace("\\", "/")
        else:
            entity.render_path = str(replacement.relative_to(root)).replace("\\", "/")
        db.commit()
    elif mutation == "source_symlink":
        bound = db.query(AnalysisJobSource).filter(
            AnalysisJobSource.analysis_job_id == job.id
        ).one()
        entity = (
            db.get(Document, int(bound.source_entity_id))
            if bound.source_entity_type == "Document"
            else db.get(DocumentPage, int(bound.source_entity_id))
        )
        source_path = entity.storage_path if isinstance(entity, Document) else entity.render_path
        outside = root.parent / "r05-outside.jpg"
        outside.write_bytes((root / source_path).read_bytes())
        link = root / "documents" / "outside-link.jpg"
        link.symlink_to(outside)
        if isinstance(entity, Document):
            entity.storage_path = str(link.relative_to(root)).replace("\\", "/")
        else:
            entity.render_path = str(link.relative_to(root)).replace("\\", "/")
        db.commit()
    else:
        payload = dict(job.request_payload)
        payload["requested_capabilities"] = list(payload["requested_capabilities"]) + [
            "unapproved_extra"
        ]
        job.request_payload = payload
        db.commit()

    blocked = service.advance(resolution.analysis_job_id)

    assert blocked.state in {"review_required", "awaiting_auth"}
    assert blocked.reason in {
        "VISUAL_V2_STAGED_SHA_MISMATCH",
        "VISUAL_V2_SOURCE_SHA_MISMATCH",
        "VISUAL_V2_EXPORT_APPROVAL_STALE",
        "VISUAL_V2_SOURCE_PATH_INVALID",
    }
    assert supervisor.created == []


def test_r05_a1_restricted_override_and_expired_approval_never_export(visual_db) -> None:
    db, root = visual_db
    first_document = _document(db, root, document_id=51)
    second_document = _document(db, root, document_id=52)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    first = service.ensure(document=first_document)
    second = service.ensure(document=second_document)
    _approve(service, first.analysis_job_id)
    _approve(service, second.analysis_job_id)

    first_document.metadata_normalized = {"sensitivity": "restricted_never_external"}
    second_job = db.get(AnalysisJob, second.analysis_job_id)
    signals = copy.deepcopy(second_job.quality_signals)
    signals["visual_export_approval"]["expires_at"] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    second_job.quality_signals = signals
    db.commit()

    assert service.advance(first.analysis_job_id).reason == (
        "VISUAL_V2_RESTRICTED_NEVER_EXTERNAL"
    )
    assert service.advance(second.analysis_job_id).reason == (
        "VISUAL_V2_EXPORT_APPROVAL_EXPIRED"
    )
    assert supervisor.created == []


def test_r05_a1_disabled_mode_keeps_local_legacy_reuse_available(visual_db, monkeypatch) -> None:
    db, root = visual_db
    document = _document(db, root)
    document.vision_status = "complete"
    document.vision_schema_version = VISION_RESULT_SCHEMA
    page = db.query(DocumentPage).one()
    page.vision_analysis = json.dumps({
        "observations": [{"source_ref": "S1", "text": "Synthetic local evidence."}],
        "visible_text": [],
    })
    db.commit()
    monkeypatch.setattr(settings, "visual_v2_enabled", False)
    supervisor = _Supervisor()

    result = VisualV2Service(db, supervisor=supervisor).ensure(document=document)

    assert result.state == "accepted"
    assert supervisor.created == []


def test_r05_a1_uncertain_handoff_is_not_exported_twice(visual_db) -> None:
    db, root = visual_db
    document = _document(db, root)

    class _UnavailableSupervisor(_Supervisor):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def create_job(self, payload: dict) -> dict:
            self.attempts += 1
            raise visual_v2_module.VisionSupervisorUnavailable(
                "synthetic unavailable after claim"
            )

    supervisor = _UnavailableSupervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)

    first = service.advance(resolution.analysis_job_id)
    second = service.advance(resolution.analysis_job_id)

    assert first.state == "awaiting_auth"
    assert second.state == "awaiting_auth"
    assert first.reason == second.reason == "VISUAL_V2_EXPORT_HANDOFF_UNCERTAIN"
    assert supervisor.attempts == 1
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    assert job.attempt_id.startswith("visual_export_")
    assert job.external_job_id is None


def test_r05_a1_changed_staged_bytes_after_claim_never_reach_supervisor(
    visual_db,
) -> None:
    db, root = visual_db
    document = _document(db, root)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)
    claimed = service.claim_approved_export(resolution.analysis_job_id)
    assert claimed is not None
    target = next((service.spool_root / "incoming").rglob("S1.jpg"))
    target.chmod(0o644)
    target.write_bytes(target.read_bytes() + b"changed-after-claim")

    with pytest.raises(
        VisualV2ContractError,
        match="VISUAL_V2_(STAGED_SHA_MISMATCH|APPROVAL_STALE)",
    ):
        service.submit_claimed_export(resolution.analysis_job_id, claimed)

    db.expire_all()
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    assert job.attempt_id is None
    assert job.external_job_id is None
    assert supervisor.created == []


def test_r05_a1_valid_claim_remains_exportable_at_submit_boundary(visual_db) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=91)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)

    claimed = service.claim_approved_export(resolution.analysis_job_id)
    assert claimed is not None
    external = service.submit_claimed_export(resolution.analysis_job_id, claimed)

    assert external["state"] == "QUEUED"
    assert len(supervisor.created) == 1


def test_r05_a1_expiry_after_claim_before_submit_blocks_handoff(
    visual_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=92)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)

    class _ControlledDateTime(datetime):
        current = datetime.now(UTC)

        @classmethod
        def now(cls, tz=None):
            value = cls.current
            return value if tz is not None else value.replace(tzinfo=None)

    monkeypatch.setattr(visual_v2_module, "datetime", _ControlledDateTime)
    candidate = service.approval_candidate(resolution.analysis_job_id, actor_user_id=1)
    service.approve_export(
        resolution.analysis_job_id,
        actor_user_id=1,
        expected_package_sha256=candidate["package_sha256"],
        expected_source_sha256={
            row["source_ref"]: row["final_sha256"]
            for row in candidate["sources"]
        },
        approval_kind="locally_redacted",
        expires_at=_ControlledDateTime.current + timedelta(minutes=1),
    )
    claimed = service.claim_approved_export(resolution.analysis_job_id)
    assert claimed is not None
    _ControlledDateTime.current += timedelta(minutes=2)

    with pytest.raises(
        VisualV2ContractError,
        match="VISUAL_V2_EXPORT_APPROVAL_EXPIRED",
    ):
        service.submit_claimed_export(resolution.analysis_job_id, claimed)

    assert supervisor.created == []


def test_r05_a1_cancel_in_fresh_session_after_claim_blocks_submit(visual_db) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=93)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)
    claimed = service.claim_approved_export(resolution.analysis_job_id)
    assert claimed is not None

    other = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()
    try:
        assert VisualV2Service(
            other,
            supervisor=supervisor,
            enabled=True,
        ).cancel(resolution.analysis_job_id)
    finally:
        other.close()

    with pytest.raises(VisualV2ContractError, match="VISUAL_V2_CANCELLED"):
        service.submit_claimed_export(resolution.analysis_job_id, claimed)

    assert supervisor.created == []


def test_r05_a1_revoke_in_fresh_session_after_claim_blocks_submit(visual_db) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=96)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)
    claimed = service.claim_approved_export(resolution.analysis_job_id)
    assert claimed is not None

    other = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()
    try:
        revoked = VisualV2Service(
            other,
            supervisor=supervisor,
            enabled=True,
        ).revoke_export_approval(
            resolution.analysis_job_id,
            actor_user_id=1,
            expected_document_id=document.id,
        )
        assert revoked.reason == "VISUAL_V2_EXPORT_APPROVAL_REVOKED"
    finally:
        other.close()

    with pytest.raises(
        VisualV2ContractError,
        match="VISUAL_V2_EXPORT_APPROVAL_REVOKED",
    ):
        service.submit_claimed_export(resolution.analysis_job_id, claimed)

    assert supervisor.created == []


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("client_id", 2),
        ("project_id", 202),
        ("inspection_id", 303),
        ("candidate_id", 404),
    ],
)
def test_r05_a1_scope_change_before_claim_invalidates_approval(
    visual_db,
    field_name: str,
    new_value: int,
) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=94)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)
    setattr(document, field_name, new_value)
    db.commit()

    assert service.claim_approved_export(resolution.analysis_job_id) is None
    db.expire_all()
    job = db.get(AnalysisJob, resolution.analysis_job_id)
    assert job.error_code == "VISUAL_V2_EXPORT_APPROVAL_STALE"
    assert supervisor.created == []


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("client_id", 2),
        ("project_id", 202),
        ("inspection_id", 303),
        ("candidate_id", 404),
    ],
)
def test_r05_a1_scope_change_in_fresh_session_after_claim_blocks_submit(
    visual_db,
    field_name: str,
    new_value: int,
) -> None:
    db, root = visual_db
    document = _document(db, root, document_id=95)
    supervisor = _Supervisor()
    service = VisualV2Service(db, supervisor=supervisor)
    resolution = service.ensure(document=document)
    _approve(service, resolution.analysis_job_id)
    claimed = service.claim_approved_export(resolution.analysis_job_id)
    assert claimed is not None

    other = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()
    try:
        current = other.get(Document, document.id)
        setattr(current, field_name, new_value)
        other.commit()
    finally:
        other.close()

    with pytest.raises(
        VisualV2ContractError,
        match="VISUAL_V2_EXPORT_APPROVAL_STALE",
    ):
        service.submit_claimed_export(resolution.analysis_job_id, claimed)

    assert supervisor.created == []
