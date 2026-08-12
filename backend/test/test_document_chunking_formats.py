from __future__ import annotations

from dataclasses import dataclass

from app.database.session import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_chunking_service import (
    DocumentChunkingService,
)


@dataclass(frozen=True)
class TestCase:
    document_id: int
    label: str
    expect_text: bool


TEST_CASES = [
    TestCase(
        document_id=37,
        label="PDF drawing",
        expect_text=True,
    ),
    TestCase(
        document_id=770,
        label="Legacy DOC",
        expect_text=True,
    ),
    TestCase(
        document_id=52,
        label="DOCX",
        expect_text=True,
    ),
    TestCase(
        document_id=184,
        label="ODT",
        expect_text=True,
    ),
    TestCase(
        document_id=5915,
        label="Legacy XLS",
        expect_text=True,
    ),
    TestCase(
        document_id=2815,
        label="XLSX",
        expect_text=True,
    ),
    TestCase(
        document_id=1608,
        label="Tiny PNG",
        expect_text=False,
    ),
    TestCase(
        document_id=3277,
        label="HEIC",
        expect_text=True,
    ),
    TestCase(
        document_id=5066,
        label="RFC822",
        expect_text=True,
    ),
    TestCase(
        document_id=5914,
        label="Archive child PDF",
        expect_text=True,
    ),
    TestCase(
        document_id=5916,
        label="CPT PDF",
        expect_text=True,
    ),
    TestCase(
        document_id=5917,
        label="CPT PDF",
        expect_text=True,
    ),
]


def main() -> None:
    db = SessionLocal()

    try:
        document_repository = (
            DocumentRepository(
                db
            )
        )

        service = (
            DocumentChunkingService(
                db
            )
        )

        failures: list[str] = []

        chunked_documents = 0
        no_text_documents = 0
        skipped_documents = 0

        total_chunks = 0
        page_aware_chunks = 0
        document_level_chunks = 0

        print()
        print("=" * 120)
        print(
            "DOCUMENT CHUNKING FORMAT REGRESSION"
        )
        print("=" * 120)

        for case in TEST_CASES:
            print()
            print("=" * 120)
            print(
                f"DOCUMENT {case.document_id} "
                f"- {case.label}"
            )
            print("=" * 120)

            document = (
                document_repository.get(
                    case.document_id
                )
            )

            if document is None:
                print(
                    "status: SKIPPED "
                    "- document not found"
                )

                skipped_documents += 1
                continue

            print(
                "filename:",
                document.original_filename
                or document.filename,
            )

            print(
                "content_type:",
                document.content_type,
            )

            print(
                "processing_status:",
                document.processing_status,
            )

            print(
                "document_text_chars:",
                len(
                    document.extracted_text
                    or ""
                ),
            )

            pages = (
                document_repository.get_pages(
                    case.document_id
                )
            )

            print(
                "pages:",
                len(pages),
            )

            result = service.chunk_document(
                document_id=case.document_id,
                force=True,
            )

            print()
            print(
                "--- FIRST RUN ---"
            )

            print(
                "status:",
                result.status,
            )

            print(
                "chunk_count:",
                result.chunk_count,
            )

            print(
                "created_count:",
                result.created_count,
            )

            print(
                "character_count:",
                result.character_count,
            )

            print(
                "error:",
                result.error,
            )

            chunks = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id
                    == case.document_id
                )
                .order_by(
                    DocumentChunk.chunk_index.asc()
                )
                .all()
            )

            current_failures: list[str] = []

            if case.expect_text:
                if result.status != "chunked":
                    current_failures.append(
                        "expected status chunked"
                    )

                if not chunks:
                    current_failures.append(
                        "expected at least one chunk"
                    )

            else:
                if result.status != "no_text":
                    current_failures.append(
                        "expected status no_text"
                    )

                if chunks:
                    current_failures.append(
                        "no-text document created chunks"
                    )

            if chunks:
                indexes = [
                    chunk.chunk_index
                    for chunk in chunks
                ]

                if indexes != list(
                    range(
                        len(chunks)
                    )
                ):
                    current_failures.append(
                        "chunk indexes are not sequential"
                    )

                if any(
                    not chunk.content
                    or not chunk.content.strip()
                    for chunk in chunks
                ):
                    current_failures.append(
                        "empty chunk found"
                    )

                if any(
                    chunk.character_count
                    != len(chunk.content)
                    for chunk in chunks
                ):
                    current_failures.append(
                        "character count mismatch"
                    )

                if any(
                    not chunk.content_hash
                    or len(
                        chunk.content_hash
                    ) != 64
                    for chunk in chunks
                ):
                    current_failures.append(
                        "invalid content hash"
                    )

                if any(
                    chunk.chunking_version
                    != "v1"
                    for chunk in chunks
                ):
                    current_failures.append(
                        "invalid chunking version"
                    )

                if any(
                    chunk.embedding_status
                    != "pending"
                    for chunk in chunks
                ):
                    current_failures.append(
                        "invalid embedding status"
                    )

                if any(
                    chunk.page_from
                    is not None
                    and chunk.page_to
                    is not None
                    and chunk.page_to
                    < chunk.page_from
                    for chunk in chunks
                ):
                    current_failures.append(
                        "invalid page range"
                    )

            page_aware = sum(
                1
                for chunk in chunks
                if chunk.page_from
                is not None
            )

            document_level = sum(
                1
                for chunk in chunks
                if chunk.page_from
                is None
            )

            print()
            print(
                "--- CHUNKS ---"
            )

            print(
                "database_chunks:",
                len(chunks),
            )

            print(
                "page_aware:",
                page_aware,
            )

            print(
                "document_level:",
                document_level,
            )

            print(
                "sources:",
                sorted(
                    {
                        chunk.content_source
                        for chunk in chunks
                    }
                ),
            )

            print(
                "pages_represented:",
                sorted(
                    {
                        chunk.page_from
                        for chunk in chunks
                        if chunk.page_from
                        is not None
                    }
                ),
            )

            print()
            print(
                "--- IDEMPOTENCY ---"
            )

            second = service.chunk_document(
                document_id=case.document_id,
                force=False,
            )

            print(
                "status:",
                second.status,
            )

            print(
                "chunk_count:",
                second.chunk_count,
            )

            print(
                "created_count:",
                second.created_count,
            )

            print(
                "existing_count:",
                second.existing_count,
            )

            print(
                "error:",
                second.error,
            )

            chunks_after = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id
                    == case.document_id
                )
                .count()
            )

            if case.expect_text:
                if second.status != "existing":
                    current_failures.append(
                        "idempotency status is not existing"
                    )

                if (
                    chunks_after
                    != len(chunks)
                ):
                    current_failures.append(
                        "chunk count changed after "
                        "idempotency run"
                    )

            else:
                if second.status != "no_text":
                    current_failures.append(
                        "no-text second run "
                        "returned unexpected status"
                    )

            if current_failures:
                print()
                print(
                    "RESULT: FAILED"
                )

                for failure in current_failures:
                    print(
                        " -",
                        failure,
                    )

                    failures.append(
                        f"{case.document_id}: "
                        f"{failure}"
                    )

            else:
                print()
                print(
                    "RESULT: OK"
                )

            if result.status == "chunked":
                chunked_documents += 1

            if result.status == "no_text":
                no_text_documents += 1

            total_chunks += len(chunks)
            page_aware_chunks += page_aware
            document_level_chunks += (
                document_level
            )

        print()
        print("=" * 120)
        print("SUMMARY")
        print("=" * 120)

        print(
            "configured_documents:",
            len(TEST_CASES),
        )

        print(
            "skipped_documents:",
            skipped_documents,
        )

        print(
            "chunked_documents:",
            chunked_documents,
        )

        print(
            "no_text_documents:",
            no_text_documents,
        )

        print(
            "total_chunks:",
            total_chunks,
        )

        print(
            "page_aware_chunks:",
            page_aware_chunks,
        )

        print(
            "document_level_chunks:",
            document_level_chunks,
        )

        print(
            "failures:",
            len(failures),
        )

        if failures:
            print()
            print(
                "FAILURE DETAILS"
            )

            for failure in failures:
                print(
                    " -",
                    failure,
                )

        print()
        print("=" * 120)
        print("FINAL")
        print("=" * 120)

        if failures:
            print(
                "DOCUMENT CHUNKING FORMAT "
                "REGRESSION: CHECK RESULTS"
            )
        else:
            print(
                "DOCUMENT CHUNKING FORMAT "
                "REGRESSION: OK"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
