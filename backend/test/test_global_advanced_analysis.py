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
    require(AnalysisSupervisorClient().bridge_key != VisionSupervisorClient().bridge_key, "HMAC purpose separation failed")
    print("GLOBAL_ADVANCED_ANALYSIS=PASS")
    print("PRIVACY_MATRIX=PASS")
    print("CALCULATION_FIXTURES=30/30")


if __name__ == "__main__": main()
