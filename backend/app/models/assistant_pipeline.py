from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentIntelligenceArtifact(Base):
    __tablename__ = "document_intelligence_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    input_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    analyzer_generation: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_key: Mapped[str] = mapped_column(
        String(100), nullable=False, default="default", server_default="default"
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", server_default="draft"
    )
    validation_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    sensitivity: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_details: Mapped[dict | None] = mapped_column(JSON)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    processor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_identity: Mapped[str | None] = mapped_column(String(100))
    tool_identity: Mapped[str | None] = mapped_column(String(100))
    preparation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_preparation_jobs.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DocumentIntelligenceSource(Base):
    __tablename__ = "document_intelligence_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("document_intelligence_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    source_ref: Mapped[str] = mapped_column(String(8), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    excerpt_sha256: Mapped[str | None] = mapped_column(String(64))
    source_role: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssistantRun(Base):
    __tablename__ = "assistant_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_id: Mapped[str] = mapped_column(String(80), nullable=False)
    api_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="assistant-runs-v2", server_default="assistant-runs-v2"
    )
    orchestrator_version: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_contract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_generation: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    target_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    complexity: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="created", server_default="created"
    )
    current_stage: Mapped[str | None] = mapped_column(String(40))
    plan: Mapped[dict | None] = mapped_column(JSON)
    plan_sha256: Mapped[str | None] = mapped_column(String(64))
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    result_payload_sha256: Mapped[str | None] = mapped_column(String(64))
    sensitivity: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default="1"
    )
    recovery_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssistantRunStage(Base):
    __tablename__ = "assistant_run_stages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assistant_run_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_runs.id", ondelete="CASCADE"), nullable=False
    )
    stage_key: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default="queued"
    )
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    attempt: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, server_default="1"
    )
    max_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=3, server_default="3"
    )
    progress_current: Mapped[int | None] = mapped_column(BigInteger)
    progress_total: Mapped[int | None] = mapped_column(BigInteger)
    progress_unit: Mapped[str | None] = mapped_column(String(24))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inactivity_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    absolute_cap_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    result_kind: Mapped[str | None] = mapped_column(String(32))
    result_manifest: Mapped[dict | None] = mapped_column(JSON)
    analysis_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="SET NULL")
    )
    document_preparation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_preparation_jobs.id", ondelete="SET NULL")
    )
    intelligence_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_intelligence_artifacts.id", ondelete="SET NULL")
    )
    external_job_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssistantRunMaterial(Base):
    __tablename__ = "assistant_run_materials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_run_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_ref: Mapped[str] = mapped_column(String(8), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_role: Mapped[str] = mapped_column(String(24), nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    readiness_level: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="resolving", server_default="resolving"
    )
    source_checksum: Mapped[str | None] = mapped_column(String(64))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    document_preparation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_preparation_jobs.id", ondelete="SET NULL")
    )
    intelligence_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_intelligence_artifacts.id", ondelete="SET NULL")
    )
    sensitivity: Mapped[str] = mapped_column(String(30), nullable=False)
    source_manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
