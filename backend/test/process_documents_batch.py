from __future__ import annotations

import argparse
import time

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func

from app.database.session import SessionLocal
from app.models.document import Document
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
)


@dataclass
class BatchProblem:
    document_id: int
    filename: str
    content_type: str
    status: str
    error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate DocumentProcessingService "
            "on a representative batch."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--start-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--end-id",
        type=int,
        default=None,
    )

    return parser.parse_args()


def choose_documents(
    *,
    db,
    limit: int,
    start_id: int | None,
    end_id: int | None,
) -> list[Document]:
    base_query = db.query(Document)

    if start_id is not None:
        base_query = base_query.filter(
            Document.id >= start_id
        )

    if end_id is not None:
        base_query = base_query.filter(
            Document.id <= end_id
        )

    content_types = (
        base_query
        .with_entities(
            Document.content_type,
            func.count(Document.id),
        )
        .group_by(Document.content_type)
        .order_by(
            func.count(Document.id).desc()
        )
        .all()
    )

    if not content_types:
        return []

    selected: dict[int, Document] = {}

    type_count = len(content_types)

    per_type = max(
        1,
        limit // min(
            type_count,
            12,
        ),
    )

    for content_type, _ in content_types:
        if len(selected) >= limit:
            break

        query = db.query(Document).filter(
            Document.content_type
            == content_type
        )

        if start_id is not None:
            query = query.filter(
                Document.id >= start_id
            )

        if end_id is not None:
            query = query.filter(
                Document.id <= end_id
            )

        documents = (
            query
            .order_by(
                func.random()
            )
            .limit(per_type)
            .all()
        )

        for document in documents:
            selected[document.id] = (
                document
            )

            if len(selected) >= limit:
                break

    if len(selected) < limit:
        remaining = (
            base_query
            .filter(
                ~Document.id.in_(
                    list(selected.keys())
                    or [-1]
                )
            )
            .order_by(
                func.random()
            )
            .limit(
                limit
                - len(selected)
            )
            .all()
        )

        for document in remaining:
            selected[document.id] = (
                document
            )

    return list(
        selected.values()
    )[:limit]


def main() -> None:
    args = parse_args()

    db = SessionLocal()

    try:
        repository = DocumentRepository(
            db
        )

        service = (
            DocumentProcessingService(
                db
            )
        )

        documents = choose_documents(
            db=db,
            limit=args.limit,
            start_id=args.start_id,
            end_id=args.end_id,
        )

        print()
        print("=" * 120)
        print("AI-LAB DOCUMENT BATCH VALIDATION")
        print("=" * 120)

        print(
            "documents_selected:",
            len(documents),
        )

        print(
            "force:",
            args.force,
        )

        print()

        type_counter = Counter(
            document.content_type
            for document in documents
        )

        print("CONTENT TYPE SAMPLE")

        for (
            content_type,
            count,
        ) in type_counter.most_common():
            print(
                f"{count:>3} | "
                f"{content_type}"
            )

        statuses: Counter[str] = (
            Counter()
        )

        metadata_statuses: Counter[
            str
        ] = Counter()

        problems: list[
            BatchProblem
        ] = []

        total_pages = 0
        total_native_chars = 0
        total_ocr_chars = 0
        total_combined_chars = 0

        started = time.perf_counter()

        for index, source_document in enumerate(
            documents,
            start=1,
        ):
            document_id = (
                source_document.id
            )

            filename = (
                source_document
                .original_filename
                or source_document.filename
            )

            content_type = (
                source_document
                .content_type
            )

            item_started = (
                time.perf_counter()
            )

            print()
            print("-" * 120)
            print(
                f"[{index}/{len(documents)}] "
                f"ID={document_id}"
            )

            print(
                "file:",
                filename,
            )

            print(
                "type:",
                content_type,
            )

            try:
                result = (
                    service.process_document(
                        document_id=document_id,
                        ocr_dpi=150,
                        render_dpi=150,
                        force=args.force,
                    )
                )

                elapsed = (
                    time.perf_counter()
                    - item_started
                )

                statuses[
                    result.status
                ] += 1

                if result.metadata_status:
                    metadata_statuses[
                        result.metadata_status
                    ] += 1

                total_pages += (
                    result.page_count
                )

                total_native_chars += (
                    result
                    .native_character_count
                )

                total_ocr_chars += (
                    result
                    .ocr_character_count
                )

                total_combined_chars += (
                    result
                    .combined_character_count
                )

                print(
                    "status:",
                    result.status,
                )

                print(
                    "pages:",
                    result.page_count,
                )

                print(
                    "native_chars:",
                    result
                    .native_character_count,
                )

                print(
                    "ocr_chars:",
                    result
                    .ocr_character_count,
                )

                print(
                    "combined_chars:",
                    result
                    .combined_character_count,
                )

                print(
                    "metadata:",
                    result.metadata_status,
                )

                print(
                    "render:",
                    result.render_status,
                )

                print(
                    "seconds:",
                    round(
                        elapsed,
                        2,
                    ),
                )

                print(
                    "error:",
                    result.error,
                )

                if result.status in {
                    "failed",
                    "stored",
                } or result.error:
                    problems.append(
                        BatchProblem(
                            document_id=(
                                document_id
                            ),
                            filename=filename,
                            content_type=(
                                content_type
                            ),
                            status=(
                                result.status
                            ),
                            error=(
                                result.error
                            ),
                        )
                    )

            except Exception as error:
                db.rollback()

                elapsed = (
                    time.perf_counter()
                    - item_started
                )

                statuses[
                    "exception"
                ] += 1

                problems.append(
                    BatchProblem(
                        document_id=(
                            document_id
                        ),
                        filename=filename,
                        content_type=(
                            content_type
                        ),
                        status="exception",
                        error=str(error),
                    )
                )

                print(
                    "status: EXCEPTION"
                )

                print(
                    "seconds:",
                    round(
                        elapsed,
                        2,
                    ),
                )

                print(
                    "error:",
                    repr(error),
                )

        elapsed_total = (
            time.perf_counter()
            - started
        )

        print()
        print("=" * 120)
        print("SUMMARY")
        print("=" * 120)

        print()
        print("PROCESSING STATUS")

        for status, count in (
            statuses.most_common()
        ):
            print(
                f"{status:<24} "
                f"{count}"
            )

        print()
        print("METADATA STATUS")

        for status, count in (
            metadata_statuses
            .most_common()
        ):
            print(
                f"{status:<24} "
                f"{count}"
            )

        print()
        print(
            "documents:",
            len(documents),
        )

        print(
            "pages:",
            total_pages,
        )

        print(
            "native_characters:",
            total_native_chars,
        )

        print(
            "ocr_characters:",
            total_ocr_chars,
        )

        print(
            "combined_characters:",
            total_combined_chars,
        )

        print(
            "elapsed_seconds:",
            round(
                elapsed_total,
                2,
            ),
        )

        if documents:
            print(
                "average_seconds_per_document:",
                round(
                    elapsed_total
                    / len(documents),
                    2,
                ),
            )

        print()
        print("=" * 120)
        print("PROBLEMS")
        print("=" * 120)

        if not problems:
            print(
                "NO PROCESSING PROBLEMS"
            )

        else:
            for problem in problems:
                print()
                print(
                    "ID:",
                    problem.document_id,
                )

                print(
                    "FILE:",
                    problem.filename,
                )

                print(
                    "TYPE:",
                    problem.content_type,
                )

                print(
                    "STATUS:",
                    problem.status,
                )

                print(
                    "ERROR:",
                    problem.error,
                )

        print()
        print("=" * 120)
        print("FINAL")
        print("=" * 120)

        failed_count = (
            statuses.get(
                "failed",
                0,
            )
            + statuses.get(
                "exception",
                0,
            )
        )

        print(
            "problem_count:",
            len(problems),
        )

        print(
            "hard_failures:",
            failed_count,
        )

        if failed_count == 0:
            print(
                "BATCH VALIDATION: OK"
            )
        else:
            print(
                "BATCH VALIDATION: "
                "CHECK RESULTS"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()