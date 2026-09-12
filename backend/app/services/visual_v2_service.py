from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.models.knowledge_base import AnalysisJob, AnalysisJobSource
from app.models.role import Role
from app.models.user import User
from app.schemas.agent import AgentSource
from app.schemas.vision import VISION_RESULT_SCHEMA, VisionResult
from app.services.document_service import (
    DocumentStorageError,
    resolve_document_storage_path,
)
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
VISUAL_EXPORT_POLICY_VERSION = "visual-export-v1"
VISUAL_EXPORT_CHANNEL = "temporary_chat_visual"
VISUAL_EXPORT_APPROVAL_KEY = "visual_export_approval"
VISUAL_EXPORT_HANDOFF_KEY = "visual_export_handoff"
VISUAL_EXPORT_HANDOFF_SCHEMA = "VISUAL_EXPORT_HANDOFF_STATE_V1"
VISUAL_EXPORT_HANDOFF_CLAIMED = "claimed_no_contact"
VISUAL_EXPORT_HANDOFF_CONTACT = "contact_may_have_started"
VISUAL_EXPORT_HANDOFF_RECORDED = "external_id_recorded"
VISUAL_EXPORT_HANDOFF_LOCAL_DENIED = "local_denied"
VISUAL_EXPORT_BINDING_SCHEMA = "VISUAL_EXPORT_BINDING_V2"
VISUAL_EXPORT_DOCUMENT_SCOPE_SCHEMA = "VISUAL_EXPORT_DOCUMENT_SCOPE_V1"
VISUAL_EXPORT_WAIT_CODES = (
    "VISUAL_V2_EXPORT_APPROVAL_REQUIRED",
    "VISUAL_V2_EXPORT_APPROVAL_REVOKED",
    "VISUAL_V2_EXPORT_APPROVAL_EXPIRED",
    "VISUAL_V2_EXPORT_APPROVAL_STALE",
    "VISUAL_V2_EXPORT_SCOPE_MISMATCH",
    "VISUAL_V2_EXPORT_HANDOFF_UNCERTAIN",
)


def _export_attempt_id(request_key: str) -> str:
    return f"visual_export_{request_key}"

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
class VisualExportApprovalPreview:
    content: bytes
    content_type: str
    source_ref: str
    source_sha256: str
    package_sha256: str


@dataclass(frozen=True)
class _PlannedSource:
    local_ref: str
    external_ref: str
    entity_type: str
    entity_id: str
    page_number: int | None
    canonical_sha256: str
    candidate: VisionSourceCandidate


@dataclass(frozen=True)
class _StagedExport:
    request_key: str
    request: dict[str, Any]
    package_sha256: str
    package_size: int
    approval_binding: dict[str, Any]


class VisualV2ContractError(RuntimeError):
    pass


class VisualV2Service:
    """One durable Visual V2 boundary over the existing AnalysisJob ledger."""

    def __init__(
        self,
        db: Session,
        *,
        supervisor: Any | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.db = db
        self.supervisor = supervisor or VisionSupervisorClient()
        self.enabled = settings.visual_v2_enabled if enabled is None else enabled
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
            document_scope=self._document_scope(document),
            sources=planned,
        )
        existing = self._current_job(fingerprint)
        if existing is not None:
            if not self.enabled and existing.status != "accepted_advanced":
                return VisualV2Resolution(
                    "review_required",
                    "VISUAL_V2_RUNTIME_DISABLED",
                    existing.id,
                )
            return self._resolution(existing)

        payload = {
            "contract_generation": VISUAL_V2_CONTRACT_GENERATION,
            "document_checksum": checksum,
            "document_scope": self._document_scope(document),
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
            legacy = self._legacy_payload(document, planned, job=job)
            if legacy is not None:
                self._accept(job, legacy, raw_sha256=self._hash_json(legacy), mode="legacy_v1_reuse")
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            current = self._current_job(fingerprint)
            if current is None:
                raise
            job = current
        if not self.enabled and job.status != "accepted_advanced":
            return VisualV2Resolution(
                "review_required",
                "VISUAL_V2_RUNTIME_DISABLED",
                job.id,
            )
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
        if not self.enabled:
            return VisualV2Resolution(
                "review_required", "VISUAL_V2_RUNTIME_DISABLED", job.id
            )
        if job.status not in VISUAL_V2_ACTIVE_STATUSES:
            return self._resolution(job)
        if job.cancel_requested_at is not None:
            self._cancel_locked(job)
            return self._resolution(job)

        try:
            if not job.external_job_id:
                staged = self.claim_approved_export(job.id)
                if staged is None:
                    return self._resolution(self._locked_job(job_id))
                external = self.submit_claimed_export(job.id, staged)
                job = self.record_external_handoff(job.id, external)
                if job.status == "cancelled":
                    return self._resolution(job)
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
                if self._handoff_state(job) == VISUAL_EXPORT_HANDOFF_LOCAL_DENIED:
                    return self._resolution(job)
                handoff_uncertain = self._handoff_may_have_started(job)
                job.status = "awaiting_auth" if handoff_uncertain else "review_required"
                job.decision = "review_required"
                job.error_code = (
                    "VISUAL_V2_EXPORT_HANDOFF_UNCERTAIN"
                    if handoff_uncertain
                    else self._safe_error(
                        str(error) or f"VISUAL_V2_{error.__class__.__name__.upper()}"
                    )
                )
                job.finished_at = None if handoff_uncertain else datetime.now(UTC)
                job.last_progress_at = datetime.now(UTC)
                self.db.commit()
                return self._resolution(job)
            raise

    def claim_approved_export(self, job_id: str) -> _StagedExport | None:
        """Atomically bind approved final bytes before an external handoff.

        Visual V2 and the legacy Vision V1 adapter share this claim. A durable
        attempt without a known external identifier is intentionally paused so
        neither route can send a second copy after an uncertain handoff.
        """
        job = self._locked_job(job_id)
        if job.external_job_id:
            return None
        if job.attempt_id:
            if self._handoff_state(job) == VISUAL_EXPORT_HANDOFF_CLAIMED:
                # Another caller owns a claim that durably proves no external
                # contact has started. Do not submit it concurrently; an
                # operator can revoke and create a fresh approval if needed.
                self.db.commit()
                return None
            job.status = "awaiting_auth"
            job.decision = "review_required"
            job.error_code = "VISUAL_V2_EXPORT_HANDOFF_UNCERTAIN"
            job.finished_at = None
            job.last_progress_at = datetime.now(UTC)
            self.db.commit()
            return None
        if job.cancel_requested_at is not None or job.status == "cancelled":
            self._cancel_locked(job)
            self.db.commit()
            return None

        job.status = "local_processing"
        job.started_at = job.started_at or datetime.now(UTC)
        job.reasoning_attempt_count += 1
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        staged = self._stage_export(job.id)
        self.db.expire_all()
        job = self._locked_job(job_id)
        if job.external_job_id:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
        if job.attempt_id:
            if self._handoff_state(job) == VISUAL_EXPORT_HANDOFF_CLAIMED:
                self.db.commit()
                return None
            job.status = "awaiting_auth"
            job.decision = "review_required"
            job.error_code = "VISUAL_V2_EXPORT_HANDOFF_UNCERTAIN"
            job.finished_at = None
            job.last_progress_at = datetime.now(UTC)
            self.db.commit()
            return None
        if job.cancel_requested_at is not None or job.status == "cancelled":
            self._cancel_locked(job)
            self.db.commit()
            return None

        # Re-derive the final-byte binding while holding the durable job lock.
        staged = self._stage_export(job.id)
        approval_error = self._approval_error(job, staged.approval_binding)
        if approval_error is not None:
            job.status = "awaiting_auth"
            job.decision = "review_required"
            job.error_code = approval_error
            job.finished_at = None
            job.last_progress_at = datetime.now(UTC)
            self.db.commit()
            return None
        self._verify_staged_request(staged.request)
        job.attempt_id = _export_attempt_id(staged.request_key)
        job.sanitized_package_hash = staged.package_sha256
        job.sanitized_package_size = staged.package_size
        self._set_handoff_state(job, VISUAL_EXPORT_HANDOFF_CLAIMED)
        job.status = "advanced_processing"
        job.decision = None
        job.error_code = None
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return staged

    def record_external_handoff(
        self,
        job_id: str,
        external: dict[str, Any],
    ) -> AnalysisJob:
        """Persist one external identifier before either pipeline reads output."""
        external_id = str(external.get("job_id") or "")
        if not external_id:
            raise VisualV2ContractError("VISUAL_V2_EXTERNAL_JOB_ID_MISSING")
        self.db.expire_all()
        job = self._locked_job(job_id)
        if (
            not job.attempt_id
            or self._handoff_state(job) != VISUAL_EXPORT_HANDOFF_CONTACT
        ):
            raise VisualV2ContractError("VISUAL_V2_EXPORT_CLAIM_MISMATCH")
        job.external_job_id = external_id
        self._set_handoff_state(job, VISUAL_EXPORT_HANDOFF_RECORDED)
        if job.cancel_requested_at is not None or job.status == "cancelled":
            self._cancel_locked(job)
            self.db.commit()
            self.supervisor.cancel_job(external_id)
            return job
        job.status = self._external_status(external)
        job.error_code = self._safe_error(external.get("error_code"))
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return job

    def submit_claimed_export(
        self,
        job_id: str,
        staged: _StagedExport,
    ) -> dict[str, Any]:
        """Re-derive and verify the claimed bytes at the Supervisor boundary."""
        # The claim is durable, but consent, cancellation and document scope can
        # change before the actual Supervisor call. Refresh and serialize that
        # final transition so a confirmed local decision wins before contact.
        try:
            self.db.expire_all()
            job = self._locked_job(job_id)
            if job.cancel_requested_at is not None or job.status == "cancelled":
                raise VisualV2ContractError("VISUAL_V2_CANCELLED")
            approval_error = self._approval_error(job, staged.approval_binding)
            if approval_error is not None:
                raise VisualV2ContractError(approval_error)
            if (
                job.attempt_id != _export_attempt_id(staged.request_key)
                or job.sanitized_package_hash != staged.package_sha256
                or self._handoff_state(job) != VISUAL_EXPORT_HANDOFF_CLAIMED
            ):
                raise VisualV2ContractError("VISUAL_V2_EXPORT_CLAIM_MISMATCH")
            if job.external_job_id is not None:
                raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
            current = self._stage_export(job_id)
            if (
                current.package_sha256 != staged.package_sha256
                or current.approval_binding != staged.approval_binding
                or current.request != staged.request
            ):
                raise VisualV2ContractError("VISUAL_V2_EXPORT_APPROVAL_STALE")
            approval_error = self._approval_error(job, current.approval_binding)
            if approval_error is not None:
                raise VisualV2ContractError(approval_error)
            self._verify_staged_request(current.request)
        except (
            VisualV2ContractError,
            OSError,
            UnidentifiedImageError,
            ValueError,
        ) as error:
            # No external call has happened yet, so this claim may be released
            # and reported as a deterministic local validation failure.
            self.db.rollback()
            self.db.expire_all()
            current_job = self._locked_job(job_id)
            self._release_precontact_claim(
                current_job,
                attempt_id=_export_attempt_id(staged.request_key),
                reason=self._safe_error(str(error)),
            )
            raise
        # Persist the last locally certain state before contact. A process crash
        # or uncertain Supervisor result can then never be confused with a
        # claim that is still safe to revoke and submit again.
        self._set_handoff_state(job, VISUAL_EXPORT_HANDOFF_CONTACT)
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return self.supervisor.create_job(current.request)

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

    def approval_candidate(
        self,
        job_id: str,
        *,
        actor_user_id: int,
    ) -> dict[str, Any]:
        """Return the exact server-derived bytes/scope an operator may approve.

        This method intentionally does not accept caller-provided source metadata.
        It stages local bytes and derives every binding from the durable job/source
        rows plus the current document records.
        """
        self._require_export_operator(actor_user_id)
        job = self._locked_job(job_id)
        if job.status == "accepted_advanced":
            raise VisualV2ContractError("VISUAL_V2_ALREADY_ACCEPTED")
        handoff_state = self._handoff_state(job)
        if job.external_job_id or (
            job.attempt_id and handoff_state != VISUAL_EXPORT_HANDOFF_CLAIMED
        ):
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
        staged = self._stage_export(job.id)
        request_sources = {
            row["source_ref"]: row
            for row in staged.request.get("sources") or []
            if isinstance(row, dict) and isinstance(row.get("source_ref"), str)
        }
        approval = self._approval_public_state(job)
        omitted = job.request_payload.get("omitted_count", 0)
        if not isinstance(omitted, int) or isinstance(omitted, bool) or omitted < 0:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        return {
            "analysis_job_id": job.id,
            "policy_version": VISUAL_EXPORT_POLICY_VERSION,
            "channel": VISUAL_EXPORT_CHANNEL,
            "package_sha256": staged.package_sha256,
            "binding_sha256": self._hash_json(staged.approval_binding),
            "selected_source_count": len(staged.approval_binding["sources"]),
            "omitted_source_count": omitted,
            "complete_source_coverage": omitted == 0,
            **approval,
            "sources": [
                {
                    "source_ref": row["source_ref"],
                    "source_entity_type": row["source_entity_type"],
                    "source_entity_id": row["source_entity_id"],
                    "document_id": row["document_id"],
                    "document_scope": row["document_scope"],
                    "sensitivity": row["sensitivity"],
                    "original_sha256": row["original_sha256"],
                    "final_sha256": row["final_sha256"],
                    "preview_content_type": "image/jpeg",
                    "preview_size": self._staged_source_path(
                        request_sources[row["source_ref"]]
                    ).stat().st_size,
                }
                for row in staged.approval_binding["sources"]
            ],
        }

    def approval_source_preview(
        self,
        job_id: str,
        *,
        actor_user_id: int,
        expected_document_id: int,
        source_ref: str,
        expected_package_sha256: str,
        expected_binding_sha256: str,
        expected_source_sha256: str,
    ) -> VisualExportApprovalPreview:
        """Read one bounded final raster once after re-deriving its binding."""
        self._require_export_operator(actor_user_id)
        job = self._locked_job(job_id)
        if job.external_job_id or (
            job.attempt_id
            and self._handoff_state(job) != VISUAL_EXPORT_HANDOFF_CLAIMED
        ):
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
        staged = self._stage_export(job.id)
        if staged.package_sha256 != expected_package_sha256:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_BYTES_MISMATCH")
        if self._hash_json(staged.approval_binding) != expected_binding_sha256:
            raise VisualV2ContractError("VISUAL_V2_EXPORT_SCOPE_MISMATCH")
        binding = next(
            (
                row
                for row in staged.approval_binding["sources"]
                if row["source_ref"] == source_ref
            ),
            None,
        )
        descriptor = next(
            (
                row
                for row in staged.request.get("sources") or []
                if isinstance(row, dict) and row.get("source_ref") == source_ref
            ),
            None,
        )
        if binding is None or descriptor is None:
            raise VisualV2ContractError("VISUAL_V2_SOURCE_BINDING_INVALID")
        if binding["document_id"] != expected_document_id:
            raise VisualV2ContractError("VISUAL_V2_EXPORT_SCOPE_MISMATCH")
        if binding["final_sha256"] != expected_source_sha256:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_BYTES_MISMATCH")
        target = self._staged_source_path(descriptor)
        with target.open("rb") as stream:
            content = stream.read(MAX_PREPARED_BYTES + 1)
        if len(content) > MAX_PREPARED_BYTES:
            raise VisualV2ContractError("VISUAL_V2_PREVIEW_TOO_LARGE")
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != expected_source_sha256:
            raise VisualV2ContractError("VISUAL_V2_STAGED_SHA_MISMATCH")
        return VisualExportApprovalPreview(
            content=content,
            content_type="image/jpeg",
            source_ref=source_ref,
            source_sha256=actual_sha256,
            package_sha256=staged.package_sha256,
        )

    def approve_export(
        self,
        job_id: str,
        *,
        actor_user_id: int,
        expected_package_sha256: str,
        expected_source_sha256: dict[str, str],
        approval_kind: Literal["public_safe", "locally_redacted"],
        expires_at: datetime,
        expected_binding_sha256: str | None = None,
    ) -> VisualV2Resolution:
        """Persist a bounded administrator decision for exact staged bytes."""
        self._require_export_operator(actor_user_id)
        job = self._locked_job(job_id)
        if job.status == "accepted_advanced":
            raise VisualV2ContractError("VISUAL_V2_ALREADY_ACCEPTED")
        if job.external_job_id or job.attempt_id:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
        if job.cancel_requested_at is not None or job.status == "cancelled":
            raise VisualV2ContractError("VISUAL_V2_CANCELLED")
        if expires_at.tzinfo is None:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_EXPIRY_INVALID")
        normalized_expiry = expires_at.astimezone(UTC)
        if normalized_expiry <= datetime.now(UTC):
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_EXPIRED")
        if approval_kind not in {"public_safe", "locally_redacted"}:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_KIND_INVALID")
        staged = self._stage_export(job.id)
        actual_sources = {
            row["source_ref"]: row["final_sha256"]
            for row in staged.approval_binding["sources"]
        }
        if (
            expected_package_sha256 != staged.package_sha256
            or expected_source_sha256 != actual_sources
        ):
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_BYTES_MISMATCH")
        if (
            expected_binding_sha256 is not None
            and expected_binding_sha256 != self._hash_json(staged.approval_binding)
        ):
            raise VisualV2ContractError("VISUAL_V2_EXPORT_SCOPE_MISMATCH")
        signals = dict(job.quality_signals or {})
        signals[VISUAL_EXPORT_APPROVAL_KEY] = {
            "schema": "VISUAL_EXPORT_APPROVAL_V1",
            "state": "approved",
            "policy_version": VISUAL_EXPORT_POLICY_VERSION,
            "channel": VISUAL_EXPORT_CHANNEL,
            "approved_by_user_id": actor_user_id,
            "approval_kind": approval_kind,
            "approved_at": datetime.now(UTC).isoformat(),
            "expires_at": normalized_expiry.isoformat(),
            "binding": staged.approval_binding,
        }
        job.quality_signals = signals
        job.status = "advanced_queued"
        job.decision = None
        job.error_code = None
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return self._resolution(job)

    def revoke_export_approval(
        self,
        job_id: str,
        *,
        actor_user_id: int,
        expected_document_id: int,
    ) -> VisualV2Resolution:
        self._require_export_operator(actor_user_id)
        job = self._locked_job(job_id)
        document_ids = {
            self._document_for_source(source).id
            for source in self.db.query(AnalysisJobSource).filter(
                AnalysisJobSource.analysis_job_id == job.id
            ).all()
        }
        if document_ids != {expected_document_id}:
            raise VisualV2ContractError("VISUAL_V2_EXPORT_SCOPE_MISMATCH")
        if job.external_job_id:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
        if job.attempt_id:
            # A confirmed local revocation may release a claim only while the
            # durable ledger still proves that no Supervisor contact started.
            if self._handoff_state(job) != VISUAL_EXPORT_HANDOFF_CLAIMED:
                raise VisualV2ContractError("VISUAL_V2_APPROVAL_ALREADY_EXPORTED")
            claimed_attempt = job.attempt_id
            job.attempt_id = None
            job.sanitized_package_hash = None
            job.sanitized_package_size = None
        else:
            claimed_attempt = None
        signals = dict(job.quality_signals or {})
        previous = signals.get(VISUAL_EXPORT_APPROVAL_KEY)
        approval = dict(previous) if isinstance(previous, dict) else {}
        approval.update({
            "schema": "VISUAL_EXPORT_APPROVAL_V1",
            "state": "revoked",
            "revoked_by_user_id": actor_user_id,
            "revoked_at": datetime.now(UTC).isoformat(),
        })
        signals[VISUAL_EXPORT_APPROVAL_KEY] = approval
        job.quality_signals = signals
        self._set_handoff_state(
            job,
            VISUAL_EXPORT_HANDOFF_LOCAL_DENIED,
            attempt_id=claimed_attempt,
            reason="VISUAL_V2_EXPORT_APPROVAL_REVOKED",
        )
        job.status = "awaiting_auth"
        job.decision = "review_required"
        job.error_code = "VISUAL_V2_EXPORT_APPROVAL_REVOKED"
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return self._resolution(job)

    def _locked_job(self, job_id: str) -> AnalysisJob:
        job = self.db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            AnalysisJob.analysis_type == VISUAL_V2_ANALYSIS_TYPE,
            AnalysisJob.source_domain == VISUAL_V2_SOURCE_DOMAIN,
        ).with_for_update().one_or_none()
        if job is None:
            raise VisualV2ContractError("VISUAL_V2_JOB_NOT_FOUND")
        return job

    @staticmethod
    def _handoff_record(job: AnalysisJob) -> dict[str, Any] | None:
        signals = job.quality_signals if isinstance(job.quality_signals, dict) else {}
        record = signals.get(VISUAL_EXPORT_HANDOFF_KEY)
        if not isinstance(record, dict):
            return None
        if record.get("schema") != VISUAL_EXPORT_HANDOFF_SCHEMA:
            return None
        return record

    @classmethod
    def _handoff_state(cls, job: AnalysisJob) -> str | None:
        record = cls._handoff_record(job)
        if record is None:
            return None
        state = str(record.get("state") or "")
        if state in {
            VISUAL_EXPORT_HANDOFF_CLAIMED,
            VISUAL_EXPORT_HANDOFF_CONTACT,
            VISUAL_EXPORT_HANDOFF_RECORDED,
        } and record.get("attempt_id") != job.attempt_id:
            return None
        if state not in {
            VISUAL_EXPORT_HANDOFF_CLAIMED,
            VISUAL_EXPORT_HANDOFF_CONTACT,
            VISUAL_EXPORT_HANDOFF_RECORDED,
            VISUAL_EXPORT_HANDOFF_LOCAL_DENIED,
        }:
            return None
        return state

    @classmethod
    def _handoff_may_have_started(cls, job: AnalysisJob) -> bool:
        if job.external_job_id:
            # Once the durable external identifier exists, failures belong to
            # result retrieval/validation rather than the uncertain-contact
            # window addressed by this marker.
            return False
        if not job.attempt_id:
            return False
        # Historical attempts without the versioned marker are ambiguous and
        # remain fail-closed. Only the explicit pre-contact state is releasable.
        return cls._handoff_state(job) != VISUAL_EXPORT_HANDOFF_CLAIMED

    @staticmethod
    def _set_handoff_state(
        job: AnalysisJob,
        state: str,
        *,
        attempt_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        signals = dict(job.quality_signals or {})
        record: dict[str, Any] = {
            "schema": VISUAL_EXPORT_HANDOFF_SCHEMA,
            "state": state,
            "attempt_id": attempt_id if attempt_id is not None else job.attempt_id,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        if reason:
            record["reason"] = reason
        signals[VISUAL_EXPORT_HANDOFF_KEY] = record
        job.quality_signals = signals

    def _release_precontact_claim(
        self,
        job: AnalysisJob,
        *,
        attempt_id: str,
        reason: str,
    ) -> bool:
        if (
            job.status == "cancelled"
            or job.cancel_requested_at is not None
            or job.external_job_id is not None
            or job.attempt_id != attempt_id
            or self._handoff_state(job) != VISUAL_EXPORT_HANDOFF_CLAIMED
        ):
            return False
        job.attempt_id = None
        job.sanitized_package_hash = None
        job.sanitized_package_size = None
        self._set_handoff_state(
            job,
            VISUAL_EXPORT_HANDOFF_LOCAL_DENIED,
            attempt_id=attempt_id,
            reason=reason,
        )
        job.status = "awaiting_auth"
        job.decision = "review_required"
        job.error_code = reason
        job.finished_at = None
        job.last_progress_at = datetime.now(UTC)
        self.db.commit()
        return True

    def _require_export_operator(self, actor_user_id: int) -> None:
        actor = self.db.query(User).join(Role, User.role_id == Role.id).filter(
            User.id == actor_user_id,
            User.is_active.is_(True),
            User.trashed_at.is_(None),
            User.purged_at.is_(None),
            Role.name == "Administrator",
        ).with_for_update().one_or_none()
        if actor is None:
            raise VisualV2ContractError("VISUAL_V2_APPROVAL_FORBIDDEN")

    def assistant_evidence(
        self,
        resolution: VisualV2Resolution,
        *,
        document_id: int,
        question: str | None = None,
    ) -> tuple[list[AgentSource], list[dict[str, Any]]]:
        payload = resolution.result_payload
        if resolution.state != "accepted" or not isinstance(payload, dict):
            return [], []
        coverage = self.validated_coverage(resolution, question=question)
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
                "coverage": coverage,
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
        staged = self._stage_export(job_id)
        return (
            staged.request_key,
            staged.request,
            staged.package_sha256,
            staged.package_size,
        )

    def _stage_export(self, job_id: str) -> _StagedExport:
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
        approval_sources: list[dict[str, Any]] = []
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
            document = self._document_for_source(source)
            if self._restricted(document):
                raise VisualV2ContractError("VISUAL_V2_RESTRICTED_NEVER_EXTERNAL")
            prepared = self._normalized_raster(path)
            external_ref = str(row.get("external_ref") or "")
            prepared_sha256 = self._sha256(prepared)
            staged.append((external_ref, prepared, prepared_sha256))
            approval_sources.append({
                "source_ref": external_ref,
                "source_entity_type": source.source_entity_type,
                "source_entity_id": source.source_entity_id,
                "document_id": document.id,
                "document_scope": self._document_scope(document),
                "document_sha256": str(document.checksum_sha256 or "").casefold(),
                "original_sha256": source.checksum_sha256,
                "final_sha256": prepared_sha256,
                "storage_identity_sha256": self._storage_identity(path),
                "sensitivity": (
                    "restricted_never_external"
                    if self._restricted(document)
                    else source.sensitivity
                ),
            })
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
            if path != target and not target.exists():
                try:
                    with path.open("rb") as source_stream, target.open("xb") as target_stream:
                        shutil.copyfileobj(source_stream, target_stream)
                except FileExistsError:
                    pass
            actual = self._sha256(target)
            if actual != checksum:
                raise VisualV2ContractError("VISUAL_V2_STAGED_SHA_MISMATCH")
            try:
                os.chmod(target, 0o444)
            except OSError:
                # Exact hashes are rechecked immediately before the boundary;
                # read-only mode is additional local hardening, not the proof.
                pass
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
            "policy_version": VISUAL_EXPORT_POLICY_VERSION,
            "channel": VISUAL_EXPORT_CHANNEL,
            "request_key": request_key,
            "sources": [{"source_ref": row["source_ref"], "sha256": row["sha256"]} for row in descriptors],
            "capabilities": list(job.request_payload.get("requested_capabilities") or []),
        }
        canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        package_sha256 = hashlib.sha256(canonical).hexdigest()
        binding = {
            "schema": VISUAL_EXPORT_BINDING_SCHEMA,
            "policy_version": VISUAL_EXPORT_POLICY_VERSION,
            "channel": VISUAL_EXPORT_CHANNEL,
            "package_sha256": package_sha256,
            "request_key": request_key,
            "sources": approval_sources,
        }
        return _StagedExport(
            request_key=request_key,
            request={"request_key": request_key, "sources": descriptors},
            package_sha256=package_sha256,
            package_size=len(canonical),
            approval_binding=binding,
        )

    def _approval_error(
        self,
        job: AnalysisJob,
        binding: dict[str, Any],
    ) -> str | None:
        signals = job.quality_signals if isinstance(job.quality_signals, dict) else {}
        approval = signals.get(VISUAL_EXPORT_APPROVAL_KEY)
        if not isinstance(approval, dict):
            return "VISUAL_V2_EXPORT_APPROVAL_REQUIRED"
        if approval.get("state") == "revoked":
            return "VISUAL_V2_EXPORT_APPROVAL_REVOKED"
        if approval.get("state") != "approved":
            return "VISUAL_V2_EXPORT_APPROVAL_REQUIRED"
        if (
            approval.get("schema") != "VISUAL_EXPORT_APPROVAL_V1"
            or approval.get("policy_version") != VISUAL_EXPORT_POLICY_VERSION
            or approval.get("channel") != VISUAL_EXPORT_CHANNEL
            or approval.get("approval_kind") not in {"public_safe", "locally_redacted"}
        ):
            return "VISUAL_V2_EXPORT_SCOPE_MISMATCH"
        try:
            expires_at = datetime.fromisoformat(str(approval.get("expires_at") or ""))
            if expires_at.tzinfo is None or expires_at.astimezone(UTC) <= datetime.now(UTC):
                return "VISUAL_V2_EXPORT_APPROVAL_EXPIRED"
        except ValueError:
            return "VISUAL_V2_EXPORT_APPROVAL_EXPIRED"
        if approval.get("binding") != binding:
            return "VISUAL_V2_EXPORT_APPROVAL_STALE"
        return None

    def _approval_public_state(self, job: AnalysisJob) -> dict[str, Any]:
        signals = job.quality_signals if isinstance(job.quality_signals, dict) else {}
        approval = signals.get(VISUAL_EXPORT_APPROVAL_KEY)
        state = "not_approved"
        approval_kind = None
        expires_at = None
        if isinstance(approval, dict):
            raw_state = approval.get("state")
            if raw_state == "revoked":
                state = "revoked"
            elif raw_state == "approved":
                approval_kind = approval.get("approval_kind")
                expires_at = approval.get("expires_at")
                try:
                    expiry = datetime.fromisoformat(str(expires_at or ""))
                    state = (
                        "approved"
                        if expiry.tzinfo is not None
                        and expiry.astimezone(UTC) > datetime.now(UTC)
                        else "expired"
                    )
                except ValueError:
                    state = "expired"
        no_contact = not job.attempt_id or (
            self._handoff_state(job) == VISUAL_EXPORT_HANDOFF_CLAIMED
        )
        return {
            "approval_state": state,
            "approval_kind": approval_kind,
            "approval_expires_at": expires_at,
            "can_approve": not job.attempt_id and state != "approved",
            "can_revoke": state == "approved" and not job.external_job_id and no_contact,
        }

    def _staged_source_path(self, descriptor: dict[str, Any]) -> Path:
        relative = str(descriptor.get("incoming_relative_path") or "")
        try:
            target = (self.spool_root / relative).resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise VisualV2ContractError("VISUAL_V2_STAGED_PATH_INVALID") from error
        if not target.is_relative_to(self.spool_root) or not target.is_file():
            raise VisualV2ContractError("VISUAL_V2_STAGED_PATH_INVALID")
        return target

    def _verify_staged_request(self, request: dict[str, Any]) -> None:
        for row in request.get("sources") or []:
            if not isinstance(row, dict):
                raise VisualV2ContractError("VISUAL_V2_SOURCE_MANIFEST_INVALID")
            target = self._staged_source_path(row)
            if self._sha256(target) != row.get("sha256"):
                raise VisualV2ContractError("VISUAL_V2_STAGED_SHA_MISMATCH")

    def _document_for_source(self, source: AnalysisJobSource) -> Document:
        if source.source_entity_type == "Document":
            document = self.db.get(Document, int(source.source_entity_id))
        elif source.source_entity_type == "DocumentPage":
            entity = self.db.get(DocumentPage, int(source.source_entity_id))
            document = self.db.get(Document, entity.document_id) if entity else None
        elif source.source_entity_type == "DocumentAsset":
            entity = self.db.get(DocumentAsset, int(source.source_entity_id))
            document = self.db.get(Document, entity.document_id) if entity else None
        else:
            document = None
        if document is None or document.trashed_at is not None or document.purged_at is not None:
            raise VisualV2ContractError("VISUAL_V2_DOCUMENT_UNAVAILABLE")
        return document

    def _storage_identity(self, path: Path) -> str:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.data_root):
            raise VisualV2ContractError("VISUAL_V2_SOURCE_PATH_INVALID")
        relative = resolved.relative_to(self.data_root).as_posix()
        return hashlib.sha256(relative.encode("utf-8")).hexdigest()

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
        coverage = self._validated_coverage_payload(payload)
        if coverage["required_page"] is not None and not coverage["required_page_covered"]:
            raise VisualV2ContractError("VISUAL_V2_REQUIRED_PAGE_NOT_COVERED")
        self._validate_payload_size(payload)
        return payload, raw_sha256

    def _legacy_payload(
        self,
        document: Document,
        planned: list[_PlannedSource],
        *,
        job: AnalysisJob,
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
        payload = self._result_payload(job, atoms[:MAX_VISUAL_ATOMS], len(planned))
        coverage = self._validated_coverage_payload(payload)
        if coverage["required_page"] is not None and not coverage["required_page_covered"]:
            return None
        self._validate_payload_size(payload)
        return payload

    @classmethod
    def _result_payload(
        cls,
        job: AnalysisJob,
        atoms: list[dict[str, Any]],
        selected_count: int,
    ) -> dict[str, Any]:
        request = job.request_payload if isinstance(job.request_payload, dict) else {}
        persisted_selected = request.get("selected_count")
        omitted_count = request.get("omitted_count")
        required_page = request.get("required_page")
        if persisted_selected != selected_count:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        direct_atoms = [
            item
            for item in atoms
            if item.get("kind") in {"observation", "visible_text"}
            and isinstance(item.get("text"), str)
            and item["text"].strip()
        ]
        covered_source_count = len({item.get("source_ref") for item in direct_atoms})
        required_page_covered = bool(
            required_page is not None
            and any(item.get("page_number") == required_page for item in direct_atoms)
        )
        complete = (
            covered_source_count == selected_count
            and omitted_count == 0
        )
        payload = {
            "schema_version": VISUAL_V2_RESULT_SCHEMA,
            "analysis_job_id": job.id,
            "input_fingerprint": job.input_fingerprint,
            "evidence": atoms,
            "coverage": {
                "selected_source_count": selected_count,
                "covered_source_count": covered_source_count,
                "omitted_source_count": omitted_count,
                "required_page": required_page,
                "required_page_covered": required_page_covered,
                "complete": complete,
                "limitation_code": (
                    "VISUAL_V2_SOURCE_LIMIT_PARTIAL"
                    if isinstance(omitted_count, int)
                    and not isinstance(omitted_count, bool)
                    and omitted_count > 0
                    else None
                ),
            },
        }
        cls._validated_coverage_payload(payload)
        return payload

    def validated_coverage(
        self,
        resolution: VisualV2Resolution,
        *,
        question: str | None = None,
    ) -> dict[str, Any]:
        payload = resolution.result_payload
        if resolution.state != "accepted" or not isinstance(payload, dict):
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        stored = self._validated_coverage_payload(payload)
        required_page = self._requested_page(question)
        evidence = payload.get("evidence")
        direct_atoms = [
            item
            for item in evidence
            if isinstance(item, dict)
            and item.get("kind") in {"observation", "visible_text"}
            and isinstance(item.get("text"), str)
            and item["text"].strip()
        ]
        scoped = dict(stored)
        scoped["required_page"] = required_page
        scoped["required_page_covered"] = bool(
            required_page is not None
            and any(item.get("page_number") == required_page for item in direct_atoms)
        )
        scoped_payload = dict(payload)
        scoped_payload["coverage"] = scoped
        return dict(self._validated_coverage_payload(scoped_payload))

    @staticmethod
    def _validated_coverage_payload(payload: dict[str, Any]) -> dict[str, Any]:
        coverage = payload.get("coverage")
        evidence = payload.get("evidence")
        if not isinstance(coverage, dict) or not isinstance(evidence, list):
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        selected = coverage.get("selected_source_count")
        covered = coverage.get("covered_source_count")
        omitted = coverage.get("omitted_source_count")
        required_page = coverage.get("required_page")
        required_covered = coverage.get("required_page_covered")
        complete = coverage.get("complete")
        limitation = coverage.get("limitation_code")
        integers = (selected, covered, omitted)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in integers):
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        if selected < 1 or selected > MAX_VISUAL_SOURCES or covered < 0 or omitted < 0:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        if covered > selected:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        if required_page is not None and (
            not isinstance(required_page, int)
            or isinstance(required_page, bool)
            or required_page < 1
        ):
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        if not isinstance(required_covered, bool) or not isinstance(complete, bool):
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        if required_page is None and required_covered:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        direct_atoms = [
            item
            for item in evidence
            if isinstance(item, dict)
            and item.get("kind") in {"observation", "visible_text"}
            and isinstance(item.get("text"), str)
            and item["text"].strip()
        ]
        direct_refs = {
            item.get("source_ref")
            for item in direct_atoms
            if isinstance(item.get("source_ref"), str)
        }
        if covered != len(direct_refs):
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        page_is_covered = bool(
            required_page is not None
            and any(item.get("page_number") == required_page for item in direct_atoms)
        )
        if required_covered != page_is_covered:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        expected_complete = covered == selected and omitted == 0
        if complete != expected_complete:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        expected_limitation = (
            "VISUAL_V2_SOURCE_LIMIT_PARTIAL" if omitted > 0 else None
        )
        if limitation != expected_limitation:
            raise VisualV2ContractError("VISUAL_V2_COVERAGE_INVALID")
        return coverage

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
        self._validated_coverage_payload(payload)
        self._validate_payload_size(payload)
        validated_sha256 = self._hash_json(payload)
        job.result_payload = payload
        job.status = "accepted_advanced"
        job.decision = "accepted"
        job.error_code = None
        quality_signals = dict(job.quality_signals or {})
        quality_signals.update({
            "contract": VISUAL_V2_RESULT_SCHEMA,
            "mode": mode,
            "raw_response_sha256": raw_sha256,
            "validated_payload_sha256": validated_sha256,
            "source_count": len(job.sources),
        })
        job.quality_signals = quality_signals
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
        try:
            return resolve_document_storage_path(
                storage_path=storage_path,
                data_root=self.data_root,
            )
        except DocumentStorageError as error:
            raise VisualV2ContractError("VISUAL_V2_SOURCE_PATH_INVALID") from error

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
        try:
            return resolve_document_storage_path(
                storage_path=storage_path,
                data_root=self.data_root,
            )
        except DocumentStorageError as error:
            raise VisualV2ContractError("VISUAL_V2_SOURCE_PATH_INVALID") from error

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
        document_scope: dict[str, Any],
        sources: list[_PlannedSource],
    ) -> str:
        canonical = json.dumps({
            "contract": VISUAL_V2_CONTRACT_GENERATION,
            "document_checksum": document_checksum,
            "document_scope": document_scope,
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
    def _document_scope(document: Document) -> dict[str, Any]:
        """Return the server-derived, versioned business scope of source bytes."""
        return {
            "schema": VISUAL_EXPORT_DOCUMENT_SCOPE_SCHEMA,
            "document_id": document.id,
            "client_id": document.client_id,
            "project_id": document.project_id,
            "inspection_id": document.inspection_id,
            "candidate_id": document.candidate_id,
        }

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
            or_(
                AnalysisJob.status != "awaiting_auth",
                AnalysisJob.error_code.is_(None),
                AnalysisJob.error_code.notin_(VISUAL_EXPORT_WAIT_CODES),
            ),
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


def start_visual_v2_dispatcher() -> asyncio.Task | None:
    if not settings.visual_v2_enabled:
        logger.info("Visual V2 dispatcher disabled by configuration.")
        return None
    return asyncio.create_task(VisualV2Dispatcher().run(), name="visual-v2-dispatcher")
