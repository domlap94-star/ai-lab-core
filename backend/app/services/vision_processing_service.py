from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.repositories.document_asset_repository import DocumentAssetRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.vision import VISION_RESULT_SCHEMA, VisionResult
from app.services.document_service import (
    DocumentContentUnavailableError,
    UnsafeDocumentStoragePathError,
    resolve_document_storage_path,
)
from app.services.vision_need_classifier import (
    VisionClassificationResult,
    VisionNeedClassifier,
    VisionSourceCandidate,
)
from app.services.vision_supervisor_client import (
    VisionSupervisorClient,
    VisionSupervisorUnavailable,
)


register_heif_opener()


@dataclass(frozen=True)
class VisionAdvanceResult:
    document_id: int
    classification: str | None
    status: str
    worker_status: str | None = None


class VisionDocumentNotFound(RuntimeError):
    pass


class VisionDocumentUnsupported(RuntimeError):
    pass


class VisionProcessingService:
    MAX_IMAGE_EDGE = 2048
    MAX_PREPARED_BYTES = 12 * 1024 * 1024

    def __init__(self, db: Session, *, supervisor=None, classifier=None) -> None:
        self.db = db
        self.documents = DocumentRepository(db)
        self.assets = DocumentAssetRepository(db)
        self.supervisor = supervisor or VisionSupervisorClient()
        self.classifier = classifier or VisionNeedClassifier()
        self.data_root = Path(settings.data_dir).resolve()
        self.spool_root = (self.data_root / "vision-spool").resolve()

    def advance(self, document_id: int, *, explicit: bool = False) -> VisionAdvanceResult:
        document = self.documents.get(document_id)
        if document is None:
            raise VisionDocumentNotFound
        if not explicit and not document.vision_auto_eligible:
            return self._result(document)
        if document.vision_attempt_count >= 3 and document.vision_status in {
            "failed_retryable", "failed_permanent"
        }:
            document.vision_status = "failed_permanent"
            document.vision_error_code = document.vision_error_code or "MAX_ATTEMPTS"
            self.documents.commit()
            return self._result(document, "FAILED")
        pages = self.documents.get_pages(document.id)
        assets = self.assets.get_for_document(document.id)
        classification = self.classifier.classify(document=document, pages=pages, assets=assets)
        if not classification.sources and classification.reason in {"IMAGE_AWAITS_NORMAL_PROCESSING", "DOCUMENT_AWAITS_PAGE_RENDER"}:
            return self._result(document)
        document.vision_classification = classification.classification
        if classification.classification == "text_sufficient":
            document.vision_status = "not_needed"
            document.vision_error_code = None
            self.documents.commit()
            return self._result(document)
        if classification.classification == "unsupported" or not classification.sources:
            document.vision_status = "failed_permanent"
            document.vision_error_code = "UNSUPPORTED"
            self.documents.commit()
            return self._result(document)
        try:
            request_key, payload, source_map = self._stage(document, classification)
            job = self.supervisor.create_job(payload)
            return self._apply_job(document, classification, request_key, source_map, job)
        except (
            VisionDocumentUnsupported,
            DocumentContentUnavailableError,
            UnsafeDocumentStoragePathError,
            UnidentifiedImageError,
        ):
            document.vision_status = "failed_permanent"
            document.vision_error_code = "UNSUPPORTED_INPUT"
            self.documents.commit()
            return self._result(document, "FAILED")
        except VisionSupervisorUnavailable:
            document.vision_attempt_count += 1
            document.vision_status = (
                "failed_permanent"
                if document.vision_attempt_count >= 3
                else "failed_retryable"
            )
            document.vision_error_code = "WORKER_UNAVAILABLE"
            document.vision_next_retry_at = (
                None
                if document.vision_attempt_count >= 3
                else self._next_retry(document.vision_attempt_count)
            )
            self.documents.commit()
            return self._result(document, "FAILED")

    def _stage(self, document: Document, classification: VisionClassificationResult):
        descriptors = []
        source_map: dict[str, VisionSourceCandidate] = {}
        prepared: list[tuple[VisionSourceCandidate, Path, str]] = []
        for index, candidate in enumerate(classification.sources[:4], 1):
            source_path = self._source_path(document, candidate)
            prepared_path, extension = self._prepare_path(source_path)
            checksum = self._sha256(prepared_path)
            prepared.append((candidate, prepared_path, extension))
            descriptors.append(f"S{index}:{document.id}:{candidate.page.page_number if candidate.page else 0}:{candidate.asset.id if candidate.asset else 0}:{checksum}")
        request_key = hashlib.sha256((VISION_RESULT_SCHEMA + "|" + "|".join(descriptors)).encode()).hexdigest()
        incoming = self.spool_root / "incoming" / request_key
        incoming.mkdir(parents=True, exist_ok=True)
        for index, (candidate, source_path, extension) in enumerate(prepared, 1):
            ref = f"S{index}"
            target = incoming / f"{ref}{extension}"
            if source_path != target:
                shutil.copy2(source_path, target)
            checksum = self._sha256(target)
            source_map[ref] = candidate
            descriptors[index - 1] = {
                "source_ref": ref,
                "document_id": document.id,
                "page_number": candidate.page.page_number if candidate.page else None,
                "asset_id": candidate.asset.id if candidate.asset else None,
                "sha256": checksum,
                "incoming_relative_path": f"incoming/{request_key}/{target.name}",
            }
        return request_key, {"request_key": request_key, "sources": descriptors}, source_map

    def _apply_job(self, document, classification, request_key, source_map, job):
        state = str(job.get("state") or "FAILED").upper()
        document.vision_attempt_count = max(document.vision_attempt_count, int(job.get("attempt_count") or 0))
        document.vision_source_checksum = request_key
        document.vision_next_retry_at = self._parse_time(job.get("next_retry_at"))
        state_map = {
            "QUEUED": "queued", "RUNNING": "processing", "AUTH_REQUIRED": "pending_auth",
            "UI_CHANGED": "ui_changed", "FAILED": "failed_retryable", "CANCELLED": "failed_retryable",
        }
        if state == "COMPLETE":
            self._persist_complete(document, classification, source_map, str(job["job_id"]))
            self.documents.commit()
            return self._result(document, state)
        document.vision_status = (
            "failed_permanent"
            if state == "FAILED" and document.vision_attempt_count >= 3
            else state_map.get(state, "failed_retryable")
        )
        document.vision_error_code = str(job.get("error_code") or state)[:100]
        for candidate in source_map.values():
            source = candidate.page or candidate.asset
            source.vision_status = document.vision_status
            source.vision_attempt_count = document.vision_attempt_count
            source.vision_error_code = document.vision_error_code
        self.documents.commit()
        return self._result(document, state)

    def _persist_complete(self, document, classification, source_map, job_id):
        job_dir = self.spool_root / "jobs" / job_id
        result_path = job_dir / "output" / "vision.json"
        manifest_path = job_dir / "output" / "result_manifest.json"
        if not result_path.is_file() or not manifest_path.is_file():
            raise VisionSupervisorUnavailable
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        result = VisionResult.model_validate(raw)
        if result.job_id != job_id:
            raise VisionSupervisorUnavailable
        refs = set(source_map)
        result_refs = {item.source_ref for key in (result.observations, result.possible_interpretations, result.uncertainties, result.visible_text, result.measurements, result.image_quality) for item in key}
        if not result_refs.issubset(refs) or {item.source_ref for item in result.image_quality} != refs:
            raise VisionSupervisorUnavailable
        result_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        job_manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
        expected_sources = {
            item["source_ref"]: item["sha256"] for item in job_manifest.get("sources", [])
        }
        if result_manifest.get("source_sha256") != expected_sources:
            raise VisionSupervisorUnavailable
        canonical_hash = hashlib.sha256((json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n").encode()).hexdigest()
        if result_manifest.get("output_sha256") != canonical_hash:
            raise VisionSupervisorUnavailable
        analyzed_at = datetime.now(UTC)
        for ref, candidate in source_map.items():
            source = candidate.page or candidate.asset
            filtered = self._for_source(result, ref)
            source.vision_analysis = json.dumps(filtered, ensure_ascii=False, separators=(",", ":"))
            source.vision_status = "complete"
            source.vision_analyzed_at = analyzed_at
            source.vision_schema_version = VISION_RESULT_SCHEMA
            source.vision_source_checksum = result_manifest["source_sha256"][ref]
            source.vision_error_code = None
            source.vision_attempt_count = document.vision_attempt_count
        document.vision_status = "partial" if classification.partial else "complete"
        document.vision_analyzed_at = analyzed_at
        document.vision_schema_version = VISION_RESULT_SCHEMA
        document.vision_error_code = None
        document.vision_next_retry_at = None

    @staticmethod
    def _for_source(result: VisionResult, ref: str) -> dict:
        data = result.model_dump(mode="json")
        for key in ("observations", "possible_interpretations", "uncertainties", "visible_text", "measurements", "image_quality"):
            data[key] = [item for item in data[key] if item["source_ref"] == ref]
        return data

    def _source_path(self, document, candidate):
        storage_path = candidate.asset.storage_path if candidate.asset else candidate.page.render_path if candidate.page and not candidate.use_document_file else document.storage_path
        if not storage_path:
            raise VisionDocumentUnsupported
        return resolve_document_storage_path(storage_path=storage_path, data_root=self.data_root)

    def _prepare_path(self, source: Path):
        extension = source.suffix.casefold()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}:
            raise VisionDocumentUnsupported
        with Image.open(source) as image:
            requires_copy = (
                extension in {".heic", ".heif", ".tif", ".tiff", ".bmp"}
                or max(image.size) > self.MAX_IMAGE_EDGE
                or source.stat().st_size > self.MAX_PREPARED_BYTES
            )
            if not requires_copy:
                return source, extension
            converted_root = self.spool_root / "converted"
            converted_root.mkdir(parents=True, exist_ok=True)
            converted = converted_root / f"{self._sha256(source)}.jpg"
            if not converted.exists():
                prepared = image.convert("RGB")
                prepared.thumbnail(
                    (self.MAX_IMAGE_EDGE, self.MAX_IMAGE_EDGE),
                    Image.Resampling.LANCZOS,
                )
                prepared.save(converted, format="JPEG", quality=90, optimize=True)
            if converted.stat().st_size > self.MAX_PREPARED_BYTES:
                raise VisionDocumentUnsupported
            return converted, ".jpg"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _parse_time(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

    @staticmethod
    def _next_retry(attempt_count):
        from datetime import timedelta
        return datetime.now(UTC) + timedelta(minutes=5 if attempt_count < 2 else 30)

    @staticmethod
    def _result(document, worker_status=None):
        return VisionAdvanceResult(document.id, document.vision_classification, document.vision_status, worker_status)
