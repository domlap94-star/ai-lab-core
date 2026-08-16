from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.client_reconstruction import ClientReconstructionProposal
from app.services.openai_client_reconstruction_service import SYSTEM_INSTRUCTION


class LocalOllamaStructuredOutputError(ValueError):
    """Preserves a private malformed response for durable calibration diagnostics."""

    def __init__(self, *, raw_content: str, usage: dict[str, int | float],
                 validation_error: ValidationError) -> None:
        super().__init__("Ollama structured output validation failed")
        self.raw_content = raw_content
        self.usage = usage
        self.validation_error = str(validation_error)


class ReconstructionPromptTooLargeError(ValueError):
    """Neutral hook for future chunked processing; no model call was made."""

    def __init__(self, estimated_input_tokens: int) -> None:
        super().__init__("PROMPT_TOO_LARGE")
        self.estimated_input_tokens = estimated_input_tokens


MIN_OUTPUT_RESERVE = 1024
NORMAL_CONTEXT = 4096
EXPANDED_CONTEXT = 8192
ESTIMATED_BYTES_PER_TOKEN = 2.5
TOKEN_ESTIMATE_OVERHEAD = 256


def dynamic_proposal_schema(packet: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(ClientReconstructionProposal.model_json_schema())
    references = []
    seen: set[tuple[str, str]] = set()
    for source in packet.get("source_evidence", []):
        source_type = str(source["source_type"])
        source_id = source["source_id"]
        key = (source_type, str(source_id))
        if key in seen:
            continue
        seen.add(key)
        references.append({
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "source_type": {"const": source_type},
                "source_id": {"const": source_id},
                "field": {"type": "string"},
            },
            "required": ["source_type", "source_id", "field"],
        })
    evidence = schema["properties"]["evidence_refs"]
    if references:
        evidence["items"] = {"oneOf": references}
    else:
        evidence["items"] = False
        evidence["maxItems"] = 0
    return schema


def estimate_prompt_tokens(*, messages: list[dict[str, str]], schema: dict[str, Any]) -> int:
    serialized = json.dumps({"messages": messages, "format": schema}, ensure_ascii=False)
    return math.ceil(len(serialized.encode("utf-8")) / ESTIMATED_BYTES_PER_TOKEN) + TOKEN_ESTIMATE_OVERHEAD


def select_context(estimated_input_tokens: int) -> int:
    if estimated_input_tokens + MIN_OUTPUT_RESERVE <= NORMAL_CONTEXT:
        return NORMAL_CONTEXT
    if estimated_input_tokens + MIN_OUTPUT_RESERVE <= EXPANDED_CONTEXT:
        return EXPANDED_CONTEXT
    raise ReconstructionPromptTooLargeError(estimated_input_tokens)


class LocalOllamaClientReconstructionService:
    """Toolless local evaluator using the same Phase 1A schema and policy."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.model = model
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.timeout = timeout

    def evaluate(
        self,
        packet: dict[str, Any],
    ) -> tuple[ClientReconstructionProposal, dict[str, int | float]]:
        schema = dynamic_proposal_schema(packet)
        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": "SOURCE_EVIDENCE:\n" + json.dumps(packet, ensure_ascii=False),
            },
        ]
        estimated_input_tokens = estimate_prompt_tokens(messages=messages, schema=schema)
        effective_num_ctx = select_context(estimated_input_tokens)
        request = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": effective_num_ctx,
                        "num_predict": MIN_OUTPUT_RESERVE},
            "messages": messages,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=request)
        response.raise_for_status()
        body = response.json()
        content = str((body.get("message") or {}).get("content") or "")
        prompt_count = int(body.get("prompt_eval_count") or 0)
        eval_count = int(body.get("eval_count") or 0)
        eval_duration = int(body.get("eval_duration") or 0)
        usage = {
            "input_tokens": prompt_count,
            "output_tokens": eval_count,
            "load_duration_ns": int(body.get("load_duration") or 0),
            "prompt_eval_duration_ns": int(body.get("prompt_eval_duration") or 0),
            "generation_duration_ns": eval_duration,
            "total_duration_ns": int(body.get("total_duration") or 0),
            "tokens_per_second": (
                eval_count / (eval_duration / 1_000_000_000)
                if eval_duration else 0.0
            ),
            "estimated_input_tokens": estimated_input_tokens,
            "effective_num_ctx": effective_num_ctx,
        }
        try:
            proposal = ClientReconstructionProposal.model_validate_json(content)
        except ValidationError as error:
            raise LocalOllamaStructuredOutputError(
                raw_content=content, usage=usage, validation_error=error,
            ) from error
        return proposal, usage
