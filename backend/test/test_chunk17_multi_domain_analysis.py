from __future__ import annotations

import hashlib
from uuid import uuid4

from pydantic import ValidationError

from app.schemas.analysis import (
    AdvancedAnalysisResult,
    AnalysisProvenance,
    AnalysisRequest,
    AnalysisSourceRef,
)
from app.services.analysis_calculation_validator import (
    CalculationValidationError,
    DeterministicCalculationValidator,
)
from app.services.analysis_post_validator import AnalysisPostValidator
from app.services.analysis_processors import AnalysisProcessorRegistry
from app.services.analysis_quality_gate import AnalysisQualityGate
from app.services.analysis_sanitizer import AnalysisSanitizationError, AnalysisSanitizer


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def make_request(
    analysis_type: str,
    *,
    structured_inputs: dict | None = None,
    units: dict[str, str] | None = None,
    sensitivity: str = "public_reference",
    source_count: int = 1,
    pages: bool = True,
) -> AnalysisRequest:
    sources = []
    for index in range(source_count):
        text = f"Synthetic public technical evidence {index + 1}: R = U / I."
        sources.append(AnalysisSourceRef(
            source_ref=f"S{index + 1}", checksum_sha256=hashlib.sha256(text.encode()).hexdigest(),
            page=index + 1 if pages else None, excerpt=text, extraction_confidence=99,
        ))
    checksum = hashlib.sha256("".join(source.checksum_sha256 for source in sources).encode()).hexdigest()
    return AnalysisRequest(
        analysis_id=uuid4(), analysis_type=analysis_type,
        source_domain="calculation" if analysis_type == "formula_calculation" else "technical",
        source_refs=sources, problem_statement="Analyze the bounded synthetic technical fixture.",
        structured_inputs=structured_inputs or {}, units=units or {}, formulas=[], constraints=[],
        evidence=[source.source_ref for source in sources], sensitivity=sensitivity,
        allowed_methods=["deterministic_parse", "deterministic_calculation", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum=checksum),
    )


def calculation_matrix() -> None:
    validator = DeterministicCalculationValidator()
    fixtures = [
        ("a+b", {"a": 1, "b": 2}, 3), ("a-b", {"a": 8, "b": 3}, 5),
        ("a*b", {"a": 6, "b": 7}, 42), ("a/b", {"a": 12, "b": 4}, 3),
        ("a**2", {"a": 5}, 25), ("(a+b)*c", {"a": 2, "b": 3, "c": 4}, 20),
        ("a+b*c", {"a": 2, "b": 3, "c": 4}, 14), ("-a+b", {"a": 2, "b": 5}, 3),
        ("a/2+b", {"a": 10, "b": 1}, 6), ("a*b/2", {"a": 4, "b": 5}, 10),
        ("a+b-c", {"a": 10, "b": 4, "c": 3}, 11), ("a*(b-c)", {"a": 3, "b": 8, "c": 2}, 18),
        ("a**3", {"a": 2}, 8), ("a/b*c", {"a": 12, "b": 3, "c": 2}, 8),
        ("(a+b)/(c+d)", {"a": 2, "b": 4, "c": 1, "d": 2}, 2),
        ("x+y", {"x": .1, "y": .2}, .3), ("x*1000", {"x": 1.5}, 1500),
        ("x/1000", {"x": 2500}, 2.5), ("x-y", {"x": -2, "y": 3}, -5),
        ("x*y+z", {"x": 2, "y": 5, "z": 1}, 11), ("x*(y+z)", {"x": 2, "y": 5, "z": 1}, 12),
        ("x**2+y**2", {"x": 3, "y": 4}, 25), ("load/area", {"load": 600, "area": 3}, 200),
        ("u/i", {"u": 230, "i": 10}, 23), ("length*width", {"length": 4, "width": 2.5}, 10),
        ("force/1000", {"force": 5000}, 5), ("pressure*area", {"pressure": 2, "area": 3}, 6),
        ("a+b+b", {"a": 1, "b": 2}, 5), ("(a-b)**2", {"a": 7, "b": 2}, 25),
        ("a/(b+c)", {"a": 20, "b": 2, "c": 3}, 4), ("a*0.01", {"a": 15}, .15),
        ("a/60", {"a": 120}, 2), ("a*3.6", {"a": 10}, 36),
        ("a/(b*b)", {"a": 100, "b": 2}, 25), ("(a+b+c)/3", {"a": 3, "b": 6, "c": 9}, 6),
        ("a*(1+b)", {"a": 200, "b": .05}, 210),
    ]
    require(len(fixtures) >= 30, "fewer than 30 deterministic calculations")
    for expression, variables, expected in fixtures:
        require(validator.compare(validator.evaluate(expression, variables), expected), expression)
    pressure = validator.evaluate_checked("force/area", {"force": 12, "area": .4},
                                          {"force": "kN", "area": "m2"}, "kPa")
    require(validator.compare(pressure.value, 30) and pressure.unit == "kPa", "pressure units")
    percent = validator.evaluate_checked("part/whole", {"part": 25, "whole": 100},
                                         {"part": "kg", "whole": "kg"}, "%")
    require(validator.compare(percent.value, 25), "percentage conversion")
    require(validator.evaluate_checked("length", {"length": 1000}, {"length": "mm"}, "m").value == 1,
            "SI prefix conversion")
    invalid = [
        lambda: validator.evaluate_checked("force/area", {"force": 1}, {"force": "N"}, "Pa"),
        lambda: validator.evaluate_checked("force+area", {"force": 1, "area": 1},
                                           {"force": "N", "area": "m2"}, "N"),
        lambda: validator.evaluate("a/b", {"a": 1, "b": 0}),
        lambda: validator.evaluate_checked("a", {"a": float("inf")}, {"a": "m"}, "m"),
    ]
    for action in invalid:
        try:
            action()
        except (CalculationValidationError, ZeroDivisionError):
            pass
        else:
            raise AssertionError("invalid calculation accepted")


def privacy_matrix() -> None:
    sanitizer = AnalysisSanitizer()
    attacks = [
        "Jan Kowalski", "jan@example.pl", "+48 500 600 700", "ul. Testowa 12",
        "Acme Engineering Sp. z o.o.", "client_id=123", r"C:\\private\\fixture.txt",
        "/data/private/fixture.txt", "http://10.0.0.8/private", "Bearer abc.def.secret",
        "api_key=super-secret-value",
    ]
    for attack in attacks:
        req = make_request("technical_interpretation", sensitivity="customer_sanitizable")
        req.problem_statement = f"Parametr 20 MPa; {attack}"
        try:
            package = sanitizer.sanitize(req)
        except AnalysisSanitizationError:
            continue
        require(attack not in package.canonical_json, f"sensitive value remained: {attack}")
    nested = make_request("table_analysis", sensitivity="customer_sanitizable", structured_inputs={
        "tables": [[["Header", "Wartość"], ["Jan Kowalski", "jan@example.pl"]]],
        "variables": {"Jan Kowalski": "+48 500 600 700"},
        "claims": [{"key": "owner", "value": "Acme Engineering Sp. z o.o.", "source_ref": "S1"}],
        "requested_output": "Usuń C:\\private\\x.txt i sprawdź wynik.",
    })
    package = sanitizer.sanitize(nested)
    for forbidden in ("Jan Kowalski", "jan@example.pl", "500 600 700", "Acme Engineering"):
        require(forbidden not in package.canonical_json, f"nested PII remained: {forbidden}")
    forbidden_key = make_request("technical_interpretation", structured_inputs={"customer_name": "Example"})
    try:
        sanitizer.sanitize(forbidden_key)
    except AnalysisSanitizationError:
        pass
    else:
        raise AssertionError("sensitive metadata key accepted")
    restricted = make_request("technical_interpretation", sensitivity="restricted_never_external")
    try:
        sanitizer.sanitize(restricted)
    except AnalysisSanitizationError:
        pass
    else:
        raise AssertionError("restricted input externalized")


def domain_matrix() -> None:
    registry = AnalysisProcessorRegistry.canonical()
    gate = AnalysisQualityGate()
    formula = make_request("formula_calculation", structured_inputs={
        "expression": "force/area", "variables": {"force": 12, "area": .4}, "result_unit": "kPa",
    }, units={"force": "kN", "area": "m2"})
    local = registry.process(formula)
    require(local.result["value"] == 30 and gate.evaluate(formula, local).decision == "ACCEPT_LOCAL", "formula")
    technical = make_request("technical_interpretation")
    require(gate.evaluate(technical, registry.process(technical)).decision == "ACCEPT_LOCAL", "technical")
    document = make_request("document_interpretation", source_count=2)
    require(all(item["page"] for item in registry.process(document).result["page_refs"]), "document provenance")
    table = make_request("table_analysis", structured_inputs={
        "tables": [[["Pressure", "Area"], [30, .4], [40, .5], [40, .5]]],
    })
    table_result = registry.process(table)
    require(table_result.result["tables"][0]["duplicate_rows"] == 1, "table duplicates")
    require(table_result.result["tables"][0]["numeric_columns"]["Pressure"]["sum"] == 110, "table aggregate")
    standards = make_request("standards_comparison", source_count=2, structured_inputs={
        "standards": [
            {"identity": "SYN-100", "version": "2025", "effective_date": "2025-01-01", "status": "superseded", "source_ref": "S1", "clause": "4"},
            {"identity": "SYN-100", "version": "2026", "effective_date": "2026-01-01", "status": "current", "source_ref": "S2", "clause": "4"},
        ],
    })
    standards_result = registry.process(standards).result
    require(standards_result["coverage_complete"] and standards_result["differences"], "standards metadata")
    claims = make_request("consistency_check", source_count=2, structured_inputs={
        "claims": [{"key": "pressure", "value": "30 kPa", "source_ref": "S1"},
                   {"key": "pressure", "value": "35 kPa", "source_ref": "S2"}],
    })
    require(len(registry.process(claims).result["conflicts"]) == 1, "consistency conflict")
    visual = make_request("visual_analysis", structured_inputs={"vision_result": {"classification": "diagram"}})
    require(gate.evaluate(visual, registry.process(visual)).decision == "ACCEPT_LOCAL", "visual adapter")
    missing_visual = make_request("visual_analysis")
    require(gate.evaluate(missing_visual, registry.process(missing_visual)).decision == "ESCALATE_TEMP_CHAT",
            "visual limitation did not use shared gate")


def contract_matrix() -> None:
    sanitizer = AnalysisSanitizer()
    request = make_request("formula_calculation", structured_inputs={
        "expression": "u/i", "variables": {"u": 230, "i": 10}, "expected_result": 23,
    })
    request.formulas = ["u/i"]
    package = sanitizer.sanitize(request)
    require(package.package.sources[0].source_sha256 == request.source_refs[0].checksum_sha256,
            "source hash binding")
    valid = AdvancedAnalysisResult(
        schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1", analysis_id=request.analysis_id,
        package_sha256=package.sha256, result={"value": 23}, source_refs=["S1"], formula_used="u/i",
        verification_recommendation="accept",
    )
    post = AnalysisPostValidator()
    require(post.validate(request=request, result=valid, package_sha256=package.sha256).status == "accepted_advanced",
            "advanced formula rejected")
    unknown = valid.model_copy(update={"source_refs": ["S8"]})
    require(post.validate(request=request, result=unknown, package_sha256=package.sha256).status == "rejected",
            "unknown source ref accepted")
    wrong = valid.model_copy(update={"result": {"value": 24}})
    require(post.validate(request=request, result=wrong, package_sha256=package.sha256).status == "rejected",
            "calculation disagreement accepted")
    try:
        AdvancedAnalysisResult.model_validate({**valid.model_dump(mode="json"), "unknown": True})
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown result field accepted")
    oversized = make_request("technical_interpretation")
    oversized.formulas = ["x" * 3000] * 32
    try:
        sanitizer.sanitize(oversized)
    except AnalysisSanitizationError as error:
        require(str(error) == "analysis_package_too_large", "wrong package limit error")
    else:
        raise AssertionError("oversized package silently truncated")


def main() -> None:
    calculation_matrix()
    privacy_matrix()
    domain_matrix()
    contract_matrix()
    print("CHUNK17_MULTI_DOMAIN_ANALYSIS=PASS")
    print("CALCULATION_FIXTURES=36/36")
    print("PRIVACY_ATTACK_MATRIX=PASS")
    print("DOMAIN_ADAPTERS=7/7")


if __name__ == "__main__":
    main()
