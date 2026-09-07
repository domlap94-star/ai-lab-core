from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource
from app.schemas.agent import AgentSource
from app.schemas.vision import VISION_RESULT_SCHEMA, VisionResult
from app.services.document_service import resolve_document_storage_path
from app.services.vision_need_classifier import (
    VisionNeedClassifier,
    VisionSourceCandidate,
)
from app.services.vision_supervisor_client import (
    VisionSupervisorClient,
    VisionSupervisorUnavailable,
)


register_heif_opener()
logger = logging.getLogger("ai_lab.visual_v2")

VISUAL_V2_ANALYSIS_TYPE = "visual_v2"
VISUAL_V2_SOURCE_DOMAIN = "document_visual_v2"
VISUAL_V2_PROCESSOR_ID = "assistant_visual_v2"
VISUAL_V2_PROCESSOR_VERSION = "v2"
VISUAL_V2_RESULT_SCHEMA = "ASSISTANT_VISUAL_EVIDENCE_V2"
VISUAL_V2_CONTRACT_GENERATION = "assistant-visual-v2-20260907"
VISUAL_V2_ACTIVE_STATUSES = (
    "queued",
    "local_processing",
    "advanced_queued",
    "advanced_processing",
    "awaiting_auth",
    "awaiting_ui_fix",
    "advanced_validating",
)
VISUAL_V2_WAITING_STATES = frozenset(VISUAL_V2_ACTIVE_STATUSES)
MAX_VISUAL_SOURCES = 4
MAX_VISUAL_ATOMS = 32
MAX_VISUAL_TEXT = 800
MAX_VISUAL_PAYLOAD_BYTES = 64 * 1024
MAX_IMAGE_EDGE = 2048
MAX_PREPARED_BYTES = 12 * 1024 * 1024

_VISUAL_TERMS = re.compile(
    r"\b(?:obraz\w*|zdjec\w*|fotograf\w*|skan\w*|wykres\w*|map\w*|"
    r"rysun\w*|schemat\w*|profil\w*|przekro\w*|widoczn\w*|tekst\s+na\s+"
    r"(?:obrazie|zdjeciu)|relacj\w*\s+przestrzenn\w*)\b",
    re.IGNORECASE,
)
_PAGE_TERMS = re.compile(r"\b(?:stron(?:a|ie|y|ę)|page)\s*(\d{1,5})\b", re.IGNORECASE)


VisualV2State = Literal[
    "not_required",
    "queued",
    "processing",
    "awaiting_auth",
    "awaiting_ui_fix",
    "accepted",
    "review_required",
    "failed",
    "cancelled",
]


@dataclass(frozen=True)
class VisualV2Resolution:
    state: VisualV2State
    reason: str
    analysis_job_id: str | None = None
    result_payload: dict[str, Any] | None = None

    @property
    def waiting(self) -> bool:
        return self.state in {"queued", "processing", "awaiting_auth", "awaiting_ui_fix"}


@dataclass(frozen=True)
class _PlannedSource:
    local_ref: str
    external_ref: str
    entity_type: str
    entity_id: str
    page_number: int | None
    canonical_sha256: str
    candidate: VisionSourceCandidate


class VisualV2ContractError(RuntimeError):
    pass


class VisualV2Service:
    """One durable Visual V2 boundary over the existing AnalysisJob ledger."""

    def __init__(self, db: Session, *, supervisor: Any | None = None) -> None:
        self.db = db
        self.supervisor = supervisor or VisionSupervisorClient()
        self.classifier = VisionNeedClassifier()
        self.data_root = Path(settings.data_dir).resolve()
        self.spool_root = (self.data_root / "vision-spool").resolve()

    def ensure(
        self,
        *,
        document: Document,
        question: str | None = None,
        explicit: bool = False,
        created_by_user_id: int | None = None,
        preparation_job_id: str | None = None,
    ) -> VisualV2Resolution:
        locked_document = self.db.query(Document).filter(
            Document.id == document.id
        ).with_for_update().one_or_none()
        if locked_document is None:
            return VisualV2Resolution("failed", "VISUAL_V2_DOCUMENT_UNAVAILABLE")
        document = locked_document
        if document.trashed_at is not None or document.purged_at is not None:
            return VisualV2Resolution("failed", "VISUAL_V2_DOCUMENT_UNAVAILABLE")
        checksum = str(document.checksum_sha256 or "").casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", checksum):
            return VisualV2Resolution("failed", "VISUAL_V2_DOCUMENT_CHECKSUM_REQUIRED")
        if self._restricted(document):
            return VisualV2Resolution("review_required", "VISUAL_V2_RESTRICTED_NEVER_EXTERNAL")

        pages = self.db.query(DocumentPage).filter(
            DocumentPage.document_id == document.id
        ).order_by(DocumentPage.page_number, DocumentPage.id).all()
        assets = self.db.query(DocumentAsset).filter(
            DocumentAsset.document_id == document.id
        ).order_by(DocumentAsset.page_number, DocumentAsset.asset_index, DocumentAsset.id).all()
        candidates, reason, required_page = self._candidates(
            document=document,
            pages=pages,
            assets=assets,
            question=question,
            explicit=explicit,
        )
        if not candidates:
            return VisualV2Resolution(
                "failed" if required_page is not None else "not_required",
                "VISUAL_V2_REQUIRED_PAGE_UNAVAILABLE" if required_page is not None else reason,
            )
        if required_page is not None and not any(
            item.page is not None and item.page.page_number == required_page
            for item in candidates[:MAX_VISUAL_SOURCES]
        ):
            return VisualV2Resolution("failed", "VISUAL_V2_REQUIRED_PAGE_OMITTED")

        planned = self._planned_sources(document, candidates[:MAX_VISUAL_SOURCES])
        if not planned:
            return VisualV2Resolution("failed", "VISUAL_V2_NO_SAFE_RASTER")
        if required_page is not None and not any(
            item.page_number == required_page for item in planned
        ):
            return VisualV2Resolution("failed", "VISUAL_V2_REQUIRED_PAGE_UNAVAILABLE")
        fingerprint = self._fingerprint(
            document_checksum=checksum,
            sources=planned,
        )
        existing = self._current_job(fingerprint)
        if existing is not None:
            return self._resolution(existing)

        payload = {
            "contract_generation": VISUAL_V2_CONTRACT_GENERATION,
            "document_checksum": checksum,
            "reason_codes": [reason],
            "required_page": required_page,
            "selected_count": len(planned),
            "omitted_count": max(0, len(candidates) - len(planned)),
            "sources": [
                {
                    "source_ref": source.local_ref,
                    "external_ref": source.external_ref,
                    "entity_type": source.entity_type,
                    "entity_id": source.entity_id,
                    "page_number": source.page_number,
                    "source_sha256": source.canonical_sha256,
                }
                for source in planned
            ],
            "requested_capabilities": [
                "direct_observations",
                "visible_text",
                "visible_measurements",
                "image_quality",
                "uncertainties",
            ],
        }
        job = AnalysisJob(
            id=str(uuid.uuid4()),
            analysis_type=VISUAL_V2_ANALYSIS_TYPE,
            source_domain=VISUAL_V2_SOURCE_DOMAIN,
            status="queued",
            sensitivity="customer_sanitizable",
            processor_id=VISUAL_V2_PROCESSOR_ID,
            processor_version=VISUAL_V2_PROCESSOR_VERSION,
            model_identity="temporary_chat_visual",
            input_fingerprint=fingerprint,
            request_payload=payload,
            waiting_document_preparation_job_id=preparation_job_id,
            created_by_user_id=created_by_user_id,
            last_progress_at=datetime.now(UTC),
        )
        savepoint = self.db.begin_nested()
        try:
            self.db.add(job)
            for source in planned:
                self.db.add(AnalysisJobSource(
                    analysis_job_id=job.id,
                    source_ref=source.local_ref,
                    source_domain=VISUAL_V2_SOURCE_DOMAIN,
                    source_entity_type=source.entity_type,
                    source_entity_id=source.entity_id,
                    page_number=source.page_number,
                    checksum_sha256=source.canonical_sha256,
                    sensitivity="customer_sanitizable",
                ))
            self.db.flush()
            legacy = self._legacy_payload(document, planned)
            if legacy is not None:
                self._accept(job, legacy, raw_sha256=self._hash_json(legacy), mode="legacy_v1_reuse")
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            current = self._current_job(fingerprint)
            if current is None:
                raise
            job = current
        return self._resolution(job)

    def accepted_for_document(
        self, *, document: Document, question: str | None = None
    ) -> VisualV2Resolution:
        resolution = self.ensure(document=document, question=question)
        return resolution

    def advance(self, job_id: str) -> VisualV2Resolution:
        job = self.db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
            AnalysisJob.source_domain == VISUAL_V2_SOURCE_DOMAIN,
        ).with_for_update().one_or_none()
        if job is None:
            return VisualV2Resolution("failed", "VISUAL_V2_JOB_NOT_FOUND")
        if job.status not in VISUAL_V2_ACTIVE_STATUSES:
            return self._resolution(job)
        if job.cancel_requested_at is not None:
            self._cancel_locked(job)
            return self._resolution(job)

        try:
            if not job.external_job_id:
                job.status = "local_processing"
                job.started_at = job.started_at or datetime.now(UTC)
                job.reasoning_attempt_count += 1
                job.last_progress_at = datetime.now(UTC)
                self.db.commit()
                request_key, request, package_sha256, package_size = self._stage(job.id)
                external = self.supervisor.create_job(request)
                self.db.expire_all()
                job = self.db.query(AnalysisJob).filter(
                    AnalysisJob.id == job_id,
                    AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
                ).with_for_update().one()
                if job.cancel_requested_at is not None or job.status == "cancelled":
                    external_id = str(external.get("job_id") or "")
                    if external_id:
                        self.supervisor.cancel_job(external_id)
                    self._cancel_locked(job)
                    return self._resolution(job)
                external_id = str(external.get("job_id") or "")
                if not external_id:
                    raise VisualV2ContractError("VISUAL_V2_EXTERNAL_JOB_ID_MISSING")
                job.external_job_id = external_id
                job.sanitized_package_hash = package_sha256
                job.sanitized_package_size = package_size
                job.status = self._external_status(external)
                job.error_code = self._safe_error(external.get("error_code"))
                job.last_progress_at = datetime.now(UTC)
                self.db.commit()
                # external_job_id and exact package binding are durable before
                # any output is read or accepted.
                return self._apply_external(job_id, external)

            external = self.supervisor.get_job(job.external_job_id)
            return self._apply_external(job_id, external)
        except (
            VisualV2ContractError,
            VisionSupervisorUnavailable,
            OSError,
            UnidentifiedImageError,
            ValueError,
        ) as error:
            self.db.rollback()
            job = self.db.query(AnalysisJob).filter(
                AnalysisJob.id == job_id,
                AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
            ).with_for_update().one_or_none()
            if job is not None and job.status != "cancelled":
                job.status = "review_required"
                job.decision = "review_required"
                job.error_code = self._safe_error(
                    str(error) or f"VISUAL_V2_{error.__class__.__name__.upper()}"
                )
                job.finished_at = datetime.now(UTC)
                job.last_progress_at = job.finished_at
                self.db.commit()
                return self._resolution(job)
            raise

    def cancel(self, job_id: str) -> bool:
        job = self.db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
            AnalysisJob.status.in_(VISUAL_V2_ACTIVE_STATUSES),
        ).with_for_update().one_or_none()
        if job is None:
            return False
        external_id = job.external_job_id
        self._cancel_locked(job)
        self.db.commit()
        if external_id:
            try:
                self.supervisor.cancel_job(external_id)
            except VisionSupervisorUnavailable:
                pass
        return True

    def assistant_evidence(
        self, resolution: VisualV2Resolution, *, document_id: int
    ) -> tuple[list[AgentSource], list[dict[str, Any]]]:
        payload = resolution.result_payload
        if resolution.state != "accepted" or not isinstance(payload, dict):
            return [], []
        atoms = payload.get("evidence")
        if not isinstance(atoms, list):
            return [], []
        sources: list[AgentSource] = []
        source_keys: list[tuple[str, int | None, str | None]] = []
        for atom in atoms:
            if not isinstance(atom, dict):
                continue
            text = " ".join(str(atom.get("text") or "").split())[:600]
            if not text:
                continue
            route = f"/documents/{document_id}"
            page = atom.get("page_number")
            if isinstance(page, int) and page > 0:
                route += f"?page={page}"
            source = AgentSource(
                source_type="visual",
                source_id=document_id,
                title="Zweryfikowana obserwacja wizualna",
                route=route,
                snippet=text,
            )
            key = (source.source_type, source.source_id, source.route)
            if key not in source_keys:
                sources.append(source)
                source_keys.append(key)
        tool = {
            "tool": "get_visual_v2",
            "data": {
                "schema_version": VISUAL_V2_RESULT_SCHEMA,
                "analysis_job_id": resolution.analysis_job_id,
                "evidence": atoms[:MAX_VISUAL_ATOMS],
                "coverage": payload.get("coverage") or {},
            },
            "source_keys": source_keys,
        }
        return sources, [tool]

    def _apply_external(self, job_id: str, external: dict[str, Any]) -> VisualV2Resolution:
        job = self.db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
        ).with_for_update().one()
        if job.status == "cancelled" or job.cancel_requested_at is not None:
            return self._resolution(job)
        state = str(external.get("state") or "FAILED").upper()
        if state == "COMPLETE":
            payload, raw_sha256 = self._validated_result(job)
            self._accept(job, payload, raw_sha256=raw_sha256, mode="temporary_chat")
        elif state == "AUTH_REQUIRED":
            job.status = "awaiting_auth"
            job.error_code = "VISUAL_V2_AUTH_REQUIRED"
        elif state == "UI_CHANGED":
            job.status = "awaiting_ui_fix"
            job.error_code = "VISUAL_V2_UI_CHANGED"
        elif state in {"QUEUED", "RUNNING"}:
            job.status = "advanced_processing" if state == "RUNNING" else "advanced_queued"
            job.error_code = None
        elif state == "CANCELLED":
            self._cancel_locked(job)
        else:
            job.status = "review_required"
            job.decision = "review_required"
            job.error_code = self._safe_error(external.get("error_code") or "VISUAL_V2_EXTERNAL_FAILED")
            job.finished_at = datetime.now(UTC)
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return self._resolution(job)

    def _stage(self, job_id: str) -> tuple[str, dict[str, Any], str, int]:
        job = self.db.get(AnalysisJob, job_id)
        if job is None or not isinstance(job.request_payload, dict):
            raise VisualV2ContractError("VISUAL_V2_REQUEST_MISSING")
        local_sources = {
            source.source_ref: source
            for source in self.db.query(AnalysisJobSource).filter(
                AnalysisJobSource.analysis_job_id == job.id
            ).order_by(AnalysisJobSource.source_ref).all()
        }
        descriptors: list[dict[str, Any]] = []
        staged: list[tuple[str, Path, str]] = []
        for row in job.request_payload.get("sources") or []:
            if not isinstance(row, dict):
                raise VisualV2ContractError("VISUAL_V2_SOURCE_MANIFEST_INVALID")
            local_ref = str(row.get("source_ref") or "")
            source = local_sources.get(local_ref)
            if source is None or source.checksum_sha256 != row.get("source_sha256"):
                raise VisualV2ContractError("VISUAL_V2_SOURCE_BINDING_INVALID")
            path = self._source_path(source)
            if self._sha256(path) != source.checksum_sha256:
                raise VisualV2ContractError("VISUAL_V2_SOURCE_SHA_MISMATCH")
            prepared = self._normalized_raster(path)
            staged.append((str(row.get("external_ref") or ""), prepared, self._sha256(prepared)))
        request_key = hashlib.sha256(
            (VISUAL_V2_CONTRACT_GENERATION + "|" + "|".join(
                f"{ref}:{checksum}" for ref, _, checksum in staged
            )).encode("utf-8")
        ).hexdigest()
        incoming = self.spool_root / "incoming" / request_key
        incoming.mkdir(parents=True, exist_ok=True)
        for index, (ref, path, checksum) in enumerate(staged, 1):
            if ref != f"S{index}":
                raise VisualV2ContractError("VISUAL_V2_EXTERNAL_REF_INVALID")
            target = incoming / f"S{index}.jpg"
            if path != target:
                shutil.copyfile(path, target)
            actual = self._sha256(target)
            if actual != checksum:
                raise VisualV2ContractError("VISUAL_V2_STAGED_SHA_MISMATCH")
            descriptors.append({
                "source_ref": ref,
                # The V1 local Supervisor contract requires positive numeric
                # identifiers; synthetic values avoid exposing canonical IDs.
                "document_id": 900000 + index,
                "page_number": None,
                "asset_id": None,
                "sha256": actual,
                "incoming_relative_path": f"incoming/{request_key}/{target.name}",
            })
        package = {
            "contract_generation": VISUAL_V2_CONTRACT_GENERATION,
            "request_key": request_key,
            "sources": [{"source_ref": row["source_ref"], "sha256": row["sha256"]} for row in descriptors],
            "capabilities": list(job.request_payload.get("requested_capabilities") or []),
        }
        canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return request_key, {"request_key": request_key, "sources": descriptors}, hashlib.sha256(canonical).hexdigest(), len(canonical)

    def _validated_result(self, job: AnalysisJob) -> tuple[dict[str, Any], str]:
        if not job.external_job_id or not job.sanitized_package_hash:
            raise VisualV2ContractError("VISUAL_V2_EXTERNAL_BINDING_MISSING")
        job_dir = self.spool_root / "jobs" / job.external_job_id
        result_path = job_dir / "output" / "vision.json"
        manifest_path = job_dir / "output" / "result_manifest.json"
        job_manifest_path = job_dir / "manifest.json"
        if not all(path.is_file() for path in (result_path, manifest_path, job_manifest_path)):
            raise VisualV2ContractError("VISUAL_V2_OUTPUT_MISSING")
        raw_bytes = result_path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8"))
        result = VisionResult.model_validate(raw)
        if result.job_id != job.external_job_id:
            raise VisualV2ContractError("VISUAL_V2_JOB_BINDING_INVALID")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        job_manifest = json.loads(job_manifest_path.read_text(encoding="utf-8"))
        expected = {
            str(row["source_ref"]): str(row["sha256"])
            for row in job_manifest.get("sources") or []
        }
        if manifest.get("source_sha256") != expected:
            raise VisualV2ContractError("VISUAL_V2_OUTPUT_SOURCE_SHA_MISMATCH")
        canonical_raw = (json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        raw_sha256 = hashlib.sha256(canonical_raw).hexdigest()
        if manifest.get("output_sha256") != raw_sha256:
            raise VisualV2ContractError("VISUAL_V2_OUTPUT_SHA_MISMATCH")
        local_rows = self.db.query(AnalysisJobSource).filter(
            AnalysisJobSource.analysis_job_id == job.id
        ).order_by(AnalysisJobSource.source_ref).all()
        mapping = {f"S{index}": row for index, row in enumerate(local_rows, 1)}
        refs = {
            item.source_ref
            for values in (
                result.observations,
                result.possible_interpretations,
                result.uncertainties,
                result.visible_text,
                result.measurements,
                result.image_quality,
            )
            for item in values
        }
        if not refs.issubset(mapping) or {item.source_ref for item in result.image_quality} != set(mapping):
            raise VisualV2ContractError("VISUAL_V2_FOREIGN_SOURCE_REF")
        atoms: list[dict[str, Any]] = []
        direct_count = 0
        for kind, values in (
            ("observation", result.observations),
            ("visible_text", result.visible_text),
            ("uncertainty", result.uncertainties),
        ):
            for item in values:
                text = " ".join(item.text.split())[:MAX_VISUAL_TEXT]
                if not text:
                    continue
                source = mapping[item.source_ref]
                atoms.append(self._atom(kind, text, source))
                if kind in {"observation", "visible_text"}:
                    direct_count += 1
        for item in result.measurements:
            source = mapping[item.source_ref]
            text = f"{item.value:g} {item.unit} (podstawa: widoczna skala)"
            atoms.append(self._atom("measurement", text, source))
        for item in result.image_quality:
            source = mapping[item.source_ref]
            atoms.append(self._atom("image_quality", item.quality, source))
        if direct_count == 0:
            raise VisualV2ContractError("VISUAL_V2_SUBSTANTIVE_EVIDENCE_MISSING")
        atoms = atoms[:MAX_VISUAL_ATOMS]
        payload = self._result_payload(job, atoms, len(local_rows))
        self._validate_payload_size(payload)
        return payload, raw_sha256

    def _legacy_payload(
        self, document: Document, planned: list[_PlannedSource]
    ) -> dict[str, Any] | None:
        if document.vision_status != "complete" or document.vision_schema_version != VISION_RESULT_SCHEMA:
            return None
        atoms: list[dict[str, Any]] = []
        for source in planned:
            entity = source.candidate.page or source.candidate.asset
            raw = getattr(entity, "vision_analysis", None)
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return None
            for kind, key in (("observation", "observations"), ("visible_text", "visible_text")):
                for item in parsed.get(key) or []:
                    if not isinstance(item, dict):
                        continue
                    text = " ".join(str(item.get("text") or "").split())[:MAX_VISUAL_TEXT]
                    if text:
                        atoms.append(self._atom(kind, text, self._source_row(source)))
        if not atoms:
            return None
        payload = self._result_payload(None, atoms[:MAX_VISUAL_ATOMS], len(planned))
        self._validate_payload_size(payload)
        return payload

    @staticmethod
    def _result_payload(
        job: AnalysisJob | None, atoms: list[dict[str, Any]], selected_count: int
    ) -> dict[str, Any]:
        return {
            "schema_version": VISUAL_V2_RESULT_SCHEMA,
            "analysis_job_id": job.id if job is not None else None,
            "input_fingerprint": job.input_fingerprint if job is not None else None,
            "evidence": atoms,
            "coverage": {
                "selected_source_count": selected_count,
                "covered_source_count": len({item["source_ref"] for item in atoms}),
                "complete": len({item["source_ref"] for item in atoms}) == selected_count,
            },
        }

    @staticmethod
    def _atom(kind: str, text: str, source: Any) -> dict[str, Any]:
        return {
            "kind": kind,
            "source_ref": source.source_ref,
            "page_number": source.page_number,
            "text": text,
        }

    @staticmethod
    def _source_row(source: _PlannedSource) -> Any:
        class _Row:
            source_ref = source.local_ref
            page_number = source.page_number
        return _Row()

    def _accept(self, job: AnalysisJob, payload: dict[str, Any], *, raw_sha256: str, mode: str) -> None:
        payload = dict(payload)
        payload["analysis_job_id"] = job.id
        payload["input_fingerprint"] = job.input_fingerprint
        self._validate_payload_size(payload)
        validated_sha256 = self._hash_json(payload)
        job.result_payload = payload
        job.status = "accepted_advanced"
        job.decision = "accepted"
        job.error_code = None
        job.quality_signals = {
            "contract": VISUAL_V2_RESULT_SCHEMA,
            "mode": mode,
            "raw_response_sha256": raw_sha256,
            "validated_payload_sha256": validated_sha256,
            "source_count": len(job.sources),
        }
        job.finished_at = datetime.now(UTC)
        job.last_progress_at = job.finished_at
        self.db.flush()

    def _candidates(
        self,
        *,
        document: Document,
        pages: list[DocumentPage],
        assets: list[DocumentAsset],
        question: str | None,
        explicit: bool,
    ) -> tuple[list[VisionSourceCandidate], str, int | None]:
        classification = self.classifier.classify(
            document=document, pages=pages, assets=assets
        )
        requested_page = self._requested_page(question)
        visual_question = bool(question and _VISUAL_TERMS.search(question))
        required = explicit or visual_question or requested_page is not None or (
            classification.classification in {"vision_required", "vision_optional"}
            and bool(classification.sources)
        )
        if not required:
            return [], classification.reason, requested_page
        candidates = list(classification.sources)
        if requested_page is not None:
            exact = next((page for page in pages if page.page_number == requested_page and page.render_path), None)
            if exact is None:
                return [], "EXPLICIT_PAGE_REFERENCE", requested_page
            candidates = [VisionSourceCandidate(page=exact)] + [
                item for item in candidates
                if item.page is None or item.page.id != exact.id
            ]
        if not candidates and (explicit or visual_question):
            candidates.extend(VisionSourceCandidate(page=page) for page in pages if page.render_path)
            candidates.extend(VisionSourceCandidate(asset=asset) for asset in assets if self.classifier._valuable_asset(asset))
            if not candidates and self._is_image(document):
                page = pages[0] if pages else None
                candidates.append(VisionSourceCandidate(page=page, use_document_file=True))
        unique: list[VisionSourceCandidate] = []
        seen: set[tuple[str, int]] = set()
        for item in candidates:
            key = ("page", item.page.id) if item.page is not None else ("asset", item.asset.id) if item.asset is not None else ("document", document.id)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique, "EXPLICIT_VISUAL_REQUEST" if (explicit or visual_question) else classification.reason, requested_page

    def _planned_sources(
        self, document: Document, candidates: list[VisionSourceCandidate]
    ) -> list[_PlannedSource]:
        planned: list[_PlannedSource] = []
        for candidate in candidates:
            try:
                path = self._candidate_path(document, candidate)
            except (VisualV2ContractError, ValueError, OSError):
                continue
            checksum = self._sha256(path)
            if candidate.asset is not None:
                entity_type, entity_id = "DocumentAsset", str(candidate.asset.id)
                page_number = candidate.asset.page_number
            elif candidate.page is not None and not candidate.use_document_file:
                entity_type, entity_id = "DocumentPage", str(candidate.page.id)
                page_number = candidate.page.page_number
            else:
                entity_type, entity_id = "Document", str(document.id)
                page_number = candidate.page.page_number if candidate.page else None
            index = len(planned) + 1
            planned.append(_PlannedSource(
                local_ref=f"V{index:02d}",
                external_ref=f"S{index}",
                entity_type=entity_type,
                entity_id=entity_id,
                page_number=page_number,
                canonical_sha256=checksum,
                candidate=candidate,
            ))
        return planned

    def _source_path(self, source: AnalysisJobSource) -> Path:
        if source.source_entity_type == "DocumentPage":
            entity = self.db.get(DocumentPage, int(source.source_entity_id))
            storage_path = entity.render_path if entity else None
        elif source.source_entity_type == "DocumentAsset":
            entity = self.db.get(DocumentAsset, int(source.source_entity_id))
            storage_path = entity.storage_path if entity else None
        elif source.source_entity_type == "Document":
            entity = self.db.get(Document, int(source.source_entity_id))
            storage_path = entity.storage_path if entity else None
        else:
            storage_path = None
        if not storage_path:
            raise VisualV2ContractError("VISUAL_V2_SOURCE_UNAVAILABLE")
        return resolve_document_storage_path(storage_path=storage_path, data_root=self.data_root)

    def _candidate_path(self, document: Document, candidate: VisionSourceCandidate) -> Path:
        storage_path = (
            candidate.asset.storage_path
            if candidate.asset is not None
            else candidate.page.render_path
            if candidate.page is not None and not candidate.use_document_file
            else document.storage_path
        )
        if not storage_path:
            raise VisualV2ContractError("VISUAL_V2_SOURCE_UNAVAILABLE")
        return resolve_document_storage_path(storage_path=storage_path, data_root=self.data_root)

    def _normalized_raster(self, source: Path) -> Path:
        converted_root = self.spool_root / "converted-v2"
        converted_root.mkdir(parents=True, exist_ok=True)
        target = converted_root / f"{self._sha256(source)}.jpg"
        if target.is_file():
            return target
        with Image.open(source) as image:
            prepared = image.convert("RGB")
            prepared.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            prepared.save(target, format="JPEG", quality=90, optimize=True)
        if target.stat().st_size > MAX_PREPARED_BYTES:
            target.unlink(missing_ok=True)
            raise VisualV2ContractError("VISUAL_V2_PREPARED_IMAGE_TOO_LARGE")
        return target

    def _current_job(self, fingerprint: str) -> AnalysisJob | None:
        return self.db.query(AnalysisJob).filter(
            AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
            AnalysisJob.source_domain == VISUAL_V2_SOURCE_DOMAIN,
            AnalysisJob.input_fingerprint == fingerprint,
            AnalysisJob.status.in_((*VISUAL_V2_ACTIVE_STATUSES, "accepted_advanced")),
        ).order_by(
            (AnalysisJob.status != "accepted_advanced").asc(),
            AnalysisJob.created_at.desc(),
            AnalysisJob.id.desc(),
        ).first()

    @staticmethod
    def _resolution(job: AnalysisJob) -> VisualV2Resolution:
        state: VisualV2State = {
            "queued": "queued",
            "local_processing": "processing",
            "advanced_queued": "queued",
            "advanced_processing": "processing",
            "advanced_validating": "processing",
            "awaiting_auth": "awaiting_auth",
            "awaiting_ui_fix": "awaiting_ui_fix",
            "accepted_advanced": "accepted",
            "review_required": "review_required",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(job.status, "failed")  # type: ignore[assignment]
        return VisualV2Resolution(
            state,
            job.error_code or ("VISUAL_V2_ACCEPTED" if state == "accepted" else "VISUAL_V2_ACTIVE"),
            job.id,
            job.result_payload if state == "accepted" and isinstance(job.result_payload, dict) else None,
        )

    @staticmethod
    def _external_status(external: dict[str, Any]) -> str:
        return {
            "RUNNING": "advanced_processing",
            "AUTH_REQUIRED": "awaiting_auth",
            "UI_CHANGED": "awaiting_ui_fix",
        }.get(str(external.get("state") or "QUEUED").upper(), "advanced_queued")

    @staticmethod
    def _cancel_locked(job: AnalysisJob) -> None:
        now = datetime.now(UTC)
        job.status = "cancelled"
        job.decision = "cancelled"
        job.error_code = "VISUAL_V2_CANCELLED"
        job.cancel_requested_at = job.cancel_requested_at or now
        job.finished_at = now
        job.last_progress_at = now

    @staticmethod
    def _restricted(document: Document) -> bool:
        metadata = document.metadata_normalized
        return isinstance(metadata, dict) and metadata.get("sensitivity") == "restricted_never_external"

    @staticmethod
    def _requested_page(question: str | None) -> int | None:
        match = _PAGE_TERMS.search(question or "")
        return int(match.group(1)) if match else None

    @staticmethod
    def _is_image(document: Document) -> bool:
        return (document.content_type or "").casefold().startswith("image/")

    @staticmethod
    def _fingerprint(
        *,
        document_checksum: str,
        sources: list[_PlannedSource],
    ) -> str:
        canonical = json.dumps({
            "contract": VISUAL_V2_CONTRACT_GENERATION,
            "document_checksum": document_checksum,
            "requested_capabilities": [
                "direct_observations",
                "visible_text",
                "visible_measurements",
                "image_quality",
                "uncertainties",
            ],
            "sources": [
                (item.local_ref, item.entity_type, item.entity_id, item.page_number, item.canonical_sha256)
                for item in sources
            ],
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_json(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_error(value: Any) -> str:
        normalized = re.sub(r"[^A-Z0-9_]+", "_", str(value or "VISUAL_V2_FAILED").upper())
        return normalized[:100] or "VISUAL_V2_FAILED"

    @staticmethod
    def _validate_payload_size(payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_VISUAL_PAYLOAD_BYTES:
            raise VisualV2ContractError("VISUAL_V2_RESULT_TOO_LARGE")


def _next_visual_job_id() -> str | None:
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(
            AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
            AnalysisJob.source_domain == VISUAL_V2_SOURCE_DOMAIN,
            AnalysisJob.status.in_(VISUAL_V2_ACTIVE_STATUSES),
            AnalysisJob.cancel_requested_at.is_(None),
        ).order_by(
            AnalysisJob.last_progress_at.asc().nullsfirst(),
            AnalysisJob.created_at,
            AnalysisJob.id,
        ).with_for_update(skip_locked=True).first()
        if job is None:
            db.commit()
            return None
        job.last_progress_at = datetime.now(UTC)
        db.commit()
        return job.id
    finally:
        db.close()


def _advance_visual_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        VisualV2Service(db).advance(job_id)
    except Exception as error:
        db.rollback()
        logger.warning("Visual V2 iteration failed: %s", error.__class__.__name__)
    finally:
        db.close()


class VisualV2Dispatcher:
    POLL_SECONDS = 2

    async def run(self) -> None:
        logger.info("Visual V2 dispatcher started.")
        while True:
            try:
                job_id = await asyncio.to_thread(_next_visual_job_id)
                if job_id is None:
                    await asyncio.sleep(self.POLL_SECONDS)
                    continue
                await asyncio.to_thread(_advance_visual_job, job_id)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Visual V2 dispatcher failure: %s", error.__class__.__name__)
                await asyncio.sleep(self.POLL_SECONDS)


def start_visual_v2_dispatcher() -> asyncio.Task:
    return asyncio.create_task(VisualV2Dispatcher().run(), name="visual-v2-dispatcher")
