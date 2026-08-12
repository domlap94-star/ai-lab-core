from __future__ import annotations

from sqlalchemy import func, select

from app.database.session import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_vector_store import QdrantVectorStore


def count_status(
    db,
    status: str,
) -> int:
    return (
        db.scalar(
            select(
                func.count(
                    DocumentChunk.id
                )
            ).where(
                DocumentChunk.embedding_status
                == status
            )
        )
        or 0
    )


def print_database_state(
    db,
    *,
    label: str,
) -> dict[str, int]:
    total = (
        db.scalar(
            select(
                func.count(
                    DocumentChunk.id
                )
            )
        )
        or 0
    )

    pending = count_status(
        db,
        "pending",
    )

    embedded = count_status(
        db,
        "embedded",
    )

    failed = count_status(
        db,
        "failed",
    )

    stale = count_status(
        db,
        "stale",
    )

    vector_ids = (
        db.scalar(
            select(
                func.count(
                    DocumentChunk.id
                )
            ).where(
                DocumentChunk.vector_id
                .is_not(None)
            )
        )
        or 0
    )

    print()
    print(label)
    print("-" * 110)
    print("chunks:", total)
    print("pending:", pending)
    print("embedded:", embedded)
    print("failed:", failed)
    print("stale:", stale)
    print("vector_id present:", vector_ids)

    return {
        "total": total,
        "pending": pending,
        "embedded": embedded,
        "failed": failed,
        "stale": stale,
        "vector_ids": vector_ids,
    }


def print_result(
    label: str,
    result,
) -> None:
    print()
    print(label)
    print("-" * 110)
    print("status:", result.status)
    print("selected_count:", result.selected_count)
    print("embedded_count:", result.embedded_count)
    print("failed_count:", result.failed_count)
    print("qdrant_points:", result.qdrant_points)
    print("model:", result.model)
    print("dimensions:", result.dimensions)
    print("error:", result.error)


def main() -> None:
    print()
    print("=" * 110)
    print("KNOWLEDGE LAYER E2E")
    print("=" * 110)

    with SessionLocal() as db:
        before = print_database_state(
            db,
            label="DATABASE BEFORE",
        )

        print()
        print("SERVICE INITIALIZATION")
        print("-" * 110)

        embedding_service = EmbeddingService(
            db
        )

        vector_store = QdrantVectorStore()

        print(
            "embedding_service:",
            type(
                embedding_service
            ).__name__,
        )

        print(
            "vector_store:",
            type(
                vector_store
            ).__name__,
        )

        created = (
            vector_store
            .ensure_collection()
        )

        print(
            "collection:",
            vector_store.collection_name,
        )

        print(
            "collection_created:",
            created,
        )

        print(
            "vector_dimensions:",
            vector_store.dimensions,
        )

        qdrant_before = (
            vector_store.count()
        )

        print(
            "qdrant_points_before:",
            qdrant_before,
        )

        print()
        print("=" * 110)
        print("FIRST EMBEDDING PASS")
        print("=" * 110)

        first_result = (
            embedding_service
            .embed_pending()
        )

        print_result(
            "FIRST PASS RESULT",
            first_result,
        )

        db.expire_all()

        after_first = (
            print_database_state(
                db,
                label=(
                    "DATABASE AFTER "
                    "FIRST PASS"
                ),
            )
        )

        qdrant_after_first = (
            vector_store.count()
        )

        print()
        print(
            "qdrant_points_after_first:",
            qdrant_after_first,
        )

        print()
        print("=" * 110)
        print("SECOND EMBEDDING PASS / IDEMPOTENCY")
        print("=" * 110)

        second_result = (
            embedding_service
            .embed_pending()
        )

        print_result(
            "SECOND PASS RESULT",
            second_result,
        )

        db.expire_all()

        after_second = (
            print_database_state(
                db,
                label=(
                    "DATABASE AFTER "
                    "SECOND PASS"
                ),
            )
        )

        qdrant_after_second = (
            vector_store.count()
        )

        print()
        print(
            "qdrant_points_after_second:",
            qdrant_after_second,
        )

        print()
        print("=" * 110)
        print("VALIDATION")
        print("=" * 110)

        checks = {
            (
                "all chunks embedded"
            ): (
                after_second[
                    "embedded"
                ]
                == after_second[
                    "total"
                ]
            ),
            (
                "no pending chunks"
            ): (
                after_second[
                    "pending"
                ]
                == 0
            ),
            (
                "no failed chunks"
            ): (
                after_second[
                    "failed"
                ]
                == 0
            ),
            (
                "no stale chunks"
            ): (
                after_second[
                    "stale"
                ]
                == 0
            ),
            (
                "every chunk has vector_id"
            ): (
                after_second[
                    "vector_ids"
                ]
                == after_second[
                    "total"
                ]
            ),
            (
                "qdrant count equals DB chunks"
            ): (
                qdrant_after_second
                == after_second[
                    "total"
                ]
            ),
            (
                "second pass selected nothing"
            ): (
                second_result.selected_count
                == 0
            ),
            (
                "second pass embedded nothing"
            ): (
                second_result.embedded_count
                == 0
            ),
            (
                "second pass did not duplicate vectors"
            ): (
                qdrant_after_second
                == qdrant_after_first
            ),
        }

        for name, passed in checks.items():
            print(
                f"{name}:",
                "OK" if passed else "FAIL",
            )

        failed_checks = [
            name
            for name, passed
            in checks.items()
            if not passed
        ]

        if first_result.status == "failed":
            raise RuntimeError(
                "First embedding pass failed: "
                f"{first_result.error}"
            )

        if failed_checks:
            raise RuntimeError(
                "Knowledge Layer validation "
                "failed: "
                + ", ".join(
                    failed_checks
                )
            )

        print()
        print("=" * 110)
        print("KNOWLEDGE LAYER EMBEDDING E2E: OK")
        print("=" * 110)

        print()
        print("SUMMARY")
        print("-" * 110)
        print(
            "chunks_before:",
            before["total"],
        )
        print(
            "embedded_after:",
            after_second[
                "embedded"
            ],
        )
        print(
            "qdrant_vectors:",
            qdrant_after_second,
        )
        print(
            "model:",
            first_result.model,
        )
        print(
            "dimensions:",
            first_result.dimensions,
        )


if __name__ == "__main__":
    main()
