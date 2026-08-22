from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from app.schemas.analysis import (
    AnalysisQualitySignals,
    AnalysisRequest,
    DeterministicCheck,
    LocalAnalysisResult,
)
from app.services.analysis_calculation_validator import (
    CalculationValidationError,
    DeterministicCalculationValidator,
)


class AnalysisProcessor(Protocol):
    analysis_type: str

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult: ...


def _result(
    request: AnalysisRequest,
    processor: str,
    payload: dict,
    *,
    checks: list[DeterministicCheck],
    signals: AnalysisQualitySignals | None = None,
    assumptions: list[str] | None = None,
    unresolved: list[str] | None = None,
    limitations: list[str] | None = None,
    confidence: str = "high",
) -> LocalAnalysisResult:
    return LocalAnalysisResult(
        analysis_id=request.analysis_id,
        processor_id=processor,
        processor_version="v1",
        result=payload,
        evidence_refs=[source.source_ref for source in request.source_refs],
        assumptions=assumptions or [],
        unresolved_questions=unresolved or [],
        detected_constraints=request.constraints,
        normalized_units=request.units,
        deterministic_checks=checks,
        quality_signals=signals or AnalysisQualitySignals(),
        limitations=limitations or [],
        confidence=confidence,
    )


class FormulaCalculationProcessor:
    analysis_type = "formula_calculation"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        validator = DeterministicCalculationValidator()
        expression = request.structured_inputs.get("expression")
        variables = request.structured_inputs.get("variables")
        result_unit = request.structured_inputs.get("result_unit")
        checks: list[DeterministicCheck] = []
        if not isinstance(expression, str) or not isinstance(variables, dict):
            return _result(
                request, "formula_calculation", {},
                checks=[DeterministicCheck(name="required_inputs", passed=False, code="analysis_variable_missing")],
                signals=AnalysisQualitySignals(unresolved_variables=True, unsupported_operation=True),
                unresolved=["Brak wzoru lub wartości zmiennych."], confidence="indeterminate",
            )
        try:
            numeric_variables = {key: float(value) for key, value in variables.items()}
            calculated = validator.evaluate_checked(expression, numeric_variables, request.units, result_unit)
            checks.extend([
                DeterministicCheck(name="variables_complete", passed=True),
                DeterministicCheck(name="unit_dimensions", passed=True),
                DeterministicCheck(name="finite_result", passed=True),
            ])
            minimum = request.structured_inputs.get("minimum")
            maximum = request.structured_inputs.get("maximum")
            in_range = ((minimum is None or calculated.value >= float(minimum))
                        and (maximum is None or calculated.value <= float(maximum)))
            checks.append(DeterministicCheck(
                name="range_constraints", passed=in_range,
                code=None if in_range else "analysis_range_constraint_failed",
            ))
            signals = AnalysisQualitySignals(deterministic_check_failed=not in_range)
            return _result(
                request, "formula_calculation",
                {"value": calculated.value, "unit": calculated.unit, "formula": expression,
                 "variables": numeric_variables},
                checks=checks, signals=signals,
                limitations=[] if in_range else ["Wynik narusza jawny zakres."],
                confidence="high" if in_range else "low",
            )
        except (CalculationValidationError, TypeError, ValueError, ZeroDivisionError) as error:
            code = str(error) if str(error).startswith("analysis_") else "analysis_formula_invalid"
            return _result(
                request, "formula_calculation", {},
                checks=[DeterministicCheck(name="deterministic_calculation", passed=False, code=code)],
                signals=AnalysisQualitySignals(
                    unresolved_variables=code == "analysis_variable_missing",
                    unit_ambiguity=code in {"analysis_unit_invalid", "analysis_dimension_mismatch"},
                    invalid_formula=code == "analysis_formula_invalid",
                    deterministic_check_failed=True,
                ),
                unresolved=[code], confidence="indeterminate",
            )


class TechnicalInterpretationProcessor:
    analysis_type = "technical_interpretation"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        facts = [source.excerpt.strip() for source in request.source_refs if source.excerpt.strip()]
        missing = list(request.structured_inputs.get("missing_information") or [])
        assumptions = list(request.structured_inputs.get("assumptions") or [])
        coverage = len(facts) / len(request.source_refs) if request.source_refs else 0
        sufficient = bool(facts) and coverage >= .8
        return _result(
            request, "technical_interpretation",
            {"facts": facts, "inferences": [], "missing_information": missing,
             "assumptions": assumptions, "recommended_verification": bool(missing)},
            checks=[DeterministicCheck(name="evidence_coverage", passed=sufficient,
                                       code=None if sufficient else "analysis_insufficient_evidence")],
            signals=AnalysisQualitySignals(
                missing_evidence=not bool(facts), source_coverage=coverage,
                insufficient_evidence=not sufficient,
            ), assumptions=assumptions, unresolved=missing,
            confidence="high" if sufficient and not missing else "medium",
        )


class DocumentInterpretationProcessor(TechnicalInterpretationProcessor):
    analysis_type = "document_interpretation"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        local = super().analyze(request)
        pages_present = all(source.page is not None for source in request.source_refs)
        checks = list(local.deterministic_checks) + [
            DeterministicCheck(name="page_provenance", passed=pages_present,
                               code=None if pages_present else "analysis_page_provenance_missing")
        ]
        signals = local.quality_signals.model_copy(update={
            "insufficient_evidence": local.quality_signals.insufficient_evidence or not pages_present,
        })
        return local.model_copy(update={
            "processor_id": "document_interpretation",
            "result": {**local.result, "page_refs": [
                {"source_ref": source.source_ref, "page": source.page}
                for source in request.source_refs
            ]},
            "deterministic_checks": checks,
            "quality_signals": signals,
            "confidence": "high" if pages_present and local.confidence == "high" else "medium",
        })


class TableAnalysisProcessor:
    analysis_type = "table_analysis"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        tables = request.structured_inputs.get("tables")
        if not isinstance(tables, list) or not tables:
            return _result(
                request, "table_analysis", {},
                checks=[DeterministicCheck(name="table_present", passed=False, code="analysis_table_missing")],
                signals=AnalysisQualitySignals(unsupported_operation=True, insufficient_evidence=True),
                unresolved=["Brak tabeli."], confidence="indeterminate",
            )
        summaries = []
        valid = True
        unit_checks = True
        calculator = DeterministicCalculationValidator()
        for unit in request.units.values():
            try:
                calculator.normalize(1, unit)
            except CalculationValidationError:
                unit_checks = False
        for index, table in enumerate(tables):
            if not isinstance(table, list) or len(table) < 2 or not all(isinstance(row, list) for row in table):
                valid = False; summaries.append({"table": index, "error": "shape"}); continue
            width = len(table[0])
            rectangular = width > 0 and all(len(row) == width for row in table)
            headers = table[0]
            header_valid = rectangular and all(isinstance(value, str) and value.strip() for value in headers)
            missing = sum(value is None or value == "" for row in table[1:] for value in row)
            duplicates = len(table[1:]) - len({tuple(str(value) for value in row) for row in table[1:]})
            numeric_columns: dict[str, dict[str, float]] = {}
            if rectangular and header_valid:
                for column, header in enumerate(headers):
                    values = [row[column] for row in table[1:]]
                    if values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                        numeric_columns[str(header)] = {
                            "sum": float(sum(values)), "minimum": float(min(values)),
                            "maximum": float(max(values)), "count": len(values),
                        }
            table_valid = rectangular and header_valid
            valid = valid and table_valid
            summaries.append({"table": index, "rows": len(table) - 1, "columns": width,
                              "missing_values": missing, "duplicate_rows": duplicates,
                              "numeric_columns": numeric_columns})
        valid = valid and unit_checks
        return _result(
            request, "table_analysis", {"tables": summaries},
            checks=[
                DeterministicCheck(name="table_shape_headers", passed=valid,
                                   code=None if valid else "analysis_table_invalid"),
                DeterministicCheck(name="table_units", passed=unit_checks,
                                   code=None if unit_checks else "analysis_unit_invalid"),
            ],
            signals=AnalysisQualitySignals(deterministic_check_failed=not valid),
            confidence="high" if valid else "indeterminate",
        )


class StandardsComparisonProcessor:
    analysis_type = "standards_comparison"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        standards = request.structured_inputs.get("standards")
        allowed = {source.source_ref for source in request.source_refs}
        valid = isinstance(standards, list) and len(standards) >= 2
        normalized = []
        if valid:
            for standard in standards:
                if not isinstance(standard, dict): valid = False; continue
                required = {"identity", "version", "effective_date", "status", "source_ref"}
                entry_valid = required.issubset(standard) and standard.get("source_ref") in allowed
                entry_valid = entry_valid and standard.get("status") in {"current", "superseded"}
                valid = valid and entry_valid
                normalized.append({key: standard.get(key) for key in sorted(required | {"clause", "criteria"})})
        differences = []
        conflicts = []
        comparison_fields = ("version", "effective_date", "status", "clause", "criteria")
        for first_index, first in enumerate(normalized):
            for second in normalized[first_index + 1:]:
                changed = {field: [first.get(field), second.get(field)] for field in comparison_fields
                           if first.get(field) != second.get(field)}
                if changed:
                    differences.append({"sources": [first.get("source_ref"), second.get("source_ref")],
                                        "differences": changed})
                if (first.get("identity") == second.get("identity")
                        and first.get("status") == second.get("status") == "current"
                        and first.get("criteria") != second.get("criteria")):
                    conflicts.append({"identity": first.get("identity"),
                                      "sources": [first.get("source_ref"), second.get("source_ref")],
                                      "reason": "conflicting_current_criteria"})
        return _result(
            request, "standards_comparison", {"standards": normalized, "differences": differences,
                                               "conflicts": conflicts, "coverage_complete": valid},
            checks=[DeterministicCheck(name="standard_identity_version_status", passed=valid,
                                       code=None if valid else "analysis_standard_metadata_missing")],
            signals=AnalysisQualitySignals(insufficient_evidence=not valid, source_coverage=1.0 if valid else 0.0),
            unresolved=[] if valid else ["Niepełna tożsamość, wersja, status lub źródło normy."],
            confidence="high" if valid else "indeterminate",
        )


class ConsistencyCheckProcessor:
    analysis_type = "consistency_check"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        claims = request.structured_inputs.get("claims")
        allowed = {source.source_ref for source in request.source_refs}
        valid = isinstance(claims, list) and bool(claims)
        grouped: dict[str, list[dict]] = defaultdict(list)
        if valid:
            for claim in claims:
                if (not isinstance(claim, dict) or not {"key", "value", "source_ref"}.issubset(claim)
                        or claim["source_ref"] not in allowed):
                    valid = False; continue
                grouped[str(claim["key"]).strip().casefold()].append(claim)
        conflicts, consistent = [], []
        for key, values in grouped.items():
            variants = {str(value["value"]).strip().casefold() for value in values}
            target = conflicts if len(variants) > 1 else consistent
            target.append({"key": key, "claims": values, "severity": "material" if len(variants) > 1 else "none"})
        return _result(
            request, "consistency_check",
            {"consistent_claims": consistent, "conflicts": conflicts,
             "missing_evidence": [] if valid else ["invalid_claim_source"]},
            checks=[DeterministicCheck(name="claim_source_integrity", passed=valid,
                                       code=None if valid else "analysis_unknown_source_ref")],
            signals=AnalysisQualitySignals(unknown_source_refs=not valid, source_coverage=1.0 if valid else 0.0),
            confidence="high" if valid else "indeterminate",
        )


class VisualAnalysisProcessor:
    analysis_type = "visual_analysis"

    def analyze(self, request: AnalysisRequest) -> LocalAnalysisResult:
        existing = request.structured_inputs.get("vision_result")
        if not isinstance(existing, dict):
            return _result(
                request, "visual_analysis", {},
                checks=[DeterministicCheck(name="canonical_vision_result", passed=False,
                                           code="analysis_vision_result_missing")],
                signals=AnalysisQualitySignals(unsupported_operation=True),
                unresolved=["Brak kanonicznego wyniku Vision."], confidence="indeterminate",
            )
        return _result(
            request, "visual_analysis", {"vision_result": existing},
            checks=[DeterministicCheck(name="canonical_vision_result", passed=True)],
            confidence="high",
        )


@dataclass(frozen=True)
class AnalysisProcessorRegistry:
    processors: dict[str, AnalysisProcessor]

    @classmethod
    def canonical(cls) -> "AnalysisProcessorRegistry":
        values: list[AnalysisProcessor] = [
            FormulaCalculationProcessor(), TechnicalInterpretationProcessor(),
            DocumentInterpretationProcessor(), TableAnalysisProcessor(),
            StandardsComparisonProcessor(), ConsistencyCheckProcessor(),
            VisualAnalysisProcessor(),
        ]
        return cls({processor.analysis_type: processor for processor in values})

    def process(self, request: AnalysisRequest) -> LocalAnalysisResult:
        processor = self.processors.get(request.analysis_type)
        if processor is None:
            raise ValueError("analysis_processor_not_supported")
        return processor.analyze(request)
