from __future__ import annotations

from types import SimpleNamespace

from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.unified_assistant_service import UnifiedAssistantService
from app.services.unified_document_content_service import (
    FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE,
    FILE_FOUND_NATIVE_TEXT_AVAILABLE,
    FILE_FOUND_PROCESSING_PENDING,
    UnifiedDocumentContent,
    UnifiedDocumentPage,
)


PHYSICAL_QUERY = (
    "w dokumentach klienta znajduje się plik pdf z badaniami geologicznymi. "
    "przeanalizuj, przedstaw wnioski"
)


def _document(document_id: int, filename: str):
    return SimpleNamespace(
        id=document_id,
        client_id=7,
        original_filename=filename,
        filename=f"stored-{document_id}.pdf",
        content_type="application/pdf",
    )


def _content(text: str, *, state: str = FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE):
    return UnifiedDocumentContent(
        state=state,
        pages=(UnifiedDocumentPage(1, text, "fixture"),),
        character_count=len(text),
    )


def _service(documents, content_by_id, *, client=None):
    class Query:
        def filter(self, *args):
            return self

        def all(self):
            return documents

    class Db:
        def query(self, *args):
            return Query()

        def get(self, model, item_id):
            return client

    service = UnifiedAssistantService(Db(), llm_client=SimpleNamespace())

    def access(document, **kwargs):
        value = content_by_id[document.id]
        if isinstance(value, UnifiedDocumentContent):
            return value
        text = value
        return UnifiedDocumentContent(
            state=FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE,
            pages=(UnifiedDocumentPage(1, text, "fixture"),),
            character_count=len(text),
        )

    service.document_content.access = access
    return service


def test_physical_shape_prefers_semantic_report_over_address_rich_offer():
    offer = _document(1, "oferta_Wysocko_Wielkie_700_lecia_Wsi_3.pdf")
    report = _document(2, "129-2026-Wysocko_Wielkie.pdf")
    later_offer = _document(3, "Oferta_13_VIII_2026_wysocko_wielkie.pdf")
    contract = _document(4, "Umowa_Stabilizacji_wysocko_wielkie.pdf")
    service = _service(
        [offer, report, later_offer, contract],
        {
            1: _content(
                "Oferta handlowa określa cenę, termin i zakres prac.",
                state=FILE_FOUND_NATIVE_TEXT_AVAILABLE,
            ),
            2: _content(
                "Dokumentacja badań geologicznych opisuje odwierty, warstwy gruntu, "
                "poziom wody gruntowej i warunki geotechniczne.",
                state=FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE,
            ),
            3: "Oferta handlowa określa cenę i harmonogram.",
            4: "Umowa określa obowiązki stron i termin realizacji.",
        },
        client=SimpleNamespace(
            street="700-lecia Wsi",
            building_number="3",
            postal_code=None,
            city="Wysocko Wielkie",
        ),
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    assert resolution is not None
    assert resolution.state == "UNIQUE_MATCH"
    assert resolution.document_id == report.id


def test_address_and_pdf_are_auxiliary_not_semantic_identity():
    offer = _document(1, "oferta_Wysocko_Wielkie_700_lecia_Wsi_3.pdf")
    folded = UnifiedAssistantService._fold_intent(PHYSICAL_QUERY)
    query_tokens, expanded_terms = UnifiedAssistantService._document_discovery_terms(folded)
    score = UnifiedAssistantService._document_metadata_score(
        offer,
        query_tokens=query_tokens,
        expanded_terms=expanded_terms,
        address_tokens={"700", "lecia", "wielkie", "wsi", "wysocko"},
        expects_pdf=True,
    )

    assert score.semantic == 0
    assert score.locality == 6
    assert score.type_preference == 1
    assert score.auxiliary == 7


def test_opaque_single_document_can_resolve_from_semantic_content():
    report = _document(1, "129-2026.pdf")
    service = _service(
        [report],
        {
            1: (
                "Badania geologiczne obejmują odwierty, sondowanie, opis warstw gruntu "
                "oraz poziomu wody gruntowej."
            )
        },
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    assert resolution is not None
    assert resolution.state == "UNIQUE_MATCH"
    assert resolution.document_id == report.id


def test_equal_semantic_content_candidates_fail_closed_as_ambiguous():
    first = _document(1, "100-2026.pdf")
    second = _document(2, "101-2026.pdf")
    content = (
        "Badania geologiczne opisują odwierty, sondowanie oraz warstwy gruntu."
    )
    service = _service([first, second], {1: content, 2: content})

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    assert resolution is not None
    assert resolution.state == "AMBIGUOUS"
    assert resolution.candidate_titles == ("100-2026.pdf", "101-2026.pdf")


def test_unavailable_opaque_candidate_does_not_fall_back_to_address_rich_offer():
    offer = _document(1, "oferta_Wysocko_Wielkie_700_lecia_Wsi_3.pdf")
    report = _document(2, "129-2026-Wysocko_Wielkie.pdf")
    unavailable = UnifiedDocumentContent(
        state=FILE_FOUND_PROCESSING_PENDING,
        error_code=FILE_FOUND_PROCESSING_PENDING,
    )
    service = _service(
        [offer, report],
        {
            1: "Oferta handlowa określa cenę i termin realizacji.",
            2: unavailable,
        },
        client=SimpleNamespace(
            street="700-lecia Wsi",
            building_number="3",
            postal_code=None,
            city="Wysocko Wielkie",
        ),
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    assert resolution is not None
    assert resolution.state == FILE_FOUND_PROCESSING_PENDING
    assert resolution.document_id == report.id


def test_multiple_unavailable_plausible_pdfs_fail_closed_with_bounded_titles():
    offer = _document(1, "oferta_Wysocko_Wielkie_700_lecia_Wsi_3.pdf")
    first = _document(2, "129-2026-Wysocko_Wielkie.pdf")
    second = _document(3, "130-2026-Wysocko_Wielkie.pdf")
    unavailable = UnifiedDocumentContent(
        state=FILE_FOUND_PROCESSING_PENDING,
        error_code=FILE_FOUND_PROCESSING_PENDING,
    )
    service = _service(
        [offer, first, second],
        {
            1: "Oferta handlowa określa cenę i termin realizacji.",
            2: unavailable,
            3: unavailable,
        },
        client=SimpleNamespace(
            street="700-lecia Wsi",
            building_number="3",
            postal_code=None,
            city="Wysocko Wielkie",
        ),
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    assert resolution is not None
    assert resolution.state == "AMBIGUOUS"
    assert set(resolution.candidate_titles) == {
        "129-2026-Wysocko_Wielkie.pdf",
        "130-2026-Wysocko_Wielkie.pdf",
    }


def test_exact_filename_match_remains_authoritative():
    report = _document(2, "129-2026-Wysocko_Wielkie.pdf")
    offer = _document(1, "oferta_Wysocko_Wielkie.pdf")
    reference = UnifiedAssistantService._filename_reference(
        "Przeanalizuj plik 129-2026-Wysocko_Wielkie.pdf"
    )

    state, row = UnifiedAssistantService._match_document_rows(
        reference, [offer, report]
    )

    assert state == "EXACT_MATCH"
    assert row.id == report.id


def test_geological_and_geotechnical_polish_families_expand_deterministically():
    phrases = (
        "geologia",
        "geologiczny",
        "geologiczne",
        "geologicznymi",
        "geotechnika",
        "geotechniczny",
        "geotechniczne",
        "geotechnicznymi",
        "grunt",
        "gruntu",
        "gruntowy",
        "podłoże",
        "podłoża",
        "odwiert",
        "sondowanie",
        "badanie gruntu",
        "badania gruntu",
        "badanie podłoża",
        "badania podłoża",
        "badaniami geologicznymi",
        "badania geologiczne",
        "badania geotechniczne",
        "opinia geotechniczna",
    )
    required = {"geolog", "geotechn", "grunt", "podloz", "odwiert", "sondow"}

    for phrase in phrases:
        folded = UnifiedAssistantService._fold_intent(phrase)
        _, expanded = UnifiedAssistantService._document_discovery_terms(folded)
        assert required <= expanded, phrase


def test_unrelated_query_does_not_trigger_geology_expansion():
    folded = UnifiedAssistantService._fold_intent(
        "Przedstaw ofertę handlową oraz termin płatności"
    )
    _, expanded = UnifiedAssistantService._document_discovery_terms(folded)

    assert not ({"geolog", "geotechn", "grunt", "podloz", "odwiert", "sondow"} & expanded)


def test_operational_polish_stopwords_cannot_create_content_relevance():
    folded = UnifiedAssistantService._fold_intent(PHYSICAL_QUERY)
    query_tokens, expanded = UnifiedAssistantService._document_discovery_terms(folded)

    for token in ("sie", "znajduje", "przedstaw"):
        assert token not in query_tokens
        assert token not in expanded


def test_cross_client_explicit_document_is_rejected():
    foreign = SimpleNamespace(
        id=9,
        client_id=99,
        original_filename="raport-geologiczny.pdf",
        filename="stored-9.pdf",
    )

    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return foreign

    service = UnifiedAssistantService(
        SimpleNamespace(query=lambda *args: Query()),
        llm_client=SimpleNamespace(),
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(
            question="Przeanalizuj raport-geologiczny.pdf",
            client_id=7,
            document_id=9,
        )
    )

    assert resolution is not None
    assert resolution.state == "INVALID"


def test_described_resolution_keeps_client_and_lifecycle_filters():
    captured = []

    class Query:
        def filter(self, *args):
            captured.extend(str(arg) for arg in args)
            return self

        def all(self):
            return []

    service = UnifiedAssistantService(
        SimpleNamespace(query=lambda *args: Query(), get=lambda *args: None),
        llm_client=SimpleNamespace(),
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    joined = " ".join(captured)
    assert resolution is not None
    assert resolution.state == "NOT_FOUND"
    assert "documents.client_id" in joined
    assert "documents.trashed_at IS NULL" in joined
    assert "documents.purged_at IS NULL" in joined


def test_candidate_title_ambiguity_is_bounded_to_four():
    documents = [
        _document(index, f"badania-geologiczne-{index}.pdf")
        for index in range(1, 7)
    ]
    service = _service(
        documents,
        {document.id: "Badania geologiczne i odwierty." for document in documents},
    )

    resolution = service._resolve_required_document(
        UnifiedAssistantRequest(question=PHYSICAL_QUERY, client_id=7)
    )

    assert resolution is not None
    assert resolution.state == "AMBIGUOUS"
    assert len(resolution.candidate_titles) == 4
