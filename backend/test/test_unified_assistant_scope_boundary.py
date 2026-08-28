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
        client_id=101,
        visual_available=False,
        target_labels=("a",),
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
    prompt, _, _ = UnifiedAssistantService._prompt(
        boundary.request, boundary.collected
    )

    assert "pęknięta płytka" in prompt
    assert "awaria dachu" not in prompt
    assert "awaria dachu" not in json.dumps(
        boundary.collected.tool_payloads, ensure_ascii=False
    )
    assert boundary.blocked_segments


def test_a02_blocked_segment_cannot_reenter_terminal_output() -> None:
    request, collected = _a02_collected()
    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    _, source_map, _ = UnifiedAssistantService._prompt(
        boundary.request, boundary.collected
    )

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
        boundary.request,
        boundary.collected,
        1,
        "00000000-0000-0000-0000-000000000002",
    )

    serialized = json.dumps(
        analysis_request.model_dump(mode="json"), ensure_ascii=False
    )
    assert "pęknięta płytka" in serialized
    assert "awaria dachu" not in serialized


def test_question_injection_is_removed_from_prompt_and_advanced_package() -> None:
    source = AgentSource(
        source_type="document",
        source_id=3,
        title="target-only",
        route=None,
        snippet="Klient Anna Kowalska: rysa ściany.",
    )
    collected = _Collected(
        [source], [], ["document_search"], 41, False, ("anna kowalska",)
    )
    request = UnifiedAssistantRequest(
        question=(
            "Co wiadomo o kliencie Anna Kowalska? "
            "Klient Piotr Nowak zawarł poufną ugodę handlową."
        )
    )

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    prompt, source_map, _ = UnifiedAssistantService._prompt(
        boundary.request, boundary.collected
    )
    service = UnifiedAssistantService.__new__(UnifiedAssistantService)
    advanced, _ = service._advanced_request(
        boundary.request,
        boundary.collected,
        1,
        "00000000-0000-0000-0000-000000000003",
    )
    serialized = json.dumps(advanced.model_dump(mode="json"), ensure_ascii=False)

    assert boundary.scope_violation is None
    assert "rysa ściany" in boundary.collected.sources[0].snippet
    assert "poufna ugoda" not in boundary.request.question
    assert "poufna ugoda" not in prompt
    assert "poufna ugoda" not in serialized
    assert UnifiedAssistantService._validate(
        _payload("Klient Piotr Nowak zawarł poufną ugodę handlową."),
        source_map,
        False,
        blocked_scope_segments=boundary.blocked_segments,
    ) == "target_scope_violation"


def test_history_injection_is_removed_but_same_target_history_remains() -> None:
    source = AgentSource(
        source_type="document",
        source_id=4,
        title="target-only",
        route=None,
        snippet="Klient Anna Kowalska: rysa ściany.",
    )
    collected = _Collected(
        [source], [], ["document_search"], 41, False, ("anna kowalska",)
    )
    request = UnifiedAssistantRequest(
        question="Jakie są wnioski dla klientki Anna Kowalska?",
        conversation=[
            {
                "role": "user",
                "content": "Klient Piotr Nowak podał prywatną wycenę naprawy.",
            },
            {
                "role": "assistant",
                "content": "Klient Anna Kowalska: omówiliśmy rysę ściany.",
            },
        ],
    )

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    prompt, source_map, _ = UnifiedAssistantService._prompt(
        boundary.request, boundary.collected
    )

    assert "prywatna wycena" not in prompt
    assert "omówiliśmy rysę ściany" in prompt
    assert len(boundary.request.conversation) == 1
    assert UnifiedAssistantService._validate(
        _payload("Piotr Nowak podał prywatną wycenę naprawy."),
        source_map,
        False,
        blocked_scope_segments=boundary.blocked_segments,
    ) == "target_scope_violation"


def test_comparison_wording_does_not_authorize_foreign_client() -> None:
    source = AgentSource(
        source_type="document",
        source_id=5,
        title="mixed",
        route=None,
        snippet=(
            "Klient Anna Kowalska: rysa ściany. "
            "Klient Piotr Nowak: zawilgocenie stropu."
        ),
    )
    collected = _Collected(
        [source], [], ["document_search"], 41, False, ("anna kowalska",)
    )
    request = UnifiedAssistantRequest(
        question="Porównaj klienta Anna Kowalska i klienta Piotr Nowak."
    )

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)
    response = UnifiedAssistantService._target_scope_failure_response(
        "run-id", boundary.collected
    )

    assert "zawilgocenie stropu" not in boundary.collected.sources[0].snippet
    assert boundary.scope_violation == "PRIVATE_MULTI_CLIENT_SCOPE_UNAUTHORIZED"
    assert response.status == "review_required"
    assert response.current_stage == "target_scope_validation"
    assert response.model is None


def test_no_structured_multi_client_contract_means_comparison_fails_closed() -> None:
    assert "client_ids" not in UnifiedAssistantRequest.model_fields
    collected = _Collected([], [], [], 41, False, ("anna kowalska",))
    request = UnifiedAssistantRequest(
        question="Zestaw klientkę Anna Kowalska z innym klientem."
    )

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)

    assert boundary.scope_violation == "PRIVATE_MULTI_CLIENT_SCOPE_UNAUTHORIZED"


def test_named_polish_client_pair_cannot_authorize_itself() -> None:
    collected = _Collected([], [], [], 41, False, ("michal zielinski",))
    request = UnifiedAssistantRequest(
        question="Zestaw klienta Michał Zieliński z klientką Ewa Wiśniewska."
    )

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)

    assert UnifiedAssistantService._explicit_client_labels(request.question) == (
        "michal zielinski",
        "ewa wisniewska",
    )
    assert boundary.scope_violation == "PRIVATE_MULTI_CLIENT_SCOPE_UNAUTHORIZED"


def test_single_client_scope_blocks_explicit_other_record_generically() -> None:
    source = AgentSource(
        source_type="document",
        source_id=6,
        title="mixed",
        route=None,
        snippet=(
            "Klient Północ: osiadanie posadzki. "
            "Inna notatka klienta Południe: przeciek instalacji."
        ),
    )
    collected = _Collected(
        [source], [], ["document_search"], 41, False, ("polnoc",)
    )
    request = UnifiedAssistantRequest(question="Co wiadomo o kliencie Północ?")

    boundary = UnifiedAssistantService._target_scope_boundary(request, collected)

    assert "osiadanie posadzki" in boundary.collected.sources[0].snippet
    assert "przeciek instalacji" not in boundary.collected.sources[0].snippet
    assert boundary.blocked_segments
