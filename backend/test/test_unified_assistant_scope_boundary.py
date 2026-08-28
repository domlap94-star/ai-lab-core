from __future__ import annotations

import json

from app.schemas.agent import AgentSource
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.unified_assistant_service import _Collected, UnifiedAssistantService
from test.local_llm_qualification_cases import cases


def _a02_collected() -> tuple[UnifiedAssistantRequest, _Collected]:
    case = next(item for item in cases() if item.case_id == "A02-wrongclient")
    source_ref, snippet = next(iter(case.evidence.items()))
    source = AgentSource(
        source_type="document",
        source_id=2,
        title=source_ref,
        route=None,
        snippet=snippet,
    )
    return UnifiedAssistantRequest(question=case.question), _Collected(
        sources=[source],
        tool_payloads=[{
            "tool": "document_search",
            "data": {"excerpt": snippet},
            "source_keys": [("document", 2, None)],
        }],
        tools=["document_search"],
        client_id=None,
        visual_available=False,
    )


def _payload(text: str) -> dict:
    return {
        "answer": text,
        "claims": [{
            "class": "FACT",
            "text": text,
            "source_refs": ["S01"],
            "tool_refs": [],
        }],
        "used_sources": ["S01"],
        "tool_plan": ["document_search"],
        "estimate": None,
    }


def test_a02_foreign_segment_is_removed_before_prompt_and_tool_manifest() -> None:
    request, collected = _a02_collected()
    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    prompt, _, _ = UnifiedAssistantService._prompt(request, boundary.collected)

    assert "pęknięta płytka" in prompt
    assert "awaria dachu" not in prompt
    assert "awaria dachu" not in json.dumps(
        boundary.collected.tool_payloads, ensure_ascii=False
    )
    assert boundary.blocked_segments


def test_a02_blocked_segment_cannot_reenter_terminal_output() -> None:
    request, collected = _a02_collected()
    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    _, source_map, _ = UnifiedAssistantService._prompt(request, boundary.collected)

    assert UnifiedAssistantService._validate(
        _payload("Klient A ma pękniętą płytkę."),
        source_map,
        False,
        blocked_scope_segments=boundary.blocked_segments,
    ) is None
    assert UnifiedAssistantService._validate(
        _payload("W obcej części odnotowano awarię dachu."),
        source_map,
        False,
        blocked_scope_segments=boundary.blocked_segments,
    ) == "target_scope_violation"


def test_a02_advanced_package_contains_only_sanitized_evidence() -> None:
    request, collected = _a02_collected()
    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    service = UnifiedAssistantService.__new__(UnifiedAssistantService)
    analysis_request, _ = service._advanced_request(
        request, boundary.collected, 1, "00000000-0000-0000-0000-000000000002"
    )

    serialized = json.dumps(
        analysis_request.model_dump(mode="json"), ensure_ascii=False
    )
    assert "pęknięta płytka" in serialized
    assert "awaria dachu" not in serialized


def test_explicit_authorized_comparison_preserves_both_client_segments() -> None:
    source = AgentSource(
        source_type="document",
        source_id=3,
        title="comparison",
        route=None,
        snippet="Klient A: rysa ściany. Klient B: zawilgocenie stropu.",
    )
    collected = _Collected([source], [], ["document_search"], None, False)
    request = UnifiedAssistantRequest(
        question="Porównaj klienta A i klienta B."
    )

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)

    assert boundary.blocked_segments == ()
    assert "rysa ściany" in boundary.collected.sources[0].snippet
    assert "zawilgocenie stropu" in boundary.collected.sources[0].snippet


def test_single_client_scope_blocks_explicit_other_record_generically() -> None:
    source = AgentSource(
        source_type="document",
        source_id=4,
        title="mixed",
        route=None,
        snippet=(
            "Klient Północ: osiadanie posadzki. "
            "Inna notatka klienta Południe: przeciek instalacji."
        ),
    )
    collected = _Collected([source], [], ["document_search"], 41, False)
    request = UnifiedAssistantRequest(question="Co wiadomo o kliencie Północ?")

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)

    assert "osiadanie posadzki" in boundary.collected.sources[0].snippet
    assert "przeciek instalacji" not in boundary.collected.sources[0].snippet
    assert boundary.blocked_segments
