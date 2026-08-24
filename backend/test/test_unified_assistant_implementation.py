from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.database.session import get_db
from app.main import app
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.schemas.unified_assistant import UnifiedAssistantResponse
from app.services.unified_assistant_service import MODEL, UnifiedAssistantService


def test_deterministic_router_selects_scoped_multi_domain_tools():
    request = UnifiedAssistantRequest(
        question="Przeanalizuj dokumentację klienta, ostatni mail i zdjęcie.",
        client_id=7,
        document_id=9,
        mail_source_id=11,
    )
    calls = UnifiedAssistantService._route(request, 7)
    names = [name for name, _ in calls]
    assert names[:4] == [
        "get_client", "get_document_summary", "get_document_pages",
        "get_visual_analysis",
    ]
    assert "get_email_metadata" in names
    assert all(args.get("client_id", 7) == 7 for _, args in calls)


def test_selected_unlinked_entity_never_widens_to_global_search():
    request = UnifiedAssistantRequest(
        question="Podsumuj tego kandydata",
        candidate_id=9,
    )
    # The Candidate itself is collected before routing. No unrelated global
    # CRM search is allowed solely because it has no matched Client yet.
    assert UnifiedAssistantService._route(request, None) == []


def test_general_question_does_not_trigger_broad_crm_dump():
    request = UnifiedAssistantRequest(
        question="Jak bezpiecznie przygotować wizję lokalną?",
    )
    assert UnifiedAssistantService._route(request, None) == []


def test_explicit_global_crm_search_uses_deterministic_search():
    request = UnifiedAssistantRequest(question="Znajdź klienta Kowalski")
    assert UnifiedAssistantService._route(request, None)[0][0] == "global_search"


def test_local_gate_rejects_unknown_source_and_unsupported_visual_claim():
    source = type("Source", (), {})()
    source_map = {"S01": source}
    base = {
        "answer": "Odpowiedź.",
        "claims": [{"class": "FACT", "text": "Fakt", "source_refs": ["S01"], "tool_refs": []}],
        "used_sources": ["S01"],
        "tool_plan": [],
        "estimate": None,
    }
    assert UnifiedAssistantService._validate(base, source_map, False) is None
    foreign = {**base, "used_sources": ["S99"]}
    assert UnifiedAssistantService._validate(foreign, source_map, False) == "unknown_source"
    visual = {**base, "answer": "Na zdjęciu widać pęknięcie."}
    assert UnifiedAssistantService._validate(visual, source_map, False) == "visual_provenance_missing"


def test_not_estimable_is_structural_and_forbids_number_or_low_confidence():
    source = type("Source", (), {})()
    source_map = {"S01": source}
    valid = {
        "answer": "Nie można wiarygodnie oszacować.",
        "claims": [{"class": "ESTIMATE", "text": "Brak podstaw", "source_refs": ["S01"], "tool_refs": []}],
        "used_sources": ["S01"], "tool_plan": [],
        "estimate": {"estimate_status": "NOT_ESTIMABLE", "value_or_range": None,
                     "confidence": None, "basis": ["S01"], "assumptions": [],
                     "missing_inputs": ["Brak pomiaru"], "reason": "Brak danych"},
    }
    assert UnifiedAssistantService._validate(valid, source_map, False) is None
    invalid = {**valid, "estimate": {**valid["estimate"], "confidence": "LOW"}}
    assert UnifiedAssistantService._validate(invalid, source_map, False) == "estimate_contract"
    detached = {**valid, "claims": [{"class": "FACT", "text": "Brak podstaw", "source_refs": ["S01"], "tool_refs": []}]}
    assert UnifiedAssistantService._validate(detached, source_map, False) == "estimate_contract"


def test_qualified_model_estimate_is_normalized_to_internal_status():
    raw = {
        "answer": "Nie można oszacować.",
        "claims": [{"class": "ESTIMATE", "text": "Brak podstaw", "source_refs": ["S01"]}],
        "used_sources": ["S01"], "tool_plan": [],
        "estimate": {"value_or_range": "", "confidence": "NOT_ESTIMABLE", "basis": ["opis"],
                     "assumptions": [], "missing_inputs": ["pomiar"]},
    }
    normalized = UnifiedAssistantService._normalize_model_result(raw)
    assert normalized["estimate"]["estimate_status"] == "NOT_ESTIMABLE"
    assert normalized["estimate"]["confidence"] is None
    assert normalized["estimate"]["basis"] == ["S01"]


def test_material_claims_require_provenance_and_used_sources_match_claims():
    source = type("Source", (), {})()
    source_map = {"S01": source}
    base = {
        "answer": "Hipoteza.",
        "claims": [{"class": "HYPOTHESIS", "text": "Możliwa przyczyna; pomiar potwierdzi lub obali hipotezę.", "source_refs": ["S01"], "tool_refs": []}],
        "used_sources": ["S01"], "tool_plan": [], "estimate": None,
    }
    assert UnifiedAssistantService._validate(base, source_map, False) is None
    detached = {**base, "used_sources": []}
    assert UnifiedAssistantService._validate(detached, source_map, False) == "source_binding"
    unsupported = {**base, "claims": [{"class": "HYPOTHESIS", "text": "Możliwa przyczyna; pomiar ją potwierdzi.", "source_refs": [], "tool_refs": []}], "used_sources": []}
    assert UnifiedAssistantService._validate(unsupported, source_map, False) == "missing_provenance"
    unverifiable = {**base, "claims": [{"class": "HYPOTHESIS", "text": "Możliwa przyczyna", "source_refs": ["S01"], "tool_refs": []}]}
    assert UnifiedAssistantService._validate(unverifiable, source_map, False) == "hypothesis_contract"
    empty = {**base, "claims": [], "used_sources": []}
    assert UnifiedAssistantService._validate(empty, source_map, False) == "invalid_schema"


def test_tool_provenance_is_separate_and_inherits_source_binding():
    source_map = {"S01": type("Source", (), {})()}
    payload = {
        "answer": "Wynik wynosi 2,5 MPa.",
        "claims": [{
            "class": "FACT", "text": "Wynik wynosi 2,5 MPa.",
            "source_refs": ["S01"], "tool_refs": ["T01"],
        }],
        "used_sources": ["S01"], "tool_plan": ["calculation"], "estimate": None,
    }
    assert UnifiedAssistantService._validate(
        payload, source_map, False, {"T01": {"S01"}}
    ) is None
    payload["claims"][0]["source_refs"] = ["T01"]
    assert UnifiedAssistantService._validate(
        payload, source_map, False, {"T01": {"S01"}}
    ) == "unknown_source"


def test_tool_payload_cannot_leak_competing_internal_provenance_aliases():
    cleaned = UnifiedAssistantService._strip_internal_provenance({
        "value": 2.5,
        "source_refs": ["document:T12"],
        "nested": {"tool_result_id": "CALC-01", "unit": "MPa"},
    })
    assert cleaned == {"value": 2.5, "nested": {"unit": "MPa"}}


def test_exact_tool_handle_expands_its_allowlisted_sources():
    payload = {
        "used_sources": [],
        "claims": [{"source_refs": [], "tool_refs": ["T01"]}],
    }
    resolved = UnifiedAssistantService._resolve_tool_provenance(
        payload, {"T01": {"S01"}}
    )
    assert resolved["claims"][0]["source_refs"] == ["S01"]
    assert resolved["used_sources"] == ["S01"]


def test_generation_schema_is_bounded_to_exact_request_handles():
    schema = UnifiedAssistantService._bounded_model_schema({"S01"}, set())
    claim = schema["properties"]["claims"]["items"]["properties"]
    assert claim["source_refs"]["items"]["enum"] == ["S01"]
    assert claim["tool_refs"]["maxItems"] == 0


def test_request_contract_forbids_unknown_fields_and_bounds_history():
    try:
        UnifiedAssistantRequest.model_validate({"question": "Pytanie", "mode": "business"})
    except ValueError:
        pass
    else:
        raise AssertionError("legacy mode must not enter the unified contract")


def test_source_inspector_redacts_routine_contact_identifiers():
    value = "Kontakt anna@example.com, +48 123 456 789, NIP 123-456-78-90."
    safe = UnifiedAssistantService._safe_source_excerpt(value)
    assert "anna@example.com" not in safe
    assert "123 456 789" not in safe
    assert "123-456-78-90" not in safe


def test_additive_unified_endpoint_is_authenticated_and_returns_typed_contract(monkeypatch):
    async def fake_ask(self, *, request, user_id):
        assert request.question == "Pytanie kontrolne"
        assert user_id == 71
        return UnifiedAssistantResponse(
            request_id="00000000-0000-0000-0000-000000000071",
            answer="Brakuje danych do odpowiedzi.", status="accepted_local",
            progress="complete", target_scope="TARGET_01", claims=[{
                "claim_id": "C01", "claim_class": "MISSING",
                "text": "Brakuje danych.", "source_refs": [],
            }], sources=[], used_tools=[], model=MODEL,
        )

    monkeypatch.setattr(UnifiedAssistantService, "ask", fake_ask)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=71)
    try:
        response = TestClient(app).post(
            "/api/v1/ai/assistant/ask", json={"question": "Pytanie kontrolne"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["model"] == "qwen3.5:9b"
    assert response.json()["claims"][0]["claim_class"] == "MISSING"
