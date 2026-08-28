from __future__ import annotations

import uuid

from app.schemas.agent import AgentSource
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.analysis_sanitizer import AnalysisSanitizer
from app.services.assistant_advanced_manifest import build_advanced_manifest
from app.services.unified_assistant_service import UnifiedAssistantService, _Collected


def _source(handle: str, key: str, text: str):
    return handle, key, text


def test_pressure_manifest_preserves_canonical_display_and_all_provenance() -> None:
    manifest = build_advanced_manifest(
        question="Oblicz ciśnienie.",
        sources=[_source("S1", "document:pressure", "Wzór P=F/A; 1 kN=1000 N.")],
        tool_payloads=[{
            "tool": "calculation",
            "source_keys": ["document:pressure"],
            "data": {
                "formula": "force/area", "value": 3.0, "unit": "MPa",
                "si_value": 3_000_000.0, "si_unit": "Pa",
                "display": "3,000,000 Pa = 3 MPa",
            },
        }],
    )
    tool = next(item for item in manifest.claims if item["kind"] == "TOOL_RESULT")
    assert tool["statement"] == "3,000,000 Pa = 3 MPa"
    assert tool["source_handles"] == ["S1"]
    assert tool["si_value"] == 3_000_000.0
    assert "estimate discipline" in manifest.validation_requirements


def test_limit_comparison_is_generic_source_bound_tool_result() -> None:
    manifest = build_advanced_manifest(
        question="Czy wymaganie jest spełnione?",
        sources=[
            _source("S1", "knowledge:limit", "Limit ugięcia L/300."),
            _source("S2", "document:measure", "Rozpiętość 6 m, ugięcie 25 mm."),
        ],
        tool_payloads=[{
            "tool": "calculation",
            "source_keys": ["knowledge:limit", "document:measure"],
            "data": {"formula": "span/300", "value": 20.0, "unit": "mm"},
        }],
    )
    tools = [item for item in manifest.claims if item["kind"] == "TOOL_RESULT"]
    assert tools[0]["source_handles"] == ["S1", "S2"]
    assert tools[1]["source_handles"] == ["S1", "S2"]
    assert tools[1]["observed_value"] == 25.0
    assert tools[1]["limit_value"] == 20.0
    assert tools[1]["satisfied"] is False
    assert "25 mm" in tools[1]["statement"]
    assert "20 mm" in tools[1]["statement"]
    assert "nie jest spełnione" in tools[1]["statement"]


def test_consistency_intent_gets_generic_relationship_semantics() -> None:
    manifest = build_advanced_manifest(
        question="Czy dokumenty i obserwacje są spójne?",
        sources=[_source(
            "S1", "document:soil",
            "Raport: glina twardoplastyczna. Odkrywka: luźny nasyp.",
        )],
        tool_payloads=[],
    )
    assert manifest.analysis_type == "consistency_check"
    assert len(manifest.claims) == 2
    assert {item.get("comparison_group") for item in manifest.claims} == {"C1"}
    assert all("contradiction_group" not in item for item in manifest.claims)
    assert "Jawnie wskaż" in manifest.requested_output


def test_explicit_contradiction_preserves_strict_group_contract() -> None:
    manifest = build_advanced_manifest(
        question="Wskaż sprzeczność w komunikacji.",
        sources=[_source("S1", "client:one", "Wersja pierwsza. Wersja druga.")],
        tool_payloads=[],
    )
    assert {item.get("contradiction_group") for item in manifest.claims} == {"G1"}


def test_production_advanced_request_uses_shared_tool_manifest() -> None:
    first = AgentSource(
        source_type="knowledge_base", source_id=7, title="Limit",
        route="/kb/7", snippet="Limit ugięcia L/300.",
    )
    second = AgentSource(
        source_type="document", source_id=9, title="Pomiar",
        route="/documents/9", snippet="Rozpiętość 6 m, ugięcie 25 mm.",
    )
    collected = _Collected(
        sources=[first, second],
        tool_payloads=[{
            "tool": "calculation",
            "source_keys": [
                (first.source_type, first.source_id, first.route),
                (second.source_type, second.source_id, second.route),
            ],
            "data": {"formula": "span/300", "value": 20.0, "unit": "mm"},
        }],
        tools=["calculation"], client_id=None, visual_available=False,
    )
    service = UnifiedAssistantService.__new__(UnifiedAssistantService)
    request, _ = service._advanced_request(
        UnifiedAssistantRequest(question="Czy wymaganie jest spełnione?", conversation=[]),
        collected,
        1,
        str(uuid.uuid4()),
    )
    tools = [
        item for item in request.structured_inputs["claims"]
        if item["kind"] == "TOOL_RESULT"
    ]
    assert len(tools) == 2
    assert tools[0]["source_handles"] == ["S1", "S2"]
    assert tools[1]["satisfied"] is False
    package = AnalysisSanitizer().sanitize(request).package
    assert package.claims == request.structured_inputs["claims"]


def test_production_and_qualification_key_shapes_have_manifest_parity() -> None:
    data = {
        "formula": "force/area", "value": 3.0, "unit": "MPa",
        "si_value": 3_000_000.0, "si_unit": "Pa",
        "display": "3,000,000 Pa = 3 MPa",
    }
    qualification = build_advanced_manifest(
        question="Oblicz ciśnienie.",
        sources=[_source("S1", "document:pressure", "Wzór P=F/A.")],
        tool_payloads=[{
            "tool": "calculation", "source_keys": ["document:pressure"], "data": data,
        }],
    )
    production = build_advanced_manifest(
        question="Oblicz ciśnienie.",
        sources=[_source("S1", ("document", 6, None), "Wzór P=F/A.")],
        tool_payloads=[{
            "tool": "calculation", "source_keys": [("document", 6, None)], "data": data,
        }],
    )
    assert production == qualification


def test_validated_calculation_requires_estimate_contract() -> None:
    collected = _Collected(
        sources=[],
        tool_payloads=[{
            "tool": "calculation",
            "source_keys": [],
            "data": {"value": 3.0, "unit": "MPa"},
        }],
        tools=["calculation"], client_id=None, visual_available=False,
    )
    assert UnifiedAssistantService._calculation_contract_required(collected)
    payload = {
        "answer": "Ciśnienie wynosi 3 MPa.",
        "claims": [{
            "class": "FACT", "text": "Ciśnienie wynosi 3 MPa.",
            "source_refs": ["S01"], "tool_refs": ["T01"],
        }],
        "used_sources": ["S01"], "tool_plan": [], "estimate": None,
    }
    source_map = {
        "S01": AgentSource(
            source_type="document", source_id=6, title="Pressure", snippet="P=F/A",
        )
    }
    assert UnifiedAssistantService._validate(
        payload,
        source_map,
        False,
        {"T01": {"S01"}},
        require_calculation_estimate=True,
    ) == "estimate_contract"


def main() -> None:
    tests = [
        test_pressure_manifest_preserves_canonical_display_and_all_provenance,
        test_limit_comparison_is_generic_source_bound_tool_result,
        test_consistency_intent_gets_generic_relationship_semantics,
        test_explicit_contradiction_preserves_strict_group_contract,
        test_production_advanced_request_uses_shared_tool_manifest,
        test_production_and_qualification_key_shapes_have_manifest_parity,
        test_validated_calculation_requires_estimate_contract,
    ]
    for test in tests:
        test()
    print(f"ASSISTANT_ADVANCED_MANIFEST=PASS tests={len(tests)}")


if __name__ == "__main__":
    main()
