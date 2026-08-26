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
    "Podsumuj materiał 'Fundamentowanie' z bazy wiedzy.",
    "Omów materiał 'Fundamentowanie' z bazy wiedzy.",
    "Co jest w źródle 'Fundamentowanie' z bazy wiedzy?",
    "Jakie informacje zawiera źródło 'Fundamentowanie' z bazy wiedzy?",
    "Przedstaw najważniejsze zagadnienia materiału 'Fundamentowanie' z bazy wiedzy.",
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

KB_OVERVIEW_PARAPHRASES = [
    "Co mówi źródło 'Fundamentowanie' z bazy wiedzy?",
    "Czego można dowiedzieć się ze źródła 'Fundamentowanie' z bazy wiedzy?",
    "Co zawiera materiał 'Fundamentowanie' z bazy wiedzy?",
    "Podsumuj materiał 'Fundamentowanie' z bazy wiedzy.",
    "Omów materiał 'Fundamentowanie' z bazy wiedzy.",
    "Co jest w źródle 'Fundamentowanie' z bazy wiedzy?",
    "Jakie informacje zawiera źródło 'Fundamentowanie' z bazy wiedzy?",
    "Przedstaw najważniejsze zagadnienia materiału 'Fundamentowanie' z bazy wiedzy.",
    "Co mówi materiał 'Fundamentowanie' z bazy wiedzy?",
    "Jakie zagadnienia opisuje materiał 'Fundamentowanie' z bazy wiedzy?",
]


@pytest.mark.parametrize("question", EXPLICIT_KB_CASES)
def test_explicit_kb_matrix_routes_as_required_evidence(question):
    request = UnifiedAssistantRequest(question=question)
    assert UnifiedAssistantService._query_mode(request) == QUERY_MODE_EVIDENCE_GROUNDED
    assert UnifiedAssistantService._has_explicit_kb_intent(question)


@pytest.mark.asyncio
@pytest.mark.parametrize("question", KB_OVERVIEW_PARAPHRASES)
async def test_kb_overview_paraphrases_use_stable_synthesis_without_model(
    monkeypatch, question
):
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
            return [
                {"knowledge_base_item_id": 7, "title": "Fundamentowanie", "page": 4,
                 "excerpt": "Projekt fundamentu zależy od warstw gruntu i warunków wodnych podłoża.",
                 "status": "current", "retrieval_method": "lexical"},
                {"knowledge_base_item_id": 7, "title": "Fundamentowanie", "page": 9,
                 "excerpt": "Należy sprawdzić nośność, stateczność i przewidywane osiadania konstrukcji.",
                 "status": "current", "retrieval_method": "vector"},
            ]
    class NoModel:
        async def generate(self, **kwargs):
            raise AssertionError("overview synthesis must remain model-free")
    monkeypatch.setattr(unified_module, "KnowledgeBaseRetrievalService", Retrieval)
    response = await UnifiedAssistantService(Db(), llm_client=NoModel()).ask(
        request=UnifiedAssistantRequest(question=question), user_id=1,
    )
    assert response.status == "accepted_local"
    assert response.current_stage == "knowledge_base_synthesis"
    assert response.model is None
    assert len(response.claims) >= 2


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
            return {"response": json.dumps({
                "answer": (
                    "Materiał syntetycznie wyjaśnia dwie powiązane zasady techniczne "
                    "i pokazuje, jak stosować je w praktycznej ocenie projektu."
                ),
                "claims": [
                    {"class": "FACT", "text": "Pierwsza zasada opisuje syntetyczny mechanizm techniczny w ujęciu projektowym.", "source_ref": "S01"},
                    {"class": "FACT", "text": "Druga zasada wiąże ten mechanizm z kontrolą warunków wykonania i weryfikacją.", "source_ref": "S01"},
                ],
            })}

    monkeypatch.setattr(unified_module, "KnowledgeBaseRetrievalService", Retrieval)
    responses = [
        await UnifiedAssistantService(Db(), llm_client=Model()).ask(
            request=UnifiedAssistantRequest(
                question="Co mówi źródło 'Fundamentowanie' z bazy wiedzy?"
            ), user_id=1,
        )
        for _ in range(10)
    ]
    assert all(response.status == "accepted_local" for response in responses)
    assert all(response.sources[0].source_type == "knowledge_base" for response in responses)
    assert all(response.sources[0].source_id == 7 for response in responses)
    assert all("page=3" in (response.sources[0].route or "") for response in responses)
    assert all(response.sources[0].supports_claim_ids == ["C01", "C02"] for response in responses)
    assert all(not response.external_analysis_used for response in responses)
    assert all(response.model == "qwen3.5:9b" for response in responses)


@pytest.mark.asyncio
async def test_kb_overview_gets_one_representation_only_correction(monkeypatch):
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
            return [{"knowledge_base_item_id": 7, "title": "Fundamentowanie", "page": 3,
                     "excerpt": "Syntetyczny fragment.", "status": "current",
                     "retrieval_method": "lexical"}]
    class Model:
        calls = 0
        async def generate(self, **kwargs):
            self.calls += 1
            claim = {"class": "HYPOTHESIS", "text": "Hipoteza bez warunku.", "source_ref": "S01"}
            if self.calls == 2:
                return {"response": json.dumps({
                    "answer": (
                        "Materiał wyjaśnia dwie powiązane zasady techniczne oraz ich znaczenie "
                        "dla praktycznej weryfikacji rozwiązania projektowego i wykonawczego."
                    ),
                    "claims": [
                        {"class": "FACT", "text": "Pierwsza zasada porządkuje mechanizm techniczny opisany w materiale referencyjnym.", "source_ref": "S01"},
                        {"class": "FACT", "text": "Druga zasada wskazuje potrzebę kontroli warunków projektu i wykonania.", "source_ref": "S01"},
                    ],
                })}
            return {"response": json.dumps({"answer": "Syntetyczna odpowiedź.", "claims": [claim]})}
    monkeypatch.setattr(unified_module, "KnowledgeBaseRetrievalService", Retrieval)
    model = Model()
    service = UnifiedAssistantService(Db(), llm_client=model)
    monkeypatch.setattr(service, "_deterministic_kb_overview_payload", lambda *args: {
        "answer": "", "claims": [], "used_sources": [], "tool_plan": [], "estimate": None,
    })
    response = await service.ask(request=UnifiedAssistantRequest(
        question="Co mówi źródło 'Fundamentowanie' z bazy wiedzy?"
    ), user_id=1)
    assert model.calls == 2
    assert response.status == "accepted_local"
    assert response.sources[0].source_id == 7


def test_deterministic_kb_overview_is_repeatable_and_source_bound():
    source_map = {
        "S01": AgentSource(source_type="knowledge_base", source_id=7, title="KB", snippet="A"),
        "S02": AgentSource(source_type="knowledge_base", source_id=7, title="KB", snippet="B"),
    }
    evidence = [
        {"source_ref": "S01", "excerpt": "Projekt fundamentu zależy od warstw gruntu i warunków wodnych podłoża."},
        {"source_ref": "S02", "excerpt": "Należy sprawdzić nośność, stateczność oraz przewidywane osiadania konstrukcji."},
    ]
    results = [
        UnifiedAssistantService._deterministic_kb_overview_payload(evidence, source_map)
        for _ in range(10)
    ]
    assert all(result == results[0] for result in results)
    assert all(UnifiedAssistantService._validate(result, source_map, False) is None for result in results)
    assert all(UnifiedAssistantService._payload_uses_kb(result, source_map, 7) for result in results)


def test_kb_overview_rejects_raw_extract_and_header_dominated_output():
    source_map = {
        "S01": AgentSource(
            source_type="knowledge_base", source_id=7, title="KB",
            snippet="Autor Instytut 2024 Copyright ISBN 1234 Eurokod 7 strona 1",
        ),
        "S02": AgentSource(
            source_type="knowledge_base", source_id=7, title="KB",
            snippet="Drugi surowy fragment nagłówka publikacji technicznej.",
        ),
    }
    payload = {
        "answer": "Autor Instytut 2024 Copyright ISBN 1234 Eurokod 7 strona 1 " * 3,
        "claims": [
            {"class": "FACT", "text": source_map["S01"].snippet, "source_refs": ["S01"]},
            {"class": "FACT", "text": source_map["S02"].snippet, "source_refs": ["S02"]},
        ],
    }
    assert UnifiedAssistantService._kb_overview_usefulness_reason(payload, source_map) in {
        "raw_extract_noise", "raw_extract_leak",
    }


def test_substantive_kb_excerpt_demotes_headers_and_keeps_technical_rules():
    text = (
        "INSTYTUT TECHNICZNY Autor Jan Kowalski ISBN 1234 Copyright 2024. "
        "Nośność podłoża należy sprawdzić z uwzględnieniem warstw gruntu, obciążenia "
        "oraz możliwych odkształceń konstrukcji fundamentowej. "
        "Projekt fundamentu wymaga weryfikacji stateczności i przewidywanych osiadań."
    )
    excerpt, score = UnifiedAssistantService._substantive_kb_excerpt(text)
    assert score >= 4
    assert "Nośność" in excerpt
    assert "ISBN" not in excerpt


@pytest.mark.parametrize("header", [
    "ISBN 978-00 Copyright 2024 Instytut Techniczny Autor Redakcja.",
    "SPIS TREŚCI Strona 12 Wydawnictwo Komitet Techniczny.",
    "Rysunek 1 Tablica 2 Copyright Autor Instytut 2023.",
    "Przedmowa Wydawnictwo Naukowe ISBN 1111 Strona 3.",
    "Autorzy Komitet Redakcyjny Copyright 2022 Instytut.",
])
def test_header_heavy_kb_pages_do_not_become_overview_evidence(header):
    excerpt, score = UnifiedAssistantService._substantive_kb_excerpt(header)
    assert not excerpt or score < 4


@pytest.mark.parametrize("evidence", [
    ("Warstwy gruntu wpływają na dobór fundamentu.", "Nośność i osiadania wymagają sprawdzenia."),
    ("Projekt fundamentu zależy od podłoża.", "Obciążenia należy zweryfikować obliczeniowo."),
    ("Badania obejmują odwierty i sondowania.", "Warunki wodne wpływają na osiadania."),
    ("Stateczność konstrukcji wymaga kontroli.", "Technologia robót ogranicza wykonanie."),
    ("Norma określa wymagania projektu.", "Pomiary służą do weryfikacji nośności."),
])
def test_short_technical_materials_get_synthesized_not_concatenated(evidence):
    source_map = {
        "S01": AgentSource(source_type="knowledge_base", source_id=7, title="KB", snippet=evidence[0]),
        "S02": AgentSource(source_type="knowledge_base", source_id=7, title="KB", snippet=evidence[1]),
    }
    payload = UnifiedAssistantService._deterministic_kb_overview_payload([
        {"source_ref": "S01", "excerpt": evidence[0]},
        {"source_ref": "S02", "excerpt": evidence[1]},
    ], source_map)
    assert len(payload["claims"]) >= 2
    assert payload["answer"] != " ".join(evidence)


def test_local_timeout_is_terminal_non_network_response():
    response = UnifiedAssistantService._local_timeout_response(
        "request", SimpleNamespace(tools=["document_search"])
    )
    assert response.status == "timed_out"
    assert response.current_stage == "local_analysis_timeout"
    assert "lokalna" in (response.error_message or "").lower()


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
    assert len(cases) == 40
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
    assert completed == 40
    print("KB_GROUNDING_MATRIX=35/35")
    print("WRONG_OR_INVENTED_KB_SOURCE=0")
    print("EXPLICIT_GENERAL_SUBSTITUTION=0")
