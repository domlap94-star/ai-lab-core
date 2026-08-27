from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.inspection import Inspection
from app.schemas.assistant_pipeline import AssistantRunCreateRequest, validate_bounded_json
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.local_model_time_policy import (
    DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS,
    GENERATION_INACTIVITY_SECONDS,
    STANDARD_LOCAL_ABSOLUTE_SECONDS,
)
from app.services.unified_assistant_service import UnifiedAssistantService


ORCHESTRATOR_VERSION = "assistant-pipeline-v2.1"
EVIDENCE_CONTRACT_VERSION = "unified-evidence-v2"
POLICY_GENERATION = "assistant-policy-20260826"


class AssistantRunScopeError(RuntimeError):
    pass


@dataclass(frozen=True)
class AssistantRunPlan:
    request: UnifiedAssistantRequest
    target_scope: dict
    intent: str
    complexity: str
    sensitivity: str
    priority: int
    stages: tuple[dict, ...]

    def as_json(self) -> dict:
        value = {
            "version": ORCHESTRATOR_VERSION,
            "intent": self.intent,
            "complexity": self.complexity,
            "stages": list(self.stages),
        }
        return validate_bounded_json(value, field_name="plan")


class AssistantRunPlanner:
    """Fail-closed deterministic planner.  It never invokes an LLM."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def plan(self, request: AssistantRunCreateRequest) -> AssistantRunPlan:
        unified = UnifiedAssistantRequest.model_validate(request.model_dump(mode="json"))
        unified = UnifiedAssistantService._apply_conversation_reset(unified)
        self._validate_scope(unified)
        query_mode = UnifiedAssistantService._query_mode(unified)
        intent = self._intent(unified, query_mode)
        complexity = self._complexity(unified, intent)
        stages = self._stages(intent, complexity)
        target_scope = {
            "scope_handle": "TARGET_01",
            "client_id": unified.client_id,
            "candidate_id": unified.candidate_id,
            "document_id": unified.document_id,
            "mail_source_id": unified.mail_source_id,
            "inspection_id": unified.inspection_id,
        }
        validate_bounded_json(target_scope, field_name="target_scope")
        sensitivity = (
            "restricted_never_external"
            if unified.document_id is not None or unified.mail_source_id is not None
            else "customer_sanitizable"
            if any((unified.client_id, unified.candidate_id, unified.inspection_id))
            else "public_reference"
        )
        return AssistantRunPlan(
            request=unified,
            target_scope=target_scope,
            intent=intent,
            complexity=complexity,
            sensitivity=sensitivity,
            priority=0 if any((unified.document_id, unified.client_id)) else 1,
            stages=stages,
        )

    def _validate_scope(self, request: UnifiedAssistantRequest) -> None:
        if request.client_id is not None:
            row = self.db.query(Client).filter(
                Client.id == request.client_id,
                Client.deleted_at.is_(None),
                Client.purged_at.is_(None),
            ).one_or_none()
            if row is None:
                raise AssistantRunScopeError("CLIENT_SCOPE_INVALID")
        if request.candidate_id is not None:
            candidate = self.db.query(ClientCandidate).filter(
                ClientCandidate.id == request.candidate_id,
                ClientCandidate.deleted_at.is_(None),
            ).one_or_none()
            if candidate is None:
                raise AssistantRunScopeError("CANDIDATE_SCOPE_INVALID")
            if (
                request.client_id is not None
                and candidate.matched_client_id is not None
                and candidate.matched_client_id != request.client_id
            ):
                raise AssistantRunScopeError("CANDIDATE_SCOPE_INVALID")
        if request.document_id is not None:
            document = self.db.query(Document).filter(
                Document.id == request.document_id,
                Document.trashed_at.is_(None),
                Document.purged_at.is_(None),
            ).one_or_none()
            if document is None:
                raise AssistantRunScopeError("DOCUMENT_SCOPE_INVALID")
            if request.client_id is not None and document.client_id not in {None, request.client_id}:
                raise AssistantRunScopeError("DOCUMENT_SCOPE_INVALID")
        if request.inspection_id is not None:
            inspection = self.db.query(Inspection).filter(
                Inspection.id == request.inspection_id,
                Inspection.deleted_at.is_(None),
            ).one_or_none()
            if inspection is None:
                raise AssistantRunScopeError("INSPECTION_SCOPE_INVALID")
            if request.client_id is not None and inspection.client_id != request.client_id:
                raise AssistantRunScopeError("INSPECTION_SCOPE_INVALID")

    @staticmethod
    def _intent(request: UnifiedAssistantRequest, query_mode: str) -> str:
        folded = UnifiedAssistantService._fold_intent(request.question)
        explicit_kb = UnifiedAssistantService._has_explicit_kb_intent(request.question)
        broad_kb = explicit_kb and not re.search(r"[\"']([^\"']{2,180})[\"']", request.question)
        if query_mode == "SYSTEM_META":
            return "system_meta"
        if broad_kb and any(token in folded for token in ("zrodla", "materialy", "co jest", "katalog", "baza wiedzy")):
            return "knowledge_base_catalog"
        if query_mode == "GENERAL_KNOWLEDGE":
            return "general_knowledge"
        if request.document_id is not None or "dokument" in folded or "plik" in folded:
            return "document_reasoning"
        return "evidence_reasoning"

    @staticmethod
    def _complexity(request: UnifiedAssistantRequest, intent: str) -> str:
        folded = UnifiedAssistantService._fold_intent(request.question)
        if intent in {"system_meta", "knowledge_base_catalog"}:
            return "fast"
        if any(token in folded for token in ("zdjec", "obraz", "skan", "widoczn")):
            return "visual"
        active_domains = sum(value is not None for value in (
            request.client_id, request.candidate_id, request.document_id,
            request.mail_source_id, request.inspection_id,
        ))
        if active_domains >= 2 or any(token in folded for token in (
            "porownaj", "sprzeczn", "wnioski", "przyczyn", "oblicz", "oszacuj", "przeanalizuj"
        )):
            return "deep"
        return "standard"

    @staticmethod
    def _stages(intent: str, complexity: str) -> tuple[dict, ...]:
        definitions: list[tuple[str, int, int]] = [("planning", 10, 30)]
        if intent == "system_meta":
            definitions += [("finalizing", 10, 30)]
        elif intent == "knowledge_base_catalog":
            definitions += [("retrieving_knowledge_base", 30, 120), ("finalizing", 10, 30)]
        else:
            definitions += [("resolving_targets", 30, 120)]
            if intent == "document_reasoning":
                definitions += [
                    ("waiting_for_material", 120, 86400),
                    ("building_intelligence", 120, 21600),
                    ("validating_intelligence", 30, 300),
                ]
            definitions += [("retrieving_case_evidence", 30, 120)]
            if intent in {"document_reasoning", "evidence_reasoning"}:
                definitions += [("retrieving_knowledge_base", 30, 120)]
            if complexity == "visual":
                definitions += [("waiting_for_vision", 180, 3600), ("analyzing_vision", 180, 3600)]
            definitions += [(
                "analyzing_local",
                GENERATION_INACTIVITY_SECONDS,
                DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS
                if complexity == "deep"
                else STANDARD_LOCAL_ABSOLUTE_SECONDS,
            )]
            if complexity == "deep":
                definitions += [
                    (
                        "reducing_findings",
                        GENERATION_INACTIVITY_SECONDS,
                        DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS,
                    ),
                    (
                        "synthesizing",
                        GENERATION_INACTIVITY_SECONDS,
                        DEEP_LOCAL_SUBSTAGE_ABSOLUTE_SECONDS,
                    ),
                ]
            definitions += [
                ("validating_local", 60, 300),
                ("waiting_for_advanced", 180, 1800),
                ("analyzing_advanced", 180, 1800),
                ("validating_advanced", 120, 600),
                ("finalizing", 30, 120),
            ]
        return tuple(
            {
                "stage_key": f"{ordinal:02d}-{stage_type}",
                "stage_type": stage_type,
                "ordinal": ordinal,
                "inactivity_timeout_seconds": inactivity,
                "absolute_cap_seconds": absolute,
            }
            for ordinal, (stage_type, inactivity, absolute) in enumerate(definitions)
        )
