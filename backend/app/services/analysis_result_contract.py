from __future__ import annotations

from dataclasses import dataclass
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
        for group in {item.get("contradiction_group") for item in manifest["facts"].values()} - {None}:
            members = {handle for handle, item in manifest["facts"].items() if item.get("contradiction_group") == group}
            if len(selected_facts & members) >= 2 and not members.issubset(contradiction_handles):
                return self._reject("analysis_result_material_contradiction_missing", "contradiction_missing")

        artifact = {
            "schema": self.SCHEMA,
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
        allowed = {"class", "value_or_range", "confidence", "basis_fact_handles", "basis_tool_handles", "assumptions", "missing_inputs"}
        if set(claim) - allowed:
            return self._reject("analysis_result_claim_schema_invalid", "claim_schema")
        facts = self._handles(claim.get("basis_fact_handles"))
        tools = self._handles(claim.get("basis_tool_handles"))
        if facts - set(manifest["facts"]):
            return self._reject("analysis_result_unknown_fact_handle", "unknown_fact")
        if tools - set(manifest["tools"]):
            return self._reject("analysis_result_unknown_tool_handle", "unknown_tool")
        if not (facts or tools):
            return self._reject("analysis_result_estimate_basis_missing", "estimate_basis")
        if not claim.get("value_or_range") or claim.get("confidence") not in self.CONFIDENCE:
            return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        if not isinstance(claim.get("assumptions"), list) or not isinstance(claim.get("missing_inputs"), list):
            return self._reject("analysis_result_estimate_contract_invalid", "estimate_contract")
        sources = self._sources_for(facts, tools, manifest)
        return {"class": "ESTIMATE", "text": str(claim["value_or_range"]), "confidence": claim["confidence"],
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

    @staticmethod
    def _manifest(request: AnalysisRequest) -> dict[str, Any]:
        sources = {item.source_ref for item in request.source_refs}
        facts: dict[str, dict[str, str]] = {}
        tools: dict[str, dict[str, Any]] = {}
        visuals: dict[str, dict[str, Any]] = {}
        for item in request.structured_inputs.get("claims", []):
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "FACT" and item.get("fact_handle") and item.get("source_handle") in sources:
                facts[str(item["fact_handle"])] = {
                    "statement": str(item.get("statement") or ""), "source_ref": str(item["source_handle"]),
                    "contradiction_group": item.get("contradiction_group"),
                }
            elif (item.get("kind") == "TOOL_RESULT" and item.get("tool_handle")
                  and item.get("source_handle") in sources):
                tools[str(item["tool_handle"])] = item
            elif item.get("kind") == "VISUAL_OBSERVATION" and item.get("visual_handle"):
                visual_sources = set(item.get("source_handles") or [])
                if visual_sources and visual_sources.issubset(sources):
                    visuals[str(item["visual_handle"])] = item
        return {"sources": sources, "facts": facts, "tools": tools, "visuals": visuals}

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
            if item.get("source_handle"):
                sources.add(str(item["source_handle"]))
        return sources

    @classmethod
    def _reject(cls, code: str, issue: str) -> ResultContractValidation:
        return ResultContractValidation(True, "rejected", code, issues=(issue,))
