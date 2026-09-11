from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


VISION_JOB_SCHEMA = "NEXT_STABIL_VISION_JOB_V1"
VISION_RESULT_SCHEMA = "NEXT_STABIL_VISION_V1"


class VisionEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(pattern=r"^S[1-4]$")
    text: str = Field(min_length=1, max_length=2000)


class VisionMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(pattern=r"^S[1-4]$")
    value: float
    unit: str = Field(min_length=1, max_length=20)
    basis: Literal["visible_scale"]


class VisionImageQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(pattern=r"^S[1-4]$")
    quality: Literal["good", "limited", "poor"]


class VisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["NEXT_STABIL_VISION_V1"]
    job_id: str = Field(pattern=r"^[a-f0-9-]{16,64}$")
    observations: list[VisionEvidenceItem] = Field(max_length=40)
    possible_interpretations: list[VisionEvidenceItem] = Field(max_length=40)
    uncertainties: list[VisionEvidenceItem] = Field(max_length=40)
    visible_text: list[VisionEvidenceItem] = Field(max_length=40)
    measurements: list[VisionMeasurement] = Field(max_length=12)
    image_quality: list[VisionImageQuality] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_quality_refs(self):
        refs = [item.source_ref for item in self.image_quality]
        if len(refs) != len(set(refs)):
            raise ValueError("Duplicate image quality source")
        return self


class VisionStatusRead(BaseModel):
    document_id: int
    classification: str | None
    status: str
    auto_eligible: bool
    attempt_count: int
    next_retry_at: datetime | None
    error_code: str | None
    analyzed_at: datetime | None
    schema_version: str | None
    worker_status: str | None = None


class VisionAnalyzeResponse(BaseModel):
    document_id: int
    status: str
    classification: str | None


class VisionExportApprovalSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(pattern=r"^S[1-4]$")
    source_entity_type: str
    source_entity_id: str
    document_id: int
    original_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    final_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class VisionExportApprovalCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_job_id: str
    policy_version: str
    channel: str
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: list[VisionExportApprovalSource] = Field(min_length=1, max_length=4)


class VisionExportApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_job_id: str
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_sha256: dict[str, str]
    approval_kind: Literal["public_safe", "locally_redacted"]
    expires_at: datetime


class VisionExportApprovalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    analysis_job_id: str
    state: str
    reason: str
