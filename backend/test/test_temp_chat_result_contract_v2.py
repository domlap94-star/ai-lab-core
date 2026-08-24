from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.schemas.analysis import AdvancedAnalysisResult, AnalysisProvenance, AnalysisRequest, AnalysisSourceRef
from app.services.analysis_result_contract import TemporaryChatResultContractV2
from app.services.analysis_sanitizer import AnalysisSanitizationError, AnalysisSanitizer
from test.local_llm_qualification_cases import cases


FIXTURE = Path(__file__).parent / "fixtures" / "temp_chat_result_contract_v2_regression.json"


def request_for(case, *, claims=None) -> AnalysisRequest:
    refs = []
    manifest = []
    for index, (_, excerpt) in enumerate(case.evidence.items(), 1):
        source = f"S{index}"
        refs.append(AnalysisSourceRef(source_ref=source, checksum_sha256=hashlib.sha256(excerpt.encode()).hexdigest(), excerpt=excerpt))
        manifest.append({"kind": "FACT", "fact_handle": f"F{index}", "source_handle": source, "statement": excerpt})
    return AnalysisRequest(
        analysis_id=uuid4(), analysis_type="technical_interpretation", source_domain="technical",
        source_refs=refs, problem_statement=case.question,
        structured_inputs={"claims": claims if claims is not None else manifest},
        evidence=list(case.evidence), sensitivity="public_reference", allowed_methods=["local_llm", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum="0" * 64),
    )


def result_for(request: AnalysisRequest, claims: list[dict], *, source_refs=None, contradictions=None) -> AdvancedAnalysisResult:
    return AdvancedAnalysisResult(
        schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1", analysis_id=request.analysis_id,
        package_sha256="1" * 64,
        result={"schema": TemporaryChatResultContractV2.SCHEMA, "claims": claims,
                "contradictions": contradictions or []},
        source_refs=source_refs if source_refs is not None else [item.source_ref for item in request.source_refs],
        verification_recommendation="accept",
    )


def test_exact_fifteen_positive_manifest_bound_variants() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    selected = {case.case_id: case for case in cases() if case.case_id in fixture["cases"]}
    assert len(fixture["cases"]) == 15 and len(selected) == 15
    for case_id in fixture["cases"]:
        request = request_for(selected[case_id])
        outcome = TemporaryChatResultContractV2().validate(
            request=request, result=result_for(request, [{"class": "FACT", "fact_handles": ["F1"]}])
        )
        assert outcome.status == "accepted_advanced", (case_id, outcome)
        assert outcome.artifact["claims"][0]["claim_id"] == "C01"


def test_exact_fifteen_contract_variant_matrix() -> None:
    """Every frozen case carries the same positive and negative controls.

    This deliberately tests representation and binding only.  It does not
    infer a missing source from claim wording and it never asks another model
    to repair a rejected artifact.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    selected = {case.case_id: case for case in cases() if case.case_id in fixture["cases"]}
    validator = TemporaryChatResultContractV2()
    accepted = rejected = privacy_rejected = 0
    for case_id in fixture["cases"]:
        request = request_for(selected[case_id])
        positive = (
            {"class": "HYPOTHESIS", "statement": "Wymaga weryfikacji.",
             "support_fact_handles": ["F1"], "contradiction_fact_handles": [],
             "confirm_or_refute": "Sprawdzić w źródle."}
            if case_id in {"B05-action", "X01-synthesis"}
            else {"class": "FACT", "fact_handles": ["F1"]}
        )
        variants = {
            "valid_manifest_bound": (result_for(request, [positive]), "accepted_advanced"),
            "safe_paraphrase": (
                result_for(request, [{"class": "HYPOTHESIS", "statement": "Należy to potwierdzić.",
                                      "support_fact_handles": ["F1"], "contradiction_fact_handles": [],
                                      "confirm_or_refute": "Porównać z materiałem źródłowym."}]),
                "accepted_advanced",
            ),
            "unknown_source": (result_for(request, [{"class": "FACT", "fact_handles": ["F999"]}]), "rejected"),
            "missing_source": (result_for(request, [{"class": "FACT", "fact_handles": []}]), "rejected"),
            "estimate_as_fact": (
                result_for(request, [{"class": "ESTIMATE", "value_or_range": "dokładnie 10 mm",
                                      "confidence": "HIGH", "basis_fact_handles": [],
                                      "basis_tool_handles": [], "assumptions": [], "missing_inputs": []}]),
                "rejected",
            ),
            "wrong_scope": (
                result_for(request, [{"class": "FACT", "fact_handles": ["F1"]}], source_refs=["S8"]),
                "rejected",
            ),
        }
        assert set(variants) == set(fixture["variants_per_case"]) - {"privacy_violation"}
        for name, (result, expected) in variants.items():
            outcome = validator.validate(request=request, result=result)
            assert outcome.status == expected, (case_id, name, outcome)
            if expected == "accepted_advanced":
                accepted += 1
            else:
                rejected += 1
        privacy = result_for(request, [{"class": "FACT", "fact_handles": ["F1"]}])
        privacy.result["leak"] = "case.marker@example.invalid"
        try:
            AnalysisSanitizer().validate_external_result(privacy.model_dump(mode="json"))
        except AnalysisSanitizationError:
            privacy_rejected += 1
        else:
            raise AssertionError((case_id, "privacy_violation_accepted"))
    assert accepted == 30
    assert rejected == 60
    assert privacy_rejected == 15


def test_unknown_missing_and_wrong_scope_sources_fail_closed() -> None:
    case = cases()[0]
    request = request_for(case)
    validator = TemporaryChatResultContractV2()
    unknown = validator.validate(request=request, result=result_for(request, [{"class": "FACT", "fact_handles": ["F999"]}]))
    missing = validator.validate(request=request, result=result_for(request, [{"class": "FACT", "fact_handles": []}]))
    wrong_scope = validator.validate(
        request=request, result=result_for(request, [{"class": "FACT", "fact_handles": ["F1"]}], source_refs=["S8"])
    )
    assert {unknown.status, missing.status, wrong_scope.status} == {"rejected"}


def test_estimate_contract_and_external_claim_id_fail_closed() -> None:
    case = cases()[0]
    request = request_for(case)
    validator = TemporaryChatResultContractV2()
    invalid_estimate = validator.validate(
        request=request,
        result=result_for(request, [{"class": "ESTIMATE", "value_or_range": "10 mm", "confidence": "LOW",
                                     "basis_fact_handles": [], "basis_tool_handles": [], "assumptions": [], "missing_inputs": []}]),
    )
    external_id = validator.validate(
        request=request, result=result_for(request, [{"class": "FACT", "claim_id": "MODEL-1", "fact_handles": ["F1"]}])
    )
    assert invalid_estimate.status == "rejected"
    assert external_id.status == "rejected"


def test_safe_hypothesis_paraphrase_keeps_exact_fact_binding() -> None:
    case = cases()[0]
    request = request_for(case)
    outcome = TemporaryChatResultContractV2().validate(
        request=request,
        result=result_for(request, [{"class": "HYPOTHESIS", "statement": "Wymaga sprawdzenia podczas oględzin.",
                                     "support_fact_handles": ["F1"], "contradiction_fact_handles": [],
                                     "confirm_or_refute": "Zweryfikować na miejscu."}]),
    )
    assert outcome.status == "accepted_advanced"
    assert outcome.artifact["claims"][0]["source_refs"] == ["S1"]


def test_unknown_tool_and_visual_handles_fail_closed() -> None:
    case = cases()[0]
    request = request_for(case)
    validator = TemporaryChatResultContractV2()
    unknown_tool = validator.validate(
        request=request, result=result_for(request, [{"class": "FACT", "fact_handles": [], "tool_handles": ["T1"]}])
    )
    unknown_visual = validator.validate(
        request=request, result=result_for(request, [{"class": "FACT", "fact_handles": [], "visual_handles": ["V1"]}])
    )
    assert unknown_tool.status == "rejected"
    assert unknown_visual.status == "rejected"


def test_out_of_scope_tool_manifest_cannot_create_authority() -> None:
    case = cases()[0]
    claims = [
        {"kind": "FACT", "fact_handle": "F1", "source_handle": "S1", "statement": "fakt"},
        {"kind": "TOOL_RESULT", "tool_handle": "T1", "source_handle": "S8", "statement": "10 mm"},
    ]
    request = request_for(case, claims=claims)
    outcome = TemporaryChatResultContractV2().validate(
        request=request,
        result=result_for(request, [{"class": "FACT", "fact_handles": [], "tool_handles": ["T1"]}]),
    )
    assert outcome.status == "rejected"
    assert outcome.code == "analysis_result_unknown_tool_handle"


def test_material_contradiction_cannot_be_silently_suppressed() -> None:
    case = cases()[0]
    manifest = [
        {"kind": "FACT", "fact_handle": "F1", "source_handle": "S1", "statement": "wersja A", "contradiction_group": "G1"},
        {"kind": "FACT", "fact_handle": "F2", "source_handle": "S1", "statement": "wersja B", "contradiction_group": "G1"},
    ]
    request = request_for(case, claims=manifest)
    hidden = TemporaryChatResultContractV2().validate(
        request=request, result=result_for(request, [{"class": "FACT", "fact_handles": ["F1", "F2"]}])
    )
    disclosed = TemporaryChatResultContractV2().validate(
        request=request, result=result_for(
            request, [{"class": "FACT", "fact_handles": ["F1", "F2"]}],
            contradictions=[{"description": "Źródła są sprzeczne.", "fact_handles": ["F1", "F2"]}],
        )
    )
    assert hidden.status == "rejected"
    assert disclosed.status == "accepted_advanced"


def test_privacy_violation_remains_rejected_before_contract() -> None:
    request = request_for(cases()[0])
    result = result_for(request, [{"class": "FACT", "fact_handles": ["F1"]}])
    result.result["leak"] = "user@example.invalid"
    try:
        AnalysisSanitizer().validate_external_result(result.model_dump(mode="json"))
    except AnalysisSanitizationError:
        return
    raise AssertionError("privacy violation was accepted")


def main() -> None:
    tests = [
        test_exact_fifteen_positive_manifest_bound_variants,
        test_exact_fifteen_contract_variant_matrix,
        test_unknown_missing_and_wrong_scope_sources_fail_closed,
        test_estimate_contract_and_external_claim_id_fail_closed,
        test_safe_hypothesis_paraphrase_keeps_exact_fact_binding,
        test_unknown_tool_and_visual_handles_fail_closed,
        test_out_of_scope_tool_manifest_cannot_create_authority,
        test_material_contradiction_cannot_be_silently_suppressed,
        test_privacy_violation_remains_rejected_before_contract,
    ]
    for test in tests:
        test()
    print(f"TEMP_CHAT_RESULT_CONTRACT_V2=PASS tests={len(tests)}")


if __name__ == "__main__":
    main()
