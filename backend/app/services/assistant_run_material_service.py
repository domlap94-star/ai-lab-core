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


MAX_MATERIAL_PROVENANCE_ITEMS = 100


class AssistantMaterialSourceRefConflict(ValueError):
    error_code = "ASSISTANT_MATERIAL_SOURCE_REF_CONFLICT"

    def __init__(self, source_ref: str) -> None:
        super().__init__(f"{self.error_code}:{source_ref}")


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
        observed: list[tuple[tuple[str, str, str], dict[str, str | None]]] = []
        for index, source in enumerate(sources, 1):
            handle = f"S{index:02d}"
            source_id = str(
                source.source_id
                if source.source_id is not None
                else source.route or index
            )[:100]
            domain = self._domain(source.source_type)
            entity_type = self._entity_type(source.source_type)
            excerpt = " ".join((source.snippet or source.title).split())[:2000]
            observed.append(
                (
                    (domain, entity_type, source_id),
                    {
                        "source_ref": handle,
                        "route": source.route,
                        "excerpt_sha256": hashlib.sha256(
                            excerpt.encode("utf-8")
                        ).hexdigest(),
                        "source_type": source.source_type,
                    },
                )
            )

        existing_rows = (
            self.db.query(AssistantRunMaterial)
            .filter(AssistantRunMaterial.assistant_run_id == run_id)
            .order_by(AssistantRunMaterial.id)
            .all()
        )
        # SessionLocal intentionally disables autoflush. Include pending rows
        # so this ledger boundary remains correct even when a caller has added
        # another material before invoking the collected-source binder.
        existing_rows.extend(
            row
            for row in self.db.new
            if isinstance(row, AssistantRunMaterial)
            and row.assistant_run_id == run_id
            and row not in existing_rows
        )
        by_identity: dict[tuple[str, str, str], AssistantRunMaterial] = {}
        ref_owner: dict[str, tuple[str, str, str]] = {}
        for row in existing_rows:
            identity = (
                row.source_domain,
                row.source_entity_type,
                row.source_entity_id,
            )
            by_identity[identity] = row
            refs = self._manifest_source_refs(row)
            for source_ref in refs:
                owner = ref_owner.get(source_ref)
                if owner is not None and owner != identity:
                    raise AssistantMaterialSourceRefConflict(source_ref)
                ref_owner[source_ref] = identity

        grouped: dict[
            tuple[str, str, str], list[dict[str, str | None]]
        ] = {}
        for identity, observation in observed:
            source_ref = str(observation["source_ref"])
            owner = ref_owner.get(source_ref)
            if owner is not None and owner != identity:
                raise AssistantMaterialSourceRefConflict(source_ref)
            ref_owner[source_ref] = identity
            grouped.setdefault(identity, []).append(observation)

        for identity, observations in grouped.items():
            domain, entity_type, source_id = identity
            existing = by_identity.get(identity)
            if existing is None:
                primary = observations[0]
                source_ref = str(primary["source_ref"])
                manifest = self._merge_source_manifest(
                    {}, primary_ref=source_ref, observations=observations
                )
                existing = AssistantRunMaterial(
                    assistant_run_id=run_id,
                    source_ref=source_ref,
                    source_domain=domain,
                    source_entity_type=entity_type,
                    source_entity_id=source_id,
                    source_role=(
                        "reference" if domain == "knowledge_base" else "case_fact"
                    ),
                    required=False,
                    readiness_level="query_ready",
                    status="ready",
                    source_checksum=str(primary["excerpt_sha256"]),
                    sensitivity=(
                        "restricted_never_external"
                        if domain in {"document", "mail", "knowledge_base"}
                        else "customer_sanitizable"
                    ),
                    source_manifest=manifest,
                )
                self.db.add(existing)
                by_identity[identity] = existing
            else:
                # A durable row owns a stable primary handle. Retrieval retries
                # may add aliases, but must never renumber that primary.
                existing.readiness_level = "query_ready"
                existing.status = "ready"
                existing.source_manifest = self._merge_source_manifest(
                    existing.source_manifest,
                    primary_ref=existing.source_ref,
                    observations=observations,
                )
        self.db.flush()

    @staticmethod
    def _manifest_source_refs(material: AssistantRunMaterial) -> list[str]:
        manifest = material.source_manifest if isinstance(material.source_manifest, dict) else {}
        values = manifest.get("source_refs")
        refs = [material.source_ref]
        if isinstance(values, list):
            refs.extend(value for value in values if isinstance(value, str))
        return list(dict.fromkeys(refs))

    @staticmethod
    def _merge_source_manifest(
        current: dict | None,
        *,
        primary_ref: str,
        observations: list[dict[str, str | None]],
    ) -> dict:
        manifest = dict(current) if isinstance(current, dict) else {}
        refs: list[str] = [primary_ref]
        raw_refs = manifest.get("source_refs")
        if isinstance(raw_refs, list):
            refs.extend(value for value in raw_refs if isinstance(value, str))

        existing_observations = manifest.get("observations")
        merged_observations: list[dict[str, str | None]] = []
        if isinstance(existing_observations, list):
            merged_observations.extend(
                dict(value) for value in existing_observations if isinstance(value, dict)
            )
        elif any(key in manifest for key in ("route", "excerpt_sha256", "source_type")):
            merged_observations.append(
                {
                    "source_ref": primary_ref,
                    "route": manifest.get("route"),
                    "excerpt_sha256": manifest.get("excerpt_sha256"),
                    "source_type": manifest.get("source_type"),
                }
            )

        for observation in observations:
            source_ref = str(observation["source_ref"])
            refs.append(source_ref)
            if observation not in merged_observations:
                merged_observations.append(dict(observation))

        refs = list(dict.fromkeys(refs))
        if (
            len(refs) > MAX_MATERIAL_PROVENANCE_ITEMS
            or len(merged_observations) > MAX_MATERIAL_PROVENANCE_ITEMS
        ):
            raise ValueError("ASSISTANT_MATERIAL_PROVENANCE_LIMIT")

        primary_observation = next(
            (
                item
                for item in merged_observations
                if item.get("source_ref") == primary_ref
            ),
            merged_observations[0] if merged_observations else {},
        )
        manifest.update(
            {
                "route": primary_observation.get("route"),
                "excerpt_sha256": primary_observation.get("excerpt_sha256"),
                "source_type": primary_observation.get("source_type"),
                "source_refs": refs,
                "observations": merged_observations,
            }
        )
        return validate_bounded_json(manifest, field_name="source_manifest")

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
