from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

from app.schemas.analysis import AdvancedAnalysisResult, AnalysisRequest


@dataclass(frozen=True)
class ResultContractValidation:
    applied: bool
    status: Literal["accepted_advanced", "review_required", "rejected"]
    code: str
    artifact: dict[str, Any] | None = None
    issues: tuple[str, ...] = ()


class TemporaryChatResultContractV2:
    """Strict handle-based external result contract.

    Facts and tool results originate locally.  The external model may select
    their opaque handles, but cannot create source authority or canonical claim
    IDs.  Natural-language FACT text is rendered from the local manifest.
    """

    SCHEMA = "NEXT_STABIL_TEMP_CHAT_RESULT_V2"
    CLASSES = {"FACT", "ESTIMATE", "HYPOTHESIS", "MISSING"}
    CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "NOT_ESTIMABLE"}

    def validate(self, *, request: AnalysisRequest, result: AdvancedAnalysisResult) -> ResultContractValidation:
        payload = result.result
        if payload.get("schema") != self.SCHEMA:
            return ResultContractValidation(False, "accepted_advanced", "analysis_result_contract_not_applicable")
        manifest = self._manifest(request)
        if not manifest["scope_valid"]:
            return self._reject("analysis_result_target_scope_invalid", "target_scope")
        if not manifest["facts"]:
            return self._reject("analysis_result_fact_manifest_missing", "fact_manifest_missing")
        if set(result.source_refs) - manifest["sources"]:
            return self._reject("analysis_result_unknown_source_handle", "unknown_source")
        claims = payload.get("claims")
        if not isinstance(claims, list) or not claims:
            return self._reject("analysis_result_claim_schema_invalid", "claim_schema")

        normalized: list[dict[str, Any]] = []
        for index, claim in enumerate(claims, 1):
            if not isinstance(claim, dict):
                return self._reject("analysis_result_claim_schema_invalid", "claim_schema")
            claim_class = str(claim.get("class") or "").upper()
            if claim_class not in self.CLASSES:
                return self._reject("analysis_result_claim_class_invalid", "claim_class")
            if claim.get("claim_id"):
                return self._reject("analysis_result_external_claim_id_forbidden", "external_claim_id")
            validator = getattr(self, f"_normalize_{claim_class.casefold()}")
            item = validator(claim, manifest)
            if isinstance(item, ResultContractValidation):
                return item
            item["claim_id"] = f"C{index:02d}"
            normalized.append(item)

        contradictions = payload.get("contradictions", [])
        if not isinstance(contradictions, list):
            return self._reject("analysis_result_contradiction_schema_invalid", "contradiction_schema")
        normalized_contradictions = []
        for item in contradictions:
            if not isinstance(item, dict) or not isinstance(item.get("description"), str):
                return self._reject("analysis_result_contradiction_schema_invalid", "contradiction_schema")
            handles = self._handles(item.get("fact_handles"))
            if not handles or handles - set(manifest["facts"]):
                return self._reject("analysis_result_unknown_fact_handle", "unknown_fact")
            normalized_contradictions.append({"description": item["description"], "fact_handles": sorted(handles)})
        selected_facts = {handle for item in normalized for handle in item.get("fact_handles", [])}
        contradiction_handles = {handle for item in normalized_contradictions for handle in item["fact_handles"]}
        relationship_coverages = [
            set(item.get("support_fact_handles", [])) | set(item.get("contradiction_fact_handles", []))
            for item in normalized
            if item.get("class") == "HYPOTHESIS"
        ]
        relationship_coverages.extend(set(item["fact_handles"]) for item in normalized_contradictions)
        comparison_selected_facts = selected_facts | {
            handle
            for coverage in relationship_coverages
            for handle in coverage
        }
        if request.analysis_type == "consistency_check":
            groups = {item.get("comparison_group") for item in manifest["facts"].values()} - {None}
            for group in groups:
                members = {
                    handle
                    for handle, item in manifest["facts"].items()
                    if item.get("comparison_group") == group
                }
                if len(comparison_selected_facts & members) >= 2 and not any(
                    members.issubset(coverage) for coverage in relationship_coverages
                ):
                    return self._reject(
                        "analysis_result_consistency_relationship_missing",
                        "consistency_relationship_missing",
                    )
        for group in {item.get("contradiction_group") for item in manifest["facts"].values()} - {None}:
            members = {handle for handle, item in manifest["facts"].items() if item.get("contradiction_group") == group}
            if len(selected_facts & members) >= 2 and not members.issubset(contradiction_handles):
                return self._reject("analysis_result_material_contradiction_missing", "contradiction_missing")

        artifact = {
            "schema": self.SCHEMA,
            "target_scope_handle": manifest["target_scope_handle"],
            "answer": self.render_answer(normalized, normalized_contradictions),
            "claims": normalized,
            "contradictions": normalized_contradictions,
            "source_refs": sorted({ref for item in normalized for ref in item.get("source_refs", [])}),
        }
        return ResultContractValidation(True, "accepted_advanced", "analysis_result_contract_v2_accepted", artifact)

    @staticmethod
    def render_answer(claims: list[dict[str, Any]], contradictions: list[dict[str, Any]]) -> str:
        labels = {"FACT": "FAKT", "ESTIMATE": "ESTYMACJA", "HYPOTHESIS": "HIPOTEZA", "MISSING": "BRAK"}
        parts = [f"{labels[item['class']]}: {item['text']}" for item in claims]
        parts.extend(f"SPRZECZNOŚĆ: {item['description']}" for item in contradictions)
        return "\n".join(parts)

    def _normalize_fact(self, claim: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any] | ResultContractValidation:
        allowed = {"class", "fact_handles", "tool_handles", "visual_handles"}
        if set(claim) - allowed:
            return self._reject("analysis_result_claim_schema_invalid", "claim_schema")
        handles = self._handles(claim.get("fact_handles"))
        tools = self._handles(claim.get("tool_handles"))
        visuals = self._handles(claim.get("visual_handles"))
        if not (handles or tools or visuals):
            return self._reject("analysis_result_material_provenance_missing", "missing_provenance")
        if handles - set(manifest["facts"]):
            return self._reject("analysis_result_unknown_fact_handle", "unknown_fact")
        if tools - set(manifest["tools"]):
            return self._reject("analysis_result_unknown_tool_handle", "unknown_tool")
        if visuals - set(manifest["visuals"]):
            return self._reject("analysis_result_unknown_visual_handle", "unknown_visual")
        facts = [manifest["facts"][handle] for handle in sorted(handles)]
        statements = [item["statement"] for item in facts]
        statements.extend(str(manifest["tools"][handle].get("statement") or "") for handle in sorted(tools))
        statements.extend(str(manifest["visuals"][handle].get("statement") or "") for handle in sorted(visuals))
        sources = self._sources_for(handles, tools, manifest)
        for handle in visuals:
            sources.update(manifest["visuals"][handle].get("source_handles") or [])
        return {"class": "FACT", "text": " ".join(item for item in statements if item),
                "fact_handles": sorted(handles), "tool_result_refs": sorted(tools),
                "visual_observation_refs": sorted(visuals), "source_refs": sorted(sources)}

    def _normalize_estimate(self, claim: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any] | ResultContractValidation:
        estimable = {"class", "estimate_status", "value_or_range", "confidence", "basis_fact_handles", "basis_tool_handles", "assumptions", "missing_inputs"}
        not_estimable = {"class", "estimate_status", "reason", "basis_fact_handles", "basis_tool_handles", "missing_inputs"}
        legacy = {"class", "value_or_range", "confidence", "basis_fact_handles", "basis_tool_handles", "assumptions", "missing_inputs"}
        status = claim.get("estimate_status")
        if status is None:
            if set(claim) - legacy:
                return self._reject("analysis_result_claim_schema_invalid", "claim_schema")
            status = "NOT_ESTIMABLE" if claim.get("confidence") == "NOT_ESTIMABLE" else "ESTIMABLE"
        elif status == "ESTIMABLE":
            if set(claim) != estimable:
                return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        elif status == "NOT_ESTIMABLE":
            if set(claim) != not_estimable:
                return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        else:
            return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        facts = self._handles(claim.get("basis_fact_handles"))
        tools = self._handles(claim.get("basis_tool_handles"))
        if facts - set(manifest["facts"]):
            return self._reject("analysis_result_unknown_fact_handle", "unknown_fact")
        if tools - set(manifest["tools"]):
            return self._reject("analysis_result_unknown_tool_handle", "unknown_tool")
        if not (facts or tools):
            return self._reject("analysis_result_estimate_basis_missing", "estimate_basis")
        if not isinstance(claim.get("missing_inputs"), list) or any(not isinstance(item, str) for item in claim["missing_inputs"]):
            return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        sources = self._sources_for(facts, tools, manifest)
        if status == "NOT_ESTIMABLE":
            if (not isinstance(claim.get("reason"), str) or not claim["reason"].strip()
                    or not claim["missing_inputs"]):
                return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
            return {"class": "ESTIMATE", "estimate_status": status, "text": claim["reason"].strip(),
                    "confidence": "NOT_ESTIMABLE", "fact_handles": sorted(facts),
                    "tool_result_refs": sorted(tools), "source_refs": sorted(sources),
                    "assumptions": [], "missing_inputs": claim["missing_inputs"]}
        if (not isinstance(claim.get("value_or_range"), str) or not claim["value_or_range"].strip()
                or claim.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}
                or not isinstance(claim.get("assumptions"), list)
                or any(not isinstance(item, str) for item in claim["assumptions"])):
            return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        return {"class": "ESTIMATE", "estimate_status": status, "text": str(claim["value_or_range"]), "confidence": claim["confidence"],
                "fact_handles": sorted(facts), "tool_result_refs": sorted(tools), "source_refs": sorted(sources),
                "assumptions": claim["assumptions"], "missing_inputs": claim["missing_inputs"]}

    def _normalize_hypothesis(self, claim: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any] | ResultContractValidation:
        allowed = {"class", "statement", "support_fact_handles", "contradiction_fact_handles", "confirm_or_refute"}
        if set(claim) - allowed or not isinstance(claim.get("statement"), str) or not claim["statement"].strip():
            return self._reject("analysis_result_hypothesis_contract_invalid", "hypothesis_contract")
        support = self._handles(claim.get("support_fact_handles"))
        contradiction = self._handles(claim.get("contradiction_fact_handles"))
        if not support or (support | contradiction) - set(manifest["facts"]):
            return self._reject("analysis_result_unknown_fact_handle", "unknown_fact")
        if not isinstance(claim.get("confirm_or_refute"), str) or not claim["confirm_or_refute"].strip():
            return self._reject("analysis_result_hypothesis_contract_invalid", "hypothesis_contract")
        sources = self._sources_for(support | contradiction, set(), manifest)
        return {"class": "HYPOTHESIS", "text": claim["statement"].strip(), "support_fact_handles": sorted(support),
                "contradiction_fact_handles": sorted(contradiction), "confirm_or_refute": claim["confirm_or_refute"].strip(),
                "source_refs": sorted(sources)}

    def _normalize_missing(self, claim: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any] | ResultContractValidation:
        del manifest
        allowed = {"class", "item", "why_relevant", "estimable"}
        if set(claim) - allowed or not all(isinstance(claim.get(key), str) and claim[key].strip() for key in ("item", "why_relevant")):
            return self._reject("analysis_result_missing_contract_invalid", "missing_contract")
        if not isinstance(claim.get("estimable"), bool):
            return self._reject("analysis_result_missing_contract_invalid", "missing_contract")
        return {"class": "MISSING", "text": claim["item"].strip(), "why_relevant": claim["why_relevant"].strip(),
                "estimable": claim["estimable"], "source_refs": []}

    @classmethod
    def _manifest(cls, request: AnalysisRequest) -> dict[str, Any]:
        all_sources = {item.source_ref for item in request.source_refs}
        scope = request.structured_inputs.get("target_scope")
        scope_valid = True
        target_scope_handle = None
        sources = set(all_sources)
        if scope is not None:
            scope_valid = isinstance(scope, dict) and set(scope) == {
                "scope_handle", "allowed_source_handles", "global_source_handles",
            }
            if scope_valid:
                target_scope_handle = scope.get("scope_handle")
                allowed = scope.get("allowed_source_handles")
                global_sources = scope.get("global_source_handles")
                scope_valid = (
                    isinstance(target_scope_handle, str)
                    and re.fullmatch(r"TARGET_0[1-8]", target_scope_handle) is not None
                    and isinstance(allowed, list) and bool(allowed)
                    and isinstance(global_sources, list)
                    and all(isinstance(item, str) for item in allowed + global_sources)
                    and len(allowed) == len(set(allowed))
                    and len(global_sources) == len(set(global_sources))
                    and not (set(allowed) & set(global_sources))
                    and (set(allowed) | set(global_sources)).issubset(all_sources)
                )
                if scope_valid:
                    sources = set(allowed) | set(global_sources)
        facts: dict[str, dict[str, str]] = {}
        tools: dict[str, dict[str, Any]] = {}
        visuals: dict[str, dict[str, Any]] = {}
        for item in request.structured_inputs.get("claims", []):
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "FACT" and item.get("fact_handle") and item.get("source_handle") in sources:
                facts[str(item["fact_handle"])] = {
                    "statement": str(item.get("statement") or ""), "source_ref": str(item["source_handle"]),
                    "comparison_group": item.get("comparison_group"),
                    "contradiction_group": item.get("contradiction_group"),
                }
            elif item.get("kind") == "TOOL_RESULT" and item.get("tool_handle"):
                tool_sources = cls._item_source_handles(item)
                if tool_sources and tool_sources.issubset(sources):
                    tools[str(item["tool_handle"])] = {**item, "source_handles": sorted(tool_sources)}
            elif item.get("kind") == "VISUAL_OBSERVATION" and item.get("visual_handle"):
                visual_sources = set(item.get("source_handles") or [])
                if visual_sources and visual_sources.issubset(sources):
                    visuals[str(item["visual_handle"])] = item
        return {"sources": sources, "facts": facts, "tools": tools, "visuals": visuals,
                "scope_valid": scope_valid, "target_scope_handle": target_scope_handle}

    @staticmethod
    def _item_source_handles(item: dict[str, Any]) -> set[str]:
        if isinstance(item.get("source_handles"), list):
            return {str(value) for value in item["source_handles"] if isinstance(value, str)}
        return {str(item["source_handle"])} if isinstance(item.get("source_handle"), str) else set()

    @classmethod
    def allowed_source_refs(cls, request: AnalysisRequest) -> list[str]:
        manifest = cls._manifest(request)
        return sorted(manifest["sources"]) if manifest["scope_valid"] else []

    @staticmethod
    def _handles(value: Any) -> set[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            return set()
        return set(value)

    @staticmethod
    def _sources_for(facts: set[str], tools: set[str], manifest: dict[str, Any]) -> set[str]:
        sources = {manifest["facts"][handle]["source_ref"] for handle in facts}
        for handle in tools:
            item = manifest["tools"][handle]
            sources.update(item.get("source_handles") or [])
        return sources

    @classmethod
    def _reject(cls, code: str, issue: str) -> ResultContractValidation:
        return ResultContractValidation(True, "rejected", code, issues=(issue,))
