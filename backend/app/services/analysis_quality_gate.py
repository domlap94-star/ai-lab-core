from __future__ import annotations

from dataclasses import dataclass

from app.schemas.analysis import AnalysisRequest, LocalAnalysisResult, QualityDecision


@dataclass(frozen=True)
class QualityGateResult:
    decision: QualityDecision
    code: str


class AnalysisQualityGate:
    MIN_COVERAGE = {
        "formula_calculation": 1.0,
        "standards_comparison": 0.9,
        "table_analysis": 0.85,
        "technical_interpretation": 0.8,
        "document_interpretation": 0.8,
        "consistency_check": 0.9,
        "visual_analysis": 0.8,
    }

    def evaluate(self, request: AnalysisRequest, local: LocalAnalysisResult) -> QualityGateResult:
        signals = local.quality_signals
        if request.sensitivity == "restricted_never_external":
            return QualityGateResult("REVIEW_REQUIRED", "analysis_restricted_externalization")
        if signals.unknown_source_refs or signals.invalid_formula or signals.deterministic_check_failed:
            return QualityGateResult("REVIEW_REQUIRED", "analysis_post_validation_failed")
        if signals.missing_evidence or signals.insufficient_evidence:
            return QualityGateResult("REVIEW_REQUIRED", "analysis_insufficient_evidence")
        if signals.unsupported_operation and "temporary_chat" not in request.allowed_methods:
            return QualityGateResult("FAIL", "analysis_unsupported_operation")
        threshold = self.MIN_COVERAGE[request.analysis_type]
        hard = any((signals.unresolved_variables, signals.unit_ambiguity,
                    signals.local_pass_disagreement, signals.invalid_json,
                    signals.local_timeout, signals.context_truncated,
                    signals.unsupported_operation))
        weak = local.confidence in {"low", "indeterminate"} or signals.model_uncertain
        if not hard and not weak and signals.source_coverage >= threshold:
            return QualityGateResult("ACCEPT_LOCAL", "analysis_local_accepted")
        if "temporary_chat" in request.allowed_methods and signals.source_coverage >= 0.5:
            return QualityGateResult("ESCALATE_TEMP_CHAT", "analysis_advanced_required")
        return QualityGateResult("REVIEW_REQUIRED", "analysis_review_required")
