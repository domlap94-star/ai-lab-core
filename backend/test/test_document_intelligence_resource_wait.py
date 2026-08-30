from __future__ import annotations

import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.services.assistant_run_service import AssistantRunService
from app.services.document_intelligence_service import (
    DocumentIntelligenceService,
    IntelligenceBuildInput,
    IntelligenceEvidence,
    build_document_intelligence,
)
from app.services.document_preparation_dispatcher import (
    INTELLIGENCE_HEARTBEAT_SECONDS,
    _PreparationIntelligenceHeartbeat,
    _assistant_preparation_has_no_active_waiters,
    process_preparation_intelligence,
)
from app.services.document_preparation_service import (
    LEASE_MINUTES,
    DocumentPreparationService,
    document_intelligence_resource_wait_code,
)
from app.services.local_model_resource_coordinator import (
    EMERGENCY_FLOOR_BYTES,
    GIB,
    LocalModelResourceCoordinator,
    LocalResourceSnapshot,
    QWEN9_WINDOWS_INCREMENT_BYTES,
    QWEN9_WSL_INCREMENT_BYTES,
    WINDOWS_TARGET_RESERVE_BYTES,
    WSL_TARGET_RESERVE_BYTES,
)


class _Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class _ControlledSleep:
    def __init__(self) -> None:
        self.ticks: asyncio.Queue[None] = asyncio.Queue()

    async def __call__(self, _seconds: float) -> None:
        await self.ticks.get()

    def tick(self) -> None:
        self.ticks.put_nowait(None)


class _Session:
    def __init__(self, job: SimpleNamespace) -> None:
        self.job = job
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def get(self, _model, job_id: str):
        return self.job if self.job.id == job_id else None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed += 1


class _Sessions:
    def __init__(self, job: SimpleNamespace) -> None:
        self.job = job
        self.items: list[_Session] = []

    def __call__(self) -> _Session:
        session = _Session(self.job)
        self.items.append(session)
        return session

    @property
    def commits(self) -> int:
        return sum(item.commits for item in self.items)


def _job(*, trigger: str = "ingestion") -> SimpleNamespace:
    return SimpleNamespace(
        id="prep-resource-wait",
        trigger=trigger,
        status="running",
        stage="local_analysis",
        error_code=None,
        retryability=None,
        lease_owner="worker:1",
        lease_expires_at=datetime(2026, 8, 30, 12, 45, tzinfo=UTC),
        updated_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        finished_at=None,
        attempt_count=1,
        max_attempts=3,
    )


async def _flush_loop() -> None:
    await asyncio.sleep(0)
    await asyncio.sleep(0)


class PreparationIntelligenceHeartbeatTests(unittest.IsolatedAsyncioTestCase):
    async def test_resource_wait_refreshes_lease_before_stream_and_periodically(self) -> None:
        clock = _Clock()
        sleep = _ControlledSleep()
        job = _job()
        sessions = _Sessions(job)
        heartbeat = _PreparationIntelligenceHeartbeat(
            job.id,
            interval_seconds=INTELLIGENCE_HEARTBEAT_SECONDS,
            session_factory=sessions,
            now_factory=clock.now,
            sleep=sleep,
        )
        heartbeat.start(asyncio.current_task())
        try:
            await heartbeat.resource_wait("LOCAL_RESOURCE_RESERVE_WAIT")
            self.assertEqual(job.error_code, "LOCAL_RESOURCE_RESERVE_WAIT")
            self.assertEqual(job.lease_expires_at, clock.now() + timedelta(minutes=LEASE_MINUTES))

            for _ in range(3):
                clock.advance(INTELLIGENCE_HEARTBEAT_SECONDS + 1)
                sleep.tick()
                await _flush_loop()
                self.assertEqual(
                    job.lease_expires_at,
                    clock.now() + timedelta(minutes=LEASE_MINUTES),
                )
                self.assertGreater(job.lease_expires_at, clock.now())

            await heartbeat.resource_ready("LOCAL_RESOURCE_ADMITTED")
            self.assertIsNone(job.error_code)
            self.assertEqual(job.updated_at, clock.now())
        finally:
            await heartbeat.stop()

        committed = sessions.commits
        clock.advance(INTELLIGENCE_HEARTBEAT_SECONDS + 1)
        sleep.tick()
        await _flush_loop()
        self.assertEqual(sessions.commits, committed)

    async def test_cancelled_last_assistant_waiter_stops_owner_without_retry(self) -> None:
        clock = _Clock()
        sleep = _ControlledSleep()
        job = _job(trigger="assistant")
        sessions = _Sessions(job)
        owner_started = asyncio.Event()

        async def owner() -> None:
            owner_started.set()
            await asyncio.Event().wait()

        owner_task = asyncio.create_task(owner())
        await owner_started.wait()
        heartbeat = _PreparationIntelligenceHeartbeat(
            job.id,
            session_factory=sessions,
            now_factory=clock.now,
            sleep=sleep,
        )
        with patch(
            "app.services.document_preparation_dispatcher._assistant_preparation_has_no_active_waiters",
            return_value=False,
        ):
            heartbeat.start(owner_task)
        with patch(
            "app.services.document_preparation_dispatcher._assistant_preparation_has_no_active_waiters",
            return_value=True,
        ):
            sleep.tick()
            await _flush_loop()

        with self.assertRaises(asyncio.CancelledError):
            await owner_task
        await heartbeat.stop()
        self.assertEqual((job.status, job.stage), ("cancelled", "cancelled"))
        self.assertEqual(job.error_code, "ASSISTANT_RUN_CANCELLED")
        self.assertIsNone(job.lease_expires_at)
        self.assertNotEqual(job.status, "queued")

    async def test_cancel_during_real_resource_wait_never_enters_generation(self) -> None:
        class WaitingProvider:
            async def snapshot(self) -> LocalResourceSnapshot:
                return LocalResourceSnapshot(
                    windows_total_bytes=32 * GIB,
                    windows_available_bytes=9 * GIB,
                    wsl_total_bytes=16 * GIB,
                    wsl_available_bytes=12 * GIB,
                    wsl_swap_total_bytes=8 * GIB,
                    wsl_swap_used_bytes=0,
                    resident_models=(),
                )

            async def unload(self, _model: str) -> None:
                return None

            def resident_models_sync(self):
                return ()

        clock = _Clock()
        sleep = _ControlledSleep()
        job = _job(trigger="assistant")
        sessions = _Sessions(job)
        coordinator = LocalModelResourceCoordinator(provider=WaitingProvider())
        cancel_requested = False
        generation_count = 0

        async def acquire() -> None:
            nonlocal generation_count
            heartbeat = _PreparationIntelligenceHeartbeat(
                job.id,
                session_factory=sessions,
                now_factory=clock.now,
                sleep=sleep,
            )
            owner = asyncio.current_task()
            assert owner is not None
            heartbeat.start(owner)
            try:
                async with coordinator.generator_session(
                    "qwen3.5:9b",
                    wait_timeout=None,
                    on_wait=heartbeat.resource_wait,
                    on_ready=heartbeat.resource_ready,
                ):
                    generation_count += 1
            finally:
                await heartbeat.stop()

        with patch(
            "app.services.document_preparation_dispatcher._assistant_preparation_has_no_active_waiters",
            side_effect=lambda _db, _job: cancel_requested,
        ):
            owner_task = asyncio.create_task(acquire())
            for _ in range(20):
                if job.error_code == "LOCAL_RESOURCE_RESERVE_WAIT":
                    break
                await asyncio.sleep(0)
            self.assertEqual(job.error_code, "LOCAL_RESOURCE_RESERVE_WAIT")
            cancel_requested = True
            sleep.tick()
            with self.assertRaises(asyncio.CancelledError):
                await owner_task

        self.assertEqual(generation_count, 0)
        self.assertEqual((job.status, job.stage), ("cancelled", "cancelled"))
        self.assertFalse(coordinator.state()["heavy_active"])
        self.assertEqual(coordinator.state()["heavy_waiters"], 0)

    async def test_failure_or_completion_stops_future_heartbeats(self) -> None:
        clock = _Clock()
        sleep = _ControlledSleep()
        job = _job()
        sessions = _Sessions(job)
        heartbeat = _PreparationIntelligenceHeartbeat(
            job.id,
            session_factory=sessions,
            now_factory=clock.now,
            sleep=sleep,
        )
        heartbeat.start(asyncio.current_task())
        await heartbeat.stop()
        job.status = "ready"
        committed = sessions.commits
        sleep.tick()
        await _flush_loop()
        self.assertEqual(sessions.commits, committed)


class DocumentIntelligenceCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_preparation_wait_ready_generation_and_completion_are_single(self) -> None:
        job = _job()
        job.document_id = 42
        sessions = _Sessions(job)
        clock = _Clock()
        builds = 0
        completed: list[tuple[str, str]] = []
        failed: list[tuple[str, str]] = []

        class FakePreparationService:
            def __init__(self, _db) -> None:
                pass

            def complete_intelligence(self, job_id: str, artifact_id: str) -> None:
                completed.append((job_id, artifact_id))
                job.status = "ready"
                job.stage = "ready_for_ai"
                job.error_code = None

            def fail_intelligence(self, job_id: str, error_code: str) -> None:
                failed.append((job_id, error_code))

        async def fake_build(**kwargs) -> str:
            nonlocal builds
            builds += 1
            await kwargs["on_resource_wait"]("LOCAL_RESOURCE_RESERVE_WAIT")
            await asyncio.sleep(0.005)
            await kwargs["on_resource_ready"]("LOCAL_RESOURCE_ADMITTED")
            await kwargs["progress_callback"]({"chunks": 1, "done": True})
            return "artifact-42"

        def heartbeat_factory(job_id: str) -> _PreparationIntelligenceHeartbeat:
            return _PreparationIntelligenceHeartbeat(
                job_id,
                interval_seconds=0.001,
                session_factory=sessions,
                now_factory=clock.now,
            )

        with (
            patch(
                "app.services.document_preparation_dispatcher.SessionLocal",
                side_effect=sessions,
            ),
            patch(
                "app.services.document_preparation_dispatcher.DocumentPreparationService",
                FakePreparationService,
            ),
            patch(
                "app.services.document_preparation_dispatcher._PreparationIntelligenceHeartbeat",
                side_effect=heartbeat_factory,
            ),
            patch(
                "app.services.document_preparation_dispatcher._assistant_preparation_has_no_active_waiters",
                return_value=False,
            ),
            patch(
                "app.services.document_preparation_dispatcher.build_document_intelligence",
                side_effect=fake_build,
            ),
        ):
            artifact_id = await process_preparation_intelligence(job.id)

        self.assertEqual(artifact_id, "artifact-42")
        self.assertEqual(builds, 1)
        self.assertEqual(completed, [(job.id, "artifact-42")])
        self.assertEqual(failed, [])
        self.assertEqual((job.status, job.stage), ("ready", "ready_for_ai"))
        self.assertGreaterEqual(sessions.commits, 3)

    async def test_resource_callbacks_cover_admission_and_generation_once(self) -> None:
        evidence = (
            IntelligenceEvidence(
                source_ref="P0001",
                source_kind="document_page",
                source_entity_id="10",
                page_number=1,
                text="Nośność obliczeniowa wynosi 250 kPa.",
                checksum="a" * 64,
            ),
        )
        build_input = IntelligenceBuildInput(
            document_id=10,
            document_checksum="b" * 64,
            preparation_job_id="prep-10",
            evidence=evidence,
        )
        events: list[tuple[str, str]] = []
        persisted: list[str] = []
        real_validate = DocumentIntelligenceService.validate_payload

        class FakeDb:
            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        class FakeService:
            def __init__(self, _db):
                pass

            def collect_input(self, **_kwargs):
                return build_input

            def accepted_baseline(self, **_kwargs):
                return None

            @staticmethod
            def validate_payload(payload, current_evidence):
                return real_validate(payload, current_evidence)

            def persist(self, *, kind, payload, **_kwargs):
                persisted.append(kind)
                return SimpleNamespace(id="artifact-10", payload=payload)

        class FakeClient:
            def __init__(self) -> None:
                self.generations = 0

            @asynccontextmanager
            async def resource_session(self, _model, *, on_wait, on_ready, **_kwargs):
                await on_wait("LOCAL_RESOURCE_RESERVE_WAIT")
                await on_ready("LOCAL_RESOURCE_ADMITTED")
                yield

            async def generate_streaming(
                self, *, on_resource_wait, on_resource_ready, on_progress, **_kwargs
            ):
                self.generations += 1
                await on_resource_wait("LOCAL_MODEL_BUSY")
                await on_resource_ready("LOCAL_RESOURCE_READMITTED")
                await on_progress({"chunks": 1, "done": True})
                return {
                    "response": json.dumps({
                        "document_class": "raport",
                        "language": "pl",
                        "summary": "Raport opisuje nośność podłoża.",
                        "topics": ["nośność"],
                        "findings": [{
                            "kind": "measurement",
                            "text": "Nośność wynosi 250 kPa.",
                            "source_refs": ["P0001"],
                        }],
                        "limitations": [],
                    }),
                    "done": True,
                }

        async def on_wait(reason: str) -> None:
            events.append(("wait", reason))

        async def on_ready(reason: str) -> None:
            events.append(("ready", reason))

        async def on_progress(_item: dict) -> None:
            return None

        client = FakeClient()
        with (
            patch(
                "app.services.document_intelligence_service.SessionLocal",
                side_effect=lambda: FakeDb(),
            ),
            patch(
                "app.services.document_intelligence_service.DocumentIntelligenceService",
                FakeService,
            ),
        ):
            artifact_id = await build_document_intelligence(
                document_id=10,
                preparation_job_id="prep-10",
                client=client,
                progress_callback=on_progress,
                on_resource_wait=on_wait,
                on_resource_ready=on_ready,
            )

        self.assertEqual(artifact_id, "artifact-10")
        self.assertEqual(client.generations, 1)
        self.assertEqual(persisted, ["baseline_document"])
        self.assertEqual(
            events,
            [
                ("wait", "LOCAL_RESOURCE_RESERVE_WAIT"),
                ("ready", "LOCAL_RESOURCE_ADMITTED"),
                ("wait", "LOCAL_MODEL_BUSY"),
                ("ready", "LOCAL_RESOURCE_READMITTED"),
            ],
        )


class DocumentIntelligenceProgressAndRecoveryTests(unittest.TestCase):
    def test_assistant_cancellation_respects_other_active_waiters(self) -> None:
        job = _job(trigger="assistant")

        class Query:
            def __init__(self, *, rows=None, first=None) -> None:
                self.rows = rows or []
                self.first_value = first

            def filter(self, *_args):
                return self

            def all(self):
                return self.rows

            def first(self):
                return self.first_value

        class Db:
            def __init__(self, stage_rows, legacy=None) -> None:
                self.stage_rows = stage_rows
                self.legacy = legacy
                self.calls = 0

            def query(self, _column):
                self.calls += 1
                if self.calls == 1:
                    return Query(rows=self.stage_rows)
                return Query(first=self.legacy)

        self.assertFalse(
            _assistant_preparation_has_no_active_waiters(
                Db([("cancelled",), ("waiting",)]), job
            )
        )
        self.assertFalse(
            _assistant_preparation_has_no_active_waiters(
                Db([("cancelled",)], legacy=("legacy-active",)), job
            )
        )
        self.assertTrue(
            _assistant_preparation_has_no_active_waiters(
                Db([("cancelled",)]), job
            )
        )

    def test_wait_reasons_are_bounded_and_user_visible(self) -> None:
        run = SimpleNamespace(status="waiting", current_stage="waiting_for_material")
        for reason in (
            "LOCAL_RESOURCE_RESERVE_WAIT",
            "LOCAL_MODEL_BUSY",
            "LOCAL_EXTERNAL_GENERATOR_RESIDENT",
            "LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE",
        ):
            preparation = SimpleNamespace(stage="local_analysis", error_code=reason)
            self.assertEqual(
                AssistantRunService._progress_message(run, None, preparation),
                "Oczekuję na wolne zasoby komputera.",
            )
        generating = SimpleNamespace(stage="local_analysis", error_code=None)
        self.assertEqual(
            AssistantRunService._progress_message(run, None, generating),
            "Tworzę techniczne podsumowanie dokumentu.",
        )
        self.assertEqual(
            document_intelligence_resource_wait_code("untrusted internal detail"),
            "LOCAL_RESOURCE_WAIT",
        )

    def test_dead_worker_still_uses_canonical_expired_lease_recovery(self) -> None:
        job = _job()
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

        class Query:
            def filter(self, *_args):
                return self

            def with_for_update(self, **_kwargs):
                return self

            def all(self):
                return [job]

        class Db:
            def query(self, _model):
                return Query()

        self.assertEqual(DocumentPreparationService(Db()).recover_expired(), 1)
        self.assertEqual((job.status, job.stage), ("queued", "queued"))
        self.assertIsNone(job.lease_owner)
        self.assertIsNone(job.lease_expires_at)
        self.assertEqual(job.attempt_count, 1)

    def test_existing_intelligence_failure_retry_policy_is_unchanged(self) -> None:
        job = _job()

        class Db:
            def get(self, _model, job_id: str):
                return job if job_id == job.id else None

            def flush(self) -> None:
                return None

        DocumentPreparationService(Db()).fail_intelligence(
            job.id, "SYNTHETIC_TRANSIENT_FAILURE"
        )
        self.assertEqual((job.status, job.stage), ("queued", "queued"))
        self.assertEqual(job.error_code, "SYNTHETIC_TRANSIENT_FAILURE")
        self.assertEqual(job.retryability, "recoverable")
        self.assertIsNone(job.lease_expires_at)

    def test_resource_thresholds_remain_exact(self) -> None:
        self.assertEqual(WINDOWS_TARGET_RESERVE_BYTES, 4 * GIB)
        self.assertEqual(WSL_TARGET_RESERVE_BYTES, 4 * GIB)
        self.assertEqual(EMERGENCY_FLOOR_BYTES, 3 * GIB)
        self.assertEqual(QWEN9_WINDOWS_INCREMENT_BYTES, int(6.60 * GIB))
        self.assertEqual(QWEN9_WSL_INCREMENT_BYTES, int(6.25 * GIB))


if __name__ == "__main__":
    unittest.main()
