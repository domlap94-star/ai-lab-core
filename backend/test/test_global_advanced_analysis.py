from __future__ import annotations

import hashlib
from uuid import uuid4

from app.schemas.analysis import (AdvancedAnalysisResult, AnalysisProvenance,
    AnalysisQualitySignals, AnalysisRequest, AnalysisSourceRef,
    DeterministicCheck, LocalAnalysisResult)
from app.services.analysis_calculation_validator import CalculationValidationError, DeterministicCalculationValidator
from app.services.analysis_post_validator import AnalysisPostValidator
from app.services.analysis_quality_gate import AnalysisQualityGate
from app.services.analysis_sanitizer import AnalysisSanitizationError, AnalysisSanitizer
from app.services.analysis_supervisor_client import AnalysisSupervisorClient
from app.services.vision_supervisor_client import VisionSupervisorClient


def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def request(*, sensitivity="public_reference", analysis_type="technical_interpretation", text="Wzór R = U / I, jednostki V i A.", inputs=None) -> AnalysisRequest:
    checksum = hashlib.sha256(text.encode()).hexdigest()
    return AnalysisRequest(analysis_id=uuid4(), analysis_type=analysis_type, source_domain="knowledge_base",
        source_refs=[AnalysisSourceRef(source_ref="S1", checksum_sha256=checksum, page=1, excerpt=text, extraction_confidence=98)],
        problem_statement="Przeanalizuj materiał techniczny.", structured_inputs=inputs or {}, units={}, formulas=[], constraints=[], evidence=["S1"],
        sensitivity=sensitivity, allowed_methods=["deterministic_parse", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum=checksum))


def local(req: AnalysisRequest, **signal_patch) -> LocalAnalysisResult:
    signals = AnalysisQualitySignals(**signal_patch)
    return LocalAnalysisResult(analysis_id=req.analysis_id, processor_id="test", processor_version="v1", result={"ok": True}, evidence_refs=["S1"],
        assumptions=[], unresolved_questions=[], detected_constraints=[], normalized_units={},
        deterministic_checks=[DeterministicCheck(name="fixture", passed=True)], quality_signals=signals,
        limitations=[], confidence="low" if signal_patch.get("model_uncertain") else "high")


def main() -> None:
    gate = AnalysisQualityGate()
    easy = request(); require(gate.evaluate(easy, local(easy)).decision == "ACCEPT_LOCAL", "easy local analysis escalated")
    hard = request(); require(gate.evaluate(hard, local(hard, model_uncertain=True)).decision == "ESCALATE_TEMP_CHAT", "hard analysis did not escalate")
    missing = request(); require(gate.evaluate(missing, local(missing, missing_evidence=True, insufficient_evidence=True)).decision == "REVIEW_REQUIRED", "missing evidence guessed")
    restricted = request(sensitivity="restricted_never_external"); require(gate.evaluate(restricted, local(restricted, model_uncertain=True)).decision == "REVIEW_REQUIRED", "restricted data externalized")
    internal_easy = request(sensitivity="internal_non_sensitive"); require(gate.evaluate(internal_easy, local(internal_easy)).decision == "ACCEPT_LOCAL", "internal local result rejected")
    internal_hard = request(sensitivity="internal_non_sensitive"); require(gate.evaluate(internal_hard, local(internal_hard, model_uncertain=True)).decision == "REVIEW_REQUIRED", "internal data externalized")

    sanitizer = AnalysisSanitizer()
    pii = request(sensitivity="customer_sanitizable", text="Klient: Jan Kowalski, email jan@example.com, telefon +48 500 600 700, ul. Testowa 4, CRM_ID=123. Parametr 20 MPa.")
    clean = sanitizer.sanitize(pii)
    for forbidden in ("Jan Kowalski", "jan@example.com", "500 600 700", "Testowa 4", "CRM_ID"):
        require(forbidden not in clean.canonical_json, f"PII remained: {forbidden}")
    require(clean.package.sources[0].source_ref == "S1", "opaque source ref changed")
    technical = sanitizer.sanitize(request(text="Moduł Younga E = 30 MPa według PN-EN 1992."))
    require("Younga" in technical.canonical_json and "PN-EN 1992" in technical.canonical_json, "technical false positive")
    structured = sanitizer.sanitize(request(
        sensitivity="customer_sanitizable",
        text="Parametr techniczny 20 MPa.",
        inputs={"tables": [[["jan@example.com", "+48 500 600 700"]]],
                "requested_output": "Notatka klienta: prywatne ustalenia; oblicz parametr."},
    ))
    require("jan@example.com" not in structured.canonical_json and "500 600 700" not in structured.canonical_json,
            "structured PII remained")
    require("prywatne ustalenia" not in structured.canonical_json, "free-form customer note remained")
    phone_positives = [
        "+48 500 000 017", "+48500000017", "500 000 017", "500-000-017",
        "+48 (500) 000 017", "0048 500 000 017", "22 123 45 67",
    ]
    phone_negatives = [
        "3,000,000 Pa", "3 000 000 Pa", "2,000,000 Pa", "2 000 000 Pa",
        "3.000 MPa", "2.000 MPa", "0.005 m²", "0.004 m2", "12,000 N",
        "10,000 N", "1 250.50", "1,250.50", "1024 / Cosine", "57 / 57",
        "2026-08-22", "1.0.2+26", "sha256:1234567890abcdef",
        "12 kN / 0.004 m² = 3 MPa", "10 kN / 0.005 m² = 2 MPa",
        "12 kN / 0.004 m² = 3,000,000 Pa = 3 MPa",
        "100 000 000 Pa", "100000000 N", "100 000 000 %",
    ]
    for value in phone_positives:
        require("PHONE" in sanitizer.detect_sensitive_kinds(value), f"phone missed: {value}")
    for value in phone_negatives:
        require("PHONE" not in sanitizer.detect_sensitive_kinds(value), f"technical number flagged: {value}")
    require("PHONE" in sanitizer.detect_sensitive_kinds(
        {"result": "3 MPa.", "calculation_steps": ["Contact: +48 500 000 017."]}
    ), "phone in technical result missed")
    clean_result = {
        "result": {"value": 3, "unit": "MPa"},
        "assumptions": [], "uncertainties": [],
        "calculation_steps": ["12 kN / 0.004 m² = 3,000,000 Pa = 3 MPa"],
        "normalized_units": {"force": "N", "area": "m²"},
        "constraints_checked": ["finite result"], "source_refs": ["S1"],
    }
    require(not sanitizer.detect_sensitive_kinds(clean_result), "clean technical result rejected")
    sanitizer.validate_external_result(clean_result)
    reintroduced = {
        "result": "Test Company Alpha; Jan Testowy; test@example.invalid; +48 500 000 017; "
                  "ul. Testowa 1; client_id=999999",
    }
    detected = sanitizer.detect_sensitive_kinds(reintroduced)
    require({"EMAIL", "PHONE", "ADDRESS", "INTERNAL_ID"}.issubset(detected),
            "reintroduced identifier matrix not detected")
    try: sanitizer.validate_external_result(reintroduced)
    except AnalysisSanitizationError: pass
    else: raise AssertionError("reintroduced identifiers accepted")
    try: sanitizer.sanitize(request(text="password=VerySecret123"))
    except AnalysisSanitizationError: pass
    else: raise AssertionError("secret accepted")
    try: sanitizer.sanitize(restricted)
    except AnalysisSanitizationError: pass
    else: raise AssertionError("restricted package accepted")

    validator = DeterministicCalculationValidator()
    fixtures = [
        ("a+b",{"a":1,"b":2},3),("a-b",{"a":8,"b":3},5),("a*b",{"a":6,"b":7},42),("a/b",{"a":12,"b":4},3),
        ("a**2",{"a":5},25),("(a+b)*c",{"a":2,"b":3,"c":4},20),("a+b*c",{"a":2,"b":3,"c":4},14),("-a+b",{"a":2,"b":5},3),
        ("a/2+b",{"a":10,"b":1},6),("a*b/2",{"a":4,"b":5},10),("a+b-c",{"a":10,"b":4,"c":3},11),("a*(b-c)",{"a":3,"b":8,"c":2},18),
        ("a**3",{"a":2},8),("a/b*c",{"a":12,"b":3,"c":2},8),("(a+b)/(c+d)",{"a":2,"b":4,"c":1,"d":2},2),
        ("x+y",{"x":0.1,"y":0.2},0.3),("x*1000",{"x":1.5},1500),("x/1000",{"x":2500},2.5),("x-y",{"x":-2,"y":3},-5),
        ("x*y+z",{"x":2,"y":5,"z":1},11),("x*(y+z)",{"x":2,"y":5,"z":1},12),("x**2+y**2",{"x":3,"y":4},25),
        ("load/area",{"load":600,"area":3},200),("u/i",{"u":230,"i":10},23),("length*width",{"length":4,"width":2.5},10),
        ("force/1000",{"force":5000},5),("pressure*area",{"pressure":2,"area":3},6),("a+b+b",{"a":1,"b":2},5),
        ("(a-b)**2",{"a":7,"b":2},25),("a/(b+c)",{"a":20,"b":2,"c":3},4),
    ]
    require(len(fixtures) == 30, "calculation fixture count")
    for expression, variables, expected in fixtures:
        first = validator.evaluate(expression, variables); second = validator.evaluate(expression, variables)
        require(validator.compare(first, expected) and validator.compare(first, second), f"calculation failed: {expression}")
    require(validator.normalize(1000, "mm").value == 1 and validator.normalize(1, "kN").value == 1000, "unit normalization failed")
    try: validator.normalize(1, "unknown")
    except CalculationValidationError: pass
    else: raise AssertionError("unknown unit accepted")
    try: validator.evaluate("__import__('os')", {})
    except CalculationValidationError: pass
    else: raise AssertionError("unsafe expression accepted")

    calc = request(analysis_type="formula_calculation", inputs={"expression":"u/i","variables":{"u":230,"i":10},"expected_result":23})
    package = sanitizer.sanitize(calc)
    result = AdvancedAnalysisResult(schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1", analysis_id=calc.analysis_id,
        package_sha256=package.sha256, result={"value":23}, source_refs=["S1"], assumptions=[], uncertainties=[], constraints_checked=[], normalized_units={}, formula_used="u/i", calculation_steps=["230 / 10 = 23"], verification_recommendation="accept")
    require(AnalysisPostValidator().validate(request=calc,result=result,package_sha256=package.sha256).status == "accepted_advanced", "valid advanced calculation rejected")
    wrong = result.model_copy(update={"result":{"value":24}})
    require(AnalysisPostValidator().validate(request=calc,result=wrong,package_sha256=package.sha256).status == "rejected", "wrong calculation accepted")
    pressure = request(
        analysis_type="formula_calculation",
        text="Synthetic pressure rule P = F / A.",
        inputs={"expression": "force/area", "variables": {"force": 12, "area": .004},
                "values": {"force": 12, "area": .004}, "expected_result": 3,
                "result_unit": "MPa"},
    )
    pressure.units = {"force": "kN", "area": "m2"}
    pressure.formulas = ["force/area"]
    pressure_package = sanitizer.sanitize(pressure)
    pressure_result = AdvancedAnalysisResult(
        schema_version="NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1",
        analysis_id=pressure.analysis_id, package_sha256=pressure_package.sha256,
        result={"value": 3, "unit": "MPa"}, source_refs=["S1"], assumptions=[],
        uncertainties=[], constraints_checked=[], normalized_units={"pressure": "MPa"},
        formula_used="force/area",
        calculation_steps=["12 kN / 0.004 m² = 3,000,000 Pa = 3 MPa"],
        verification_recommendation="accept",
    )
    sanitizer.validate_external_result(pressure_result.model_dump(mode="json"))
    require(AnalysisPostValidator().validate(
        request=pressure, result=pressure_result, package_sha256=pressure_package.sha256,
    ).status == "accepted_advanced", "clean pressure calculation rejected")
    require(AnalysisSupervisorClient().bridge_key != VisionSupervisorClient().bridge_key, "HMAC purpose separation failed")
    print("GLOBAL_ADVANCED_ANALYSIS=PASS")
    print("PRIVACY_MATRIX=PASS")
    print("CALCULATION_FIXTURES=30/30")


if __name__ == "__main__": main()
