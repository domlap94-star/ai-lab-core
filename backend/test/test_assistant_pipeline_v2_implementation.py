from __future__ import annotations

import asyncio
import json
import os
import re
import time
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.ai.clients.ollama_client import OllamaClient
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.assistant_pipeline import AssistantRun, AssistantRunStage
from app.models.role import Role
from app.models.user import User
from app.schemas.assistant_pipeline import (
    AssistantRunCreateRequest,
    validate_bounded_json,
)
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.assistant_run_dispatcher import StageStreamingOllamaClient, _execute_run
from app.services.assistant_run_planner import AssistantRunPlanner
from app.services.assistant_run_service import (
    AssistantRunActiveConflict,
    AssistantRunIdempotencyConflict,
    AssistantRunService,
)
from app.services.assistant_run_stage_service import AssistantRunStageService
from app.services.document_intelligence_service import (
    DocumentIntelligenceError,
    DocumentIntelligenceService,
    IntelligenceBuildInput,
    IntelligenceEvidence,
    _compact_reduce_payloads,
    build_document_intelligence,
)
from app.services.unified_assistant_service import UnifiedAssistantService
from test.support.database_safety import require_test_database_environment


class JsonBoundsTests(unittest.TestCase):
    def test_bounded_json_rejects_depth_size_and_unsupported_values(self) -> None:
        self.assertEqual(validate_bounded_json({"safe": [1, 2]}, field_name="x"), {"safe": [1, 2]})
        with self.assertRaises(ValueError):
            validate_bounded_json({"x": {"x": {"x": {"x": {"x": {"x": {"x": {"x": 1}}}}}}}}, field_name="x")
        with self.assertRaises(ValueError):
            validate_bounded_json({"x": "a" * 9000}, field_name="x")
        with self.assertRaises(ValueError):
            validate_bounded_json({"x": object()}, field_name="x")

    def test_request_contract_rejects_unbounded_or_invalid_attempt(self) -> None:
        valid = AssistantRunCreateRequest(question="Co potrafisz?", attempt_id="attempt_0001")
        self.assertEqual(valid.attempt_id, "attempt_0001")
        with self.assertRaises(ValueError):
            AssistantRunCreateRequest(question="Co potrafisz?", attempt_id="bad")


class PlannerContractTests(unittest.TestCase):
    def test_fast_and_deep_plans_are_deterministic(self) -> None:
        fast = AssistantRunPlanner._stages("system_meta", "fast")
        deep = AssistantRunPlanner._stages("document_reasoning", "deep")
        self.assertEqual([item["stage_type"] for item in fast], ["planning", "finalizing"])
        deep_types = [item["stage_type"] for item in deep]
        self.assertIn("building_intelligence", deep_types)
        self.assertIn("reducing_findings", deep_types)
        self.assertIn("waiting_for_advanced", deep_types)
        self.assertEqual(len({item["stage_key"] for item in deep}), len(deep))

    def test_v2_external_policy_is_durable_but_absolutely_bounded(self) -> None:
        deep = AssistantRunPlanner._stages("document_reasoning", "deep")
        waiting = next(
            item for item in deep if item["stage_type"] == "waiting_for_advanced"
        )
        self.assertEqual(waiting["absolute_cap_seconds"], 1800)

        job = SimpleNamespace(
            status="advanced_processing",
            started_at=datetime.now(UTC) - timedelta(seconds=200),
            created_at=datetime.now(UTC) - timedelta(seconds=200),
            external_job_id=None,
        )
        service = UnifiedAssistantService(
            SimpleNamespace(),
            advanced_queue_hard_seconds=600,
            advanced_external_hard_seconds=1800,
        )
        self.assertFalse(service._expire_advanced(job))

    def test_capability_phrase_is_fast_and_general_plan_has_no_kb_stage(self) -> None:
        request = UnifiedAssistantRequest(
            question="Czym zajmuje się Asystent AI?", conversation=[]
        )
        self.assertEqual(
            UnifiedAssistantService._query_mode(request), "SYSTEM_META"
        )
        general = AssistantRunPlanner._stages("general_knowledge", "standard")
        self.assertNotIn(
            "retrieving_knowledge_base",
            [item["stage_type"] for item in general],
        )


class IntelligenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = (
            IntelligenceEvidence(
                source_ref="P0001",
                source_kind="document_page",
                source_entity_id="10",
                page_number=1,
                text="Nośność obliczeniowa wynosi 250 kPa.",
                checksum="a" * 64,
            ),
        )

    def test_sources_and_measurements_are_fail_closed(self) -> None:
        payload = {
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
        }
        self.assertEqual(
            DocumentIntelligenceService.validate_payload(payload, self.evidence), payload
        )
        wrong_source = json.loads(json.dumps(payload))
        wrong_source["findings"][0]["source_refs"] = ["P9999"]
        with self.assertRaises(DocumentIntelligenceError):
            DocumentIntelligenceService.validate_payload(wrong_source, self.evidence)
        invented_measurement = json.loads(json.dumps(payload))
        invented_measurement["findings"][0]["text"] = "Nośność wynosi 999 kPa."
        with self.assertRaises(DocumentIntelligenceError):
            DocumentIntelligenceService.validate_payload(invented_measurement, self.evidence)

    def test_long_document_reduce_input_is_bounded_and_source_bound(self) -> None:
        sections = [{
            "summary": "s" * 500,
            "topics": ["topic" for _ in range(10)],
            "findings": [{
                "kind": "fact",
                "text": "bounded finding " * 50,
                "source_refs": [f"P{index:04d}"],
            } for _ in range(5)],
        } for index in range(40)]

        compact = _compact_reduce_payloads(sections)

        self.assertEqual(len(compact), 24)
        self.assertTrue(all(len(item["findings"]) <= 2 for item in compact))
        self.assertTrue(all(len(item["summary"]) <= 180 for item in compact))


class DocumentMapReduceRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_section_maps_are_reused_after_interruption(self) -> None:
        evidence = tuple(
            IntelligenceEvidence(
                source_ref=f"P{index:04d}",
                source_kind="document_page",
                source_entity_id=str(index),
                page_number=index,
                text=f"Syntetyczna treść strony {index}.",
                checksum=f"{index:064x}"[-64:],
            )
            for index in range(1, 18)
        )
        build_input = IntelligenceBuildInput(
            document_id=41,
            document_checksum="a" * 64,
            preparation_job_id="prep-41",
            evidence=evidence,
        )
        artifacts: dict[tuple[str, str], SimpleNamespace] = {}
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
                return artifacts.get(("baseline_document", "default"))

            def accepted(self, *, kind, artifact_key, **_kwargs):
                return artifacts.get((kind, artifact_key))

            @staticmethod
            def validate_payload(payload, current_evidence):
                return real_validate(payload, current_evidence)

            def persist(self, *, kind, artifact_key, payload, **_kwargs):
                artifact = SimpleNamespace(
                    id=f"{kind}:{artifact_key}", payload=payload,
                )
                artifacts[(kind, artifact_key)] = artifact
                return artifact

        class FakeClient:
            def __init__(self, fail_on: int | None = None):
                self.calls = 0
                self.fail_on = fail_on

            async def generate_streaming(self, *, prompt, **_kwargs):
                self.calls += 1
                if self.fail_on == self.calls:
                    raise OSError("synthetic interruption")
                refs = re.findall(r'"source_ref":\s*"(P\d{4})"', prompt)
                ref = refs[0]
                payload = {
                    "document_class": "synthetic",
                    "language": "pl",
                    "summary": "Syntetyczne podsumowanie sekcji.",
                    "topics": ["test"],
                    "findings": [{
                        "kind": "fact",
                        "text": "Syntetyczna treść została odczytana.",
                        "source_refs": [ref],
                    }],
                    "limitations": [],
                }
                return {"response": json.dumps(payload), "done": True}

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
            interrupted = FakeClient(fail_on=2)
            with self.assertRaises(OSError):
                await build_document_intelligence(
                    document_id=41,
                    preparation_job_id="prep-41",
                    client=interrupted,
                )
            self.assertIn(("section_map", "section:0001"), artifacts)

            resumed = FakeClient()
            artifact_id = await build_document_intelligence(
                document_id=41,
                preparation_job_id="prep-41",
                client=resumed,
            )

        self.assertEqual(artifact_id, "baseline_document:default")
        self.assertEqual(resumed.calls, 3)
        self.assertEqual(
            {key for key in artifacts if key[0] == "section_map"},
            {
                ("section_map", "section:0001"),
                ("section_map", "section:0002"),
                ("section_map", "section:0003"),
            },
        )


class _FakeStreamResponse:
    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield json.dumps({"response": "{\"answer\":", "done": False})
        yield json.dumps({
            "response": "\"ok\"}", "done": True, "eval_count": 3,
            "prompt_eval_count": 5, "total_duration": 10,
        })


class _FakeStreamContext:
    async def __aenter__(self):
        return _FakeStreamResponse()

    async def __aexit__(self, *_args):
        return False


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        del args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def stream(self, *_args, **_kwargs):
        return _FakeStreamContext()


class _CancelableStreamResponse:
    closed = False

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield json.dumps({"response": "{", "done": False})
        await asyncio.Event().wait()


class _CancelableStreamContext:
    response = _CancelableStreamResponse()

    async def __aenter__(self):
        type(self).response.closed = False
        return type(self).response

    async def __aexit__(self, *_args):
        type(self).response.closed = True
        return False


class _CancelableAsyncClient(_FakeAsyncClient):
    def stream(self, *_args, **_kwargs):
        return _CancelableStreamContext()


class OllamaStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_ndjson_is_combined_and_callback_contains_no_text(self) -> None:
        telemetry: list[dict] = []

        async def progress(value):
            telemetry.append(value)

        with patch("app.ai.clients.ollama_client.httpx.AsyncClient", _FakeAsyncClient):
            result = await OllamaClient().generate_streaming(
                model="synthetic", prompt="safe", on_progress=progress
            )
        self.assertEqual(result["response"], '{"answer":"ok"}')
        self.assertTrue(result["done"])
        self.assertEqual(telemetry[-1]["eval_count"], 3)
        self.assertTrue(all("response" not in item for item in telemetry))

    async def test_cancelling_stream_closes_the_http_context(self) -> None:
        with patch("app.ai.clients.ollama_client.httpx.AsyncClient", _CancelableAsyncClient):
            task = asyncio.create_task(
                OllamaClient().generate_streaming(model="synthetic", prompt="safe")
            )
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(_CancelableStreamContext.response.closed)

    async def test_stage_telemetry_is_throttled_but_terminal_event_is_persisted(self) -> None:
        client = StageStreamingOllamaClient("run-id", "stage-id")
        with patch.object(client, "_persist") as persist:
            await client._progress({"chunks": 1, "done": False})
            client._last_progress_persisted_at = time.monotonic()
            await client._progress({"chunks": 2, "done": False})
            await client._progress({"chunks": 3, "done": True})
        self.assertEqual(persist.call_count, 2)


def integration_main() -> None:
    require_test_database_environment()
    previous = settings.assistant_pipeline_v2_enabled
    settings.assistant_pipeline_v2_enabled = True
    db = SessionLocal()
    try:
        role = Role(id=900041, name="assistant-v2-test", description="isolated")
        user = User(
            id=900041,
            username="assistant-v2-test",
            email="assistant-v2@test.invalid",
            password_hash="not-used",
            role_id=role.id,
        )
        db.add_all([role, user])
        db.commit()
        request = AssistantRunCreateRequest(
            question="Czym zajmujesz się w tym systemie?",
            attempt_id="assistant_v2_system_0001",
        )
        created = AssistantRunService(db).create(request=request, user_id=user.id)
        assert created.status == "queued" and created.result is None
        duplicate = AssistantRunService(db).create(request=request, user_id=user.id)
        assert duplicate.run_id == created.run_id
        try:
            AssistantRunService(db).create(
                request=request.model_copy(update={"question": "Co potrafisz?"}),
                user_id=user.id,
            )
            raise AssertionError("idempotency conflict was not rejected")
        except AssistantRunIdempotencyConflict:
            pass
        try:
            AssistantRunService(db).create(
                request=AssistantRunCreateRequest(
                    question="Co potrafisz?",
                    attempt_id="assistant_v2_parallel_0001",
                ),
                user_id=user.id,
            )
            raise AssertionError("second active run was not rejected")
        except AssistantRunActiveConflict:
            pass
        asyncio.run(_execute_run(created.run_id))
        db.expire_all()
        completed = AssistantRunService(db).get(run_id=created.run_id, user_id=user.id)
        assert completed.status == "completed"
        assert completed.result is not None and completed.result.model is None

        waiting = AssistantRunService(db).create(
            request=AssistantRunCreateRequest(
                question="Co to jest osiadanie różnicowe?",
                attempt_id="assistant_v2_cancel_0001",
            ),
            user_id=user.id,
        )
        cancelled = AssistantRunService(db).cancel(run_id=waiting.run_id, user_id=user.id)
        assert cancelled.status == "cancelled"

        # A virtual >130 s active stage remains transport-independent while
        # substantive progress advances; heartbeat alone cannot hide a stall.
        run = db.get(AssistantRun, waiting.run_id)
        run.status = "running"
        run.current_stage = "analyzing_local"
        run.cancel_requested_at = None
        run.finished_at = None
        stage = db.query(AssistantRunStage).filter_by(
            assistant_run_id=run.id, stage_type="analyzing_local"
        ).one()
        stage.status = "running"
        stage.started_at = datetime.now(UTC) - timedelta(seconds=140)
        stage.last_progress_at = datetime.now(UTC)
        stage.heartbeat_at = datetime.now(UTC)
        stage.lease_expires_at = datetime.now(UTC) + timedelta(seconds=60)
        db.commit()
        assert AssistantRunStageService(db).timeout_code(run.id) is None
        stage.last_progress_at = datetime.now(UTC) - timedelta(seconds=121)
        stage.heartbeat_at = datetime.now(UTC)
        db.commit()
        assert AssistantRunStageService(db).timeout_code(run.id) == "STAGE_INACTIVITY_TIMEOUT"
        stage.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert AssistantRunStageService(db).recover_expired() == 1
        db.commit()
        db.expire_all()
        recovered = db.get(AssistantRun, run.id)
        assert recovered.status == "queued"
        assert recovered.recovery_generation == 1

        print("ASSISTANT_PIPELINE_V2_INTEGRATION=PASS")
        print("SYSTEM_META_MODEL_CALLS=0")
        print("VIRTUAL_LONG_LOCAL_SECONDS=140")
        print("INACTIVITY_HEARTBEAT_SEPARATION=PASS")
        print("LEASE_RESTART_RECOVERY=PASS")
    finally:
        try:
            db.rollback()
            db.query(AssistantRun).filter(AssistantRun.created_by_user_id == 900041).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id == 900041).delete(synchronize_session=False)
            db.query(Role).filter(Role.id == 900041).delete(synchronize_session=False)
            db.commit()
        finally:
            settings.assistant_pipeline_v2_enabled = previous
            db.close()


if __name__ == "__main__":
    if os.environ.get("RUN_ASSISTANT_PIPELINE_V2_INTEGRATION") == "1":
        integration_main()
    else:
        unittest.main()
