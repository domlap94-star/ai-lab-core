from __future__ import annotations

import inspect
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.agent import AgentSource
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.unified_assistant_service import (
    QUERY_MODE_SYSTEM_META,
    UnifiedAssistantService,
)


SNAPSHOT = os.environ.get("R02_SNAPSHOT", "").strip().lower()
if SNAPSHOT not in {"main", "rescue"}:
    raise RuntimeError("R02_SNAPSHOT must be exactly 'main' or 'rescue'")


def _service(**kwargs) -> UnifiedAssistantService:
    # Only the external document/vector boundary is replaced. Every tested
    # routing, collection, prompt and validation method remains the real
    # snapshot implementation.
    with patch(
        "app.services.unified_assistant_service.UnifiedDocumentContentService",
        return_value=MagicMock(),
    ):
        return UnifiedAssistantService(
            MagicMock(),
            llm_client=MagicMock(),
            **kwargs,
        )


def _request(question: str, **kwargs) -> UnifiedAssistantRequest:
    return UnifiedAssistantRequest(question=question, **kwargs)


def _source(kind: str, source_id: int) -> AgentSource:
    return AgentSource(
        source_type=kind,
        source_id=source_id,
        title=f"synthetic-{kind}-{source_id}",
        route=f"/synthetic/{kind}/{source_id}",
        snippet=f"synthetic evidence {source_id}",
    )


def test_rep_001_selected_document_capability_wording_is_system_meta() -> None:
    actual = UnifiedAssistantService._query_mode(
        _request("Czy możesz przeanalizować ten dokument?", document_id=1)
    )
    print(f"REP-001 snapshot={SNAPSHOT} actual={actual}")
    assert actual == QUERY_MODE_SYSTEM_META


def test_rep_002_operational_term_suppresses_technical_kb_retrieval() -> None:
    technical = _request("Oceń nośność fundamentu na gruncie.")
    mixed = _request("Oceń nośność fundamentu na gruncie i podaj adres klienta.")
    technical_actual = UnifiedAssistantService._should_retrieve_kb(technical)
    mixed_actual = UnifiedAssistantService._should_retrieve_kb(mixed)
    print(
        "REP-002 "
        f"snapshot={SNAPSHOT} technical={technical_actual} mixed={mixed_actual}"
    )
    assert technical_actual is True
    assert mixed_actual is False


@pytest.mark.parametrize("steel_grade", ["S235", "S355"])
def test_rep_003_ordinary_steel_grade_is_rejected_as_internal_handle(
    steel_grade: str,
) -> None:
    source = _source("document", 1)
    payload = {
        "answer": f"Stal {steel_grade} jest wskazana w materiale.",
        "claims": [{
            "class": "FACT",
            "text": f"Materiał wskazuje stal {steel_grade}.",
            "source_refs": ["S01"],
            "tool_refs": [],
        }],
        "used_sources": ["S01"],
        "tool_plan": [],
        "estimate": None,
    }
    actual = UnifiedAssistantService._validate(payload, {"S01": source}, False)
    print(f"REP-003 snapshot={SNAPSHOT} grade={steel_grade} actual={actual}")
    assert actual == "user_output_internal_leak"


def test_rep_004_kb_exception_is_indistinguishable_from_no_match() -> None:
    service = _service()
    request = _request("Oceń nośność fundamentu.")
    registry = MagicMock()
    no_match_retrieval = MagicMock()
    no_match_retrieval.search.return_value = []
    with (
        patch(
            "app.services.unified_assistant_service.AgentToolRegistry",
            return_value=registry,
        ),
        patch.object(service, "_route", return_value=[]),
        patch(
            "app.services.unified_assistant_service.KnowledgeBaseRetrievalService",
            return_value=no_match_retrieval,
        ),
    ):
        no_match = service._collect(request)
    failed_retrieval = MagicMock()
    failed_retrieval.search.side_effect = RuntimeError("synthetic retrieval failure")
    with (
        patch(
            "app.services.unified_assistant_service.AgentToolRegistry",
            return_value=registry,
        ),
        patch.object(service, "_route", return_value=[]),
        patch(
            "app.services.unified_assistant_service.KnowledgeBaseRetrievalService",
            return_value=failed_retrieval,
        ),
    ):
        failed = service._collect(request)
    actual = (
        failed.sources,
        failed.tool_payloads,
        failed.tools,
        failed.visual_available,
    )
    expected = (
        no_match.sources,
        no_match.tool_payloads,
        no_match.tools,
        no_match.visual_available,
    )
    print(f"REP-004 snapshot={SNAPSHOT} indistinguishable={actual == expected}")
    assert actual == expected


def test_kb_plus_supplemental_visual_actual_collect_and_prompt_boundary() -> None:
    constructor = inspect.signature(UnifiedAssistantService.__init__)
    if "supplemental_sources" not in constructor.parameters:
        print(
            "R02-KB-VISUAL snapshot=main supplemental_sources=NOT_PRESENT "
            "collect_prompt=NOT_APPLICABLE"
        )
        assert SNAPSHOT == "main"
        return

    case_sources = [_source("document", index) for index in range(1, 6)]
    visual_sources = [_source("visual_v2", 100 + index) for index in range(1, 5)]
    supplemental_payload = {
        "tool": "get_visual_v2",
        "data": {"synthetic": True},
        "source_keys": [
            (source.source_type, source.source_id, source.route)
            for source in visual_sources
        ],
    }
    service = _service(
        supplemental_sources=visual_sources,
        supplemental_tool_payloads=[supplemental_payload],
    )
    request = _request("Oceń fundament z użyciem technicznej bazy wiedzy.")
    registry = MagicMock()
    registry.execute.return_value = SimpleNamespace(
        data={"synthetic": True},
        sources=case_sources,
        coverage={"records": 5},
        limitations=[],
    )
    kb_rows = [{
        "knowledge_base_item_id": 200 + index,
        "title": f"synthetic-kb-{index}",
        "page": index,
        "excerpt": f"synthetic technical knowledge {index}",
        "retrieval_method": "synthetic",
        "status": "current",
    } for index in range(1, 4)]
    retrieval = MagicMock()
    retrieval.search.return_value = kb_rows
    with (
        patch(
            "app.services.unified_assistant_service.AgentToolRegistry",
            return_value=registry,
        ),
        patch.object(service, "_route", return_value=[("synthetic_case", {})]),
        patch(
            "app.services.unified_assistant_service.KnowledgeBaseRetrievalService",
            return_value=retrieval,
        ),
    ):
        collected = service._collect(request)
    prompt, source_map, _tool_map = service._prompt(request, collected)
    counts = {
        kind: sum(source.source_type == kind for source in collected.sources)
        for kind in ("document", "knowledge_base", "visual_v2")
    }
    prompt_counts = {
        kind: sum(source.source_type == kind for source in source_map.values())
        for kind in ("document", "knowledge_base", "visual_v2")
    }
    print(
        "R02-KB-VISUAL "
        f"snapshot={SNAPSHOT} collected={counts} prompt={prompt_counts} "
        f"prompt_chars={len(prompt)}"
    )
    assert SNAPSHOT == "rescue"
    assert counts == {"document": 4, "knowledge_base": 0, "visual_v2": 4}
    assert prompt_counts == counts
