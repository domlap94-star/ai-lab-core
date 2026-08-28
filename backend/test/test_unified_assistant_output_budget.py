from __future__ import annotations

import asyncio
import json
import time
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.ai.clients.ollama_client import OllamaClient
from app.schemas.agent import AgentSource
from app.services.local_model_time_policy import (
    LOCAL_OUTPUT_BUDGET_EXHAUSTED,
    LocalOutputBudgetExhausted,
    V2_STANDARD_INITIAL_NUM_PREDICT,
    V2_STANDARD_SEMANTIC_CORRECTION_NUM_PREDICT,
    V2_STANDARD_TASK_COMPLETION_CORRECTION_NUM_PREDICT,
    V2_STANDARD_TRUNCATION_RETRY_NUM_PREDICT,
    local_output_budget_exhausted,
)
from app.services.unified_assistant_service import UnifiedAssistantService, _Collected


class _FakeLlm:
    def __init__(self, result: dict) -> None:
        self.result = result

    async def generate(self, **_kwargs) -> dict:
        return self.result


def _service(result: dict | None = None) -> UnifiedAssistantService:
    service = UnifiedAssistantService.__new__(UnifiedAssistantService)
    service.llm = _FakeLlm(result or {})
    service.local_num_thread = None
    service._model_resource_context = None
    service.local_truncation_retry_used = False
    return service


class OutputBudgetClassificationTests(unittest.IsolatedAsyncioTestCase):
    def test_policy_budgets_are_explicit_and_bounded(self) -> None:
        self.assertEqual(V2_STANDARD_INITIAL_NUM_PREDICT, 480)
        self.assertEqual(V2_STANDARD_TRUNCATION_RETRY_NUM_PREDICT, 768)
        self.assertEqual(V2_STANDARD_SEMANTIC_CORRECTION_NUM_PREDICT, 480)
        self.assertEqual(V2_STANDARD_TASK_COMPLETION_CORRECTION_NUM_PREDICT, 480)

    def test_explicit_length_reason_is_budget_exhaustion(self) -> None:
        self.assertTrue(local_output_budget_exhausted(
            done_reason="length",
            eval_count=470,
            requested_num_predict=480,
            parse_failed=False,
        ))

    def test_missing_reason_uses_exact_budget_and_parse_failure_fallback(self) -> None:
        self.assertTrue(local_output_budget_exhausted(
            done_reason=None,
            eval_count=480,
            requested_num_predict=480,
            parse_failed=True,
        ))
        self.assertFalse(local_output_budget_exhausted(
            done_reason=None,
            eval_count=479,
            requested_num_predict=480,
            parse_failed=True,
        ))

    def test_malformed_normal_completion_is_not_budget_exhaustion(self) -> None:
        self.assertFalse(local_output_budget_exhausted(
            done_reason="stop",
            eval_count=480,
            requested_num_predict=480,
            parse_failed=True,
        ))

    async def test_generate_local_raises_canonical_exhaustion(self) -> None:
        service = _service({
            "response": '{"answer":"cut',
            "done": True,
            "done_reason": "length",
            "eval_count": 480,
        })
        with self.assertRaisesRegex(
            LocalOutputBudgetExhausted, LOCAL_OUTPUT_BUDGET_EXHAUSTED
        ):
            await service._generate_local("safe", {}, num_predict=480)

    async def test_generate_local_preserves_ordinary_json_error(self) -> None:
        service = _service({
            "response": '{"answer":"cut',
            "done": True,
            "done_reason": "stop",
            "eval_count": 120,
        })
        with self.assertRaises(json.JSONDecodeError):
            await service._generate_local("safe", {}, num_predict=480)

    async def test_one_truncation_retry_uses_original_prompt_and_larger_budget(self) -> None:
        service = _service()
        service._generate_before_deadline = AsyncMock(side_effect=[
            LocalOutputBudgetExhausted(
                requested_num_predict=480, eval_count=480, done_reason="length"
            ),
            {"answer": "ok"},
        ])
        result = await service._generate_standard_with_truncation_retry(
            "ORIGINAL", {}, time.monotonic() + 10
        )
        self.assertEqual(result, {"answer": "ok"})
        self.assertTrue(service.local_truncation_retry_used)
        calls = service._generate_before_deadline.await_args_list
        self.assertEqual(calls[0].kwargs["num_predict"], 480)
        self.assertEqual(calls[1].kwargs["num_predict"], 768)
        self.assertTrue(calls[1].args[0].startswith("ORIGINAL"))
        self.assertIn("OUTPUT_BUDGET_RETRY", calls[1].args[0])
        self.assertNotIn("PREVIOUS=", calls[1].args[0])

    async def test_second_exhaustion_stops_after_one_retry(self) -> None:
        service = _service()
        exhausted = LocalOutputBudgetExhausted(
            requested_num_predict=480, eval_count=480, done_reason="length"
        )
        service._generate_before_deadline = AsyncMock(side_effect=[exhausted, exhausted])
        with self.assertRaises(LocalOutputBudgetExhausted):
            await service._generate_standard_with_truncation_retry(
                "ORIGINAL", {}, time.monotonic() + 10
            )
        self.assertEqual(service._generate_before_deadline.await_count, 2)

    async def test_semantic_correction_can_consume_unused_shared_retry(self) -> None:
        service = _service()
        exhausted = LocalOutputBudgetExhausted(
            requested_num_predict=480, eval_count=480, done_reason="length"
        )
        service._generate_before_deadline = AsyncMock(side_effect=[
            {"answer": "initial-complete"}, exhausted, {"answer": "corrected-complete"},
        ])
        initial = await service._generate_standard_with_truncation_retry(
            "ORIGINAL", {}, time.monotonic() + 10
        )
        corrected = await service._generate_with_shared_truncation_retry(
            "SEMANTIC_CORRECTION",
            {},
            time.monotonic() + 10,
            num_predict=V2_STANDARD_SEMANTIC_CORRECTION_NUM_PREDICT,
        )
        self.assertEqual(initial, {"answer": "initial-complete"})
        self.assertEqual(corrected, {"answer": "corrected-complete"})
        self.assertEqual(
            [call.kwargs["num_predict"] for call in service._generate_before_deadline.await_args_list],
            [480, 480, 768],
        )
        self.assertIn(
            "SEMANTIC_CORRECTION",
            service._generate_before_deadline.await_args_list[2].args[0],
        )

    async def test_consumed_initial_retry_blocks_later_semantic_retry(self) -> None:
        service = _service()
        exhausted = LocalOutputBudgetExhausted(
            requested_num_predict=480, eval_count=480, done_reason="length"
        )
        service._generate_before_deadline = AsyncMock(side_effect=[
            exhausted, {"answer": "initial-recovered"}, exhausted,
        ])
        await service._generate_standard_with_truncation_retry(
            "ORIGINAL", {}, time.monotonic() + 10
        )
        with self.assertRaises(LocalOutputBudgetExhausted):
            await service._generate_with_shared_truncation_retry(
                "SEMANTIC_CORRECTION",
                {},
                time.monotonic() + 10,
                num_predict=V2_STANDARD_SEMANTIC_CORRECTION_NUM_PREDICT,
            )
        self.assertEqual(service._generate_before_deadline.await_count, 3)
        self.assertEqual(
            [call.kwargs["num_predict"] for call in service._generate_before_deadline.await_args_list],
            [480, 768, 480],
        )

    def test_second_exhaustion_has_fail_closed_response(self) -> None:
        response = UnifiedAssistantService._local_output_budget_exhausted_response(
            "run-id", _Collected([], [], ["document_read"], None, False)
        )
        self.assertEqual(response.status, "review_required")
        self.assertEqual(response.current_stage, "local_output_budget_exhausted")
        self.assertEqual(response.answer, "")
        self.assertEqual(response.sources, [])

    def test_source_and_internal_output_validation_remain_fail_closed(self) -> None:
        source_map = {
            "S01": AgentSource(
                source_type="document",
                source_id=1,
                title="Synthetic",
                route="synthetic://document/1",
                snippet="safe",
            )
        }
        payload = {
            "answer": "Bezpieczne podsumowanie.",
            "claims": [{
                "class": "FACT",
                "text": "Treść wynika ze źródła.",
                "source_refs": ["S01"],
                "tool_refs": [],
            }],
            "used_sources": ["S01"],
            "tool_plan": [],
            "estimate": None,
        }
        self.assertIsNone(UnifiedAssistantService._validate(payload, source_map, False))
        payload["claims"][0]["source_refs"] = ["S02"]
        self.assertEqual(
            UnifiedAssistantService._validate(payload, source_map, False),
            "unknown_source",
        )
        payload["claims"][0]["source_refs"] = ["S01"]
        payload["answer"] = "VALIDATED_EVIDENCE"
        self.assertEqual(
            UnifiedAssistantService._validate(payload, source_map, False),
            "user_output_internal_leak",
        )


class _StreamResponse:
    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield json.dumps({"response": "{", "done": False})
        yield json.dumps({
            "response": "}",
            "done": True,
            "done_reason": "length",
            "eval_count": 2,
        })


class _StreamContext:
    async def __aenter__(self):
        return _StreamResponse()

    async def __aexit__(self, *_args):
        return False


class _AsyncClient:
    def __init__(self, *_args, **_kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def stream(self, *_args, **_kwargs):
        return _StreamContext()


class _ResourceCoordinator:
    @asynccontextmanager
    async def generator_session(self, *_args, **_kwargs):
        yield None

    async def unload_owned_model(self, _model):
        return True


class StreamingTerminalMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_done_reason_is_returned_and_exposed_as_bounded_telemetry(self) -> None:
        telemetry: list[dict] = []

        async def progress(value: dict) -> None:
            telemetry.append(value)

        with patch("app.ai.clients.ollama_client.httpx.AsyncClient", _AsyncClient):
            result = await OllamaClient(
                resource_coordinator=_ResourceCoordinator()
            ).generate_streaming(
                model="synthetic", prompt="safe", on_progress=progress
            )
        self.assertEqual(result["done_reason"], "length")
        self.assertEqual(telemetry[-1]["done_reason"], "length")
        self.assertNotIn("response", telemetry[-1])


if __name__ == "__main__":
    unittest.main()
