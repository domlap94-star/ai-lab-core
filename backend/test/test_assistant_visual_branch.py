from __future__ import annotations

import asyncio
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.models.assistant_pipeline import AssistantRun
from app.models.document import Document
from app.schemas.unified_assistant import UnifiedAssistantRequest, UnifiedAssistantResponse
from app.schemas.vision import VISION_RESULT_SCHEMA
from app.services import assistant_run_dispatcher as dispatcher
from app.services import document_preparation_dispatcher as preparation_dispatcher
from app.services.assistant_run_planner import AssistantRunPlanner
from app.schemas.agent import AgentSource


class _FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args, **_kwargs):
        return self

    def with_for_update(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, harness):
        self.harness = harness

    def query(self, _model):
        return _FakeQuery(self.harness.run)

    def get(self, model, _identity):
        if model is AssistantRun:
            return self.harness.run
        if model is Document:
            return self.harness.document
        return None

    def commit(self):
        self.harness.events.append("db:commit")

    def rollback(self):
        self.harness.events.append("db:rollback")

    def expire_all(self):
        self.harness.events.append("db:expire")

    def close(self):
        return None


class _FakeStages:
    def __init__(self, harness, visual: bool):
        self.harness = harness
        complexity = "visual" if visual else "standard"
        self.planned = {
            item["stage_type"]
            for item in AssistantRunPlanner._stages("document_reasoning", complexity)
        }
        self.status = {item: "queued" for item in self.planned}
        self.manifests: dict[str, dict] = {}

    def latest(self, _run_id, stage_type):
        if stage_type not in self.planned:
            return None
        return SimpleNamespace(status=self.status[stage_type])

    def start(self, run, stage_type):
        self.harness.events.append(f"stage:start:{stage_type}")
        self.status[stage_type] = "running"
        run.status = "running"
        run.current_stage = stage_type
        return SimpleNamespace(id=f"stage-{stage_type}")

    def wait(self, run, stage_type, **kwargs):
        self.harness.events.append(f"stage:wait:{stage_type}")
        self.status[stage_type] = "waiting"
        self.manifests[stage_type] = kwargs.get("manifest") or {}
        run.status = "waiting"
        run.current_stage = stage_type

    def complete(self, run, stage_type, **kwargs):
        self.harness.events.append(f"stage:complete:{stage_type}")
        self.status[stage_type] = "completed"
        self.manifests[stage_type] = kwargs.get("result_manifest") or {}
        return SimpleNamespace(id=f"stage-{stage_type}")

    def skip(self, _run, stage_type, _reason):
        if stage_type in self.planned and self.status[stage_type] not in {
            "completed",
            "skipped",
        }:
            self.harness.events.append(f"stage:skip:{stage_type}")
            self.status[stage_type] = "skipped"

    def fail(self, run, stage_type, error_code):
        self.harness.events.append(f"stage:fail:{stage_type}:{error_code}")
        if stage_type in self.planned:
            self.status[stage_type] = "failed"
        run.status = "failed"
        run.current_stage = None


_ACTIVE_HARNESS = None


class _FakeUnifiedService:
    def __init__(self, _db, **_kwargs):
        self.harness = _ACTIVE_HARNESS
        self.local_truncation_retry_used = False
        self.supplemental_sources = list(_kwargs.get("supplemental_sources") or [])
        self.supplemental_tool_payloads = list(
            _kwargs.get("supplemental_tool_payloads") or []
        )
        self.supervisor = None
        self.allow_advanced_escalation = _kwargs.get(
            "allow_advanced_escalation", True
        )
        self.allow_existing_advanced_result = _kwargs.get(
            "allow_existing_advanced_result", True
        )
        self.harness.service_configurations.append({
            "allow_advanced_escalation": self.allow_advanced_escalation,
            "allow_existing_advanced_result": self.allow_existing_advanced_result,
            "expire_durable_advanced_wait": _kwargs.get(
                "expire_durable_advanced_wait", True
            ),
            "supplemental_tools": [
                item.get("tool")
                for item in self.supplemental_tool_payloads
                if isinstance(item, dict)
            ],
        })

    def _resolve_required_document(self, _request):
        return self.harness.resolution

    def _document_resolution_response(self, _request, _resolution):
        return self.harness.response("review_required")

    def _resolve_required_kb(self, _request):
        return None

    def _collect(self, _request, **_kwargs):
        available = bool(self.supplemental_tool_payloads)
        self.harness.events.append(
            "collect:visual" if available else "collect:no-visual"
        )
        source = SimpleNamespace(
            source_type="document",
            source_id=71,
            route="/documents/71",
            snippet="synthetic",
            title="synthetic",
        )
        sources = [source]
        payloads = []
        tools = ["get_document_summary"]
        if available:
            sources.extend(self.supplemental_sources)
            payloads.extend(self.supplemental_tool_payloads)
            tools.append("get_visual_v2")
        return SimpleNamespace(
            sources=sources,
            tool_payloads=payloads,
            tools=tools,
            client_id=None,
            visual_available=available,
            target_labels=(),
        )

    async def ask(self, *, request, user_id):
        del user_id
        current = self._collect(request)
        if self.harness.visual_planned:
            assert current.visual_available
        status = self.harness.next_response_status()
        self.harness.events.append(f"reasoner:ask:{status}")
        return self.harness.response(status)


class _VisualResolution:
    def __init__(self, state, reason, job_id="visual-job-1", payload=None):
        self.state = state
        self.reason = reason
        self.analysis_job_id = job_id
        self.result_payload = payload

    @property
    def waiting(self):
        return self.state in {"queued", "processing", "awaiting_auth", "awaiting_ui_fix"}


class _FakeVisualService:
    def __init__(self, _db, **_kwargs):
        self.harness = _ACTIVE_HARNESS

    def ensure(self, **_kwargs):
        if not self.harness.visual_planned:
            return _VisualResolution("not_required", "EXTRACTED_TEXT_SUFFICIENT", None)
        if self.harness.vision_status == "partial":
            return _VisualResolution("review_required", "VISION_REQUIRED_COVERAGE_INCOMPLETE")
        if self.harness.vision_schema_version != VISION_RESULT_SCHEMA:
            return _VisualResolution("review_required", "VISION_SCHEMA_INVALID")
        if not self.harness.visual_available:
            return _VisualResolution("review_required", "VISION_REQUIRED_NOT_AVAILABLE")
        return _VisualResolution(
            "accepted",
            "VISUAL_V2_ACCEPTED",
            payload={
                "schema_version": "ASSISTANT_VISUAL_EVIDENCE_V2",
                "coverage": self.harness.visual_coverage,
            },
        )

    def validated_coverage(self, resolution):
        return resolution.result_payload["coverage"]

    def assistant_evidence(self, _resolution, **_kwargs):
        evidence = []
        for result in self.harness.visual_results:
            for key, kind in (("observations", "observation"), ("visible_text", "visible_text")):
                for item in result.get(key) or []:
                    if isinstance(item, dict) and str(item.get("text") or "").strip():
                        evidence.append({
                            "kind": kind,
                            "source_ref": "V01",
                            "page_number": 1,
                            "text": item["text"],
                        })
        if not evidence:
            return [], [{
                "tool": "get_visual_v2",
                "data": {"evidence": []},
                "source_keys": [],
            }]
        source = AgentSource(
            source_type="visual",
            source_id=71,
            title="visual",
            route="/documents/71?page=1",
            snippet=evidence[0]["text"],
        )
        return [source], [{
            "tool": "get_visual_v2",
            "data": {"evidence": evidence},
            "source_keys": [(source.source_type, source.source_id, source.route)],
        }]


class _FakeIntelligenceService:
    def __init__(self, _db):
        self.harness = _ACTIVE_HARNESS

    def accepted_baseline(self, **_kwargs):
        return self.harness.artifact


class _FakeMaterialService:
    def __init__(self, _db):
        self.harness = _ACTIVE_HARNESS

    def attach_document(self, **_kwargs):
        self.harness.events.append("material:attach")

    def bind_collected_sources(self, **_kwargs):
        self.harness.events.append("material:bind")

    @staticmethod
    def artifact_payload(_artifact):
        return {"summary": "synthetic"}


class _FakeRunService:
    def __init__(self, _db):
        self.harness = _ACTIVE_HARNESS

    @staticmethod
    def _hash_json(_value):
        return "a" * 64

    def finish(self, *, run, response):
        self.harness.events.append(f"run:finish:{response.status}")
        run.status = (
            "completed"
            if response.status in {"accepted_local", "accepted_advanced"}
            else "review_required"
        )
        run.current_stage = None


class _DispatcherHarness:
    def __init__(
        self,
        *,
        visual: bool = True,
        initial_visual: bool = True,
        has_document: bool = True,
        vision_status: str | None = None,
        vision_schema_version: str | None = VISION_RESULT_SCHEMA,
        visual_results: list[dict] | None = None,
        response_status: str = "accepted_local",
        response_statuses: list[str] | None = None,
        cancelled: bool = False,
        terminal_resolution: bool = False,
        question: str | None = None,
        visual_coverage: dict | None = None,
    ) -> None:
        self.events: list[str] = []
        self.service_configurations: list[dict] = []
        self.response_statuses = list(response_statuses or [response_status])
        self.response_index = 0
        self.visual_planned = visual
        self.visual_available = initial_visual
        self.visual_coverage = visual_coverage or {
            "selected_source_count": 1,
            "covered_source_count": 1,
            "omitted_source_count": 0,
            "required_page": None,
            "required_page_covered": False,
            "complete": True,
            "limitation_code": None,
        }
        self.visual_results = (
            visual_results
            if visual_results is not None
            else [
                {
                    "observations": [
                        {
                            "source_ref": "S1",
                            "text": "Na stronie widoczny jest przekrój warstw.",
                        }
                    ],
                    "possible_interpretations": [],
                    "uncertainties": [],
                    "visible_text": [],
                }
            ]
        )
        self.response_status = response_status
        self.vision_status = vision_status or (
            "complete" if initial_visual else "not_evaluated"
        )
        self.vision_schema_version = vision_schema_version
        document_id = 71 if has_document else None
        request = UnifiedAssistantRequest(
            question=(
                question
                or ("Co widać na obrazie?" if visual else "Podsumuj dokument.")
            ),
            document_id=document_id,
            conversation=[],
        )
        self.run = SimpleNamespace(
            id="run-visual-1",
            request_payload=request.model_dump(mode="json"),
            plan={"intent": "document_reasoning"},
            current_stage=None,
            status="cancelled" if cancelled else "running",
            cancel_requested_at=SimpleNamespace() if cancelled else None,
            created_by_user_id=41,
            complexity="visual" if visual else "standard",
            target_scope={},
            started_at=None,
            heartbeat_at=None,
        )
        self.document = (
            Document(
                id=71,
                filename="synthetic.pdf",
                original_filename="synthetic.pdf",
                content_type="application/pdf",
                file_size=100,
                checksum_sha256="b" * 64,
                processing_status="processed",
                vision_status=(
                    self.vision_status
                ),
                vision_schema_version=self.vision_schema_version,
            )
            if has_document
            else None
        )
        self.artifact = (
            SimpleNamespace(
                id="artifact-1",
                preparation_job_id="prep-1",
                payload_sha256="c" * 64,
                analyzer_generation="synthetic",
            )
            if has_document
            else None
        )
        self.resolution = (
            SimpleNamespace(state="NOT_FOUND", document_id=None)
            if terminal_resolution
            else None
        )
        self.db = _FakeDb(self)
        self.stages = _FakeStages(self, visual)

    def next_response_status(self) -> str:
        index = min(self.response_index, len(self.response_statuses) - 1)
        self.response_index += 1
        return self.response_statuses[index]

    def response(self, status):
        return UnifiedAssistantResponse(
            request_id="00000000-0000-0000-0000-000000000071",
            answer="" if status == "review_required" else "synthetic answer",
            status=status,
            progress="complete",
            target_scope="TARGET_01",
            claims=(
                [{
                    "claim_id": "C01",
                    "claim_class": "FACT",
                    "text": "Zwalidowany wynik rozszerzony.",
                    "source_refs": ["S1"],
                }]
                if status == "accepted_advanced"
                else []
            ),
            sources=[],
            used_tools=[],
            model="synthetic" if status != "review_required" else None,
            current_stage="complete",
            can_cancel=False,
            error_message=("safe review" if status == "review_required" else None),
        )

    def execute(self):
        global _ACTIVE_HARNESS
        _ACTIVE_HARNESS = self
        with (
            patch.object(dispatcher, "SessionLocal", return_value=self.db),
            patch.object(
                dispatcher,
                "AssistantRunStageService",
                side_effect=lambda _db: self.stages,
            ),
            patch.object(dispatcher, "UnifiedAssistantService", _FakeUnifiedService),
            patch.object(
                dispatcher,
                "DocumentIntelligenceService",
                _FakeIntelligenceService,
            ),
            patch.object(
                dispatcher,
                "AssistantRunMaterialService",
                _FakeMaterialService,
            ),
            patch.object(dispatcher, "AssistantRunService", _FakeRunService),
            patch.object(dispatcher, "VisualV2Service", _FakeVisualService),
        ):
            asyncio.run(dispatcher._execute_run(self.run.id))
        _ACTIVE_HARNESS = None


class AssistantVisualBranchTests(unittest.TestCase):
    def test_t01_complete_visual_is_reused_before_local(self):
        harness = _DispatcherHarness()
        harness.execute()
        waiting = harness.events.index("stage:complete:waiting_for_vision")
        analyzing = harness.events.index("stage:start:analyzing_vision")
        analyzed = harness.events.index("stage:complete:analyzing_vision")
        local = harness.events.index("stage:start:analyzing_local")
        self.assertLess(waiting, analyzing)
        self.assertLess(analyzing, analyzed)
        self.assertLess(analyzed, local)
        self.assertEqual(
            harness.stages.manifests["analyzing_vision"]["mode"],
            "visual_v2",
        )
        visible_text = _DispatcherHarness(
            visual_results=[
                {
                    "observations": [],
                    "possible_interpretations": [],
                    "uncertainties": [],
                    "visible_text": [
                        {"source_ref": "S1", "text": "1,8 m"}
                    ],
                }
            ]
        )
        visible_text.execute()
        self.assertIn("reasoner:ask:accepted_local", visible_text.events)

    def test_t02_local_reasoning_precedes_advanced(self):
        harness = _DispatcherHarness(response_status="advanced_queued")
        harness.execute()
        visual = harness.events.index("stage:complete:analyzing_vision")
        local = harness.events.index("reasoner:ask:advanced_queued")
        advanced = harness.events.index("stage:wait:waiting_for_advanced")
        self.assertLess(visual, local)
        self.assertLess(local, advanced)

    def test_t03_missing_visual_is_review_required(self):
        harness = _DispatcherHarness(initial_visual=False)
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISION_REQUIRED_NOT_AVAILABLE",
            harness.events,
        )
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))

    def test_t04_missing_visual_creates_no_external_work(self):
        harness = _DispatcherHarness(initial_visual=False)
        with patch.object(dispatcher.asyncio, "to_thread") as external_thread:
            harness.execute()
        external_thread.assert_not_called()
        self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_t05_partial_visual_is_review_required(self):
        harness = _DispatcherHarness(vision_status="partial")
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISION_REQUIRED_COVERAGE_INCOMPLETE",
            harness.events,
        )

    def test_t06_partial_visual_never_reaches_local_or_advanced(self):
        harness = _DispatcherHarness(
            vision_status="partial",
            response_status="advanced_queued",
        )
        harness.execute()
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))
        self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_t07_missing_or_wrong_visual_schema_fails_closed(self):
        for schema in (None, "vision_result_v0"):
            with self.subTest(schema=schema):
                harness = _DispatcherHarness(vision_schema_version=schema)
                harness.execute()
                self.assertEqual(harness.run.status, "review_required")
                self.assertIn(
                    "stage:fail:waiting_for_vision:VISION_SCHEMA_INVALID",
                    harness.events,
                )
                self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))
                self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_t08_visual_without_document_fails_closed(self):
        harness = _DispatcherHarness(has_document=False)
        with patch.object(dispatcher.asyncio, "to_thread") as external_thread:
            harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISION_DOCUMENT_REQUIRED",
            harness.events,
        )
        external_thread.assert_not_called()
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))

    def test_t09_cancelled_run_has_no_answer_or_evidence_binding(self):
        harness = _DispatcherHarness(cancelled=True)
        harness.execute()
        self.assertEqual(harness.run.status, "cancelled")
        self.assertNotIn("material:bind", harness.events)
        self.assertFalse(
            any(event.startswith("run:finish:") for event in harness.events)
        )
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))

    def test_t10_non_visual_path_is_unchanged(self):
        harness = _DispatcherHarness(visual=False, initial_visual=False)
        with patch.object(dispatcher.asyncio, "to_thread") as external_thread:
            harness.execute()
        external_thread.assert_not_called()
        self.assertIn("reasoner:ask:accepted_local", harness.events)

    def test_t11_terminal_resolution_skips_visual_stages(self):
        harness = _DispatcherHarness(terminal_resolution=True)
        harness.execute()
        self.assertEqual(harness.stages.status["waiting_for_vision"], "skipped")
        self.assertEqual(harness.stages.status["analyzing_vision"], "skipped")
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))

    def test_t12_dispatcher_has_no_external_vision_reference(self):
        source = Path(dispatcher.__file__).read_text(encoding="utf-8")
        self.assertNotIn("process_explicit_vision_document", source)
        self.assertNotIn("VisionSupervisor", source)

    def test_t13_vision_processing_service_matches_main_blob(self):
        service_path = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "services"
            / "vision_processing_service.py"
        )
        content = service_path.read_bytes().replace(b"\r\n", b"\n")
        git_blob = hashlib.sha1(
            f"blob {len(content)}\0".encode("ascii") + content,
            usedforsecurity=False,
        ).hexdigest()
        self.assertLess(
            0,
            len(content),
        )
        self.assertEqual(git_blob, "5f0d14de81c16dd314efec4c7cbe9fe4c9d5bd59")

    def test_t14_ingestion_still_cannot_invoke_explicit_vision(self):
        source = Path(preparation_dispatcher.__file__).read_text(encoding="utf-8")
        self.assertNotIn("process_explicit_vision_document", source)
        self.assertIn("VisualV2Service", source)

    def test_t15_complete_but_empty_visual_fails_closed(self):
        harness = _DispatcherHarness(
            visual_results=[
                {
                    "observations": [],
                    "possible_interpretations": [],
                    "uncertainties": [],
                    "visible_text": [],
                }
            ]
        )
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISION_REQUIRED_NOT_AVAILABLE",
            harness.events,
        )
        self.assertEqual(harness.events.count("material:bind"), 1)
        self.assertNotIn("stage:complete:analyzing_vision", harness.events)
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))
        self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_t16_interpretation_only_visual_fails_closed(self):
        harness = _DispatcherHarness(
            visual_results=[
                {
                    "observations": [],
                    "possible_interpretations": [
                        {
                            "source_ref": "S1",
                            "text": "Możliwe uszkodzenie konstrukcyjne.",
                        }
                    ],
                    "uncertainties": [],
                    "visible_text": [],
                }
            ]
        )
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISION_REQUIRED_NOT_AVAILABLE",
            harness.events,
        )
        self.assertEqual(harness.events.count("material:bind"), 1)
        self.assertNotIn("stage:complete:analyzing_vision", harness.events)
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))
        self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_t17_accepted_advanced_returns_to_one_final_local_synthesis(self):
        harness = _DispatcherHarness(
            response_statuses=[
                "advanced_queued",
                "accepted_advanced",
                "accepted_local",
            ]
        )
        harness.execute()
        self.assertEqual(harness.run.status, "waiting")
        harness.execute()

        external = harness.events.index("reasoner:ask:accepted_advanced")
        synthesis = harness.events.index("stage:start:synthesizing")
        final_local = harness.events.index("reasoner:ask:accepted_local")
        self.assertLess(external, synthesis)
        self.assertLess(synthesis, final_local)
        self.assertEqual(harness.run.status, "completed")
        self.assertNotIn("run:finish:accepted_advanced", harness.events)
        self.assertEqual(harness.events.count("run:finish:accepted_local"), 1)
        final_configuration = next(
            value
            for value in reversed(harness.service_configurations)
            if "validated_advanced_analysis" in value["supplemental_tools"]
        )
        self.assertFalse(final_configuration["allow_advanced_escalation"])
        self.assertFalse(final_configuration["allow_existing_advanced_result"])

    def test_t18_final_local_synthesis_cannot_reenter_advanced(self):
        harness = _DispatcherHarness(
            response_statuses=[
                "advanced_queued",
                "accepted_advanced",
                "review_required",
            ]
        )
        harness.execute()
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertEqual(harness.events.count("stage:wait:waiting_for_advanced"), 1)
        self.assertEqual(harness.events.count("run:finish:review_required"), 1)

    def test_v22_general_assistant_partial_visual_fails_closed(self):
        harness = _DispatcherHarness(
            visual_coverage={
                "selected_source_count": 4,
                "covered_source_count": 4,
                "omitted_source_count": 2,
                "required_page": None,
                "required_page_covered": False,
                "complete": False,
                "limitation_code": "VISUAL_V2_SOURCE_LIMIT_PARTIAL",
            }
        )
        harness.execute()

        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISION_REQUIRED_COVERAGE_INCOMPLETE",
            harness.events,
        )
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))
        self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_v23_explicit_page_covered_may_continue(self):
        harness = _DispatcherHarness(
            question="Co widać na stronie 5?",
            visual_coverage={
                "selected_source_count": 4,
                "covered_source_count": 1,
                "omitted_source_count": 2,
                "required_page": 5,
                "required_page_covered": True,
                "complete": False,
                "limitation_code": "VISUAL_V2_SOURCE_LIMIT_PARTIAL",
            },
        )
        harness.execute()

        self.assertEqual(harness.run.status, "completed")
        self.assertIn("reasoner:ask:accepted_local", harness.events)
        self.assertNotIn(
            "stage:fail:waiting_for_vision:VISION_REQUIRED_COVERAGE_INCOMPLETE",
            harness.events,
        )

    def test_v24_explicit_page_not_covered_fails_closed(self):
        harness = _DispatcherHarness(
            question="Co widać na stronie 5?",
            visual_coverage={
                "selected_source_count": 4,
                "covered_source_count": 1,
                "omitted_source_count": 2,
                "required_page": 5,
                "required_page_covered": False,
                "complete": False,
                "limitation_code": "VISUAL_V2_SOURCE_LIMIT_PARTIAL",
            },
        )
        harness.execute()

        self.assertEqual(harness.run.status, "review_required")
        self.assertIn(
            "stage:fail:waiting_for_vision:VISUAL_V2_REQUIRED_PAGE_NOT_COVERED",
            harness.events,
        )
        self.assertFalse(any(item.startswith("reasoner:ask:") for item in harness.events))


if __name__ == "__main__":
    unittest.main()
