from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai.clients.ollama_client import OllamaClient
from app.database.session import SessionLocal
from app.models.assistant_pipeline import (
    DocumentIntelligenceArtifact,
    DocumentIntelligenceSource,
)
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.models.document_preparation_job import DocumentPreparationJob
from app.schemas.assistant_pipeline import validate_bounded_json


ANALYZER_GENERATION = "document-intelligence-v2"
MODEL = "qwen3.5:9b"
MAX_PAGE_CHARS = 1_200
PAGES_PER_SECTION = 8
MAX_SECTIONS = 32
MAX_FINDINGS = 16


INTELLIGENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["document_class", "language", "summary", "topics", "findings", "limitations"],
    "properties": {
        "document_class": {"type": "string", "maxLength": 100},
        "language": {"type": "string", "maxLength": 30},
        "summary": {"type": "string", "maxLength": 1600},
        "topics": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 120}},
        "findings": {
            "type": "array", "maxItems": MAX_FINDINGS,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["kind", "text", "source_refs"],
                "properties": {
                    "kind": {"type": "string", "enum": [
                        "fact", "measurement", "conclusion", "recommendation", "warning", "limitation"
                    ]},
                    "text": {"type": "string", "maxLength": 800},
                    "source_refs": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}},
                },
            },
        },
        "limitations": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 300}},
    },
}


@dataclass(frozen=True)
class IntelligenceEvidence:
    source_ref: str
    source_kind: str
    source_entity_id: str
    page_number: int | None
    text: str
    checksum: str
    visual: bool = False


@dataclass(frozen=True)
class IntelligenceBuildInput:
    document_id: int
    document_checksum: str
    preparation_job_id: str | None
    evidence: tuple[IntelligenceEvidence, ...]


class DocumentIntelligenceError(RuntimeError):
    pass


class DocumentIntelligenceService:
    """Build reusable, checksum-bound intelligence without document rewrites."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def accepted(
        self, *, document_id: int, checksum: str, kind: str = "baseline_document",
        artifact_key: str = "default",
    ) -> DocumentIntelligenceArtifact | None:
        return self.db.query(DocumentIntelligenceArtifact).filter(
            DocumentIntelligenceArtifact.document_id == document_id,
            DocumentIntelligenceArtifact.input_checksum == checksum.casefold(),
            DocumentIntelligenceArtifact.analyzer_generation == ANALYZER_GENERATION,
            DocumentIntelligenceArtifact.kind == kind,
            DocumentIntelligenceArtifact.artifact_key == artifact_key,
            DocumentIntelligenceArtifact.status == "accepted",
            DocumentIntelligenceArtifact.validation_state == "passed",
            DocumentIntelligenceArtifact.superseded_at.is_(None),
        ).one_or_none()

    def accepted_baseline(
        self, *, document_id: int, checksum: str
    ) -> DocumentIntelligenceArtifact | None:
        return self.accepted(
            document_id=document_id,
            checksum=checksum,
            kind="baseline_document",
        ) or self.accepted(
            document_id=document_id,
            checksum=checksum,
            kind="baseline_visual",
        )

    def collect_input(
        self, *, document_id: int, preparation_job_id: str | None = None
    ) -> IntelligenceBuildInput:
        document = self.db.get(Document, document_id)
        if document is None or document.trashed_at is not None or document.purged_at is not None:
            raise DocumentIntelligenceError("DOCUMENT_NOT_FOUND")
        checksum = (document.checksum_sha256 or "").strip().casefold()
        if len(checksum) != 64:
            raise DocumentIntelligenceError("DOCUMENT_CHECKSUM_REQUIRED")
        pages = self.db.query(DocumentPage).filter(
            DocumentPage.document_id == document_id
        ).order_by(DocumentPage.page_number.asc(), DocumentPage.id.asc()).all()
        evidence: list[IntelligenceEvidence] = []
        for page in pages:
            textual = page.extracted_text or page.ocr_text
            visual = page.vision_analysis if not textual else None
            text = " ".join((textual or visual or "").split())[:MAX_PAGE_CHARS]
            if not text:
                continue
            source_ref = f"P{int(page.page_number):04d}"[:8]
            evidence.append(IntelligenceEvidence(
                source_ref=source_ref,
                source_kind="document_page",
                source_entity_id=str(page.id),
                page_number=page.page_number,
                text=text,
                checksum=(
                    (page.vision_source_checksum or "").casefold()
                    or hashlib.sha256(text.encode("utf-8")).hexdigest()
                ) if visual else hashlib.sha256(text.encode("utf-8")).hexdigest(),
                visual=bool(visual),
            ))
        assets = self.db.query(DocumentAsset).filter(
            DocumentAsset.document_id == document_id,
            DocumentAsset.vision_status == "complete",
            DocumentAsset.vision_analysis.is_not(None),
        ).order_by(DocumentAsset.asset_index.asc(), DocumentAsset.id.asc()).all()
        for asset in assets:
            text = " ".join((asset.vision_analysis or "").split())[:MAX_PAGE_CHARS]
            if not text:
                continue
            evidence.append(IntelligenceEvidence(
                source_ref=f"A{int(asset.asset_index):04d}"[:8],
                source_kind="document_asset",
                source_entity_id=str(asset.id),
                page_number=asset.page_number,
                text=text,
                checksum=(asset.vision_source_checksum or asset.checksum_sha256 or "").casefold()
                or hashlib.sha256(text.encode("utf-8")).hexdigest(),
                visual=True,
            ))
        if not evidence:
            text = " ".join((document.extracted_text or "").split())[:MAX_PAGE_CHARS * 4]
            if text:
                evidence.append(IntelligenceEvidence(
                    source_ref="D0001",
                    source_kind="document",
                    source_entity_id=str(document.id),
                    page_number=None,
                    text=text,
                    checksum=checksum,
                ))
        if not evidence:
            raise DocumentIntelligenceError("DOCUMENT_CONTENT_NOT_READY")
        return IntelligenceBuildInput(
            document_id=document.id,
            document_checksum=checksum,
            preparation_job_id=preparation_job_id,
            evidence=tuple(evidence[: PAGES_PER_SECTION * MAX_SECTIONS]),
        )

    @staticmethod
    def validate_payload(payload: dict[str, Any], evidence: tuple[IntelligenceEvidence, ...]) -> dict[str, Any]:
        validate_bounded_json(payload, field_name="document_intelligence_artifact")
        if set(payload) != {"document_class", "language", "summary", "topics", "findings", "limitations"}:
            raise DocumentIntelligenceError("INTELLIGENCE_SCHEMA_INVALID")
        if not isinstance(payload["summary"], str) or not payload["summary"].strip():
            raise DocumentIntelligenceError("INTELLIGENCE_SUMMARY_EMPTY")
        if not isinstance(payload["findings"], list) or not payload["findings"]:
            raise DocumentIntelligenceError("INTELLIGENCE_FINDINGS_EMPTY")
        allowed = {item.source_ref: item for item in evidence}
        forbidden = re.compile(r"(?:chain.of.thought|tok(?:en)?|password|authorization|bearer)", re.I)
        if forbidden.search(json.dumps(payload, ensure_ascii=False)):
            raise DocumentIntelligenceError("INTELLIGENCE_FORBIDDEN_CONTENT")
        for finding in payload["findings"]:
            if not isinstance(finding, dict) or finding.get("kind") not in {
                "fact", "measurement", "conclusion", "recommendation", "warning", "limitation"
            }:
                raise DocumentIntelligenceError("INTELLIGENCE_FINDING_INVALID")
            refs = finding.get("source_refs")
            if not isinstance(refs, list) or not refs or any(ref not in allowed for ref in refs):
                raise DocumentIntelligenceError("INTELLIGENCE_SOURCE_BINDING")
            if finding.get("kind") == "measurement":
                numbers = re.findall(r"\d+(?:[.,]\d+)?", str(finding.get("text") or ""))
                source_text = " ".join(allowed[ref].text for ref in refs)
                if any(number not in source_text for number in numbers):
                    raise DocumentIntelligenceError("INTELLIGENCE_MEASUREMENT_UNBOUND")
        return payload

    def persist(
        self, *, build_input: IntelligenceBuildInput, kind: str, artifact_key: str,
        payload: dict[str, Any], processor_version: str = "2",
    ) -> DocumentIntelligenceArtifact:
        existing = self.accepted(
            document_id=build_input.document_id,
            checksum=build_input.document_checksum,
            kind=kind,
            artifact_key=artifact_key,
        )
        if existing is not None:
            return existing
        payload = self.validate_payload(payload, build_input.evidence)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        now = datetime.now(UTC)
        self.db.query(DocumentIntelligenceArtifact).filter(
            DocumentIntelligenceArtifact.document_id == build_input.document_id,
            DocumentIntelligenceArtifact.kind == kind,
            DocumentIntelligenceArtifact.artifact_key == artifact_key,
            DocumentIntelligenceArtifact.status == "accepted",
            DocumentIntelligenceArtifact.validation_state == "passed",
            DocumentIntelligenceArtifact.superseded_at.is_(None),
        ).update({
            DocumentIntelligenceArtifact.status: "superseded",
            DocumentIntelligenceArtifact.superseded_at: now,
        }, synchronize_session=False)
        artifact = DocumentIntelligenceArtifact(
            id=str(uuid.uuid4()),
            document_id=build_input.document_id,
            input_checksum=build_input.document_checksum,
            analyzer_generation=ANALYZER_GENERATION,
            kind=kind,
            artifact_key=artifact_key,
            status="accepted",
            validation_state="passed",
            sensitivity="restricted_never_external",
            payload=payload,
            validation_details={"contract": "document-intelligence-v2", "source_count": len(build_input.evidence)},
            payload_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            processor_id="document_intelligence",
            processor_version=processor_version,
            model_identity=MODEL,
            preparation_job_id=build_input.preparation_job_id,
            started_at=now,
            validated_at=now,
        )
        self.db.add(artifact)
        self.db.flush()
        used_refs = {
            ref
            for finding in payload["findings"]
            for ref in finding.get("source_refs", [])
        }
        for source in build_input.evidence:
            if source.source_ref not in used_refs:
                continue
            roles = {
                finding["kind"]
                for finding in payload["findings"]
                if source.source_ref in finding.get("source_refs", [])
            }
            role = "visual" if source.visual else (sorted(roles)[0] if roles else "fact")
            if role == "limitation":
                role = "limitation"
            self.db.add(DocumentIntelligenceSource(
                artifact_id=artifact.id,
                source_ref=source.source_ref,
                source_kind=source.source_kind,
                source_entity_id=source.source_entity_id,
                page_number=source.page_number,
                source_checksum=source.checksum,
                excerpt_sha256=hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
                source_role=role,
            ))
        self.db.flush()
        return artifact


def _compact_reduce_payloads(payloads: list[dict]) -> list[dict]:
    """Keep reduce input inside the local 4096-token envelope.

    Section artifacts remain durable in full.  The final reducer receives only
    bounded, source-bound product findings, never the complete document again.
    """
    compact: list[dict] = []
    for payload in payloads[:24]:
        findings = []
        for finding in list(payload.get("findings") or [])[:2]:
            findings.append({
                "kind": str(finding.get("kind") or "fact")[:24],
                "text": " ".join(str(finding.get("text") or "").split())[:240],
                "source_refs": list(finding.get("source_refs") or [])[:4],
            })
        compact.append({
            "summary": " ".join(str(payload.get("summary") or "").split())[:180],
            "topics": [str(item)[:80] for item in list(payload.get("topics") or [])[:4]],
            "findings": findings,
        })
    validate_bounded_json(compact, field_name="document_intelligence_reduce_input")
    return compact


def _prompt(evidence: tuple[IntelligenceEvidence, ...], *, reduce_payloads: list[dict] | None = None) -> str:
    if reduce_payloads:
        rows = [
            {"source_ref": item.source_ref, "page": item.page_number}
            for item in evidence
        ]
        map_aids = _compact_reduce_payloads(reduce_payloads)
    else:
        rows = [
            {"source_ref": item.source_ref, "page": item.page_number, "text": item.text}
            for item in evidence
        ]
        map_aids = []
    return (
        "Zbuduj zwięzłą inteligencję dokumentu wyłącznie z EVIDENCE. "
        "Nie ujawniaj toku rozumowania. Nie dodawaj wiedzy ogólnej. "
        "Każde ustalenie musi wskazać source_refs. Pomiary muszą zachować liczby i jednostki. "
        "Zwróć wyłącznie JSON zgodny ze schematem.\n"
        f"EVIDENCE={json.dumps(rows, ensure_ascii=False)}\n"
        f"MAP_AIDS={json.dumps(map_aids, ensure_ascii=False)}"
    )


async def _generate_payload(
    client: OllamaClient,
    evidence: tuple[IntelligenceEvidence, ...],
    *,
    reduce_payloads: list[dict] | None = None,
    on_progress=None,
) -> dict[str, Any]:
    prompt = _prompt(evidence, reduce_payloads=reduce_payloads)
    last_error: Exception | None = None
    for attempt in range(2):
        current = prompt if attempt == 0 else (
            prompt + "\nKOREKTA: poprzedni wynik naruszył kontrakt reprezentacji. "
            "Nie zmieniaj źródeł ani faktów; popraw wyłącznie JSON i wiązanie source_refs."
        )
        try:
            raw = await asyncio.wait_for(
                client.generate_streaming(
                    model=MODEL,
                    prompt=current,
                    format=INTELLIGENCE_SCHEMA,
                    options={"temperature": 0.0, "num_ctx": 4096, "num_predict": 420},
                    think=False,
                    keep_alive="2m",
                    on_progress=on_progress,
                ),
                timeout=300,
            )
            parsed = json.loads(str(raw.get("response") or "{}"))
            return DocumentIntelligenceService.validate_payload(parsed, evidence)
        except (ValueError, TypeError, json.JSONDecodeError, DocumentIntelligenceError) as error:
            last_error = error
            continue
    raise DocumentIntelligenceError(
        str(last_error) if last_error is not None else "INTELLIGENCE_GENERATION_FAILED"
    )


async def build_document_intelligence(
    *, document_id: int, preparation_job_id: str | None,
    client: OllamaClient | None = None, progress_callback=None,
) -> str:
    """Build/reuse one baseline artifact using short-lived DB sessions."""
    db = SessionLocal()
    try:
        service = DocumentIntelligenceService(db)
        build_input = service.collect_input(
            document_id=document_id, preparation_job_id=preparation_job_id
        )
        accepted = service.accepted_baseline(
            document_id=document_id, checksum=build_input.document_checksum
        )
        if accepted is not None:
            return accepted.id
    finally:
        db.close()

    model = client or OllamaClient()
    evidence = build_input.evidence
    section_payloads: list[dict] = []
    if len(evidence) > PAGES_PER_SECTION:
        for index in range(0, len(evidence), PAGES_PER_SECTION):
            section = evidence[index:index + PAGES_PER_SECTION]
            artifact_key = f"section:{index // PAGES_PER_SECTION + 1:04d}"
            section_db = SessionLocal()
            try:
                section_service = DocumentIntelligenceService(section_db)
                existing = section_service.accepted(
                    document_id=document_id,
                    checksum=build_input.document_checksum,
                    kind="section_map",
                    artifact_key=artifact_key,
                )
                if existing is not None:
                    section_payloads.append(existing.payload)
                    continue
            finally:
                section_db.close()
            payload = await _generate_payload(
                model, section, on_progress=progress_callback
            )
            section_input = IntelligenceBuildInput(
                document_id=build_input.document_id,
                document_checksum=build_input.document_checksum,
                preparation_job_id=build_input.preparation_job_id,
                evidence=section,
            )
            section_db = SessionLocal()
            try:
                artifact = DocumentIntelligenceService(section_db).persist(
                    build_input=section_input,
                    kind="section_map",
                    artifact_key=artifact_key,
                    payload=payload,
                )
                section_db.commit()
                section_payloads.append(artifact.payload)
            except Exception:
                section_db.rollback()
                raise
            finally:
                section_db.close()

    payload = await _generate_payload(
        model, evidence, reduce_payloads=section_payloads, on_progress=progress_callback
    )
    baseline_kind = (
        "baseline_visual"
        if all(item.visual for item in evidence)
        else "baseline_document"
    )
    final_db = SessionLocal()
    try:
        artifact = DocumentIntelligenceService(final_db).persist(
            build_input=build_input,
            kind=baseline_kind,
            artifact_key="default",
            payload=payload,
        )
        final_db.commit()
        return artifact.id
    except Exception:
        final_db.rollback()
        raise
    finally:
        final_db.close()
