from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.analysis import AdvancedAnalysisResult, AnalysisRequest
from app.services.analysis_calculation_validator import DeterministicCalculationValidator, CalculationValidationError


@dataclass(frozen=True)
class PostValidationResult:
    status: Literal["accepted_advanced", "review_required", "rejected"]
    code: str


class AnalysisPostValidator:
    def validate(self, *, request: AnalysisRequest, result: AdvancedAnalysisResult, package_sha256: str) -> PostValidationResult:
        if str(result.analysis_id) != str(request.analysis_id) or result.package_sha256 != package_sha256:
            return PostValidationResult("rejected", "analysis_result_binding_invalid")
        allowed = {source.source_ref for source in request.source_refs}
        if not set(result.source_refs).issubset(allowed):
            return PostValidationResult("rejected", "analysis_unknown_source_ref")
        if request.evidence and not result.source_refs:
            return PostValidationResult("review_required", "analysis_insufficient_evidence")
        if result.verification_recommendation == "reject":
            return PostValidationResult("rejected", "analysis_external_rejected")
        if result.verification_recommendation == "review" or result.uncertainties:
            return PostValidationResult("review_required", "analysis_review_required")
        calculator = DeterministicCalculationValidator()
        for unit in result.normalized_units.values():
            try:
                calculator.normalize(1, unit)
            except CalculationValidationError:
                return PostValidationResult("rejected", "analysis_unit_invalid")
        if request.analysis_type == "formula_calculation":
            if not result.formula_used:
                return PostValidationResult("review_required", "analysis_formula_missing")
            expression = request.structured_inputs.get("expression") or (request.formulas[0] if request.formulas else None)
            if isinstance(expression, str):
                compact_expected = "".join(expression.split()).casefold()
                compact_actual = "".join(result.formula_used.split()).casefold()
                if compact_expected != compact_actual:
                    return PostValidationResult("rejected", "analysis_formula_mismatch")
            variables = request.structured_inputs.get("variables")
            if isinstance(expression, str) and isinstance(variables, dict):
                try:
                    recalculated = calculator.evaluate(expression, variables)
                except (CalculationValidationError, TypeError, ZeroDivisionError):
                    return PostValidationResult("rejected", "analysis_deterministic_recalculation_failed")
                actual = result.result.get("value")
                if not isinstance(actual, (int, float)) or not calculator.compare(recalculated, float(actual)):
                    return PostValidationResult("rejected", "analysis_deterministic_recalculation_failed")
            expected = request.structured_inputs.get("expected_result")
            if expected is not None:
                actual = result.result.get("value")
                if not isinstance(actual, (int, float)) or abs(float(actual) - float(expected)) > max(1e-9, abs(float(expected)) * 1e-6):
                    return PostValidationResult("rejected", "analysis_deterministic_recalculation_failed")
        return PostValidationResult("accepted_advanced", "analysis_advanced_accepted")
