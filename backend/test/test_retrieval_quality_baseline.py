from __future__ import annotations

from dataclasses import dataclass

from app.services.semantic_search_service import (
    SemanticSearchResult,
    SemanticSearchService,
)


@dataclass(frozen=True)
class RetrievalCase:
    name: str
    query: str

    expected_document_ids: tuple[int, ...]

    expected_filename_contains: tuple[str, ...] = ()

    forbidden_content_contains: tuple[str, ...] = (
        "----- Message truncated -----",
    )

    top_k: int = 5


CASES = [
    RetrievalCase(
        name="wall_cracks",
        query="problemy z pękaniem ścian",
        expected_document_ids=(
            770,
        ),
        expected_filename_contains=(
            "Warnowo",
        ),
    ),
    RetrievalCase(
        name="cpt",
        query="badania gruntu CPT",
        expected_document_ids=(
            5914,
            5915,
            5917,
        ),
        expected_filename_contains=(
            "CPT",
            "geotechniczna",
            "qc",
        ),
    ),
    RetrievalCase(
        name="floor_lifting_contract",
        query=(
            "umowa dotycząca "
            "podnoszenia posadzki"
        ),
        expected_document_ids=(
            52,
        ),
        expected_filename_contains=(
            "umowy",
        ),
    ),
    RetrievalCase(
        name="foundation_settlement",
        query="osiadanie fundamentów",
        expected_document_ids=(),
    ),
]


def normalized(
    value: str | None,
) -> str:
    if not value:
        return ""

    return " ".join(
        value.lower().split()
    )


def is_expected(
    result: SemanticSearchResult,
    case: RetrievalCase,
) -> bool:
    if (
        case.expected_document_ids
        and result.document_id
        in case.expected_document_ids
    ):
        return True

    filename = normalized(
        result.filename
    )

    for token in (
        case.expected_filename_contains
    ):
        if (
            normalized(token)
            in filename
        ):
            return True

    return False


def is_forbidden(
    result: SemanticSearchResult,
    case: RetrievalCase,
) -> bool:
    content = normalized(
        result.content
    )

    for token in (
        case.forbidden_content_contains
    ):
        if (
            normalized(token)
            in content
        ):
            return True

    return False


def reciprocal_rank(
    results: list[
        SemanticSearchResult
    ],
    case: RetrievalCase,
) -> float:
    for rank, result in enumerate(
        results,
        start=1,
    ):
        if is_expected(
            result,
            case,
        ):
            return 1.0 / rank

    return 0.0


def print_case(
    case: RetrievalCase,
    results: list[
        SemanticSearchResult
    ],
) -> None:
    print()
    print("=" * 110)
    print(
        f"CASE: {case.name}"
    )
    print("=" * 110)

    print(
        "query:",
        case.query,
    )

    print(
        "results:",
        len(results),
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):
        print()
        print(
            f"RANK #{rank}"
        )

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
            "expected:",
            is_expected(
                result,
                case,
            ),
        )

        print(
            "forbidden:",
            is_forbidden(
                result,
                case,
            ),
        )

        fragment = " ".join(
            result.content.split()
        )

        if len(fragment) > 350:
            fragment = (
                fragment[:350]
                + "..."
            )

        print(
            "fragment:",
            fragment,
        )


def main() -> None:
    print()
    print("=" * 110)
    print("RETRIEVAL QUALITY BASELINE")
    print("=" * 110)

    service = (
        SemanticSearchService()
    )

    total_cases = 0
    cases_with_expected = 0

    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0

    reciprocal_rank_sum = 0.0

    forbidden_hits = 0

    for case in CASES:
        results = (
            service.search(
                query=case.query,
                limit=case.top_k,
            )
        )

        print_case(
            case,
            results,
        )

        total_cases += 1

        if not (
            case.expected_document_ids
            or case.expected_filename_contains
        ):
            continue

        cases_with_expected += 1

        expected_ranks = [
            rank
            for rank, result in enumerate(
                results,
                start=1,
            )
            if is_expected(
                result,
                case,
            )
        ]

        if expected_ranks:
            best_rank = min(
                expected_ranks
            )

            if best_rank <= 1:
                hit_at_1 += 1

            if best_rank <= 3:
                hit_at_3 += 1

            if best_rank <= 5:
                hit_at_5 += 1

        reciprocal_rank_sum += (
            reciprocal_rank(
                results,
                case,
            )
        )

        forbidden_hits += sum(
            1
            for result in results
            if is_forbidden(
                result,
                case,
            )
        )

    mrr = (
        reciprocal_rank_sum
        / cases_with_expected
        if cases_with_expected
        else 0.0
    )

    print()
    print()
    print("=" * 110)
    print("BASELINE METRICS")
    print("=" * 110)

    print(
        "total_cases:",
        total_cases,
    )

    print(
        "cases_with_expected:",
        cases_with_expected,
    )

    print(
        "hit_at_1:",
        f"{hit_at_1}/"
        f"{cases_with_expected}",
    )

    print(
        "hit_at_3:",
        f"{hit_at_3}/"
        f"{cases_with_expected}",
    )

    print(
        "hit_at_5:",
        f"{hit_at_5}/"
        f"{cases_with_expected}",
    )

    print(
        "mrr:",
        round(
            mrr,
            6,
        ),
    )

    print(
        "forbidden_hits:",
        forbidden_hits,
    )

    print()
    print(
        "NOTE: foundation_settlement "
        "currently has no expected-positive "
        "document configured. It remains "
        "a qualitative failure case until "
        "we identify a valid source document."
    )

    print()
    print("=" * 110)
    print("RETRIEVAL QUALITY BASELINE COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()
