from __future__ import annotations

import asyncio
import hashlib
import logging
import json
from pathlib import Path
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.knowledge_base import (AnalysisJob, AnalysisJobSource,
    KnowledgeBaseAnalysisArtifact, KnowledgeBaseItem, KnowledgeBasePage,
    KnowledgeBaseProcessingJob)
from app.models.user import User
from app.schemas.analysis import AnalysisContextLimits, AnalysisProvenance, AnalysisRequest, AnalysisSourceRef
from app.services.advanced_analysis_orchestrator import AdvancedAnalysisOrchestrator
from app.services.knowledge_base_analysis_service import KnowledgeBaseLocalProcessor
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_vector_service import KnowledgeBaseVectorService


logger = logging.getLogger("ai_lab.knowledge_base")


class KnowledgeBaseDispatcher:
    POLL_SECONDS = 5
    STALE_JOB_SECONDS = 15 * 60

    @staticmethod
    def _index_if_enabled(db, item: KnowledgeBaseItem) -> None:
        if not settings.knowledge_base_vector_writes_enabled:
            item.indexing_status = "not_ready"
            return
        item.indexing_status = "indexing"
        db.flush()
        try:
            KnowledgeBaseVectorService(db).index_item(item)
            item.indexing_status = "indexed"
        except Exception as error:
            item.indexing_status = "failed"
            logger.warning("KB indexing failed: %s", error.__class__.__name__)

    def _request(self, item: KnowledgeBaseItem, pages: list[KnowledgeBasePage], analysis_id: UUID) -> tuple[AnalysisRequest, dict[str, tuple[str, str, int | None]]]:
        selected = [page for page in pages if (page.text or "").strip()][:8]
        refs: list[AnalysisSourceRef] = []
        entities: dict[str, tuple[str, str, int | None]] = {}
        for index, page in enumerate(selected, 1):
            ref = f"S{index}"; text = " ".join((page.text or "").split())[:2000]
            checksum = hashlib.sha256(text.encode()).hexdigest()
            refs.append(AnalysisSourceRef(source_ref=ref, checksum_sha256=checksum, page=page.page_number,
                                          excerpt=text, extraction_confidence=page.confidence))
            entities[ref] = ("knowledge_base_page", str(page.id), page.page_number)
        if not refs:
            fallback = "Brak tekstu źródłowego."
            refs.append(AnalysisSourceRef(source_ref="S1", checksum_sha256=hashlib.sha256(fallback.encode()).hexdigest(), excerpt=fallback))
            entities["S1"] = ("knowledge_base_item", str(item.id), None)
        request = AnalysisRequest(
            analysis_id=analysis_id, analysis_type="technical_interpretation",
            source_domain="knowledge_base", source_refs=refs,
            problem_statement="Wyodrębnij wyłącznie techniczną wiedzę źródłową i zachowaj cytowania stron.",
            structured_inputs={"requested_output": "Definicje, formuły, jednostki, ograniczenia, wartości, tabele i standardy."},
            units={}, formulas=[], constraints=[], evidence=[ref.source_ref for ref in refs],
            sensitivity="public_reference",
            allowed_methods=["deterministic_parse", "local_llm", "temporary_chat"],
            context_limits=AnalysisContextLimits(),
            provenance=AnalysisProvenance(requested_by_user_id=item.updated_by_user_id,
                                          source_checksum=item.checksum_sha256),
        )
        return request, entities

    def process_one(self) -> bool:
        db = SessionLocal()
        try:
            job = db.query(KnowledgeBaseProcessingJob).filter(KnowledgeBaseProcessingJob.status == "queued").order_by(KnowledgeBaseProcessingJob.created_at, KnowledgeBaseProcessingJob.id).with_for_update(skip_locked=True).first()
            if job is None: return False
            job.status = "running"; job.stage = "extracting"; job.attempt_count += 1; job.started_at = datetime.now(UTC)
            item = db.get(KnowledgeBaseItem, job.item_id)
            actor = db.get(User, job.created_by_user_id)
            if item is None or actor is None: raise RuntimeError("knowledge_base_processing_source_missing")
            db.commit()
            service = KnowledgeBaseService(db)
            service.process(item, actor=actor, audit=False)
            if item.processing_status != "processed": raise RuntimeError(item.processing_error or "knowledge_base_processing_failed")
            item.analysis_status = "local_processing"; job.stage = "local_analysis"; db.flush()
            pages = db.query(KnowledgeBasePage).filter(KnowledgeBasePage.item_id == item.id).order_by(KnowledgeBasePage.page_number).all()
            analysis_id = uuid4(); request, entities = self._request(item, pages, analysis_id)
            local = KnowledgeBaseLocalProcessor().analyze(request, item)
            analysis_job = AdvancedAnalysisOrchestrator(db).execute_local(request=request, local=local, source_entities=entities, actor_user_id=actor.id)
            item.analysis_reason = analysis_job.error_code
            if analysis_job.status == "accepted_local":
                item.analysis_status = "local_accepted"
                db.add(KnowledgeBaseAnalysisArtifact(item_id=item.id, analysis_job_id=analysis_job.id,
                    kind="structured_technical_knowledge", payload=local.result,
                    source_page_refs=[{"source_ref": ref.source_ref, "page": ref.page} for ref in request.source_refs],
                    origin="local", validation_state="accepted"))
            elif analysis_job.status in {"advanced_queued", "advanced_processing"}:
                item.analysis_status = analysis_job.status
            elif analysis_job.status == "review_required": item.analysis_status = "review_required"
            else: item.analysis_status = "failed"
            if item.analysis_status == "local_accepted":
                self._index_if_enabled(db, item)
            else:
                item.indexing_status = "not_ready"
            job.status = "completed"; job.stage = "completed"; job.finished_at = datetime.now(UTC); job.error_code = None
            db.commit(); return True
        except Exception as error:
            db.rollback()
            if 'job' in locals() and job is not None:
                failed = db.get(KnowledgeBaseProcessingJob, job.id)
                if failed:
                    failed.status = "failed"; failed.stage = "failed"; failed.error_code = str(error)[:100]; failed.finished_at = datetime.now(UTC)
                    item = db.get(KnowledgeBaseItem, failed.item_id)
                    if item: item.processing_status = "failed"; item.processing_error = failed.error_code; item.analysis_status = "failed"
                    db.commit()
            logger.warning("KB processing failed: %s", error.__class__.__name__)
            return True
        finally: db.close()

    def recover_stale_processing(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=self.STALE_JOB_SECONDS)
        db = SessionLocal()
        try:
            jobs = db.query(KnowledgeBaseProcessingJob).filter(
                KnowledgeBaseProcessingJob.status == "running",
                KnowledgeBaseProcessingJob.updated_at < cutoff,
            ).with_for_update(skip_locked=True).all()
            for job in jobs:
                job.status = "queued"
                job.stage = "queued"
                job.error_code = "knowledge_base_worker_restarted"
                job.started_at = None
                item = db.get(KnowledgeBaseItem, job.item_id)
                if item is not None:
                    item.processing_status = "queued"
                    item.processing_error = None
            db.commit()
            return len(jobs)
        finally:
            db.close()

    def poll_one(self) -> bool:
        if not settings.advanced_analysis_enabled: return False
        db = SessionLocal()
        try:
            job = db.query(AnalysisJob).filter(
                AnalysisJob.source_domain == "knowledge_base",
                AnalysisJob.external_job_id.is_not(None),
                AnalysisJob.status.in_(["advanced_queued", "advanced_processing", "awaiting_auth", "awaiting_ui_fix", "advanced_validating"]),
            ).order_by(AnalysisJob.updated_at, AnalysisJob.id).first()
            if job is None: return False
            source = db.query(AnalysisJobSource).filter(AnalysisJobSource.analysis_job_id == job.id).order_by(AnalysisJobSource.source_ref).first()
            if source is None: return False
            if source.source_entity_type == "knowledge_base_page":
                page = db.get(KnowledgeBasePage, int(source.source_entity_id)); item = db.get(KnowledgeBaseItem, page.item_id) if page else None
            else: item = db.get(KnowledgeBaseItem, int(source.source_entity_id))
            if item is None: return False
            pages = db.query(KnowledgeBasePage).filter(KnowledgeBasePage.item_id == item.id).order_by(KnowledgeBasePage.page_number).all()
            request, _ = self._request(item, pages, UUID(job.id))
            status = AdvancedAnalysisOrchestrator(db).apply_external(job=job, request=request)
            item.analysis_status = {
                "accepted_advanced": "advanced_accepted",
                "cancelled": "failed",
            }.get(status, status)
            item.analysis_reason = job.error_code
            if status == "accepted_advanced":
                result_path = Path(settings.data_dir) / "analysis-spool" / "jobs" / str(job.external_job_id) / "output" / "analysis.json"
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                page_numbers = {str(page.id): page.page_number for page in pages}
                evidence_pages = {
                    source.source_ref: page_numbers.get(source.source_entity_id, source.page_number)
                    for source in job.sources
                }
                db.add(KnowledgeBaseAnalysisArtifact(item_id=item.id, analysis_job_id=job.id,
                    kind="structured_technical_knowledge", payload=payload["result"],
                    source_page_refs=[{"source_ref": ref, "page": evidence_pages.get(ref)}
                                      for ref in payload.get("source_refs", [])],
                    origin="advanced", validation_state="accepted"))
                self._index_if_enabled(db, item)
            db.commit(); return True
        except Exception as error:
            db.rollback(); logger.warning("Advanced analysis polling failed: %s", error.__class__.__name__); return True
        finally: db.close()

    async def run(self) -> None:
        await asyncio.to_thread(self.recover_stale_processing)
        while True:
            try:
                worked = await asyncio.to_thread(self.process_one)
                if not worked: worked = await asyncio.to_thread(self.poll_one)
                if not worked: await asyncio.sleep(self.POLL_SECONDS)
            except asyncio.CancelledError: raise
            except Exception as error:
                logger.warning("KB dispatcher iteration failed: %s", error.__class__.__name__)
                await asyncio.sleep(self.POLL_SECONDS)


def start_knowledge_base_dispatcher() -> asyncio.Task | None:
    if not settings.knowledge_base_processing_enabled: return None
    return asyncio.create_task(KnowledgeBaseDispatcher().run(), name="knowledge-base-dispatcher")
