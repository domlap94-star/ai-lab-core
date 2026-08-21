from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.knowledge_base import KnowledgeBaseItem, KnowledgeBasePage
from app.models.user import User
from app.schemas.knowledge_base import KnowledgeBaseMetadata, KnowledgeBasePatch
from app.services.change_history_service import ChangeHistoryService
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_ocr_service import DocumentOCRService


class KnowledgeBaseError(ValueError):
    pass


class KnowledgeBaseService:
    MAX_BYTES = 250 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".tsv", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
    ALLOWED_MIME_TYPES = {
        ".pdf": {"application/pdf"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".txt": {"text/plain"},
        ".csv": {"text/csv", "text/plain", "application/csv"},
        ".tsv": {"text/tab-separated-values", "text/plain"},
        ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
        ".png": {"image/png"}, ".tif": {"image/tiff"},
        ".tiff": {"image/tiff"}, ".webp": {"image/webp"},
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage_root = Path(settings.data_dir) / "knowledge-base"

    @staticmethod
    def _snapshot(item: KnowledgeBaseItem) -> dict[str, object]:
        snapshot = {name: getattr(item, name) for name in ("title", "source", "publisher", "version", "effective_date", "category", "status", "supersedes_id", "processing_status", "processing_method", "archived_at")}
        snapshot["tags"] = ", ".join(item.tags or [])
        return snapshot

    @staticmethod
    def _safe_name(value: str) -> str:
        name = Path(value).name
        if name != value or not name.strip() or len(name) > 255 or "\x00" in name:
            raise KnowledgeBaseError("knowledge_base_filename_invalid")
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:180]

    def create(self, *, metadata: KnowledgeBaseMetadata, filename: str, content_type: str, content: bytes, actor: User) -> tuple[KnowledgeBaseItem, list[int]]:
        if not content or len(content) > self.MAX_BYTES:
            raise KnowledgeBaseError("knowledge_base_file_size_invalid")
        safe = self._safe_name(filename)
        extension = Path(safe).suffix.lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            raise KnowledgeBaseError("knowledge_base_file_type_unsupported")
        normalized_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        if normalized_type != "application/octet-stream" and normalized_type not in self.ALLOWED_MIME_TYPES[extension]:
            raise KnowledgeBaseError("knowledge_base_mime_type_mismatch")
        checksum = hashlib.sha256(content).hexdigest()
        duplicates = [row[0] for row in self.db.query(KnowledgeBaseItem.id).filter(KnowledgeBaseItem.checksum_sha256 == checksum, KnowledgeBaseItem.archived_at.is_(None)).limit(10).all()]
        stored = f"{uuid.uuid4().hex}{extension}"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        path = self.storage_root / stored
        path.write_bytes(content)
        item = KnowledgeBaseItem(**metadata.model_dump(), original_filename=safe, stored_filename=stored, content_type=(content_type or "application/octet-stream")[:255], file_size=len(content), storage_path=str(path), checksum_sha256=checksum, created_by_user_id=actor.id, updated_by_user_id=actor.id)
        self.db.add(item); self.db.flush()
        try:
            if item.supersedes_id is not None:
                superseded = self.db.get(KnowledgeBaseItem, item.supersedes_id)
                if superseded is None or superseded.archived_at is not None:
                    raise KnowledgeBaseError("knowledge_base_superseded_item_missing")
                superseded.status = "superseded"
                superseded.updated_by_user_id = actor.id
            self.process(item, actor=actor, audit=False)
            ChangeHistoryService(self.db).persist(actor_user_id=actor.id, entity_type="knowledge_base_item", entity_id=item.id, action="created", before={}, after=self._snapshot(item), source_key=f"knowledge_base:{item.id}:created")
            self.db.commit(); self.db.refresh(item)
            return item, duplicates
        except Exception:
            self.db.rollback()
            if path.exists(): path.unlink()
            raise

    def process(self, item: KnowledgeBaseItem, *, actor: User, audit: bool = True) -> KnowledgeBaseItem:
        before = self._snapshot(item)
        item.processing_status = "extracting"; item.processing_error = None
        self.db.query(KnowledgeBasePage).filter(KnowledgeBasePage.item_id == item.id).delete()
        path = Path(item.storage_path)
        result = DocumentExtractionService().extract(path=path, content_type=item.content_type, original_filename=item.original_filename)
        if result.status == "extracted":
            item.extracted_text = result.text; item.processing_method = "native_text"; item.processing_status = "processed"
            if path.suffix.lower() == ".pdf":
                reader = PdfReader(str(path))
                for index, page in enumerate(reader.pages, 1):
                    text = " ".join((page.extract_text() or "").split()).strip()
                    self.db.add(KnowledgeBasePage(item_id=item.id, page_number=index, text=text or None, extraction_method="native_text"))
            else:
                self.db.add(KnowledgeBasePage(item_id=item.id, page_number=1, text=result.text, extraction_method="native_text"))
        elif result.status == "requires_ocr":
            item.processing_status = "ocr"
            ocr = DocumentOCRService().ocr_document(path=path, content_type=item.content_type, original_filename=item.original_filename, max_pages=250)
            if ocr.status != "ocr_extracted":
                item.processing_status = "failed"; item.processing_error = "knowledge_base_ocr_failed"; item.processing_method = "ocr"
            else:
                item.extracted_text = ocr.text; item.processing_method = "ocr"; item.processing_status = "processed"
                for page in ocr.pages:
                    self.db.add(KnowledgeBasePage(item_id=item.id, page_number=page.page_number, text=page.text, extraction_method="ocr", confidence=page.confidence))
        else:
            item.processing_status = "failed"; item.processing_error = "knowledge_base_extraction_failed"; item.processing_method = result.extractor
        item.updated_by_user_id = actor.id
        self.db.flush()
        if audit:
            ChangeHistoryService(self.db).persist(actor_user_id=actor.id, entity_type="knowledge_base_item", entity_id=item.id, action="processing_retried", before=before, after=self._snapshot(item), source_key=f"knowledge_base:{item.id}:retry:{uuid.uuid4().hex}")
            self.db.commit(); self.db.refresh(item)
        return item

    def update(self, item: KnowledgeBaseItem, patch: KnowledgeBasePatch, actor: User) -> KnowledgeBaseItem:
        before = self._snapshot(item)
        values = patch.model_dump(exclude_unset=True)
        if values.get("supersedes_id") == item.id: raise KnowledgeBaseError("knowledge_base_self_supersession")
        if values.get("supersedes_id") is not None and self.db.get(KnowledgeBaseItem, values["supersedes_id"]) is None: raise KnowledgeBaseError("knowledge_base_superseded_item_missing")
        for key, value in values.items(): setattr(item, key, value)
        if item.supersedes_id is not None:
            superseded = self.db.get(KnowledgeBaseItem, item.supersedes_id)
            if superseded is None or superseded.archived_at is not None:
                raise KnowledgeBaseError("knowledge_base_superseded_item_missing")
            superseded.status = "superseded"
            superseded.updated_by_user_id = actor.id
        item.updated_by_user_id = actor.id
        self.db.flush()
        ChangeHistoryService(self.db).persist(actor_user_id=actor.id, entity_type="knowledge_base_item", entity_id=item.id, action="updated", before=before, after=self._snapshot(item), source_key=f"knowledge_base:{item.id}:update:{uuid.uuid4().hex}")
        self.db.commit(); self.db.refresh(item); return item

    def get(self, item_id: int) -> KnowledgeBaseItem:
        item = self.db.query(KnowledgeBaseItem).options(selectinload(KnowledgeBaseItem.pages)).filter(KnowledgeBaseItem.id == item_id, KnowledgeBaseItem.archived_at.is_(None)).first()
        if item is None: raise KnowledgeBaseError("knowledge_base_item_not_found")
        return item

    def list(self, *, query: str | None, category: str | None, status: str | None, publisher: str | None, skip: int, limit: int) -> tuple[list[KnowledgeBaseItem], int]:
        q = self.db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.archived_at.is_(None))
        if category: q = q.filter(KnowledgeBaseItem.category == category)
        if status: q = q.filter(KnowledgeBaseItem.status == status)
        if publisher: q = q.filter(KnowledgeBaseItem.publisher.ilike(f"%{publisher.strip()}%"))
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            q = q.filter(or_(KnowledgeBaseItem.title.ilike(pattern), KnowledgeBaseItem.source.ilike(pattern), KnowledgeBaseItem.publisher.ilike(pattern), KnowledgeBaseItem.version.ilike(pattern), KnowledgeBaseItem.category.ilike(pattern), cast(KnowledgeBaseItem.tags, String).ilike(pattern), KnowledgeBaseItem.extracted_text.ilike(pattern)))
        total = q.count(); return q.order_by(KnowledgeBaseItem.effective_date.desc().nullslast(), KnowledgeBaseItem.id.desc()).offset(skip).limit(limit).all(), total

    def search(self, query: str, limit: int) -> list[dict[str, object]]:
        pattern = f"%{query.strip()}%"
        rows = self.db.query(KnowledgeBasePage, KnowledgeBaseItem).select_from(KnowledgeBaseItem).outerjoin(KnowledgeBasePage).filter(KnowledgeBaseItem.archived_at.is_(None), or_(KnowledgeBasePage.text.ilike(pattern), KnowledgeBaseItem.title.ilike(pattern), KnowledgeBaseItem.source.ilike(pattern), KnowledgeBaseItem.publisher.ilike(pattern), KnowledgeBaseItem.version.ilike(pattern), KnowledgeBaseItem.category.ilike(pattern), cast(KnowledgeBaseItem.tags, String).ilike(pattern))).order_by(KnowledgeBaseItem.status.asc(), KnowledgeBaseItem.id.desc(), KnowledgeBasePage.page_number).limit(limit).all()
        return [{"knowledge_base_item_id": item.id, "title": item.title, "publisher": item.publisher, "version": item.version, "effective_date": item.effective_date, "category": item.category, "status": item.status, "source_file": item.original_filename, "page": page.page_number if page else None, "excerpt": self._excerpt((page.text if page else None) or item.extracted_text or item.source, query), "retrieval_method": "lexical"} for page, item in rows]

    def archive(self, item: KnowledgeBaseItem, actor: User) -> None:
        before = self._snapshot(item)
        item.archived_at = datetime.now(UTC)
        item.updated_by_user_id = actor.id
        self.db.flush()
        ChangeHistoryService(self.db).persist(actor_user_id=actor.id, entity_type="knowledge_base_item", entity_id=item.id, action="deleted", before=before, after=self._snapshot(item), source_key=f"knowledge_base:{item.id}:archive:{uuid.uuid4().hex}")
        self.db.commit()

    @staticmethod
    def _excerpt(text: str, query: str) -> str:
        clean = " ".join(text.split()); index = clean.casefold().find(query.casefold()); start = max(0, index - 120) if index >= 0 else 0
        return clean[start:start + 500]
