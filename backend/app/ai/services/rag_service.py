from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.ai.clients.ollama_client import OllamaClient
from app.services.semantic_search_service import (
    SemanticSearchResult,
    SemanticSearchService,
)


@dataclass(frozen=True)
class RagSource:
    source_number: int
    score: float

    document_id: int
    chunk_id: int
    chunk_index: int

    filename: str | None

    page_from: int | None
    page_to: int | None

    client_id: int | None

    content_source: str | None

    fragment: str


@dataclass(frozen=True)
class RagEvidence:
    evidence_id: int
    source_number: int
    text: str


@dataclass(frozen=True)
class RagClaim:
    evidence_id: int
    source_number: int
    quote: str


@dataclass(frozen=True)
class RagResponse:
    question: str
    answer: str
    model: str

    sources: list[RagSource]
    evidence: list[RagEvidence]
    claims: list[RagClaim]

    cited_source_numbers: list[int]
    generation_attempts: int


class RagService:
    """
    Deterministic evidence-selection RAG.

    The LLM never generates source text.

    Backend flow:

    retrieved chunks
        ->
    deterministic evidence segments
        ->
    numbered EVIDENCE_ID values
        ->
    LLM selects evidence IDs only
        ->
    backend resolves exact original text
        ->
    grounded response

    This prevents the LLM from changing:
    - numbers,
    - units,
    - technical symbols,
    - OCR text,
    - quotations,
    - formulas.
    """

    MAX_GENERATION_ATTEMPTS = 2

    MIN_EVIDENCE_CHARS = 25
    MAX_EVIDENCE_CHARS = 900

    def __init__(self) -> None:
        self.search_service = (
            SemanticSearchService()
        )

        self.llm_client = (
            OllamaClient()
        )

    async def answer(
        self,
        *,
        question: str,
        model: str = "llama3.2",
        retrieval_limit: int = 5,
        client_id: int | None = None,
        document_id: int | None = None,
        content_type: str | None = None,
        score_threshold: float | None = None,
    ) -> RagResponse:
        cleaned_question = (
            question.strip()
        )

        if not cleaned_question:
            raise ValueError(
                "Question cannot be empty."
            )

        if retrieval_limit <= 0:
            raise ValueError(
                "retrieval_limit must be greater than 0."
            )

        results = (
            self.search_service.search(
                query=cleaned_question,
                limit=retrieval_limit,
                client_id=client_id,
                document_id=document_id,
                content_type=content_type,
                score_threshold=score_threshold,
            )
        )

        sources = (
            self._build_sources(
                results
            )
        )

        if not sources:
            return self._no_source_response(
                question=cleaned_question,
                model=model,
            )

        evidence = (
            self._build_evidence(
                sources
            )
        )

        if not evidence:
            return self._no_source_response(
                question=cleaned_question,
                model=model,
            )

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.MAX_GENERATION_ATTEMPTS + 1,
        ):
            prompt = (
                self._build_prompt(
                    question=cleaned_question,
                    evidence=evidence,
                    retry=(
                        attempt > 1
                    ),
                )
            )

            response = (
                await self.llm_client.generate(
                    model=model,
                    prompt=prompt,
                    stream=False,
                    format=(
                        self._build_output_schema(
                            evidence
                        )
                    ),
                )
            )

            response_model = str(
                response.get(
                    "model",
                    model,
                )
            )

            raw_answer = str(
                response.get(
                    "response",
                    "",
                )
            ).strip()

            if not raw_answer:
                last_error = RuntimeError(
                    "Ollama returned an empty "
                    "RAG response."
                )

                continue

            try:
                selected_ids = (
                    self._parse_selected_evidence(
                        raw_answer=raw_answer,
                        evidence=evidence,
                    )
                )

                if not selected_ids:
                    last_error = RuntimeError(
                        "LLM selected no evidence despite "
                        "available retrieval sources."
                    )

                    continue

                claims = (
                    self._resolve_claims(
                        evidence_ids=selected_ids,
                        evidence=evidence,
                    )
                )

                answer = (
                    self._render_answer(
                        claims
                    )
                )

                cited_source_numbers = sorted(
                    {
                        claim.source_number
                        for claim in claims
                    }
                )

                return RagResponse(
                    question=cleaned_question,
                    answer=answer,
                    model=response_model,
                    sources=sources,
                    evidence=evidence,
                    claims=claims,
                    cited_source_numbers=(
                        cited_source_numbers
                    ),
                    generation_attempts=attempt,
                )

            except (
                ValueError,
                RuntimeError,
                json.JSONDecodeError,
            ) as error:
                last_error = error

        raise RuntimeError(
            "Evidence-ID RAG contract failed "
            "after retry. "
            f"{last_error}"
        )

    @staticmethod
    def _no_source_response(
        *,
        question: str,
        model: str,
    ) -> RagResponse:
        return RagResponse(
            question=question,
            answer=(
                "Nie znaleziono wystarczających "
                "źródeł w dokumentacji, aby "
                "udzielić odpowiedzi."
            ),
            model=model,
            sources=[],
            evidence=[],
            claims=[],
            cited_source_numbers=[],
            generation_attempts=0,
        )

    def _build_sources(
        self,
        results: list[
            SemanticSearchResult
        ],
    ) -> list[RagSource]:
        sources: list[RagSource] = []

        for result in results:
            fragment = (
                self._normalize_text(
                    result.content
                )
            )

            if not fragment:
                continue

            sources.append(
                RagSource(
                    source_number=(
                        len(sources) + 1
                    ),
                    score=result.score,
                    document_id=(
                        result.document_id
                    ),
                    chunk_id=(
                        result.chunk_id
                    ),
                    chunk_index=(
                        result.chunk_index
                    ),
                    filename=(
                        result.filename
                    ),
                    page_from=(
                        result.page_from
                    ),
                    page_to=(
                        result.page_to
                    ),
                    client_id=(
                        result.client_id
                    ),
                    content_source=(
                        result.content_source
                    ),
                    fragment=fragment,
                )
            )

        return sources

    def _build_evidence(
        self,
        sources: list[RagSource],
    ) -> list[RagEvidence]:
        evidence: list[RagEvidence] = []

        for source in sources:
            segments = (
                self._segment_text(
                    source.fragment
                )
            )

            for segment in segments:
                evidence.append(
                    RagEvidence(
                        evidence_id=(
                            len(evidence) + 1
                        ),
                        source_number=(
                            source.source_number
                        ),
                        text=segment,
                    )
                )

        return evidence

    def _segment_text(
        self,
        text: str,
    ) -> list[str]:
        normalized = (
            self._normalize_text(
                text
            )
        )

        if not normalized:
            return []

        raw_segments = re.split(
            r"(?<=[.!?])\s+"
            r"|(?=\s*[©@]\s+)",
            normalized,
        )

        segments: list[str] = []

        for raw_segment in raw_segments:
            segment = (
                raw_segment.strip()
            )

            if (
                len(segment)
                < self.MIN_EVIDENCE_CHARS
            ):
                continue

            if (
                len(segment)
                <= self.MAX_EVIDENCE_CHARS
            ):
                segments.append(
                    segment
                )

                continue

            segments.extend(
                self._split_long_segment(
                    segment
                )
            )

        if not segments:
            segments.append(
                normalized[
                    :self.MAX_EVIDENCE_CHARS
                ]
            )

        return segments

    def _split_long_segment(
        self,
        text: str,
    ) -> list[str]:
        parts: list[str] = []

        remaining = text

        while len(
            remaining
        ) > self.MAX_EVIDENCE_CHARS:
            split_at = remaining.rfind(
                " ",
                0,
                self.MAX_EVIDENCE_CHARS,
            )

            if split_at < 100:
                split_at = (
                    self.MAX_EVIDENCE_CHARS
                )

            part = (
                remaining[
                    :split_at
                ].strip()
            )

            if (
                len(part)
                >= self.MIN_EVIDENCE_CHARS
            ):
                parts.append(
                    part
                )

            remaining = (
                remaining[
                    split_at:
                ].strip()
            )

        if (
            len(remaining)
            >= self.MIN_EVIDENCE_CHARS
        ):
            parts.append(
                remaining
            )

        return parts

    def _build_prompt(
        self,
        *,
        question: str,
        evidence: list[RagEvidence],
        retry: bool,
    ) -> str:
        context = (
            self._format_evidence(
                evidence
            )
        )

        retry_text = ""

        if retry:
            retry_text = """
POPRZEDNIA PRÓBA NIE SPEŁNIŁA KONTRAKTU.

Wybierz ponownie wyłącznie EVIDENCE_ID
najbardziej bezpośrednio odpowiadające
na pytanie.
""".strip()

        return f"""
Jesteś modułem wyboru źródeł systemu AI-Lab.

Nie generujesz odpowiedzi tekstowej.

Nie parafrazujesz dokumentacji.

Nie wykonujesz obliczeń.

Nie interpretujesz danych samodzielnie.

Twoim jedynym zadaniem jest wskazanie
EVIDENCE_ID fragmentów, które najlepiej
odpowiadają na pytanie użytkownika.

ZASADY:

1. Zwróć wyłącznie listę evidence_ids.

2. Możesz wybrać wyłącznie istniejące
   EVIDENCE_ID.

3. Wybieraj fragmenty, które bezpośrednio
   odpowiadają na pytanie.

4. Nie wybieraj fragmentu tylko dlatego,
   że zawiera pojedyncze podobne słowo.

5. Dla pytania o parametry preferuj
   fragmenty, które wprost opisują
   nazwy parametrów.

6. Dla pytania o przyczyny preferuj
   fragmenty, które wprost opisują
   przyczynę lub obserwację.

7. Nie obliczaj nowych wartości.

8. Nie korzystaj z wiedzy ogólnej.

9. Wybierz maksymalnie 6 fragmentów.

10. Jeśli żaden fragment nie odpowiada
    na pytanie, zwróć pustą listę.

{retry_text}

PYTANIE:

{question}

DOSTĘPNE FRAGMENTY:

{context}
""".strip()

    @staticmethod
    def _build_output_schema(
        evidence: list[RagEvidence],
    ) -> dict[str, Any]:
        valid_ids = [
            item.evidence_id
            for item in evidence
        ]

        return {
            "type": "object",
            "properties": {
                "evidence_ids": {
                    "type": "array",
                    "maxItems": 6,
                    "uniqueItems": True,
                    "items": {
                        "type": "integer",
                        "enum": valid_ids,
                    },
                },
            },
            "required": [
                "evidence_ids",
            ],
            "additionalProperties": False,
        }

    @staticmethod
    def _format_evidence(
        evidence: list[RagEvidence],
    ) -> str:
        parts: list[str] = []

        for item in evidence:
            parts.append(
                "\n".join(
                    [
                        (
                            f"[EVIDENCE "
                            f"{item.evidence_id}]"
                        ),
                        (
                            "EVIDENCE_ID: "
                            f"{item.evidence_id}"
                        ),
                        (
                            "SOURCE_INDEX: "
                            f"{item.source_number}"
                        ),
                        "TEXT:",
                        item.text,
                    ]
                )
            )

        return "\n\n".join(
            parts
        )

    def _parse_selected_evidence(
        self,
        *,
        raw_answer: str,
        evidence: list[RagEvidence],
    ) -> list[int]:
        json_text = (
            self._extract_json_text(
                raw_answer
            )
        )

        data = json.loads(
            json_text
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "RAG response must be "
                "a JSON object."
            )

        raw_ids = data.get(
            "evidence_ids"
        )

        if not isinstance(
            raw_ids,
            list,
        ):
            raise ValueError(
                "RAG response must contain "
                "evidence_ids list."
            )

        valid_ids = {
            item.evidence_id
            for item in evidence
        }

        selected: list[int] = []

        for raw_id in raw_ids:
            try:
                evidence_id = int(
                    raw_id
                )

            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Invalid evidence ID."
                ) from error

            if evidence_id not in valid_ids:
                raise ValueError(
                    "Unknown evidence ID: "
                    f"{evidence_id}"
                )

            if evidence_id not in selected:
                selected.append(
                    evidence_id
                )

        return selected

    @staticmethod
    def _resolve_claims(
        *,
        evidence_ids: list[int],
        evidence: list[RagEvidence],
    ) -> list[RagClaim]:
        evidence_map = {
            item.evidence_id: item
            for item in evidence
        }

        claims: list[RagClaim] = []

        for evidence_id in evidence_ids:
            item = evidence_map[
                evidence_id
            ]

            claims.append(
                RagClaim(
                    evidence_id=(
                        evidence_id
                    ),
                    source_number=(
                        item.source_number
                    ),
                    quote=item.text,
                )
            )

        return claims

    @staticmethod
    def _render_answer(
        claims: list[RagClaim],
    ) -> str:
        return "\n".join(
            [
                (
                    f'- "{claim.quote}" '
                    f"[SOURCE "
                    f"{claim.source_number}; "
                    f"EVIDENCE "
                    f"{claim.evidence_id}]"
                )
                for claim in claims
            ]
        )

    @staticmethod
    def _extract_json_text(
        text: str,
    ) -> str:
        cleaned = text.strip()

        if cleaned.startswith(
            "```"
        ):
            cleaned = re.sub(
                r"^```(?:json)?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

            cleaned = re.sub(
                r"\s*```$",
                "",
                cleaned,
            )

        first = cleaned.find(
            "{"
        )

        last = cleaned.rfind(
            "}"
        )

        if (
            first == -1
            or last == -1
            or last < first
        ):
            raise ValueError(
                "No JSON object found "
                "in RAG response."
            )

        return cleaned[
            first:
            last + 1
        ]

    @staticmethod
    def _normalize_text(
        text: str,
        *,
        max_chars: int = 3500,
    ) -> str:
        normalized = " ".join(
            text.split()
        )

        if len(normalized) <= max_chars:
            return normalized

        return (
            normalized[:max_chars]
            + "..."
        )
