from __future__ import annotations

import re
import shutil
import uuid

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_archive_service import (
    ArchiveMemberResult,
    DocumentArchiveService,
)


@dataclass(frozen=True)
class ArchiveChildImportResult:
    document_id: int | None
    archive_member_path: str
    original_filename: str
    status: str
    created: bool
    checksum_sha256: str | None
    error: str | None = None


@dataclass(frozen=True)
class ArchiveDocumentImportResult:
    parent_document_id: int
    status: str
    archive_type: str | None
    archive_member_count: int
    imported_count: int
    existing_count: int
    skipped_count: int
    failed_count: int
    children: list[ArchiveChildImportResult]
    error: str | None = None


class DocumentArchiveImportService:
    MAX_ARCHIVE_DEPTH = 5

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.repository = DocumentRepository(
            db
        )

        self.archive_service = (
            DocumentArchiveService()
        )

        self.data_directory = Path(
            settings.data_dir
        )

        self.extraction_root = (
            self.data_directory
            / "archive-extracted"
        )

        self.child_storage_root = (
            self.data_directory
            / "documents"
            / "archive_member"
        )

    def import_zip(
        self,
        *,
        parent_document_id: int,
        cleanup_extracted: bool = True,
    ) -> ArchiveDocumentImportResult:
        parent = self.repository.get(
            parent_document_id
        )

        if parent is None:
            return ArchiveDocumentImportResult(
                parent_document_id=parent_document_id,
                status="failed",
                archive_type=None,
                archive_member_count=0,
                imported_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=0,
                children=[],
                error="Parent document not found.",
            )

        if not parent.storage_path:
            return ArchiveDocumentImportResult(
                parent_document_id=parent.id,
                status="failed",
                archive_type=None,
                archive_member_count=0,
                imported_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=0,
                children=[],
                error="Parent document has no storage path.",
            )

        child_depth = (
            parent.archive_depth + 1
        )

        if child_depth > self.MAX_ARCHIVE_DEPTH:
            return ArchiveDocumentImportResult(
                parent_document_id=parent.id,
                status="rejected",
                archive_type="zip",
                archive_member_count=0,
                imported_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=0,
                children=[],
                error=(
                    "Maximum archive nesting depth "
                    f"exceeded: {child_depth} > "
                    f"{self.MAX_ARCHIVE_DEPTH}"
                ),
            )

        source_path = (
            self.data_directory
            / parent.storage_path
        )

        extraction_directory = (
            self.extraction_root
            / str(parent.id)
        )

        self.archive_service.clear_output_directory(
            extraction_directory
        )

        extraction_result = (
            self.archive_service.extract_zip(
                source_path=source_path,
                output_dir=extraction_directory,
            )
        )

        if extraction_result.status in {
            "failed",
            "rejected",
        }:
            if cleanup_extracted:
                self.archive_service.clear_output_directory(
                    extraction_directory
                )

            return ArchiveDocumentImportResult(
                parent_document_id=parent.id,
                status=extraction_result.status,
                archive_type=(
                    extraction_result.archive_type
                ),
                archive_member_count=(
                    extraction_result.member_count
                ),
                imported_count=0,
                existing_count=0,
                skipped_count=(
                    extraction_result.skipped_count
                ),
                failed_count=(
                    extraction_result.failed_count
                ),
                children=[],
                error=extraction_result.error,
            )

        children: list[
            ArchiveChildImportResult
        ] = []

        imported_count = 0
        existing_count = 0
        skipped_count = (
            extraction_result.skipped_count
        )
        failed_count = (
            extraction_result.failed_count
        )

        for member in extraction_result.members:
            if member.status != "extracted":
                continue

            result = self._import_member(
                parent=parent,
                member=member,
                extraction_directory=(
                    extraction_directory
                ),
                archive_depth=child_depth,
            )

            children.append(
                result
            )

            if result.status == "imported":
                imported_count += 1

            elif result.status == "existing":
                existing_count += 1

            elif result.status == "skipped":
                skipped_count += 1

            elif result.status == "failed":
                failed_count += 1

        if cleanup_extracted:
            self.archive_service.clear_output_directory(
                extraction_directory
            )

        if failed_count > 0:
            status = "partial"

        elif skipped_count > 0:
            status = "partial"

        else:
            status = "imported"

        return ArchiveDocumentImportResult(
            parent_document_id=parent.id,
            status=status,
            archive_type=(
                extraction_result.archive_type
            ),
            archive_member_count=(
                extraction_result.member_count
            ),
            imported_count=imported_count,
            existing_count=existing_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            children=children,
            error=None,
        )

    def _import_member(
        self,
        *,
        parent: Document,
        member: ArchiveMemberResult,
        extraction_directory: Path,
        archive_depth: int,
    ) -> ArchiveChildImportResult:
        archive_member_path = (
            member.archive_name.strip()
        )

        if not archive_member_path:
            return ArchiveChildImportResult(
                document_id=None,
                archive_member_path="",
                original_filename="",
                status="skipped",
                created=False,
                checksum_sha256=(
                    member.checksum_sha256
                ),
                error="Empty archive member path.",
            )

        existing = (
            self.repository.get_archive_child(
                parent_document_id=parent.id,
                archive_member_path=(
                    archive_member_path
                ),
            )
        )

        if existing is not None:
            return ArchiveChildImportResult(
                document_id=existing.id,
                archive_member_path=(
                    archive_member_path
                ),
                original_filename=(
                    existing.original_filename
                    or existing.filename
                ),
                status="existing",
                created=False,
                checksum_sha256=(
                    existing.checksum_sha256
                ),
                error=None,
            )

        if not member.relative_path:
            return ArchiveChildImportResult(
                document_id=None,
                archive_member_path=(
                    archive_member_path
                ),
                original_filename=(
                    member.safe_name
                    or Path(
                        archive_member_path
                    ).name
                ),
                status="failed",
                created=False,
                checksum_sha256=(
                    member.checksum_sha256
                ),
                error=(
                    "Extracted member has no "
                    "relative path."
                ),
            )

        extracted_path = (
            extraction_directory
            / member.relative_path
        )

        if not extracted_path.exists():
            return ArchiveChildImportResult(
                document_id=None,
                archive_member_path=(
                    archive_member_path
                ),
                original_filename=(
                    member.safe_name
                    or Path(
                        archive_member_path
                    ).name
                ),
                status="failed",
                created=False,
                checksum_sha256=(
                    member.checksum_sha256
                ),
                error=(
                    "Extracted member file "
                    "does not exist."
                ),
            )

        if member.file_size <= 0:
            return ArchiveChildImportResult(
                document_id=None,
                archive_member_path=(
                    archive_member_path
                ),
                original_filename=(
                    member.safe_name
                    or Path(
                        archive_member_path
                    ).name
                ),
                status="skipped",
                created=False,
                checksum_sha256=(
                    member.checksum_sha256
                ),
                error="Archive member is empty.",
            )

        original_filename = (
            member.safe_name
            or Path(
                archive_member_path
            ).name
            or "document.bin"
        )

        safe_filename = (
            self._sanitize_filename(
                original_filename
            )
        )

        storage_directory = (
            self.child_storage_root
            / str(parent.id)
        )

        storage_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        stored_filename = (
            f"{uuid.uuid4().hex}_"
            f"{safe_filename}"
        )

        absolute_storage_path = (
            storage_directory
            / stored_filename
        )

        relative_storage_path = (
            absolute_storage_path
            .relative_to(
                self.data_directory
            )
            .as_posix()
        )

        linked = (
            parent.candidate_id is not None
            or parent.client_id is not None
        )

        if linked:
            if parent.match_status in {
                "matched",
                "confirmed",
            }:
                match_status = (
                    parent.match_status
                )
            else:
                match_status = "matched"

            match_confidence = (
                parent.match_confidence
                if parent.match_confidence
                is not None
                else 1.0
            )

            match_method = (
                "archive_parent_inheritance"
            )

            matched_at = (
                parent.matched_at
                or datetime.now(UTC)
            )

        else:
            match_status = "unmatched"
            match_confidence = None
            match_method = None
            matched_at = None

        document = Document(
            filename=stored_filename,
            original_filename=(
                safe_filename
            ),
            content_type=(
                member.content_type
                or "application/octet-stream"
            ),
            file_size=member.file_size,
            storage_path=(
                relative_storage_path
            ),
            checksum_sha256=(
                member.checksum_sha256
            ),
            parent_document_id=parent.id,
            archive_member_path=(
                archive_member_path
            ),
            archive_depth=archive_depth,
            source_type=parent.source_type,
            external_id=None,
            gmail_message_id=(
                parent.gmail_message_id
            ),
            gmail_thread_id=(
                parent.gmail_thread_id
            ),
            candidate_id=(
                parent.candidate_id
            ),
            client_id=(
                parent.client_id
            ),
            captured_at=(
                parent.captured_at
            ),
            latitude=parent.latitude,
            longitude=parent.longitude,
            location_accuracy_m=(
                parent.location_accuracy_m
            ),
            location_source=(
                parent.location_source
            ),
            inspection_session_id=(
                parent.inspection_session_id
            ),
            processing_status="stored",
            processing_error=None,
            extracted_text=None,
            metadata_status="pending",
            metadata_raw=None,
            metadata_normalized=None,
            metadata_error=None,
            metadata_extracted_at=None,
            match_status=match_status,
            match_confidence=(
                match_confidence
            ),
            match_method=match_method,
            matched_at=matched_at,
        )

        try:
            shutil.copy2(
                extracted_path,
                absolute_storage_path,
            )

            created_document = (
                self.repository.create(
                    document
                )
            )

            self.repository.commit()

            return ArchiveChildImportResult(
                document_id=(
                    created_document.id
                ),
                archive_member_path=(
                    archive_member_path
                ),
                original_filename=(
                    safe_filename
                ),
                status="imported",
                created=True,
                checksum_sha256=(
                    member.checksum_sha256
                ),
                error=None,
            )

        except Exception as error:
            self.repository.rollback()

            if absolute_storage_path.exists():
                absolute_storage_path.unlink(
                    missing_ok=True
                )

            return ArchiveChildImportResult(
                document_id=None,
                archive_member_path=(
                    archive_member_path
                ),
                original_filename=(
                    safe_filename
                ),
                status="failed",
                created=False,
                checksum_sha256=(
                    member.checksum_sha256
                ),
                error=str(error),
            )

    @staticmethod
    def _sanitize_filename(
        filename: str,
    ) -> str:
        normalized = filename.strip()

        if not normalized:
            normalized = "document.bin"

        normalized = Path(
            normalized
        ).name

        normalized = re.sub(
            r'[<>:"/\\|?*\x00-\x1F]+',
            "_",
            normalized,
        )

        normalized = re.sub(
            r"\s+",
            "_",
            normalized,
        )

        normalized = normalized.strip(
            "._ "
        )

        if not normalized:
            return "document.bin"

        if len(normalized) > 255:
            suffix = Path(
                normalized
            ).suffix

            stem = Path(
                normalized
            ).stem

            available = (
                255 - len(suffix)
            )

            normalized = (
                stem[:available]
                + suffix
            )

        return normalized