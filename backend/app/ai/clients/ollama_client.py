from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class OllamaClient:
    """
    Client responsible for communication with the Ollama REST API.
    """

    def __init__(self) -> None:
        self.base_url = (
            settings.ollama_url.rstrip("/")
        )

        self.timeout = httpx.Timeout(
            300.0
        )

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        format: str | dict[str, Any] | None = None,
        *,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
        keep_alive: str | int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if format is not None:
            payload["format"] = format
        if options is not None:
            payload["options"] = options
        if think is not None:
            payload["think"] = think
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )

            response.raise_for_status()

            return response.json()
