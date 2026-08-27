from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.config import settings
from app.services.local_model_resource_coordinator import (
    LEGACY_RESOURCE_WAIT_SECONDS,
    LocalModelResourceCoordinator,
    ResourceCallback,
    local_model_resource_coordinator,
)


class OllamaClient:
    """
    Client responsible for communication with the Ollama REST API.
    """

    def __init__(
        self,
        *,
        resource_coordinator: LocalModelResourceCoordinator | None = None,
    ) -> None:
        self.base_url = (
            settings.ollama_url.rstrip("/")
        )

        self.timeout = httpx.Timeout(
            300.0
        )
        self.resource_coordinator = (
            resource_coordinator or local_model_resource_coordinator
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
        resource_wait_timeout: float | None = LEGACY_RESOURCE_WAIT_SECONDS,
        on_resource_wait: ResourceCallback | None = None,
        on_resource_ready: ResourceCallback | None = None,
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

        if stream:
            return await self.generate_streaming(
                model=model,
                prompt=prompt,
                format=format,
                options=options,
                think=think,
                keep_alive=keep_alive,
                resource_wait_timeout=resource_wait_timeout,
                on_resource_wait=on_resource_wait,
                on_resource_ready=on_resource_ready,
            )

        async with self.resource_session(
            model,
            wait_timeout=resource_wait_timeout,
            on_wait=on_resource_wait,
            on_ready=on_resource_ready,
        ):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )

                response.raise_for_status()

                return response.json()

    async def generate_streaming(
        self,
        *,
        model: str,
        prompt: str,
        format: str | dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
        keep_alive: str | int | None = None,
        on_progress: Callable[[dict[str, int | bool]], Awaitable[None] | None] | None = None,
        resource_wait_timeout: float | None = LEGACY_RESOURCE_WAIT_SECONDS,
        on_resource_wait: ResourceCallback | None = None,
        on_resource_ready: ResourceCallback | None = None,
    ) -> dict[str, Any]:
        """Consume Ollama NDJSON without retaining partial reasoning.

        Only aggregate output is returned to the caller.  The callback receives
        bounded counters/durations and never generated text.
        """
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True}
        if format is not None:
            payload["format"] = format
        if options is not None:
            payload["options"] = options
        if think is not None:
            payload["think"] = think
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        chunks: list[str] = []
        last: dict[str, Any] = {}
        received_chunks = 0
        async with self.resource_session(
            model,
            wait_timeout=resource_wait_timeout,
            on_wait=on_resource_wait,
            on_ready=on_resource_ready,
        ):
            async with httpx.AsyncClient(timeout=httpx.Timeout(1200.0)) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        received_chunks += 1
                        fragment = event.get("response")
                        if isinstance(fragment, str):
                            chunks.append(fragment)
                        last = event
                        if on_progress is not None:
                            telemetry: dict[str, int | bool] = {
                                "chunks": received_chunks,
                                "done": bool(event.get("done", False)),
                            }
                            for key in (
                                "load_duration", "prompt_eval_count", "prompt_eval_duration",
                                "eval_count", "eval_duration", "total_duration",
                            ):
                                value = event.get(key)
                                if isinstance(value, int) and value >= 0:
                                    telemetry[key] = value
                            callback_result = on_progress(telemetry)
                            if inspect.isawaitable(callback_result):
                                await callback_result
        if not last.get("done"):
            raise RuntimeError("OLLAMA_STREAM_INCOMPLETE")
        return {**last, "response": "".join(chunks)}

    async def unload(self, model: str) -> None:
        """Release only a model owned by this NEXT Stabil resource lease."""
        await self.resource_coordinator.unload_owned_model(model)

    def resource_session(
        self,
        model: str,
        *,
        wait_timeout: float | None = LEGACY_RESOURCE_WAIT_SECONDS,
        on_wait: ResourceCallback | None = None,
        on_ready: ResourceCallback | None = None,
    ):
        return self.resource_coordinator.generator_session(
            model,
            wait_timeout=wait_timeout,
            on_wait=on_wait,
            on_ready=on_ready,
        )
