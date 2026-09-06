from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.models.assistant_pipeline import AssistantRun
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.unified_assistant import UnifiedAssistantRequest, UnifiedAssistantResponse
from app.schemas.vision import VISION_RESULT_SCHEMA
from app.services import assistant_run_dispatcher as dispatcher
from app.services import document_preparation_dispatcher as preparation_dispatcher
from app.services.assistant_run_planner import AssistantRunPlanner
from app.services.document_preparation_service import PreparationClaim
from app.services.vision_processing_service import VisionProcessingService


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

    def _resolve_required_document(self, _request):
        return self.harness.resolution

    def _document_resolution_response(self, _request, _resolution):
        return self.harness.response("review_required")

    def _resolve_required_kb(self, _request):
        return None

    def _collect(self, _request, **_kwargs):
        available = self.harness.visual_available
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
        payloads = []
        tools = ["get_document_summary"]
        if available:
            payloads.append(
                {
                    "tool": "get_visual_analysis",
                    "data": {"visual_results": [{"observations": []}]},
                    "source_keys": [("document", 71, "/documents/71")],
                }
            )
            tools.append("get_visual_analysis")
        return SimpleNamespace(
            sources=[source],
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
        self.harness.events.append("local:ask")
        return self.harness.response(self.harness.response_status)


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
        initial_visual: bool = False,
        has_document: bool = True,
        vision_outcome: str = "complete",
        response_status: str = "accepted_local",
        cancel_after_vision: bool = False,
        terminal_resolution: bool = False,
    ) -> None:
        self.events: list[str] = []
        self.visual_planned = visual
        self.visual_available = initial_visual
        self.vision_outcome = vision_outcome
        self.response_status = response_status
        self.cancel_after_vision = cancel_after_vision
        document_id = 71 if has_document else None
        request = UnifiedAssistantRequest(
            question=("Co widać na obrazie?" if visual else "Podsumuj dokument."),
            document_id=document_id,
            conversation=[],
        )
        self.run = SimpleNamespace(
            id="run-visual-1",
            request_payload=request.model_dump(mode="json"),
            plan={"intent": "document_reasoning"},
            current_stage=None,
            status="running",
            cancel_requested_at=None,
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
                vision_status=("complete" if initial_visual else "not_evaluated"),
                vision_schema_version=(VISION_RESULT_SCHEMA if initial_visual else None),
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
        self.vision_calls = 0

    def response(self, status):
        return UnifiedAssistantResponse(
            request_id="00000000-0000-0000-0000-000000000071",
            answer="" if status == "review_required" else "synthetic answer",
            status=status,
            progress="complete",
            target_scope="TARGET_01",
            claims=[],
            sources=[],
            used_tools=[],
            model="synthetic" if status != "review_required" else None,
            current_stage="complete",
            can_cancel=False,
            error_message=("safe review" if status == "review_required" else None),
        )

    def run_vision(self, document_id):
        self.vision_calls += 1
        self.events.append(f"vision:explicit:{document_id}")
        if self.cancel_after_vision:
            self.run.status = "cancelled"
            self.run.cancel_requested_at = SimpleNamespace()
            return
        if self.vision_outcome == "complete":
            self.document.vision_status = "complete"
            self.document.vision_schema_version = VISION_RESULT_SCHEMA
            self.visual_available = True
        else:
            self.document.vision_status = self.vision_outcome
            self.document.vision_error_code = "WORKER_UNAVAILABLE"

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
            patch.object(
                dispatcher,
                "process_explicit_vision_document",
                side_effect=self.run_vision,
            ),
        ):
            asyncio.run(dispatcher._execute_run(self.run.id))
        _ACTIVE_HARNESS = None


class _VisionDocuments:
    def __init__(self, document, pages):
        self.document = document
        self.pages = pages

    def get(self, document_id):
        return self.document if document_id == self.document.id else None

    def get_pages(self, _document_id):
        return self.pages

    def commit(self):
        return None


class _VisionAssets:
    def __init__(self, assets=()):
        self.assets = list(assets)

    def get_for_document(self, _document_id):
        return self.assets


class _CaptureSupervisor:
    def __init__(self):
        self.payloads: list[dict] = []

    def create_job(self, payload):
        self.payloads.append(payload)
        return {
            "job_id": "00000000-0000-0000-0000-000000000099",
            "state": "QUEUED",
            "attempt_count": 0,
        }


class AssistantVisualBranchTests(unittest.TestCase):
    def test_t01_visual_stages_execute_before_local(self):
        harness = _DispatcherHarness()
        harness.execute()
        self.assertLess(
            harness.events.index("stage:complete:analyzing_vision"),
            harness.events.index("stage:start:analyzing_local"),
        )

    def test_t02_existing_visual_is_reused_without_vision_call(self):
        harness = _DispatcherHarness(initial_visual=True)
        harness.execute()
        self.assertEqual(harness.vision_calls, 0)
        self.assertEqual(harness.stages.manifests["analyzing_vision"]["mode"], "reused")

    def test_t03_missing_visual_invokes_explicit_path_once(self):
        harness = _DispatcherHarness()
        harness.execute()
        self.assertEqual(harness.vision_calls, 1)

    def test_t04_text_rich_rendered_pdf_is_not_suppressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (800, 600), "white").save(root / "p1.png")
            document = Document(
                id=4,
                filename="report.pdf",
                original_filename="report.pdf",
                content_type="application/pdf",
                file_size=100,
                vision_auto_eligible=False,
                vision_status="not_evaluated",
                vision_attempt_count=0,
            )
            page = DocumentPage(
                id=41,
                document_id=4,
                page_number=1,
                extracted_text="Pełna treść tekstowa. " * 20,
                render_path="p1.png",
            )
            supervisor = _CaptureSupervisor()
            service = VisionProcessingService(object(), supervisor=supervisor)
            service.data_root = root.resolve()
            service.spool_root = (root / "vision-spool").resolve()
            service.documents = _VisionDocuments(document, [page])
            service.assets = _VisionAssets()
            result = service.advance(document.id, explicit=True)
            self.assertEqual(result.status, "queued")
            self.assertEqual(document.vision_classification, "vision_required")
            self.assertEqual(len(supervisor.payloads), 1)

    def test_t05_explicit_fallback_is_deterministic_and_bounded_to_four(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pages = []
            for index in range(1, 7):
                Image.new("RGB", (800, 600), "white").save(root / f"p{index}.png")
                pages.append(
                    DocumentPage(
                        id=50 + index,
                        document_id=5,
                        page_number=index,
                        extracted_text="Pełna treść tekstowa. " * 20,
                        render_path=f"p{index}.png",
                    )
                )
            document = Document(
                id=5,
                filename="report.pdf",
                original_filename="report.pdf",
                content_type="application/pdf",
                file_size=100,
                vision_auto_eligible=False,
                vision_status="not_evaluated",
                vision_attempt_count=0,
            )
            supervisor = _CaptureSupervisor()
            service = VisionProcessingService(object(), supervisor=supervisor)
            service.data_root = root.resolve()
            service.spool_root = (root / "vision-spool").resolve()
            service.documents = _VisionDocuments(document, list(reversed(pages)))
            service.assets = _VisionAssets()
            service.advance(document.id, explicit=True)
            sources = supervisor.payloads[0]["sources"]
            self.assertEqual(len(sources), 4)
            self.assertEqual([item["page_number"] for item in sources], [1, 2, 3, 4])

    def test_t06_success_is_recollected_before_local_reasoning(self):
        harness = _DispatcherHarness()
        harness.execute()
        local_index = harness.events.index("local:ask")
        self.assertIn("collect:visual", harness.events[:local_index])
        self.assertEqual(
            harness.stages.manifests["analyzing_vision"]["visual_source_count"],
            1,
        )

    def test_t07_advanced_is_after_visual_and_local(self):
        harness = _DispatcherHarness(response_status="advanced_queued")
        harness.execute()
        visual = harness.events.index("stage:complete:analyzing_vision")
        local = harness.events.index("local:ask")
        advanced = harness.events.index("stage:wait:waiting_for_advanced")
        self.assertLess(visual, local)
        self.assertLess(local, advanced)

    def test_t08_failed_visual_reviews_without_local_or_advanced(self):
        harness = _DispatcherHarness(vision_outcome="failed_retryable")
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertNotIn("local:ask", harness.events)
        self.assertNotIn("stage:wait:waiting_for_advanced", harness.events)

    def test_t09_visual_without_document_fails_closed(self):
        harness = _DispatcherHarness(has_document=False)
        harness.execute()
        self.assertEqual(harness.run.status, "review_required")
        self.assertEqual(harness.vision_calls, 0)
        self.assertNotIn("local:ask", harness.events)

    def test_t10_cancelled_run_does_not_bind_late_visual(self):
        harness = _DispatcherHarness(cancel_after_vision=True)
        harness.execute()
        self.assertEqual(harness.run.status, "cancelled")
        self.assertNotIn("stage:complete:analyzing_vision", harness.events)
        self.assertNotIn("local:ask", harness.events)

    def test_t11_non_visual_path_does_not_call_vision(self):
        harness = _DispatcherHarness(visual=False)
        harness.execute()
        self.assertEqual(harness.vision_calls, 0)
        self.assertIn("local:ask", harness.events)

    def test_t12_terminal_resolution_skips_visual_stages(self):
        harness = _DispatcherHarness(terminal_resolution=True)
        harness.execute()
        self.assertEqual(harness.stages.status["waiting_for_vision"], "skipped")
        self.assertEqual(harness.stages.status["analyzing_vision"], "skipped")
        self.assertEqual(harness.vision_calls, 0)
        self.assertNotIn("local:ask", harness.events)

    def test_t13_non_explicit_text_sufficient_behavior_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (800, 600), "white").save(root / "p1.png")
            document = Document(
                id=13,
                filename="report.pdf",
                original_filename="report.pdf",
                content_type="application/pdf",
                file_size=100,
                vision_auto_eligible=True,
                vision_status="not_evaluated",
                vision_attempt_count=0,
            )
            page = DocumentPage(
                id=131,
                document_id=13,
                page_number=1,
                extracted_text="Pełna treść tekstowa. " * 20,
                render_path="p1.png",
            )
            supervisor = _CaptureSupervisor()
            service = VisionProcessingService(object(), supervisor=supervisor)
            service.data_root = root.resolve()
            service.spool_root = (root / "vision-spool").resolve()
            service.documents = _VisionDocuments(document, [page])
            service.assets = _VisionAssets()
            result = service.advance(document.id, explicit=False)
            self.assertEqual(result.status, "not_needed")
            self.assertEqual(supervisor.payloads, [])

    def test_t14_ingestion_still_cannot_invoke_explicit_vision(self):
        claim = PreparationClaim(job_id="prep-14", lease_owner="owner-14")
        job = SimpleNamespace(
            id=claim.job_id,
            status="running",
            lease_owner=claim.lease_owner,
            stage="vision_processing",
            trigger="ingestion",
            document_id=14,
        )

        class Db:
            def query(self, _model):
                return _FakeQuery(job)

            def commit(self):
                return None

            def close(self):
                return None

        class Preparation:
            def __init__(self, _db):
                return None

            def contain_ingestion_external_vision(self, _claim):
                return True

        with (
            patch.object(preparation_dispatcher, "SessionLocal", return_value=Db()),
            patch.object(
                preparation_dispatcher,
                "DocumentPreparationService",
                Preparation,
            ),
            patch.object(
                preparation_dispatcher,
                "process_explicit_vision_document",
            ) as explicit,
        ):
            result = asyncio.run(
                preparation_dispatcher.process_preparation_vision(claim)
            )
        self.assertFalse(result)
        explicit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
