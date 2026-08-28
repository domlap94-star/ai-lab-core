from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.services.local_model_time_policy import (
    DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS,
    GENERATION_ABSOLUTE_SECONDS,
    GENERATION_INACTIVITY_SECONDS,
    MODEL_LOAD_ABSOLUTE_SECONDS,
    PROMPT_EVALUATION_ABSOLUTE_SECONDS,
    STANDARD_LOCAL_ABSOLUTE_SECONDS,
    V2_LOCAL_NUM_THREAD,
    phase_timeout_code,
    utc_iso,
)
from app.services.assistant_run_stage_service import AssistantRunStageService
from app.services.unified_assistant_service import UnifiedAssistantService


class _NoopDb:
    def flush(self) -> None:
        return None


class _Stage:
    status = "waiting"
    started_at = None
    heartbeat_at = None
    last_progress_at = None
    lease_owner = None
    lease_expires_at = None


class _Run:
    status = "waiting"
    current_stage = None
    started_at = None
    heartbeat_at = None


class LocalModelTimePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

    def manifest(self, phase: str, elapsed: int) -> dict:
        return {
            "local_model_phase": {
                "phase": phase,
                "started_at": utc_iso(self.now - timedelta(seconds=elapsed)),
            }
        }

    def test_qualification_constants_are_bounded(self) -> None:
        self.assertIsNone(V2_LOCAL_NUM_THREAD)
        self.assertEqual(MODEL_LOAD_ABSOLUTE_SECONDS, 180)
        self.assertEqual(PROMPT_EVALUATION_ABSOLUTE_SECONDS, 300)
        self.assertEqual(GENERATION_INACTIVITY_SECONDS, 120)
        self.assertEqual(GENERATION_ABSOLUTE_SECONDS, 600)
        self.assertEqual(STANDARD_LOCAL_ABSOLUTE_SECONDS, 900)
        self.assertEqual(DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS, 900)

    def test_default_local_options_omit_num_thread(self) -> None:
        service = UnifiedAssistantService.__new__(UnifiedAssistantService)
        service.local_num_thread = None

        self.assertEqual(
            service._local_options(num_ctx=4096, num_predict=480),
            {"temperature": 0.1, "num_ctx": 4096, "num_predict": 480},
        )

    def test_explicit_local_thread_override_is_emitted(self) -> None:
        service = UnifiedAssistantService.__new__(UnifiedAssistantService)
        service.local_num_thread = 6

        self.assertEqual(
            service._local_options(num_ctx=4096, num_predict=480)["num_thread"],
            6,
        )

    def test_load_and_prompt_evaluation_use_absolute_phase_caps(self) -> None:
        old_progress = self.now - timedelta(seconds=500)
        self.assertIsNone(phase_timeout_code(
            manifest=self.manifest("model_load", 179),
            last_progress_at=old_progress,
            now=self.now,
        ))
        self.assertEqual(phase_timeout_code(
            manifest=self.manifest("model_load", 181),
            last_progress_at=old_progress,
            now=self.now,
        ), "LOCAL_MODEL_LOAD_TIMEOUT")
        self.assertIsNone(phase_timeout_code(
            manifest=self.manifest("prompt_evaluation", 299),
            last_progress_at=old_progress,
            now=self.now,
        ))
        self.assertEqual(phase_timeout_code(
            manifest=self.manifest("prompt_evaluation", 301),
            last_progress_at=old_progress,
            now=self.now,
        ), "LOCAL_PROMPT_EVALUATION_TIMEOUT")

    def test_generation_requires_real_progress_and_has_absolute_cap(self) -> None:
        self.assertIsNone(phase_timeout_code(
            manifest=self.manifest("generation", 300),
            last_progress_at=self.now - timedelta(seconds=119),
            now=self.now,
        ))
        self.assertEqual(phase_timeout_code(
            manifest=self.manifest("generation", 300),
            last_progress_at=self.now - timedelta(seconds=121),
            now=self.now,
        ), "LOCAL_GENERATION_INACTIVITY_TIMEOUT")
        self.assertEqual(phase_timeout_code(
            manifest=self.manifest("generation", 601),
            last_progress_at=self.now,
            now=self.now,
        ), "LOCAL_GENERATION_ABSOLUTE_TIMEOUT")

    def test_invalid_phase_timestamp_fails_closed(self) -> None:
        manifest = {"local_model_phase": {"phase": "model_load", "started_at": "invalid"}}
        self.assertEqual(phase_timeout_code(
            manifest=manifest,
            last_progress_at=self.now,
            now=self.now,
        ), "LOCAL_MODEL_PHASE_STATE_INVALID")

    def test_resource_wait_does_not_consume_active_stage_clock(self) -> None:
        stage = _Stage()
        old_wait_started = self.now - timedelta(hours=2)
        stage.started_at = old_wait_started
        stage.last_progress_at = old_wait_started
        service = AssistantRunStageService(_NoopDb())
        service.latest = lambda _run_id, _stage_type: stage
        run = _Run()
        run.id = "run"
        resumed = service.start(run, "analyzing_local")
        self.assertEqual(resumed.status, "running")
        self.assertGreater(resumed.started_at, old_wait_started)
        self.assertEqual(resumed.started_at, resumed.last_progress_at)


if __name__ == "__main__":
    unittest.main()
