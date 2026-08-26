from __future__ import annotations

import hashlib
import json
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.assistant_pipeline import (
    AssistantRunMaterial,
    DocumentIntelligenceArtifact,
)
from app.models.document import Document
from app.schemas.agent import AgentSource
from app.schemas.assistant_pipeline import validate_bounded_json


class AssistantRunMaterialService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def attach_document(
        self,
        *,
        run_id: str,
        document: Document,
        required: bool,
        preparation_job_id: str | None,
        artifact: DocumentIntelligenceArtifact | None,
    ) -> AssistantRunMaterial:
        existing = self.db.query(AssistantRunMaterial).filter(
            AssistantRunMaterial.assistant_run_id == run_id,
            AssistantRunMaterial.source_domain == "document",
            AssistantRunMaterial.source_entity_type == "Document",
            AssistantRunMaterial.source_entity_id == str(document.id),
        ).one_or_none()
        readiness = (
            "intelligence_ready" if artifact is not None
            else "content_ready" if document.processing_status == "processed"
            else "file_validated"
        )
        status = "ready" if artifact is not None else "waiting"
        manifest = validate_bounded_json({
            "document_id": document.id,
            "checksum": document.checksum_sha256,
            "content_type": document.content_type,
            "processing_status": document.processing_status,
            "analyzer_generation": artifact.analyzer_generation if artifact else None,
            "artifact_payload_sha256": artifact.payload_sha256 if artifact else None,
        }, field_name="source_manifest")
        if existing is None:
            existing = AssistantRunMaterial(
                assistant_run_id=run_id,
                source_ref="D01",
                source_domain="document",
                source_entity_type="Document",
                source_entity_id=str(document.id),
                source_role="case_fact",
                required=required,
                readiness_level=readiness,
                status=status,
                source_checksum=document.checksum_sha256,
                document_preparation_job_id=preparation_job_id,
                intelligence_artifact_id=artifact.id if artifact else None,
                sensitivity="restricted_never_external",
                source_manifest=manifest,
            )
            self.db.add(existing)
        else:
            existing.required = existing.required or required
            existing.readiness_level = readiness
            existing.status = status
            existing.source_checksum = document.checksum_sha256
            existing.document_preparation_job_id = preparation_job_id
            existing.intelligence_artifact_id = artifact.id if artifact else None
            existing.source_manifest = manifest
        self.db.flush()
        return existing

    def bind_collected_sources(
        self, *, run_id: str, sources: Iterable[AgentSource]
    ) -> None:
        for index, source in enumerate(sources, 1):
            source_id = str(source.source_id if source.source_id is not None else source.route or index)
            domain = self._domain(source.source_type)
            entity_type = self._entity_type(source.source_type)
            existing = self.db.query(AssistantRunMaterial).filter(
                AssistantRunMaterial.assistant_run_id == run_id,
                AssistantRunMaterial.source_domain == domain,
                AssistantRunMaterial.source_entity_type == entity_type,
                AssistantRunMaterial.source_entity_id == source_id[:100],
            ).one_or_none()
            excerpt = " ".join((source.snippet or source.title).split())[:2000]
            manifest = validate_bounded_json({
                "route": source.route,
                "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "source_type": source.source_type,
            }, field_name="source_manifest")
            handle = f"S{index:02d}"
            if existing is None:
                existing = AssistantRunMaterial(
                    assistant_run_id=run_id,
                    source_ref=handle,
                    source_domain=domain,
                    source_entity_type=entity_type,
                    source_entity_id=source_id[:100],
                    source_role="reference" if domain == "knowledge_base" else "case_fact",
                    required=False,
                    readiness_level="query_ready",
                    status="ready",
                    source_checksum=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                    sensitivity=(
                        "restricted_never_external" if domain in {"document", "mail", "knowledge_base"}
                        else "customer_sanitizable"
                    ),
                    source_manifest=manifest,
                )
                self.db.add(existing)
            else:
                # Query-time source handles are the canonical allowlist used by
                # the final response.  Keep the durable material ledger aligned
                # with that exact mapping so a result can be replay-audited.
                existing.source_ref = handle
                existing.readiness_level = "query_ready"
                existing.status = "ready"
                existing.source_manifest = {**existing.source_manifest, **manifest}
        self.db.flush()

    @staticmethod
    def artifact_payload(artifact: DocumentIntelligenceArtifact | None) -> dict | None:
        if artifact is None:
            return None
        canonical = json.dumps(
            artifact.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != artifact.payload_sha256:
            raise ValueError("INTELLIGENCE_ARTIFACT_HASH_MISMATCH")
        return artifact.payload

    @staticmethod
    def _domain(source_type: str) -> str:
        return {
            "knowledge_base": "knowledge_base",
            "document": "document",
            "mail": "mail",
            "email": "mail",
            "candidate": "candidate",
            "client": "client",
            "inspection": "visit",
            "project": "project",
            "calculation": "calculation",
            "visual": "visual",
        }.get(source_type, "general")

    @staticmethod
    def _entity_type(source_type: str) -> str:
        return {
            "knowledge_base": "KnowledgeBaseItem",
            "document": "Document",
            "mail": "Mail",
            "email": "Mail",
            "candidate": "ClientCandidate",
            "client": "Client",
            "inspection": "Inspection",
            "project": "Project",
            "calculation": "Calculation",
            "visual": "VisualObservation",
        }.get(source_type, "GeneralSource")
