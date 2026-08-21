from __future__ import annotations

import math
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ANALYSIS_REQUEST_SCHEMA = "NEXT_STABIL_ANALYSIS_REQUEST_V1"
LOCAL_RESULT_SCHEMA = "NEXT_STABIL_LOCAL_ANALYSIS_RESULT_V1"
ADVANCED_PACKAGE_SCHEMA = "NEXT_STABIL_ADVANCED_ANALYSIS_V1"
ADVANCED_RESULT_SCHEMA = "NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1"

AnalysisType = Literal[
    "technical_interpretation", "formula_calculation", "table_analysis",
    "standards_comparison", "consistency_check", "document_interpretation",
    "visual_analysis",
]
SourceDomain = Literal[
    "knowledge_base", "customer_document", "technical", "calculation", "vision"
]
Sensitivity = Literal[
    "public_reference", "internal_non_sensitive", "customer_sanitizable",
    "restricted_never_external",
]
AllowedMethod = Literal[
    "deterministic_parse", "deterministic_calculation", "local_llm",
    "ocr", "vision", "temporary_chat",
]
QualityDecision = Literal[
    "ACCEPT_LOCAL", "ESCALATE_TEMP_CHAT", "REVIEW_REQUIRED", "FAIL"
]


class AnalysisSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_ref: str = Field(pattern=r"^S[1-8]$")
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page: int | None = Field(None, ge=1)
    excerpt: str = Field(min_length=1, max_length=2000)
    extraction_confidence: float | None = Field(None, ge=0, le=100)


class AnalysisContextLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_sources: int = Field(default=8, ge=1, le=8)
    max_excerpts: int = Field(default=24, ge=1, le=24)
    max_package_bytes: int = Field(default=65536, ge=1024, le=65536)


class AnalysisProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_by_user_id: int | None = Field(None, gt=0)
    source_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    processor_policy_version: str = Field(default="v1", max_length=40)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["NEXT_STABIL_ANALYSIS_REQUEST_V1"] = ANALYSIS_REQUEST_SCHEMA
    analysis_id: UUID
    analysis_type: AnalysisType
    source_domain: SourceDomain
    source_refs: list[AnalysisSourceRef] = Field(min_length=1, max_length=8)
    problem_statement: str = Field(min_length=1, max_length=4000)
    structured_inputs: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    formulas: list[str] = Field(default_factory=list, max_length=32)
    constraints: list[str] = Field(default_factory=list, max_length=64)
    evidence: list[str] = Field(default_factory=list, max_length=64)
    sensitivity: Sensitivity
    allowed_methods: list[AllowedMethod] = Field(min_length=1, max_length=6)
    context_limits: AnalysisContextLimits = Field(default_factory=AnalysisContextLimits)
    provenance: AnalysisProvenance

    @model_validator(mode="after")
    def validate_refs_and_bounds(self):
        refs = [item.source_ref for item in self.source_refs]
        if len(refs) != len(set(refs)):
            raise ValueError("analysis_duplicate_source_ref")
        if len(self.source_refs) > self.context_limits.max_sources:
            raise ValueError("analysis_context_source_limit")
        return self


class DeterministicCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    passed: bool
    code: str | None = Field(None, max_length=100)


class AnalysisQualitySignals(BaseModel):
    model_config = ConfigDict(extra="forbid")
    missing_evidence: bool = False
    source_coverage: float = Field(default=1.0, ge=0, le=1)
    extraction_confidence: float | None = Field(None, ge=0, le=100)
    unknown_source_refs: bool = False
    unresolved_variables: bool = False
    unit_ambiguity: bool = False
    invalid_formula: bool = False
    deterministic_check_failed: bool = False
    local_pass_disagreement: bool = False
    invalid_json: bool = False
    local_timeout: bool = False
    context_truncated: bool = False
    unsupported_operation: bool = False
    insufficient_evidence: bool = False
    model_uncertain: bool = False


class LocalAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["NEXT_STABIL_LOCAL_ANALYSIS_RESULT_V1"] = LOCAL_RESULT_SCHEMA
    analysis_id: UUID
    processor_id: str = Field(min_length=1, max_length=100)
    processor_version: str = Field(min_length=1, max_length=40)
    model_identity: str | None = Field(None, max_length=100)
    result: dict[str, Any]
    evidence_refs: list[str] = Field(default_factory=list, max_length=8)
    assumptions: list[str] = Field(default_factory=list, max_length=32)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=32)
    detected_constraints: list[str] = Field(default_factory=list, max_length=64)
    normalized_units: dict[str, str] = Field(default_factory=dict)
    deterministic_checks: list[DeterministicCheck] = Field(default_factory=list, max_length=64)
    quality_signals: AnalysisQualitySignals
    limitations: list[str] = Field(default_factory=list, max_length=32)
    confidence: Literal["high", "medium", "low", "indeterminate"]


class SanitizedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_ref: str = Field(pattern=r"^S[1-8]$")
    technical_excerpt: str = Field(min_length=1, max_length=2000)
    page: int | None = Field(None, ge=1)


class AdvancedAnalysisPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["NEXT_STABIL_ADVANCED_ANALYSIS_V1"] = ADVANCED_PACKAGE_SCHEMA
    analysis_id: UUID
    analysis_type: AnalysisType
    problem: str = Field(min_length=1, max_length=4000)
    sources: list[SanitizedSource] = Field(min_length=1, max_length=8)
    tables: list[list[list[str | float | int | None]]] = Field(default_factory=list, max_length=4)
    formulas: list[str] = Field(default_factory=list, max_length=32)
    variables: dict[str, str | float | int | None] = Field(default_factory=dict)
    values: dict[str, float | int] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list, max_length=64)
    requested_output: str = Field(min_length=1, max_length=1000)
    validation_requirements: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def bounded_tables(self):
        if sum(len(row) for table in self.tables for row in table) > 2000:
            raise ValueError("analysis_table_cell_limit")
        return self


class AdvancedAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1"]
    analysis_id: UUID
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    result: dict[str, Any]
    source_refs: list[str] = Field(max_length=8)
    assumptions: list[str] = Field(default_factory=list, max_length=32)
    uncertainties: list[str] = Field(default_factory=list, max_length=32)
    constraints_checked: list[str] = Field(default_factory=list, max_length=64)
    normalized_units: dict[str, str] = Field(default_factory=dict)
    formula_used: str | None = Field(None, max_length=2000)
    calculation_steps: list[str] = Field(default_factory=list, max_length=64)
    verification_recommendation: Literal["accept", "review", "reject"]

    @field_validator("source_refs")
    @classmethod
    def source_ref_shape(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not re.fullmatch(r"S[1-8]", value) for value in values):
            raise ValueError("analysis_unknown_source_ref")
        return values

    @field_validator("result")
    @classmethod
    def finite_numbers(cls, value: dict[str, Any]) -> dict[str, Any]:
        def check(item: Any) -> None:
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("analysis_numeric_invalid")
            if isinstance(item, dict):
                for nested in item.values(): check(nested)
            if isinstance(item, list):
                for nested in item: check(nested)
        check(value)
        return value
