from __future__ import annotations

import asyncio

from app.ai.services.rag_service import (
    RagResponse,
    RagService,
)


QUESTIONS = [
    (
        "Na podstawie dokumentacji opisz, "
        "jakie informacje zawierają badania CPT "
        "i jakie parametry są w nich widoczne."
    ),
    (
        "Co dokumentacja mówi o pęknięciach "
        "lub zarysowaniach ścian?"
    ),
]


def print_response(
    number: int,
    response: RagResponse,
) -> None:
    print()
    print("=" * 110)
    print(
        f"RAG QUESTION #{number}"
    )
    print("=" * 110)

    print()
    print("QUESTION")
    print("-" * 110)
    print(
        response.question
    )

    print()
    print("MODEL")
    print("-" * 110)
    print(
        response.model
    )

    print()
    print("GENERATION")
    print("-" * 110)
    print(
        "attempts:",
        response.generation_attempts,
    )

    print()
    print("ANSWER")
    print("-" * 110)
    print(
        response.answer
    )

    print()
    print("SELECTED EVIDENCE")
    print("-" * 110)

    print(
        "count:",
        len(response.claims),
    )

    for claim in response.claims:
        print()
        print(
            "evidence_id:",
            claim.evidence_id,
        )

        print(
            "source_number:",
            claim.source_number,
        )

        print(
            "quote:",
            claim.quote,
        )


def validate_response(
    response: RagResponse,
) -> list[str]:
    errors: list[str] = []

    if not response.answer.strip():
        errors.append(
            "empty answer"
        )

    if not response.sources:
        errors.append(
            "no sources"
        )

    if not response.evidence:
        errors.append(
            "no evidence segments"
        )

    if not response.claims:
        errors.append(
            "no selected evidence"
        )

    evidence_map = {
        item.evidence_id: item
        for item in response.evidence
    }

    for claim in response.claims:
        item = evidence_map.get(
            claim.evidence_id
        )

        if item is None:
            errors.append(
                "unknown evidence ID"
            )

            continue

        if (
            claim.quote
            != item.text
        ):
            errors.append(
                "quote differs from "
                "backend evidence"
            )

        if (
            claim.source_number
            != item.source_number
        ):
            errors.append(
                "source mapping mismatch"
            )

    return errors


async def test_no_sources(
    service: RagService,
) -> list[str]:
    print()
    print("=" * 110)
    print("RAG NO-SOURCE TEST")
    print("=" * 110)

    response = (
        await service.answer(
            question=(
                "Jaki jest dokładny skład "
                "atmosfery planety Neptun "
                "według dokumentacji klienta?"
            ),
            model="llama3.2",
            retrieval_limit=5,
            score_threshold=0.95,
        )
    )

    print()
    print(
        "answer:",
        response.answer,
    )

    print(
        "sources:",
        len(response.sources),
    )

    print(
        "claims:",
        len(response.claims),
    )

    errors: list[str] = []

    if response.sources:
        errors.append(
            "no-source returned sources"
        )

    if response.claims:
        errors.append(
            "no-source returned claims"
        )

    if (
        "Nie znaleziono"
        not in response.answer
    ):
        errors.append(
            "missing safe answer"
        )

    return errors


async def main() -> None:
    print()
    print("=" * 110)
    print("RAG E2E - DETERMINISTIC EVIDENCE IDS")
    print("=" * 110)

    service = RagService()

    all_errors: list[str] = []

    for number, question in enumerate(
        QUESTIONS,
        start=1,
    ):
        response = (
            await service.answer(
                question=question,
                model="llama3.2",
                retrieval_limit=5,
            )
        )

        print_response(
            number,
            response,
        )

        for error in validate_response(
            response
        ):
            all_errors.append(
                f"Question #{number}: "
                f"{error}"
            )

    all_errors.extend(
        await test_no_sources(
            service
        )
    )

    print()
    print("=" * 110)
    print("STRUCTURAL VALIDATION")
    print("=" * 110)

    print(
        "questions:",
        len(QUESTIONS),
    )

    print(
        "validation_errors:",
        len(all_errors),
    )

    if all_errors:
        for error in all_errors:
            print(
                "FAIL:",
                error,
            )

        raise RuntimeError(
            "Evidence-ID RAG E2E failed."
        )

    print()
    print(
        "retrieval: OK"
    )

    print(
        "evidence segmentation: OK"
    )

    print(
        "evidence ID selection: OK"
    )

    print(
        "backend-controlled quotes: OK"
    )

    print(
        "source mapping: OK"
    )

    print(
        "no-source behavior: OK"
    )

    print()
    print("=" * 110)
    print("DETERMINISTIC EVIDENCE-ID RAG E2E: OK")
    print("=" * 110)


if __name__ == "__main__":
    asyncio.run(
        main()
    )
