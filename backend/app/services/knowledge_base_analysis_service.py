from __future__ import annotations

import re
from uuid import UUID

from app.models.knowledge_base import KnowledgeBaseItem
from app.schemas.analysis import AnalysisQualitySignals, AnalysisRequest, DeterministicCheck, LocalAnalysisResult


class KnowledgeBaseLocalProcessor:
    FORMULA = re.compile(r"(?m)(?:^|[.;]\s*)([A-Za-z][A-Za-z0-9_ ]{0,30}\s*=\s*[^.;\n]{1,180})")
    UNIT = re.compile(r"(?<!\w)(mm|cm|m|m2|m²|m3|m³|kg|g|kN|N|MPa|Pa|°C|K|V|A|Ω)(?!\w)", re.IGNORECASE)
    STANDARD = re.compile(r"\b(?:PN(?:-EN)?|EN|ISO|DIN)\s*[A-Z0-9:-]+", re.IGNORECASE)

    def analyze(self, request: AnalysisRequest, item: KnowledgeBaseItem) -> LocalAnalysisResult:
        text = "\n".join(source.excerpt for source in request.source_refs)
        formulas = list(dict.fromkeys(match.strip() for match in self.FORMULA.findall(text)))[:32]
        units = list(dict.fromkeys(match for match in self.UNIT.findall(text)))[:32]
        standards = list(dict.fromkeys(match.group(0) for match in self.STANDARD.finditer(text)))[:32]
        average_confidence = next((source.extraction_confidence for source in request.source_refs if source.extraction_confidence is not None), None)
        conflict = "sprzecz" in text.casefold() or "conflict" in text.casefold()
        complex_relationship = len(formulas) > 3 or conflict
        sufficient = len(text.strip()) >= 40
        result = {
            "definitions": [], "formulas": formulas,
            "variables": sorted({token for formula in formulas for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", formula)})[:128],
            "units": units, "constraints": request.constraints,
            "technical_values": re.findall(r"(?<!\w)-?\d+(?:[.,]\d+)?\s*(?:mm|cm|m|kg|kN|N|MPa|Pa|°C|V|A)", text, re.IGNORECASE)[:128],
            "tables": [], "standards": standards, "applicability": [],
            "exceptions": [], "worked_examples": [],
        }
        low_ocr = average_confidence is not None and average_confidence < 60
        signals = AnalysisQualitySignals(
            missing_evidence=not sufficient, source_coverage=1.0 if sufficient else 0.0,
            extraction_confidence=average_confidence,
            local_pass_disagreement=conflict, model_uncertain=complex_relationship or low_ocr,
            insufficient_evidence=not sufficient,
        )
        return LocalAnalysisResult(
            analysis_id=request.analysis_id, processor_id="kb_deterministic_parser",
            processor_version="v1", model_identity=None, result=result,
            evidence_refs=[source.source_ref for source in request.source_refs],
            assumptions=[], unresolved_questions=["Wymagana interpretacja relacji między formułami."] if complex_relationship else [],
            detected_constraints=request.constraints, normalized_units={unit: unit for unit in units},
            deterministic_checks=[DeterministicCheck(name="source_evidence_present", passed=sufficient,
                                                     code=None if sufficient else "analysis_insufficient_evidence")],
            quality_signals=signals, limitations=[],
            confidence="low" if (complex_relationship or low_ocr or not sufficient) else "high",
        )
