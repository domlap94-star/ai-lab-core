from __future__ import annotations

import math

from app.services.qdrant_vector_store import QdrantVectorStore
from app.services.semantic_search_service import SemanticSearchService


QUERIES = [
    "problemy z pękaniem ścian",
    "osiadanie fundamentów",
    "badania gruntu CPT",
    "umowa dotycząca podnoszenia posadzki",
]


def clean_fragment(
    text: str,
    *,
    max_length: int = 500,
) -> str:
    text = " ".join(
        text.split()
    )

    if len(text) <= max_length:
        return text

    return (
        text[:max_length]
        + "..."
    )


def print_result(
    index: int,
    result,
) -> None:
    print()
    print(
        f"RESULT #{index}"
    )
    print("-" * 110)

    print(
        "score:",
        round(
            result.score,
            6,
        ),
    )

    print(
        "document_id:",
        result.document_id,
    )

    print(
        "chunk_id:",
        result.chunk_id,
    )

    print(
        "chunk_index:",
        result.chunk_index,
    )

    print(
        "filename:",
        result.filename,
    )

    print(
        "page_from:",
        result.page_from,
    )

    print(
        "page_to:",
        result.page_to,
    )

    print(
        "client_id:",
        result.client_id,
    )

    print(
        "content_type:",
        result.content_type,
    )

    print(
        "content_source:",
        result.content_source,
    )

    print(
        "fragment:",
        clean_fragment(
            result.content
        ),
    )


def validate_result(
    result,
) -> list[str]:
    errors: list[str] = []

    if not math.isfinite(
        result.score
    ):
        errors.append(
            "score is not finite"
        )

    if result.chunk_id <= 0:
        errors.append(
            "invalid chunk_id"
        )

    if result.document_id <= 0:
        errors.append(
            "invalid document_id"
        )

    if result.chunk_index < 0:
        errors.append(
            "invalid chunk_index"
        )

    if not result.content.strip():
        errors.append(
            "empty content"
        )

    return errors


def main() -> None:
    print()
    print("=" * 110)
    print("SEMANTIC SEARCH E2E")
    print("=" * 110)

    vector_store = (
        QdrantVectorStore()
    )

    vector_store.ensure_collection()

    vector_count = (
        vector_store.count()
    )

    print()
    print("QDRANT")
    print("-" * 110)

    print(
        "collection:",
        vector_store.collection_name,
    )

    print(
        "vectors:",
        vector_count,
    )

    print(
        "dimensions:",
        vector_store.dimensions,
    )

    if vector_count == 0:
        raise RuntimeError(
            "Qdrant collection is empty."
        )

    search_service = (
        SemanticSearchService()
    )

    total_results = 0
    validation_errors: list[str] = []

    for query_number, query in enumerate(
        QUERIES,
        start=1,
    ):
        print()
        print()
        print("=" * 110)

        print(
            f"QUERY #{query_number}: "
            f"{query}"
        )

        print("=" * 110)

        results = (
            search_service.search(
                query=query,
                limit=5,
            )
        )

        print()
        print(
            "results:",
            len(results),
        )

        if not results:
            validation_errors.append(
                f'No results for query: "{query}"'
            )

            continue

        total_results += len(
            results
        )

        previous_score = None

        for index, result in enumerate(
            results,
            start=1,
        ):
            print_result(
                index,
                result,
            )

            result_errors = (
                validate_result(
                    result
                )
            )

            for error in result_errors:
                validation_errors.append(
                    f'Query "{query}", '
                    f"result #{index}: "
                    f"{error}"
                )

            if (
                previous_score is not None
                and result.score
                > previous_score
            ):
                validation_errors.append(
                    f'Query "{query}": '
                    "results are not sorted "
                    "by descending score"
                )

            previous_score = (
                result.score
            )

    print()
    print()
    print("=" * 110)
    print("STRUCTURAL VALIDATION")
    print("=" * 110)

    print(
        "queries:",
        len(QUERIES),
    )

    print(
        "total_results:",
        total_results,
    )

    print(
        "validation_errors:",
        len(validation_errors),
    )

    if validation_errors:
        print()

        for error in validation_errors:
            print(
                "FAIL:",
                error,
            )

        raise RuntimeError(
            "Semantic search structural "
            "validation failed."
        )

    print()
    print(
        "semantic search returned "
        "valid ranked results: OK"
    )

    print()
    print("=" * 110)
    print("SEMANTIC SEARCH E2E: OK")
    print("=" * 110)

    print()
    print(
        "IMPORTANT: semantic relevance "
        "must now be reviewed manually "
        "from the printed results."
    )


if __name__ == "__main__":
    main()
