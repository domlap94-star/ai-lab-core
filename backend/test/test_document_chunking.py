from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_chunking_service import (
    DocumentChunkingService,
)


DOCUMENT_IDS = [
    37,
    770,
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

        total_failures = 0

        print()
        print("=" * 120)
        print("DOCUMENT CHUNKING TEST")
        print("=" * 120)

        for document_id in DOCUMENT_IDS:
            print()
            print("=" * 120)
            print(
                f"DOCUMENT {document_id}"
            )
            print("=" * 120)

            document = (
                document_repository.get(
                    document_id
                )
            )

            if document is None:
                print(
                    "DOCUMENT NOT FOUND"
                )

                total_failures += 1
                continue

            pages = (
                document_repository.get_pages(
                    document_id
                )
            )

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

            print(
                "pages:",
                len(pages),
            )

            print()
            print(
                "--- FIRST RUN / FORCE ---"
            )

            first = service.chunk_document(
                document_id=document_id,
                force=True,
            )

            print(
                "status:",
                first.status,
            )

            print(
                "chunk_count:",
                first.chunk_count,
            )

            print(
                "created_count:",
                first.created_count,
            )

            print(
                "existing_count:",
                first.existing_count,
            )

            print(
                "character_count:",
                first.character_count,
            )

            print(
                "error:",
                first.error,
            )

            chunks = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id
                    == document_id
                )
                .order_by(
                    DocumentChunk.chunk_index.asc()
                )
                .all()
            )

            print()
            print(
                "--- DATABASE ---"
            )

            print(
                "chunks:",
                len(chunks),
            )

            if chunks:
                indexes = [
                    chunk.chunk_index
                    for chunk in chunks
                ]

                print(
                    "chunk_index_min:",
                    min(indexes),
                )

                print(
                    "chunk_index_max:",
                    max(indexes),
                )

                print(
                    "sequential_indexes:",
                    indexes
                    == list(
                        range(
                            len(indexes)
                        )
                    ),
                )

                print(
                    "with_page:",
                    sum(
                        1
                        for chunk in chunks
                        if chunk.page_from
                        is not None
                    ),
                )

                print(
                    "without_page:",
                    sum(
                        1
                        for chunk in chunks
                        if chunk.page_from
                        is None
                    ),
                )

                print(
                    "with_hash:",
                    sum(
                        1
                        for chunk in chunks
                        if chunk.content_hash
                    ),
                )

                print(
                    "pending_embeddings:",
                    sum(
                        1
                        for chunk in chunks
                        if chunk.embedding_status
                        == "pending"
                    ),
                )

                print(
                    "chunking_v1:",
                    sum(
                        1
                        for chunk in chunks
                        if chunk.chunking_version
                        == "v1"
                    ),
                )

                print(
                    "total_chunk_chars:",
                    sum(
                        chunk.character_count
                        for chunk in chunks
                    ),
                )

                source_counts = Counter(
                    chunk.content_source
                    for chunk in chunks
                )

                print(
                    "content_sources:",
                    dict(
                        source_counts
                    ),
                )

                page_numbers = sorted(
                    {
                        chunk.page_from
                        for chunk in chunks
                        if chunk.page_from
                        is not None
                    }
                )

                print(
                    "pages_represented:",
                    page_numbers,
                )

            print()
            print(
                "--- SAMPLE CHUNKS ---"
            )

            for chunk in chunks[:5]:
                preview = (
                    chunk.content
                    .replace(
                        "\n",
                        " ",
                    )[:180]
                )

                print()
                print(
                    "chunk_index:",
                    chunk.chunk_index,
                )

                print(
                    "page_from:",
                    chunk.page_from,
                )

                print(
                    "page_to:",
                    chunk.page_to,
                )

                print(
                    "source_type:",
                    chunk.source_type,
                )

                print(
                    "content_source:",
                    chunk.content_source,
                )

                print(
                    "character_count:",
                    chunk.character_count,
                )

                print(
                    "token_count:",
                    chunk.token_count,
                )

                print(
                    "content_hash:",
                    chunk.content_hash,
                )

                print(
                    "embedding_status:",
                    chunk.embedding_status,
                )

                print(
                    "preview:",
                    preview,
                )

            document_failures: list[
                str
            ] = []

            if first.status != "chunked":
                document_failures.append(
                    "first run did not return "
                    "'chunked'"
                )

            if first.chunk_count <= 0:
                document_failures.append(
                    "no chunks created"
                )

            if len(chunks) != first.chunk_count:
                document_failures.append(
                    "database chunk count does "
                    "not match result"
                )

            if chunks:
                expected_indexes = list(
                    range(
                        len(chunks)
                    )
                )

                actual_indexes = [
                    chunk.chunk_index
                    for chunk in chunks
                ]

                if (
                    actual_indexes
                    != expected_indexes
                ):
                    document_failures.append(
                        "chunk indexes are not "
                        "sequential"
                    )

                if any(
                    not chunk.content.strip()
                    for chunk in chunks
                ):
                    document_failures.append(
                        "empty chunk detected"
                    )

                if any(
                    chunk.character_count
                    != len(chunk.content)
                    for chunk in chunks
                ):
                    document_failures.append(
                        "character_count mismatch"
                    )

                if any(
                    not chunk.content_hash
                    or len(
                        chunk.content_hash
                    ) != 64
                    for chunk in chunks
                ):
                    document_failures.append(
                        "invalid content hash"
                    )

                if any(
                    chunk.embedding_status
                    != "pending"
                    for chunk in chunks
                ):
                    document_failures.append(
                        "unexpected embedding status"
                    )

                if any(
                    chunk.chunking_version
                    != "v1"
                    for chunk in chunks
                ):
                    document_failures.append(
                        "unexpected chunking version"
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
                    document_failures.append(
                        "invalid page range"
                    )

            print()
            print(
                "--- SECOND RUN / IDEMPOTENCY ---"
            )

            second = service.chunk_document(
                document_id=document_id,
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
                "character_count:",
                second.character_count,
            )

            print(
                "error:",
                second.error,
            )

            chunks_after_second = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id
                    == document_id
                )
                .order_by(
                    DocumentChunk.chunk_index.asc()
                )
                .all()
            )

            if second.status != "existing":
                document_failures.append(
                    "second run did not return "
                    "'existing'"
                )

            if (
                len(chunks_after_second)
                != len(chunks)
            ):
                document_failures.append(
                    "chunk count changed during "
                    "idempotency run"
                )

            if (
                second.existing_count
                != len(chunks)
            ):
                document_failures.append(
                    "existing_count mismatch"
                )

            print()
            print(
                "--- RESULT ---"
            )

            if document_failures:
                print(
                    "DOCUMENT CHUNKING: FAILED"
                )

                for failure in (
                    document_failures
                ):
                    print(
                        " -",
                        failure,
                    )

                total_failures += len(
                    document_failures
                )

            else:
                print(
                    "DOCUMENT CHUNKING: OK"
                )

        print()
        print("=" * 120)
        print("FINAL")
        print("=" * 120)

        total_chunks = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id.in_(
                    DOCUMENT_IDS
                )
            )
            .count()
        )

        print(
            "documents_tested:",
            len(DOCUMENT_IDS),
        )

        print(
            "total_chunks:",
            total_chunks,
        )

        print(
            "failures:",
            total_failures,
        )

        if total_failures == 0:
            print(
                "DOCUMENT CHUNKING TEST: OK"
            )
        else:
            print(
                "DOCUMENT CHUNKING TEST: "
                "CHECK RESULTS"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
