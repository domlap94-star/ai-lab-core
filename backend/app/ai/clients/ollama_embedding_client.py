from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class EmbeddingResponse:
    model: str
    embeddings: list[list[float]]
    prompt_eval_count: int | None
    total_duration: int | None
    load_duration: int | None


class OllamaEmbeddingClient:
    def __init__(self) -> None:
        self.base_url = (
            settings.ollama_url.rstrip("/")
        )

        self.model = (
            settings.embedding_model
        )

        self.dimensions = (
            settings.embedding_dimensions
        )

        self.timeout = httpx.Timeout(
            300.0
        )

    def embed(
        self,
        texts: list[str],
    ) -> EmbeddingResponse:
        if not texts:
            return EmbeddingResponse(
                model=self.model,
                embeddings=[],
                prompt_eval_count=0,
                total_duration=0,
                load_duration=0,
            )

        payload = {
            "model": self.model,
            "input": texts,
            "truncate": True,
        }

        with httpx.Client(
            timeout=self.timeout,
        ) as client:
            response = client.post(
                f"{self.base_url}/api/embed",
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

        embeddings = data.get(
            "embeddings",
            [],
        )

        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Embedding count mismatch: "
                f"inputs={len(texts)}, "
                f"vectors={len(embeddings)}."
            )

        for index, vector in enumerate(
            embeddings
        ):
            if (
                len(vector)
                != self.dimensions
            ):
                raise RuntimeError(
                    "Embedding dimension mismatch "
                    f"at index {index}: "
                    f"expected={self.dimensions}, "
                    f"actual={len(vector)}."
                )

        return EmbeddingResponse(
            model=data.get(
                "model",
                self.model,
            ),
            embeddings=embeddings,
            prompt_eval_count=(
                data.get(
                    "prompt_eval_count"
                )
            ),
            total_duration=(
                data.get(
                    "total_duration"
                )
            ),
            load_duration=(
                data.get(
                    "load_duration"
                )
            ),
        )

    def embed_one(
        self,
        text: str,
    ) -> list[float]:
        result = self.embed(
            [text]
        )

        if not result.embeddings:
            raise RuntimeError(
                "Ollama returned no embedding."
            )

        return result.embeddings[0]