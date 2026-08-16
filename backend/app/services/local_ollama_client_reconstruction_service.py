from __future__ import annotations

import json
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
        request = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": ClientReconstructionProposal.model_json_schema(),
            "options": {"temperature": 0, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {
                    "role": "user",
                    "content": "SOURCE_EVIDENCE:\n"
                    + json.dumps(packet, ensure_ascii=False),
                },
            ],
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
        }
        try:
            proposal = ClientReconstructionProposal.model_validate_json(content)
        except ValidationError as error:
            raise LocalOllamaStructuredOutputError(
                raw_content=content, usage=usage, validation_error=error,
            ) from error
        return proposal, usage
