from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.clients.ollama_client import OllamaClient
from app.schemas.agent import AgentSource
from app.schemas.unified_assistant import UnifiedAssistantRequest
from app.services.unified_assistant_service import (
    MODEL,
    MODEL_SCHEMA,
    _Collected,
    UnifiedAssistantService,
)
from local_llm_qualification_cases import QualificationCase, cases
from run_local_llm_qualification import score
from run_multi_model_pipeline_qualification import (
    deterministic_tool_results,
    deterministic_tools,
    escalation_decision,
)


def _latest(paths: list[Path]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["case_id"]] = row
    return rows


def _collected(case: QualificationCase) -> _Collected:
    sources = [
        AgentSource(
            source_type=source_ref.split(":", 1)[0],
            source_id=index,
            title=f"Frozen {source_ref}",
            route=None,
            snippet=value,
        )
        for index, (source_ref, value) in enumerate(case.evidence.items(), 1)
    ]
    source_keys = [(source.source_type, source.source_id, source.route) for source in sources]
    tool_payloads = [
        {"tool": item.get("tool", "calculation"), "data": item, "source_keys": source_keys}
        for item in deterministic_tool_results(case)
    ]
    return _Collected(
        sources=sources,
        tool_payloads=tool_payloads,
        tools=deterministic_tools(case),
        client_id=1 if "client:A" in case.evidence else None,
        visual_available=case.visual_required,
    )


def _for_frozen_score(payload: dict, case: QualificationCase) -> dict:
    handles = {
        f"S{index:02d}": source_ref
        for index, source_ref in enumerate(case.evidence, 1)
    }
    result = json.loads(json.dumps(payload))
    result["used_sources"] = [handles.get(value, value) for value in result.get("used_sources", [])]
    for claim in result.get("claims", []):
        claim["source_refs"] = [handles.get(value, value) for value in claim.get("source_refs", [])]
    estimate = result.get("estimate")
    if isinstance(estimate, dict):
        estimate["basis"] = [handles.get(value, value) for value in estimate.get("basis", [])]
    return result


def _to_production_handles(payload: dict, case: QualificationCase) -> dict:
    handles = {
        source_ref: f"S{index:02d}"
        for index, source_ref in enumerate(case.evidence, 1)
    }
    result = json.loads(json.dumps(payload))
    result["used_sources"] = [handles.get(value, value) for value in result.get("used_sources", [])]
    for claim in result.get("claims", []):
        claim["source_refs"] = [handles.get(value, value) for value in claim.get("source_refs", [])]
    estimate = result.get("estimate")
    if isinstance(estimate, dict):
        estimate["basis"] = [handles.get(value, value) for value in estimate.get("basis", [])]
    return result


def _mean(values) -> float:
    items = list(values)
    return statistics.mean(items) if items else 0.0


async def run(
    output: Path,
    advanced_paths: list[Path],
    case_ids: set[str] | None = None,
    saved_local: Path | None = None,
    supersede_paths: list[Path] | None = None,
    streaming_v2: bool = False,
) -> dict:
    llm = OllamaClient()
    async with llm.resource_session(MODEL, wait_timeout=None):
        return await _run_with_model(
            output=output,
            advanced_paths=advanced_paths,
            case_ids=case_ids,
            saved_local=saved_local,
            supersede_paths=supersede_paths,
            streaming_v2=streaming_v2,
            llm=llm,
        )


async def _run_with_model(
    *,
    output: Path,
    advanced_paths: list[Path],
    case_ids: set[str] | None,
    saved_local: Path | None,
    supersede_paths: list[Path] | None,
    streaming_v2: bool,
    llm: OllamaClient,
) -> dict:
    advanced = _latest(advanced_paths)
    saved = _latest([saved_local]) if saved_local else {}
    superseding = _latest(supersede_paths or [])
    results: list[dict] = []
    accepted: list[tuple[QualificationCase, dict]] = []
    local_count = advanced_count = review_count = failed_count = 0
    selected_cases = [case for case in cases() if not case_ids or case.case_id in case_ids]

    async def generate(prompt: str, schema: dict) -> dict:
        if not streaming_v2:
            return await service._generate_local(prompt, schema)
        raw = await llm.generate_streaming(
            model=MODEL,
            prompt=prompt,
            format=schema,
            options={"temperature": 0.1, "num_ctx": 4096, "num_predict": 480},
            think=False,
            keep_alive="5m",
        )
        return json.loads(str(raw.get("response") or "{}"))

    for case in selected_cases:
        collected = _collected(case)
        request = UnifiedAssistantRequest(question=case.question)
        prompt, source_map, tool_source_map = UnifiedAssistantService._prompt(request, collected)
        service = UnifiedAssistantService(SimpleNamespace(), llm_client=llm)
        bounded_schema = service._bounded_model_schema(
            set(source_map), set(tool_source_map)
        )
        if case.case_id in superseding:
            raw_response = superseding[case.case_id]["response"]
            response = service._resolve_tool_provenance(raw_response, tool_source_map)
        elif case.case_id in saved:
            raw_response = _to_production_handles(saved[case.case_id]["response"], case)
            response = service._resolve_tool_provenance(
                service._normalize_model_result(raw_response), tool_source_map
            )
        else:
            try:
                raw_response = await generate(prompt, bounded_schema)
                response = service._resolve_tool_provenance(
                    service._normalize_model_result(raw_response), tool_source_map
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                raw_response = {}
                response = {}
        evidence_aliases = {
            source_ref.rsplit(":", 1)[-1]
            for source_ref in case.evidence
            if ":" in source_ref and re.fullmatch(r"[A-Z]\d{1,3}", source_ref.rsplit(":", 1)[-1])
        }
        response = service._strip_known_output_handles(
            response, set(source_map) | set(tool_source_map) | evidence_aliases
        )
        validation = UnifiedAssistantService._validate(
            response, source_map, collected.visual_available, tool_source_map
        )
        if not saved_local and validation in {
            "invalid_schema", "estimate_contract", "hypothesis_contract",
            "missing_provenance", "source_binding",
        }:
            correction = service._format_correction_prompt(prompt, validation, raw_response)
            try:
                raw_response = await generate(correction, bounded_schema)
                response = service._resolve_tool_provenance(
                    service._normalize_model_result(raw_response), tool_source_map
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                response = {}
            response = service._strip_known_output_handles(
                response, set(source_map) | set(tool_source_map) | evidence_aliases
            )
            validation = UnifiedAssistantService._validate(
                response, source_map, collected.visual_available, tool_source_map
            )
        frozen_response = _for_frozen_score(response, case)
        local_score = score(case, frozen_response)
        sensitivity = (
            "customer_sanitizable" if case.case_id == "A05-privacy" else "public_reference"
        )
        difficulty = (
            None
            if validation is not None
            else UnifiedAssistantService._advanced_reason(request, response, collected)
        )
        local_gate = escalation_decision(sensitivity, local_score)
        if validation is None and difficulty is None and local_gate == "ACCEPT_LOCAL":
            decision = "accepted_local"
            final_score = local_score
            local_count += 1
        else:
            external = advanced.get(case.case_id)
            if external and external.get("contract_status") == "accepted_advanced" and external.get("score"):
                decision = "accepted_advanced"
                final_score = external["score"]
                advanced_count += 1
            elif external and external.get("contract_status") == "failed":
                decision = "failed"
                final_score = None
                failed_count += 1
            else:
                decision = "review_required"
                final_score = None
                review_count += 1
        if final_score is not None:
            accepted.append((case, final_score))
        results.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "validation": validation,
                "difficulty": difficulty,
                "local_gate": local_gate,
                "decision": decision,
                "score": final_score,
                "local_score": local_score,
                "response": response,
            }
        )
        print(
            f"{case.case_id}: {decision}; validation={validation}; "
            f"difficulty={difficulty}; gate={local_gate}",
            flush=True,
        )
        if decision == "review_required":
            print(json.dumps(response, ensure_ascii=False), flush=True)

    scores = [item for _, item in accepted]
    technical = [(case, item) for case, item in accepted if case.category in {"technical", "document"}]
    summary = {
        "execution_path": "assistant_pipeline_v2_streaming_adapter" if streaming_v2 else "legacy_non_streaming_adapter",
        "cases": len(selected_cases),
        "auto_local": local_count,
        "auto_advanced": advanced_count,
        "review": review_count,
        "failed": failed_count,
        "automatic_coverage_percent": round(100 * len(accepted) / len(selected_cases), 2),
        "overall": round(_mean(item["overall"] for item in scores), 2),
        "factual_evidence": round(
            _mean(0.5 * (item["factual"] + item["evidence"]) for item in scores), 2
        ),
        "technical_documentation": round(
            _mean(
                0.45 * item["factual"]
                + 0.35 * item["evidence"]
                + 0.10 * (100 if item["estimate"] else 0)
                + 0.10 * item["polish"]
                for _, item in technical
            ),
            2,
        ),
        "cross_domain": round(
            _mean(item["overall"] for case, item in accepted if case.category == "cross_domain"),
            2,
        ),
        "estimate_refusal_percent": round(
            100 * sum(bool(item["estimate"]) for item in scores) / len(scores), 2
        ) if scores else 0.0,
        "hard_failure_cases": sum(bool(item["hard_failures"]) for item in scores),
        "wrong_source_cases": sum(bool(item["foreign_sources"]) for item in scores),
        "privacy_failures": sum(not item["privacy"] for item in scores),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
        encoding="utf-8",
    )
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test/reports/private/unified_assistant/frozen-f0.jsonl"),
    )
    parser.add_argument("--advanced", type=Path, nargs="+", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--saved-local", type=Path)
    parser.add_argument("--supersede", type=Path, nargs="*", default=[])
    parser.add_argument("--streaming-v2", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        run(
            args.output,
            args.advanced,
            set(args.case) or None,
            saved_local=args.saved_local,
            supersede_paths=args.supersede,
            streaming_v2=args.streaming_v2,
        )
    )


if __name__ == "__main__":
    main()
