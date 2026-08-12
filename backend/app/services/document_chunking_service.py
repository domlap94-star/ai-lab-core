from __future__ import annotations

import hashlib
import re

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.repositories.document_repository import (
    DocumentRepository,
)


@dataclass(frozen=True)
class DocumentChunkingResult:
    document_id: int
    status: str
    chunk_count: int
    created_count: int
    existing_count: int
    character_count: int
    error: str | None = None


@dataclass(frozen=True)
class ChunkDraft:
    content: str
    page_from: int | None
    page_to: int | None
    content_source: str


class DocumentChunkingService:
    CHUNKING_VERSION = "v1"

    DEFAULT_MAX_CHARACTERS = 1800
    DEFAULT_OVERLAP_CHARACTERS = 250
    MIN_CHUNK_CHARACTERS = 80

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.document_repository = (
            DocumentRepository(
                db
            )
        )

        self.chunk_repository = (
            DocumentChunkRepository(
                db
            )
        )

    def chunk_document(
        self,
        *,
        document_id: int,
        force: bool = False,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
        overlap_characters: int = DEFAULT_OVERLAP_CHARACTERS,
    ) -> DocumentChunkingResult:
        document = (
            self.document_repository.get(
                document_id
            )
        )

        if document is None:
            return DocumentChunkingResult(
                document_id=document_id,
                status="failed",
                chunk_count=0,
                created_count=0,
                existing_count=0,
                character_count=0,
                error="Document not found.",
            )

        if max_characters < 200:
            return DocumentChunkingResult(
                document_id=document_id,
                status="failed",
                chunk_count=0,
                created_count=0,
                existing_count=0,
                character_count=0,
                error=(
                    "max_characters must be "
                    "at least 200."
                ),
            )

        if overlap_characters < 0:
            return DocumentChunkingResult(
                document_id=document_id,
                status="failed",
                chunk_count=0,
                created_count=0,
                existing_count=0,
                character_count=0,
                error=(
                    "overlap_characters cannot "
                    "be negative."
                ),
            )

        if overlap_characters >= max_characters:
            return DocumentChunkingResult(
                document_id=document_id,
                status="failed",
                chunk_count=0,
                created_count=0,
                existing_count=0,
                character_count=0,
                error=(
                    "overlap_characters must be "
                    "smaller than max_characters."
                ),
            )

        try:
            existing_chunks = (
                self.chunk_repository
                .get_by_document(
                    document_id
                )
            )

            if (
                existing_chunks
                and not force
                and self._chunks_are_current(
                    existing_chunks
                )
            ):
                return DocumentChunkingResult(
                    document_id=document.id,
                    status="existing",
                    chunk_count=len(
                        existing_chunks
                    ),
                    created_count=0,
                    existing_count=len(
                        existing_chunks
                    ),
                    character_count=sum(
                        chunk.character_count
                        for chunk
                        in existing_chunks
                    ),
                    error=None,
                )

            drafts = self._build_drafts(
                document_id=document.id,
                document_text=(
                    document.extracted_text
                ),
                max_characters=(
                    max_characters
                ),
                overlap_characters=(
                    overlap_characters
                ),
            )

            if not drafts:
                return DocumentChunkingResult(
                    document_id=document.id,
                    status="no_text",
                    chunk_count=0,
                    created_count=0,
                    existing_count=0,
                    character_count=0,
                    error=None,
                )

            self.chunk_repository.delete_by_document(
                document.id
            )

            created_count = 0
            total_characters = 0

            for (
                chunk_index,
                draft,
            ) in enumerate(drafts):
                content = self._clean_text(
                    draft.content
                )

                if not content:
                    continue

                character_count = len(
                    content
                )

                content_hash = (
                    self._hash_content(
                        content
                    )
                )

                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    page_from=draft.page_from,
                    page_to=draft.page_to,
                    source_type="document",
                    content_source=(
                        draft.content_source
                    ),
                    content=content,
                    token_count=(
                        self._estimate_tokens(
                            content
                        )
                    ),
                    character_count=(
                        character_count
                    ),
                    content_hash=(
                        content_hash
                    ),
                    chunking_version=(
                        self.CHUNKING_VERSION
                    ),
                    embedding_status="pending",
                    embedding_model=None,
                    embedding_version=None,
                    vector_id=None,
                    embedding_error=None,
                    embedded_at=None,
                )

                self.chunk_repository.add(
                    chunk
                )

                created_count += 1
                total_characters += (
                    character_count
                )

            self.chunk_repository.commit()

            return DocumentChunkingResult(
                document_id=document.id,
                status="chunked",
                chunk_count=created_count,
                created_count=created_count,
                existing_count=0,
                character_count=(
                    total_characters
                ),
                error=None,
            )

        except Exception as error:
            self.chunk_repository.rollback()

            return DocumentChunkingResult(
                document_id=document_id,
                status="failed",
                chunk_count=0,
                created_count=0,
                existing_count=0,
                character_count=0,
                error=str(error),
            )

    def _build_drafts(
        self,
        *,
        document_id: int,
        document_text: str | None,
        max_characters: int,
        overlap_characters: int,
    ) -> list[ChunkDraft]:
        pages = (
            self.document_repository.get_pages(
                document_id
            )
        )

        page_drafts: list[
            ChunkDraft
        ] = []

        for page in pages:
            page_text, source = (
                self._get_page_text(
                    extracted_text=(
                        page.extracted_text
                    ),
                    ocr_text=(
                        page.ocr_text
                    ),
                )
            )

            if not page_text:
                continue

            chunks = self._split_text(
                text=page_text,
                max_characters=(
                    max_characters
                ),
                overlap_characters=(
                    overlap_characters
                ),
            )

            for content in chunks:
                page_drafts.append(
                    ChunkDraft(
                        content=content,
                        page_from=(
                            page.page_number
                        ),
                        page_to=(
                            page.page_number
                        ),
                        content_source=source,
                    )
                )

        if page_drafts:
            return page_drafts

        fallback_text = self._clean_text(
            document_text
        )

        if not fallback_text:
            return []

        chunks = self._split_text(
            text=fallback_text,
            max_characters=max_characters,
            overlap_characters=(
                overlap_characters
            ),
        )

        return [
            ChunkDraft(
                content=content,
                page_from=None,
                page_to=None,
                content_source="document",
            )
            for content in chunks
        ]

    def _get_page_text(
        self,
        *,
        extracted_text: str | None,
        ocr_text: str | None,
    ) -> tuple[
        str | None,
        str,
    ]:
        native = self._clean_text(
            extracted_text
        )

        ocr = self._clean_text(
            ocr_text
        )

        if native and ocr:
            if self._texts_are_similar(
                native,
                ocr,
            ):
                return (
                    native,
                    "native",
                )

            combined = (
                native
                + "\n\n"
                + "[OCR]\n"
                + ocr
            )

            return (
                combined,
                "combined",
            )

        if native:
            return (
                native,
                "native",
            )

        if ocr:
            return (
                ocr,
                "ocr",
            )

        return (
            None,
            "none",
        )

    def _split_text(
        self,
        *,
        text: str,
        max_characters: int,
        overlap_characters: int,
    ) -> list[str]:
        cleaned = self._normalize_whitespace(
            text
        )

        if not cleaned:
            return []

        if len(cleaned) <= max_characters:
            return [
                cleaned
            ]

        paragraphs = [
            paragraph.strip()
            for paragraph
            in re.split(
                r"\n\s*\n",
                cleaned,
            )
            if paragraph.strip()
        ]

        if len(paragraphs) <= 1:
            return self._split_long_block(
                text=cleaned,
                max_characters=(
                    max_characters
                ),
                overlap_characters=(
                    overlap_characters
                ),
            )

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            if len(paragraph) > max_characters:
                if current:
                    chunks.append(
                        current.strip()
                    )
                    current = ""

                chunks.extend(
                    self._split_long_block(
                        text=paragraph,
                        max_characters=(
                            max_characters
                        ),
                        overlap_characters=(
                            overlap_characters
                        ),
                    )
                )

                continue

            candidate = (
                paragraph
                if not current
                else (
                    current
                    + "\n\n"
                    + paragraph
                )
            )

            if (
                len(candidate)
                <= max_characters
            ):
                current = candidate

                continue

            if current:
                chunks.append(
                    current.strip()
                )

            overlap = (
                self._tail_overlap(
                    current,
                    overlap_characters,
                )
            )

            current = (
                overlap
                + "\n\n"
                + paragraph
                if overlap
                else paragraph
            )

            if (
                len(current)
                > max_characters
            ):
                overflow_chunks = (
                    self._split_long_block(
                        text=current,
                        max_characters=(
                            max_characters
                        ),
                        overlap_characters=(
                            overlap_characters
                        ),
                    )
                )

                if overflow_chunks:
                    chunks.extend(
                        overflow_chunks[:-1]
                    )

                    current = (
                        overflow_chunks[-1]
                    )

        if current:
            chunks.append(
                current.strip()
            )

        return [
            chunk
            for chunk in chunks
            if (
                len(chunk)
                >= self.MIN_CHUNK_CHARACTERS
                or len(chunks) == 1
            )
        ]

    def _split_long_block(
        self,
        *,
        text: str,
        max_characters: int,
        overlap_characters: int,
    ) -> list[str]:
        chunks: list[str] = []

        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(
                start + max_characters,
                text_length,
            )

            if end < text_length:
                sentence_break = max(
                    text.rfind(
                        ". ",
                        start,
                        end,
                    ),
                    text.rfind(
                        "! ",
                        start,
                        end,
                    ),
                    text.rfind(
                        "? ",
                        start,
                        end,
                    ),
                    text.rfind(
                        "\n",
                        start,
                        end,
                    ),
                )

                if (
                    sentence_break
                    > start
                    + int(
                        max_characters
                        * 0.55
                    )
                ):
                    end = (
                        sentence_break
                        + 1
                    )

            chunk = text[
                start:end
            ].strip()

            if chunk:
                chunks.append(
                    chunk
                )

            if end >= text_length:
                break

            next_start = max(
                end
                - overlap_characters,
                start + 1,
            )

            start = next_start

        return chunks

    @staticmethod
    def _tail_overlap(
        text: str,
        overlap_characters: int,
    ) -> str:
        if (
            not text
            or overlap_characters <= 0
        ):
            return ""

        if len(text) <= overlap_characters:
            return text

        tail = text[
            -overlap_characters:
        ]

        first_space = tail.find(
            " "
        )

        if first_space >= 0:
            tail = tail[
                first_space + 1:
            ]

        return tail.strip()

    @staticmethod
    def _texts_are_similar(
        first: str,
        second: str,
    ) -> bool:
        normalized_first = (
            DocumentChunkingService
            ._comparison_text(
                first
            )
        )

        normalized_second = (
            DocumentChunkingService
            ._comparison_text(
                second
            )
        )

        if (
            not normalized_first
            or not normalized_second
        ):
            return False

        shorter = min(
            len(normalized_first),
            len(normalized_second),
        )

        longer = max(
            len(normalized_first),
            len(normalized_second),
        )

        if longer == 0:
            return False

        length_ratio = (
            shorter / longer
        )

        if length_ratio < 0.70:
            return False

        sample_length = min(
            shorter,
            500,
        )

        first_sample = (
            normalized_first[
                :sample_length
            ]
        )

        second_sample = (
            normalized_second[
                :sample_length
            ]
        )

        matches = sum(
            1
            for left, right
            in zip(
                first_sample,
                second_sample,
            )
            if left == right
        )

        similarity = (
            matches
            / sample_length
            if sample_length
            else 0
        )

        return similarity >= 0.78

    @staticmethod
    def _comparison_text(
        value: str,
    ) -> str:
        return re.sub(
            r"\s+",
            "",
            value.lower(),
        )

    @staticmethod
    def _normalize_whitespace(
        value: str,
    ) -> str:
        value = value.replace(
            "\r\n",
            "\n",
        )

        value = value.replace(
            "\r",
            "\n",
        )

        value = re.sub(
            r"[ \t]+",
            " ",
            value,
        )

        value = re.sub(
            r"\n{3,}",
            "\n\n",
            value,
        )

        return value.strip()

    @staticmethod
    def _clean_text(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return (
            normalized
            if normalized
            else None
        )

    @staticmethod
    def _hash_content(
        content: str,
    ) -> str:
        return hashlib.sha256(
            content.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _estimate_tokens(
        content: str,
    ) -> int:
        if not content:
            return 0

        return max(
            1,
            round(
                len(content)
                / 4
            ),
        )

    def _chunks_are_current(
        self,
        chunks: list[
            DocumentChunk
        ],
    ) -> bool:
        return all(
            chunk.chunking_version
            == self.CHUNKING_VERSION
            and bool(
                chunk.content_hash
            )
            for chunk in chunks
        )
