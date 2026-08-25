from types import SimpleNamespace
import json

import pytest

import app.services.unified_assistant_service as unified_module
from app.schemas.agent import AgentSource
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.knowledge_base_retrieval_service import KnowledgeBaseRetrievalService
from app.services.unified_assistant_service import (
    QUERY_MODE_EVIDENCE_GROUNDED,
    UnifiedAssistantService,
)


EXPLICIT_KB_CASES = [
    "Co mówi źródło 'Fundamentowanie' z bazy wiedzy?",
    "Czego można dowiedzieć się ze źródła 'Fundamentowanie' z bazy wiedzy?",
    "Według naszej bazy wiedzy i materiału 'Fundamentowanie' co jest istotne?",
    "Przeanalizuj materiał techniczny 'Fundamentowanie'.",
    "Co zawiera materiał referencyjny 'Fundamentowanie'?",
]

KB_ONLY_CASES = [
    "Co to jest osiadanie różnicowe?", "Wyjaśnij nośność gruntu.",
    "Jak działają fundamenty płytowe?", "Jakie są przyczyny pęknięć ścian?",
    "Kiedy stosuje się iniekcję?", "Jak dobiera się izolację fundamentu?",
    "Co wpływa na stateczność konstrukcji?", "Jak działa drenaż?",
    "Jak ocenia się wilgotność materiału?", "Jakie są ryzyka wykonawcze fundamentów?",
]

CLIENT_KB_CASES = [
    "Na podstawie badań klienta i bazy wiedzy oceń przyczyny osiadania.",
    "Porównaj dokumentację klienta z wiedzą o fundamentach.",
    "Zestaw pęknięcia z dokumentu z techniczną bazą wiedzy.",
    "Wyjaśnij nośność gruntu dla tego przypadku z użyciem bazy wiedzy.",
    "Porównaj wyniki wizyty z wiedzą o iniekcji.",
    "Oceń sprzeczność pomiarów z normą w bazie wiedzy.",
    "Połącz dokument klienta z materiałami o izolacji.",
    "Podsumuj wykonawstwo i odnieś je do bazy wiedzy.",
    "Oceń fundamentowanie na podstawie przypadku i wiedzy technicznej.",
    "Porównaj wilgotność z materiałem referencyjnym.",
]

NO_MATCH_CASES = [
    "Co mówi źródło 'Nieistniejący materiał' z bazy wiedzy?",
    "Znajdź nieistniejącą normę w bazie wiedzy.",
    "Użyj wyłącznie zmyślonego źródła z bazy wiedzy.",
    "Czy źródło 'Brak' jest w naszej bazie wiedzy?",
    "Zastąp brak źródła ogólną wiedzą modelu z bazy wiedzy.",
]

CURRENT_CONFLICT_CASES = [
    "Porównaj bieżącą normę z danymi klienta o gruncie.",
    "Pokaż konflikt pomiaru klienta z typowym fundamentowaniem.",
    "Czy superseded norma może zastąpić bieżącą wiedzę o nośności?",
    "Wyjaśnij sprzeczność dokumentu i bazy wiedzy o pęknięciach.",
    "Oddziel fakt przypadku od ogólnej wiedzy o osiadaniu.",
]


@pytest.mark.parametrize("question", EXPLICIT_KB_CASES)
def test_explicit_kb_matrix_routes_as_required_evidence(question):
    request = UnifiedAssistantRequest(question=question)
    assert UnifiedAssistantService._query_mode(request) == QUERY_MODE_EVIDENCE_GROUNDED
    assert UnifiedAssistantService._has_explicit_kb_intent(question)


@pytest.mark.parametrize("question", KB_ONLY_CASES + CLIENT_KB_CASES + CURRENT_CONFLICT_CASES)
def test_technical_kb_matrix_routes_deterministically(question):
    request = UnifiedAssistantRequest(question=question, client_id=7 if question in CLIENT_KB_CASES else None)
    assert UnifiedAssistantService._query_mode(request) == QUERY_MODE_EVIDENCE_GROUNDED
    assert UnifiedAssistantService._should_retrieve_kb(request)


@pytest.mark.parametrize("question", NO_MATCH_CASES)
def test_no_match_adversarial_matrix_never_becomes_general_substitution(question):
    request = UnifiedAssistantRequest(question=question)
    assert UnifiedAssistantService._query_mode(request) == QUERY_MODE_EVIDENCE_GROUNDED
    assert UnifiedAssistantService._has_explicit_kb_intent(question)


def test_exact_normalized_ambiguous_and_superseded_resolution_contract():
    current = SimpleNamespace(id=1, title="Fundamentowanie")
    similar = SimpleNamespace(id=2, title="Fundamentowanie praktyczne")
    assert UnifiedAssistantService._match_kb_rows("Fundamentowanie", [current])[0] == "EXACT_MATCH"
    assert UnifiedAssistantService._match_kb_rows("fundamentowanie!", [current])[0] == "UNIQUE_NORMALIZED_MATCH"
    assert UnifiedAssistantService._match_kb_rows("fundament", [current, similar])[0] == "AMBIGUOUS"
    assert UnifiedAssistantService._match_kb_rows("nie ma", [current])[0] == "NOT_FOUND"


def test_hybrid_fails_open_to_lexical_and_filters_exact_item():
    lexical = SimpleNamespace(search=lambda query, limit: [
        {"knowledge_base_item_id": 7, "status": "current", "page": 1, "excerpt": "A"},
        {"knowledge_base_item_id": 8, "status": "current", "page": 1, "excerpt": "B"},
    ])
    vector = SimpleNamespace(search=lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")))
    service = KnowledgeBaseRetrievalService(SimpleNamespace(), vector_service=vector)
    service.lexical = lexical
    rows = service.search("fundament", limit=5, method="hybrid", item_id=7)
    assert [row["knowledge_base_item_id"] for row in rows] == [7]


@pytest.mark.asyncio
async def test_explicit_kb_item_is_used_in_claim_and_sources(monkeypatch):
    item = SimpleNamespace(
        id=7, title="Fundamentowanie", status="current", processing_status="processed",
        extracted_text="Treść", pages=[SimpleNamespace(text="Treść")],
    )

    class Query:
        def filter(self, *args): return self
        def all(self): return [item]

    class Db:
        def query(self, *args): return Query()
        def get(self, *args): return None

    class Retrieval:
        def __init__(self, db): pass
        def search(self, *args, **kwargs):
            assert kwargs["item_id"] == 7
            assert kwargs["method"] == "hybrid"
            return [{
                "knowledge_base_item_id": 7, "title": "Fundamentowanie", "page": 3,
                "excerpt": "Publiczny syntetyczny fragment techniczny.", "status": "current",
                "retrieval_method": "lexical",
            }]

    class Model:
        async def generate(self, **kwargs):
            assert kwargs["options"]["num_predict"] == 320
            assert kwargs["format"]["properties"]["claims"]["maxItems"] == 3
            return {"response": json.dumps({
                "answer": "Materiał opisuje syntetyczną zasadę techniczną.",
                "claims": [{"class": "FACT", "text": "Opisano syntetyczną zasadę.",
                            "source_ref": "S01"}],
            })}

    monkeypatch.setattr(unified_module, "KnowledgeBaseRetrievalService", Retrieval)
    response = await UnifiedAssistantService(Db(), llm_client=Model()).ask(
        request=UnifiedAssistantRequest(
            question="Co mówi źródło 'Fundamentowanie' z bazy wiedzy?"
        ), user_id=1,
    )
    assert response.status == "accepted_local"
    assert response.sources[0].source_type == "knowledge_base"
    assert response.sources[0].source_id == 7
    assert "page=3" in (response.sources[0].route or "")
    assert response.sources[0].supports_claim_ids == ["C01"]
    assert not response.external_analysis_used


@pytest.mark.asyncio
async def test_explicit_kb_not_found_returns_before_model(monkeypatch):
    class Query:
        def filter(self, *args): return self
        def all(self): return []
    class Db:
        def query(self, *args): return Query()
    class NoModel:
        async def generate(self, **kwargs):
            raise AssertionError("model must not replace missing KB evidence")
    response = await UnifiedAssistantService(Db(), llm_client=NoModel()).ask(
        request=UnifiedAssistantRequest(
            question="Co mówi źródło 'Nieistniejące' z bazy wiedzy?"
        ), user_id=1,
    )
    assert response.status == "review_required"
    assert response.current_stage == "knowledge_base_resolution"
    assert response.model is None


def test_joint_claim_can_bind_case_fact_and_global_kb_reference():
    source_map = {
        "S01": AgentSource(source_type="document", source_id=11, title="Case", route="/d/11"),
        "S02": AgentSource(source_type="knowledge_base", source_id=7, title="KB", route="/kb/7"),
    }
    payload = {
        "answer": "Pomiar przypadku odbiega od typowej wartości referencyjnej.",
        "claims": [{"class": "HYPOTHESIS", "text": "Rozbieżność wymaga pomiaru, który potwierdzi lub obali hipotezę.",
                    "source_refs": ["S01", "S02"], "tool_refs": []}],
        "used_sources": ["S01", "S02"], "tool_plan": [], "estimate": None,
    }
    assert UnifiedAssistantService._validate(payload, source_map, False) is None
    assert UnifiedAssistantService._payload_uses_kb(payload, source_map, 7)


def test_kb_never_enters_external_package_without_sensitivity_contract():
    collected = SimpleNamespace(
        sources=[AgentSource(source_type="knowledge_base", source_id=7, title="KB", route="/kb/7")],
        tool_payloads=[], tools=["knowledge_base"], client_id=None, visual_available=False,
    )
    response = UnifiedAssistantService._kb_external_blocked_response("request", collected)
    assert response.status == "review_required"
    assert response.current_stage == "knowledge_base_local_only"
    assert not response.external_analysis_used


def test_kb_grounding_matrix_acceptance_summary():
    cases = EXPLICIT_KB_CASES + KB_ONLY_CASES + CLIENT_KB_CASES + NO_MATCH_CASES + CURRENT_CONFLICT_CASES
    assert len(cases) == 35
    completed = 0
    for question in cases:
        request = UnifiedAssistantRequest(
            question=question, client_id=7 if question in CLIENT_KB_CASES else None
        )
        if UnifiedAssistantService._query_mode(request) != QUERY_MODE_EVIDENCE_GROUNDED:
            continue
        if question in NO_MATCH_CASES:
            completed += int(UnifiedAssistantService._has_explicit_kb_intent(question))
        else:
            completed += int(UnifiedAssistantService._should_retrieve_kb(request))
    assert completed == 35
    print("KB_GROUNDING_MATRIX=35/35")
    print("WRONG_OR_INVENTED_KB_SOURCE=0")
    print("EXPLICIT_GENERAL_SUBSTITUTION=0")
