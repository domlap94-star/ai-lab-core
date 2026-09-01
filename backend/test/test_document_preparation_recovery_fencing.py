from __future__ import annotations

import asyncio
import tempfile
import threading
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.assistant_pipeline import AssistantRun
from app.models.document import Document
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.knowledge_base import AnalysisJob
from app.services.document_preparation_dispatcher import (
    DocumentPreparationDispatcher,
    _PreparationIntelligenceHeartbeat,
    process_preparation_intelligence,
    process_preparation_vision,
)
from app.services.document_preparation_service import (
    INGESTION_EXTERNAL_VISION_BLOCKED,
    LEASE_MINUTES,
    DocumentPreparationService,
    PreparationClaim,
)
from app.services.document_service import DocumentService
from app.services.unified_document_content_service import (
    FILE_FOUND_NATIVE_TEXT_AVAILABLE,
)
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()


class _Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


class _ControlledSleep:
    def __init__(self) -> None:
        self.ticks: asyncio.Queue[None] = asyncio.Queue()

    async def __call__(self, _seconds: float) -> None:
        await self.ticks.get()

    def tick(self) -> None:
        self.ticks.put_nowait(None)


class DocumentPreparationRecoveryFencingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db = SessionLocal()
        try:
            assert_isolated_database(db, TEST_DATABASE_NAME)
            cls.analysis_jobs_before = db.query(AnalysisJob).count()
            cls.assistant_runs_before = db.query(AssistantRun).count()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls) -> None:
        db = SessionLocal()
        try:
            assert_isolated_database(db, TEST_DATABASE_NAME)
            if db.query(AnalysisJob).count() != cls.analysis_jobs_before:
                raise AssertionError("DOC-03 tests created AnalysisJob rows")
            if db.query(AssistantRun).count() != cls.assistant_runs_before:
                raise AssertionError("DOC-03 tests created AssistantRun rows")
        finally:
            db.close()

    def setUp(self) -> None:
        self.storage = tempfile.TemporaryDirectory()
        self.previous_data_dir = settings.data_dir
        settings.data_dir = self.storage.name
        self.db = SessionLocal()
        assert_isolated_database(self.db, TEST_DATABASE_NAME)
        self.job_ids: list[str] = []

    def tearDown(self) -> None:
        self.db.rollback()
        if self.job_ids:
            self.db.query(DocumentPreparationJob).filter(
                DocumentPreparationJob.id.in_(self.job_ids)
            ).update(
                {
                    DocumentPreparationJob.status: "failed",
                    DocumentPreparationJob.stage: "failed",
                    DocumentPreparationJob.error_code: "ISOLATED_TEST_COMPLETE",
                    DocumentPreparationJob.retryability: "owner_action",
                    DocumentPreparationJob.lease_owner: None,
                    DocumentPreparationJob.lease_expires_at: None,
                    DocumentPreparationJob.finished_at: datetime.now(UTC),
                },
                synchronize_session=False,
            )
            self.db.commit()
        self.db.close()
        settings.data_dir = self.previous_data_dir
        self.storage.cleanup()

    def _store_job(
        self,
        *,
        trigger: str = "ingestion",
        priority: int = 2,
    ) -> DocumentPreparationJob:
        marker = uuid.uuid4().hex
        stored = DocumentService(self.db).store_document(
            content=f"synthetic DOC-03 {marker}\n".encode("utf-8"),
            original_filename=f"doc03-{marker}.txt",
            content_type="text/plain",
            source_type="manual_upload",
        )
        job = self.db.query(DocumentPreparationJob).filter_by(
            document_id=stored.document.id
        ).one()
        job.trigger = trigger
        job.priority = priority
        self.db.commit()
        self.job_ids.append(job.id)
        return job

    def _running(
        self,
        job: DocumentPreparationJob,
        *,
        stage: str = "local_analysis",
        attempt_count: int = 1,
        max_attempts: int = 3,
        expired: bool = False,
        owner: str | None = None,
    ) -> PreparationClaim:
        token = owner or f"doc03-test:{uuid.uuid4()}"
        job.status = "running"
        job.stage = stage
        job.attempt_count = attempt_count
        job.max_attempts = max_attempts
        job.started_at = job.started_at or datetime.now(UTC) - timedelta(minutes=5)
        job.finished_at = None
        job.error_code = None
        job.retryability = None
        job.lease_owner = token
        job.lease_expires_at = datetime.now(UTC) + (
            -timedelta(seconds=1) if expired else timedelta(minutes=LEASE_MINUTES)
        )
        self.db.commit()
        return PreparationClaim(job_id=job.id, lease_owner=token)

    def _claim(self, job: DocumentPreparationJob) -> PreparationClaim:
        job.priority = 0
        job.queued_at = datetime.now(UTC) - timedelta(minutes=1)
        self.db.commit()
        claim = DocumentPreparationService(self.db).claim_next()
        self.db.commit()
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.job_id, job.id)
        return claim

    @staticmethod
    def _assert_generated_token(test: unittest.TestCase, token: str) -> None:
        host, pid, attempt = token.rsplit(":", 2)
        test.assertTrue(host)
        test.assertGreaterEqual(int(pid), 1)
        test.assertEqual(str(uuid.UUID(attempt)), attempt)

    def _expire_recover_reclaim(
        self, job: DocumentPreparationJob
    ) -> tuple[PreparationClaim, PreparationClaim]:
        first = self._claim(job)
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        current.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 1)
        self.db.commit()
        second = self._claim(current)
        return first, second

    def test_t01_unique_claim_tokens(self) -> None:
        job = self._store_job()
        first, second = self._expire_recover_reclaim(job)
        self._assert_generated_token(self, first.lease_owner)
        self._assert_generated_token(self, second.lease_owner)
        self.assertNotEqual(first.lease_owner, second.lease_owner)

    def test_t02_recover_expired_retryable(self) -> None:
        job = self._store_job(priority=1)
        started = datetime.now(UTC) - timedelta(minutes=10)
        job.started_at = started
        claim = self._running(job, expired=True)
        checksum = job.input_checksum
        before = datetime.now(UTC)
        self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 1)
        self.db.commit()
        after = datetime.now(UTC)
        self.db.expire_all()
        recovered = self.db.get(DocumentPreparationJob, claim.job_id)
        assert recovered is not None
        self.assertEqual((recovered.status, recovered.stage), ("queued", "queued"))
        self.assertEqual(recovered.error_code, "PREPARATION_LEASE_EXPIRED")
        self.assertEqual(recovered.retryability, "recoverable")
        self.assertIsNone(recovered.lease_owner)
        self.assertIsNone(recovered.lease_expires_at)
        self.assertIsNone(recovered.finished_at)
        self.assertEqual(recovered.attempt_count, 1)
        self.assertEqual(recovered.max_attempts, 3)
        self.assertEqual(recovered.started_at, started)
        self.assertEqual(recovered.input_checksum, checksum)
        self.assertEqual(recovered.trigger, "ingestion")
        self.assertEqual(recovered.priority, 1)
        self.assertGreaterEqual(recovered.queued_at, before)
        self.assertLessEqual(recovered.queued_at, after)

    def test_t03_recover_exhausted(self) -> None:
        job = self._store_job()
        self._running(job, attempt_count=3, max_attempts=3, expired=True)
        service = DocumentPreparationService(self.db)
        self.assertEqual(service.recover_expired(), 1)
        self.db.commit()
        self.db.expire_all()
        failed = self.db.get(DocumentPreparationJob, job.id)
        assert failed is not None
        first_finished = failed.finished_at
        self.assertEqual((failed.status, failed.stage), ("failed", "failed"))
        self.assertEqual(failed.error_code, "PREPARATION_ATTEMPTS_EXHAUSTED")
        self.assertEqual(failed.retryability, "owner_action")
        self.assertIsNone(failed.lease_owner)
        self.assertIsNone(failed.lease_expires_at)
        self.assertIsNotNone(first_finished)
        self.assertEqual(service.recover_expired(), 0)
        self.db.commit()
        self.db.expire_all()
        self.assertEqual(
            self.db.get(DocumentPreparationJob, job.id).finished_at,
            first_finished,
        )

    def test_t04_recovery_idempotency(self) -> None:
        job = self._store_job()
        self._running(job, expired=True)
        service = DocumentPreparationService(self.db)
        self.assertEqual(service.recover_expired(), 1)
        self.db.commit()
        self.db.expire_all()
        first = self.db.get(DocumentPreparationJob, job.id)
        assert first is not None
        snapshot = (
            first.status,
            first.stage,
            first.error_code,
            first.queued_at,
        )
        self.assertEqual(service.recover_expired(), 0)
        self.db.commit()
        self.db.expire_all()
        second = self.db.get(DocumentPreparationJob, job.id)
        assert second is not None
        self.assertEqual(
            (second.status, second.stage, second.error_code, second.queued_at),
            snapshot,
        )

    def test_t05_stale_heartbeat_cannot_refresh_new_owner(self) -> None:
        job = self._store_job()
        old, current = self._expire_recover_reclaim(job)
        self.db.expire_all()
        replacement = self.db.get(DocumentPreparationJob, job.id)
        assert replacement is not None
        replacement.stage = "local_analysis"
        replacement.error_code = "CURRENT_ATTEMPT_STATE"
        self.db.commit()
        original = (
            replacement.lease_owner,
            replacement.lease_expires_at,
            replacement.error_code,
            replacement.status,
            replacement.stage,
        )
        heartbeat = _PreparationIntelligenceHeartbeat(old)
        self.assertFalse(heartbeat.refresh(wait_reason="LOCAL_MODEL_BUSY"))
        self.db.expire_all()
        replacement = self.db.get(DocumentPreparationJob, current.job_id)
        assert replacement is not None
        self.assertEqual(
            (
                replacement.lease_owner,
                replacement.lease_expires_at,
                replacement.error_code,
                replacement.status,
                replacement.stage,
            ),
            original,
        )

    def test_t06_current_heartbeat_refreshes_only_current_owner(self) -> None:
        job = self._store_job()
        claim = self._claim(job)
        job = self.db.get(DocumentPreparationJob, job.id)
        assert job is not None
        job.stage = "local_analysis"
        sibling = self._store_job()
        sibling_claim = self._running(sibling, stage="local_analysis")
        sibling_expiry = sibling.lease_expires_at
        self.db.commit()
        clock = _Clock()
        heartbeat = _PreparationIntelligenceHeartbeat(
            claim, now_factory=clock.now
        )
        self.assertTrue(heartbeat.refresh(wait_reason="LOCAL_MODEL_BUSY"))
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, claim.job_id)
        other = self.db.get(DocumentPreparationJob, sibling_claim.job_id)
        assert current is not None and other is not None
        self.assertEqual(current.lease_owner, claim.lease_owner)
        self.assertEqual(
            current.lease_expires_at,
            clock.now() + timedelta(minutes=LEASE_MINUTES),
        )
        self.assertEqual(current.error_code, "LOCAL_MODEL_BUSY")
        self.assertEqual(other.lease_expires_at, sibling_expiry)

    def test_t07_stale_processing_result_cannot_advance_job(self) -> None:
        job = self._store_job()
        old = self._claim(job)
        entered = threading.Event()
        release = threading.Event()
        outcome: list[bool] = []
        failures: list[BaseException] = []

        def fake_process(*_args, **_kwargs):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("synthetic processing release timeout")
            return SimpleNamespace(status="processed")

        def worker() -> None:
            db = SessionLocal()
            try:
                outcome.append(DocumentPreparationService(db).process_claimed(old))
            except BaseException as error:  # pragma: no cover - diagnostic capture
                failures.append(error)
            finally:
                db.close()

        with (
            patch(
                "app.services.document_preparation_service."
                "DocumentProcessingService.process_document",
                side_effect=fake_process,
            ),
            patch(
                "app.services.document_preparation_service."
                "UnifiedDocumentContentService.access",
                return_value=SimpleNamespace(
                    state=FILE_FOUND_NATIVE_TEXT_AVAILABLE
                ),
            ),
        ):
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            self.assertTrue(entered.wait(5))
            self.db.expire_all()
            current = self.db.get(DocumentPreparationJob, job.id)
            assert current is not None
            current.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            self.db.commit()
            self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 1)
            self.db.commit()
            replacement = self._claim(current)
            release.set()
            thread.join(5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(outcome, [False])
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        self.assertEqual(current.lease_owner, replacement.lease_owner)
        self.assertEqual((current.status, current.stage), ("running", "validating"))

    def test_t08_stale_vision_result_cannot_advance_job(self) -> None:
        asyncio.run(self._t08_stale_vision_result_cannot_advance_job())

    async def _t08_stale_vision_result_cannot_advance_job(self) -> None:
        job = self._store_job(trigger="assistant")
        old = self._claim(job)
        job = self.db.get(DocumentPreparationJob, job.id)
        assert job is not None
        job.stage = "vision_processing"
        self.db.commit()
        entered = threading.Event()
        release = threading.Event()

        def fake_vision(document_id: int) -> None:
            entered.set()
            if not release.wait(5):
                raise TimeoutError("synthetic Vision release timeout")
            db = SessionLocal()
            try:
                document = db.get(Document, document_id)
                if document is not None:
                    document.vision_status = "complete"
                    db.commit()
            finally:
                db.close()

        with patch(
            "app.services.document_preparation_dispatcher."
            "process_explicit_vision_document",
            side_effect=fake_vision,
        ):
            task = asyncio.create_task(process_preparation_vision(old))
            self.assertTrue(await asyncio.to_thread(entered.wait, 5))
            self.db.expire_all()
            current = self.db.get(DocumentPreparationJob, job.id)
            assert current is not None
            current.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            self.db.commit()
            self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 1)
            self.db.commit()
            replacement = self._claim(current)
            release.set()
            self.assertFalse(await task)

        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        self.assertEqual(current.lease_owner, replacement.lease_owner)
        self.assertEqual((current.status, current.stage), ("running", "validating"))

    def test_t09_stale_intelligence_completion_cannot_mark_ready(self) -> None:
        job = self._store_job()
        old, current = self._expire_recover_reclaim(job)
        replacement = self.db.get(DocumentPreparationJob, current.job_id)
        assert replacement is not None
        replacement.stage = "local_analysis"
        replacement.error_code = None
        replacement.retryability = None
        self.db.commit()
        completed = DocumentPreparationService(self.db).complete_intelligence(
            old, "synthetic-stale-artifact"
        )
        self.assertFalse(completed)
        self.db.commit()
        self.db.expire_all()
        replacement = self.db.get(DocumentPreparationJob, current.job_id)
        assert replacement is not None
        self.assertEqual(replacement.lease_owner, current.lease_owner)
        self.assertEqual((replacement.status, replacement.stage), ("running", "local_analysis"))

    def test_t10_stale_intelligence_failure_cannot_requeue_new_attempt(self) -> None:
        job = self._store_job()
        old, current = self._expire_recover_reclaim(job)
        replacement = self.db.get(DocumentPreparationJob, current.job_id)
        assert replacement is not None
        replacement.stage = "local_analysis"
        replacement.error_code = None
        replacement.retryability = None
        self.db.commit()
        self.assertFalse(DocumentPreparationService(self.db).fail_intelligence(
            old, "SYNTHETIC_OLD_FAILURE"
        ))
        self.db.commit()
        self.db.expire_all()
        replacement = self.db.get(DocumentPreparationJob, current.job_id)
        assert replacement is not None
        self.assertEqual(replacement.lease_owner, current.lease_owner)
        self.assertEqual((replacement.status, replacement.stage), ("running", "local_analysis"))
        self.assertIsNone(replacement.error_code)

    def test_t11_child_cancellation_does_not_kill_dispatcher(self) -> None:
        asyncio.run(self._t11_child_cancellation_does_not_kill_dispatcher())

    async def _t11_child_cancellation_does_not_kill_dispatcher(self) -> None:
        job = self._store_job()
        claim = self._claim(job)
        job = self.db.get(DocumentPreparationJob, job.id)
        assert job is not None
        job.stage = "local_analysis"
        self.db.commit()
        started = asyncio.Event()
        child_holder: list[asyncio.Task] = []

        async def blocked_build(**_kwargs) -> str:
            child = asyncio.current_task()
            assert child is not None
            child_holder.append(child)
            started.set()
            await asyncio.Event().wait()
            return "unreachable"

        process_calls = 0

        def next_claim() -> PreparationClaim | None:
            nonlocal process_calls
            process_calls += 1
            return claim if process_calls == 1 else None

        async def vision_ready(_claim: PreparationClaim) -> bool:
            return True

        with (
            patch(
                "app.services.document_preparation_dispatcher."
                "process_one_preparation",
                side_effect=next_claim,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "process_preparation_vision",
                side_effect=vision_ready,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "build_document_intelligence",
                side_effect=blocked_build,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "_next_waiting_id",
                return_value=None,
            ),
            patch.object(DocumentPreparationDispatcher, "POLL_SECONDS", 0.01),
        ):
            dispatcher = asyncio.create_task(
                DocumentPreparationDispatcher().run()
            )
            await asyncio.wait_for(started.wait(), 5)
            child_holder[0].cancel()
            for _ in range(100):
                if process_calls >= 2:
                    break
                await asyncio.sleep(0.01)
            else:
                self.fail("dispatcher did not continue after child cancellation")
            self.assertFalse(dispatcher.done())
            dispatcher.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await dispatcher

        self.assertGreaterEqual(process_calls, 2)
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        self.assertEqual((current.status, current.stage), ("queued", "queued"))
        self.assertEqual(current.error_code, "WORKER_INTERRUPTED")

    def test_t12_application_shutdown_still_propagates(self) -> None:
        asyncio.run(self._t12_application_shutdown_still_propagates())

    async def _t12_application_shutdown_still_propagates(self) -> None:
        job = self._store_job()
        claim = self._claim(job)
        job = self.db.get(DocumentPreparationJob, job.id)
        assert job is not None
        job.stage = "local_analysis"
        self.db.commit()
        started = asyncio.Event()
        child_holder: list[asyncio.Task] = []

        async def blocked_build(**_kwargs) -> str:
            child = asyncio.current_task()
            assert child is not None
            child_holder.append(child)
            started.set()
            await asyncio.Event().wait()
            return "unreachable"

        async def vision_ready(_claim: PreparationClaim) -> bool:
            return True

        with (
            patch(
                "app.services.document_preparation_dispatcher."
                "process_one_preparation",
                return_value=claim,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "process_preparation_vision",
                side_effect=vision_ready,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "build_document_intelligence",
                side_effect=blocked_build,
            ),
        ):
            dispatcher = asyncio.create_task(DocumentPreparationDispatcher().run())
            await asyncio.wait_for(started.wait(), 5)
            dispatcher.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await dispatcher

        self.assertTrue(child_holder[0].done())
        self.assertFalse(any(
            task.get_name() == "document-preparation-recovery"
            and not task.done()
            for task in asyncio.all_tasks()
        ))
        self.db.expire_all()
        current = self.db.get(DocumentPreparationJob, job.id)
        assert current is not None
        self.assertEqual((current.status, current.stage), ("queued", "queued"))
        self.assertEqual(current.error_code, "WORKER_INTERRUPTED")

    def test_t13_independent_recovery_runs_while_child_blocked(self) -> None:
        asyncio.run(self._t13_independent_recovery_runs_while_child_blocked())

    async def _t13_independent_recovery_runs_while_child_blocked(self) -> None:
        active = self._store_job()
        claim = self._claim(active)
        active = self.db.get(DocumentPreparationJob, active.id)
        assert active is not None
        active.stage = "local_analysis"
        expired = self._store_job(priority=3)
        self._running(expired, stage="local_analysis", expired=True)
        self.db.commit()
        started = asyncio.Event()

        async def blocked_build(**_kwargs) -> str:
            started.set()
            await asyncio.Event().wait()
            return "unreachable"

        async def vision_ready(_claim: PreparationClaim) -> bool:
            return True

        with (
            patch(
                "app.services.document_preparation_dispatcher."
                "process_one_preparation",
                return_value=claim,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "process_preparation_vision",
                side_effect=vision_ready,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "build_document_intelligence",
                side_effect=blocked_build,
            ),
            patch(
                "app.services.document_preparation_dispatcher."
                "RECOVERY_POLL_SECONDS",
                0.01,
            ),
        ):
            dispatcher = asyncio.create_task(DocumentPreparationDispatcher().run())
            await asyncio.wait_for(started.wait(), 5)
            for _ in range(100):
                probe = SessionLocal()
                try:
                    row = probe.get(DocumentPreparationJob, expired.id)
                    if row is not None and row.status == "queued":
                        break
                finally:
                    probe.close()
                await asyncio.sleep(0.01)
            else:
                self.fail("independent recovery did not recover expired job")
            dispatcher.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await dispatcher

        self.db.expire_all()
        recovered = self.db.get(DocumentPreparationJob, expired.id)
        assert recovered is not None
        self.assertEqual((recovered.status, recovered.stage), ("queued", "queued"))
        self.assertEqual(recovered.error_code, "PREPARATION_LEASE_EXPIRED")

    def test_t14_queue_drain_after_stale_job(self) -> None:
        stale = self._store_job(priority=3)
        self._running(stale, stage="local_analysis", expired=True)
        queued = [self._store_job(priority=0) for _ in range(8)]
        for row in queued:
            row.queued_at = datetime.now(UTC) - timedelta(minutes=10)
        self.db.commit()
        self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 1)
        self.db.commit()
        claim = DocumentPreparationService(self.db).claim_next()
        self.db.commit()
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertIn(claim.job_id, {row.id for row in queued})
        self._assert_generated_token(self, claim.lease_owner)
        running = self.db.query(DocumentPreparationJob).filter(
            DocumentPreparationJob.id.in_(self.job_ids),
            DocumentPreparationJob.status == "running",
        ).all()
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0].lease_owner, claim.lease_owner)

    def test_t15_doc01_fencing(self) -> None:
        job = self._store_job(trigger="ingestion")
        old, current = self._expire_recover_reclaim(job)
        self.assertFalse(
            DocumentPreparationService(self.db).contain_ingestion_external_vision(old)
        )
        self.assertTrue(
            DocumentPreparationService(self.db).contain_ingestion_external_vision(current)
        )
        self.db.commit()
        self.db.expire_all()
        contained = self.db.get(DocumentPreparationJob, job.id)
        assert contained is not None
        self.assertEqual((contained.status, contained.stage), ("failed", "failed"))
        self.assertEqual(contained.error_code, INGESTION_EXTERNAL_VISION_BLOCKED)

    def test_t16_assistant_cancellation(self) -> None:
        asyncio.run(self._t16_assistant_cancellation())

    async def _t16_assistant_cancellation(self) -> None:
        job = self._store_job(trigger="assistant")
        claim = self._claim(job)
        job = self.db.get(DocumentPreparationJob, job.id)
        assert job is not None
        job.stage = "local_analysis"
        sibling = self._store_job()
        sibling_claim = self._running(sibling, stage="local_analysis")
        self.db.commit()
        sleep = _ControlledSleep()
        owner_started = asyncio.Event()

        async def child() -> None:
            owner_started.set()
            await asyncio.Event().wait()

        owner = asyncio.create_task(child())
        await owner_started.wait()
        heartbeat = _PreparationIntelligenceHeartbeat(claim, sleep=sleep)
        with patch(
            "app.services.document_preparation_dispatcher."
            "_assistant_preparation_has_no_active_waiters",
            return_value=False,
        ):
            self.assertTrue(heartbeat.start(owner))
        with patch(
            "app.services.document_preparation_dispatcher."
            "_assistant_preparation_has_no_active_waiters",
            return_value=True,
        ):
            sleep.tick()
            with self.assertRaises(asyncio.CancelledError):
                await owner
        await heartbeat.stop()
        self.db.expire_all()
        cancelled = self.db.get(DocumentPreparationJob, claim.job_id)
        other = self.db.get(DocumentPreparationJob, sibling_claim.job_id)
        assert cancelled is not None and other is not None
        self.assertEqual((cancelled.status, cancelled.stage), ("cancelled", "cancelled"))
        self.assertEqual(cancelled.error_code, "ASSISTANT_RUN_CANCELLED")
        self.assertEqual(other.lease_owner, sibling_claim.lease_owner)
        self.assertEqual((other.status, other.stage), ("running", "local_analysis"))
        self.assertEqual(asyncio.current_task().cancelling(), 0)

    def test_t17_terminal_immutability(self) -> None:
        stage_by_status = {
            "ready": "ready_for_ai",
            "failed": "failed",
            "unsupported": "unsupported",
            "integrity_failed": "integrity_failed",
            "cancelled": "cancelled",
        }
        snapshots: dict[str, tuple] = {}
        for status, stage in stage_by_status.items():
            job = self._store_job()
            finished = datetime.now(UTC) - timedelta(minutes=1)
            job.status = status
            job.stage = stage
            job.error_code = f"TERMINAL_{status.upper()}"
            job.retryability = None
            job.lease_owner = None
            job.lease_expires_at = datetime.now(UTC) - timedelta(hours=1)
            job.finished_at = finished
            snapshots[job.id] = (
                status,
                stage,
                job.error_code,
                job.lease_expires_at,
                finished,
            )
        self.db.commit()
        self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 0)
        self.db.commit()
        self.db.expire_all()
        for job_id, expected in snapshots.items():
            job = self.db.get(DocumentPreparationJob, job_id)
            assert job is not None
            self.assertEqual(
                (
                    job.status,
                    job.stage,
                    job.error_code,
                    job.lease_expires_at,
                    job.finished_at,
                ),
                expected,
            )

    def test_t18_no_external_side_effects(self) -> None:
        job = self._store_job()
        self._running(job, stage="local_analysis", expired=True)
        analysis_before = self.db.query(AnalysisJob).count()
        assistant_before = self.db.query(AssistantRun).count()
        with (
            patch(
                "app.services.document_preparation_dispatcher."
                "build_document_intelligence"
            ) as model,
            patch(
                "app.services.document_preparation_dispatcher."
                "process_explicit_vision_document"
            ) as vision,
        ):
            self.assertEqual(DocumentPreparationService(self.db).recover_expired(), 1)
            self.db.commit()
        model.assert_not_called()
        vision.assert_not_called()
        self.assertEqual(self.db.query(AnalysisJob).count(), analysis_before)
        self.assertEqual(self.db.query(AssistantRun).count(), assistant_before)


if __name__ == "__main__":
    unittest.main()
