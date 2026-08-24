from __future__ import annotations

import hashlib
from uuid import uuid4

from app.schemas.analysis import AdvancedAnalysisResult, AnalysisProvenance, AnalysisRequest, AnalysisSourceRef
from app.services.analysis_result_contract import TemporaryChatResultContractV2
from app.services.analysis_sanitizer import AnalysisSanitizer


def source(handle: str, text: str) -> AnalysisSourceRef:
    return AnalysisSourceRef(
        source_ref=handle,
        checksum_sha256=hashlib.sha256(text.encode()).hexdigest(),
        excerpt=text,
    )


def request(*, scope: dict | None = None) -> AnalysisRequest:
    structured = {
        "contract_version": TemporaryChatResultContractV2.SCHEMA,
        "claims": [
            {"kind": "FACT", "fact_handle": "F1", "source_handle": "S1", "statement": "Rysa przy oknie."},
            {"kind": "FACT", "fact_handle": "F2", "source_handle": "S2", "statement": "Rysa przy drzwiach."},
            {"kind": "FACT", "fact_handle": "F3", "source_handle": "S3", "statement": "Norma publiczna."},
            {"kind": "TOOL_RESULT", "tool_handle": "T1", "source_handles": ["S1", "S3"], "statement": "10 mm"},
            {"kind": "TOOL_RESULT", "tool_handle": "T2", "source_handles": ["S2"], "statement": "20 mm"},
            {"kind": "VISUAL_OBSERVATION", "visual_handle": "V1", "source_handles": ["S1"], "statement": "Linia."},
            {"kind": "VISUAL_OBSERVATION", "visual_handle": "V2", "source_handles": ["S2"], "statement": "Plama."},
        ],
        "requested_output": "Strict V2",
        "validation_requirements": [],
    }
    if scope is not None:
        structured["target_scope"] = scope
    return AnalysisRequest(
        analysis_id=uuid4(),
        analysis_type="technical_interpretation",
        source_domain="technical",
        source_refs=[source("S1", "Rysa przy oknie."), source("S2", "Rysa przy drzwiach."), source("S3", "Norma publiczna.")],
        problem_statement="Odpowiedz wyłącznie dla TARGET_01.",
        structured_inputs=structured,
        evidence=["opaque:one", "opaque:two", "public:standard"],
        sensitivity="public_reference",
        allowed_methods=["local_llm", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum="0" * 64),
    )


def scoped_request() -> AnalysisRequest:
    return request(scope={
        "scope_handle": "TARGET_01",
        "allowed_source_handles": ["S1"],
        "global_source_handles": ["S3"],
    })


def result(req: AnalysisRequest, claims: list[dict]) -> AdvancedAnalysisResult:
    return AdvancedAnalysisResult(
        schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1",
        analysis_id=req.analysis_id,
        package_sha256="1" * 64,
        result={"schema": TemporaryChatResultContractV2.SCHEMA, "claims": claims, "contradictions": []},
        source_refs=TemporaryChatResultContractV2.allowed_source_refs(req),
        verification_recommendation="accept",
    )


def status(req: AnalysisRequest, claims: list[dict]) -> str:
    return TemporaryChatResultContractV2().validate(request=req, result=result(req, claims)).status


def fact(*, facts=None, tools=None, visuals=None) -> dict:
    return {"class": "FACT", "fact_handles": facts or [], "tool_handles": tools or [], "visual_handles": visuals or []}


def test_target_scope_positive_and_global_source() -> None:
    req = scoped_request()
    outcome = TemporaryChatResultContractV2().validate(request=req, result=result(req, [fact(facts=["F1", "F3"])]))
    assert outcome.status == "accepted_advanced"
    assert outcome.artifact["target_scope_handle"] == "TARGET_01"
    assert outcome.artifact["source_refs"] == ["S1", "S3"]


def test_cross_scope_fact_and_mixed_claim_reject() -> None:
    req = scoped_request()
    assert status(req, [fact(facts=["F2"])]) == "rejected"
    assert status(req, [fact(facts=["F1", "F2"])]) == "rejected"


def test_tool_and_visual_inherit_scope() -> None:
    req = scoped_request()
    assert status(req, [fact(tools=["T1"])]) == "accepted_advanced"
    assert status(req, [fact(tools=["T2"])]) == "rejected"
    assert status(req, [fact(visuals=["V1"])]) == "accepted_advanced"
    assert status(req, [fact(visuals=["V2"])]) == "rejected"


def test_unknown_empty_duplicate_and_overlapping_scope_fail_closed() -> None:
    invalid = [
        {"scope_handle": "TARGET_09", "allowed_source_handles": ["S1"], "global_source_handles": []},
        {"scope_handle": "TARGET_01", "allowed_source_handles": [], "global_source_handles": []},
        {"scope_handle": "TARGET_01", "allowed_source_handles": ["S1", "S1"], "global_source_handles": []},
        {"scope_handle": "TARGET_01", "allowed_source_handles": ["S1"], "global_source_handles": ["S1"]},
        {"scope_handle": "TARGET_01", "allowed_source_handles": ["S8"], "global_source_handles": []},
    ]
    for scope in invalid:
        req = request(scope=scope)
        assert status(req, [fact(facts=["F1"])]) == "rejected"


def test_same_type_sources_remain_distinct_without_identity() -> None:
    req = scoped_request()
    package = AnalysisSanitizer().sanitize(req).package.model_dump(mode="json")
    assert package["target_scope"] == {
        "scope_handle": "TARGET_01", "allowed_source_handles": ["S1"], "global_source_handles": ["S3"],
    }
    serialized = AnalysisSanitizer().sanitize(req).canonical_json.casefold()
    assert all(marker not in serialized for marker in ("name", "email", "phone", "address", "nip", "regon", "kowalski"))


def estimate_estimable(**updates) -> dict:
    value = {
        "class": "ESTIMATE", "estimate_status": "ESTIMABLE", "value_or_range": "8–12 mm",
        "confidence": "MEDIUM", "basis_fact_handles": ["F1"], "basis_tool_handles": [],
        "assumptions": ["stałe warunki"], "missing_inputs": [],
    }
    value.update(updates)
    return value


def estimate_not_estimable(**updates) -> dict:
    value = {
        "class": "ESTIMATE", "estimate_status": "NOT_ESTIMABLE",
        "reason": "Brak danych potrzebnych do obronnego oszacowania.",
        "basis_fact_handles": ["F1"], "basis_tool_handles": [],
        "missing_inputs": ["pomiar"],
    }
    value.update(updates)
    return value


def test_estimation_states_positive() -> None:
    req = scoped_request()
    assert status(req, [estimate_estimable()]) == "accepted_advanced"
    outcome = TemporaryChatResultContractV2().validate(request=req, result=result(req, [estimate_not_estimable()]))
    assert outcome.status == "accepted_advanced"
    assert outcome.artifact["claims"][0]["confidence"] == "NOT_ESTIMABLE"
    assert outcome.artifact["claims"][0]["assumptions"] == []


def test_estimation_states_negative() -> None:
    req = scoped_request()
    invalid = [
        estimate_estimable(basis_fact_handles=[]),
        estimate_estimable(confidence=None),
        estimate_not_estimable(value_or_range="10 mm"),
        estimate_not_estimable(confidence="LOW"),
        estimate_not_estimable(missing_inputs=[]),
        estimate_not_estimable(reason=""),
    ]
    for claim in invalid:
        assert status(req, [claim]) == "rejected"


def main() -> None:
    tests = [
        test_target_scope_positive_and_global_source,
        test_cross_scope_fact_and_mixed_claim_reject,
        test_tool_and_visual_inherit_scope,
        test_unknown_empty_duplicate_and_overlapping_scope_fail_closed,
        test_same_type_sources_remain_distinct_without_identity,
        test_estimation_states_positive,
        test_estimation_states_negative,
    ]
    for item in tests:
        item()
    print("TEMP_CHAT_V2_SCOPE_ESTIMATION=PASS tests=7")


if __name__ == "__main__":
    main()
