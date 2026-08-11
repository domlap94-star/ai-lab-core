from __future__ import annotations

import hashlib
import mimetypes
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_MEMBERS = 500
MAX_SINGLE_FILE_SIZE = 250 * 1024 * 1024
MAX_TOTAL_EXTRACTED_SIZE = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 500.0


@dataclass
class ArchiveMemberResult:
    archive_name: str
    safe_name: str | None
    relative_path: str | None
    content_type: str | None
    file_size: int
    compressed_size: int
    checksum_sha256: str | None
    status: str
    error: str | None


@dataclass
class ArchiveExtractionResult:
    status: str
    archive_type: str
    member_count: int
    extracted_count: int
    skipped_count: int
    failed_count: int
    total_extracted_size: int
    members: list[ArchiveMemberResult]
    error: str | None


class DocumentArchiveService:
    def extract_zip(
        self,
        *,
        source_path: Path,
        output_dir: Path,
    ) -> ArchiveExtractionResult:
        source_path = Path(source_path)
        output_dir = Path(output_dir)

        if not source_path.exists():
            return ArchiveExtractionResult(
                status="failed",
                archive_type="zip",
                member_count=0,
                extracted_count=0,
                skipped_count=0,
                failed_count=0,
                total_extracted_size=0,
                members=[],
                error="Archive file does not exist.",
            )

        try:
            archive = zipfile.ZipFile(
                source_path,
                "r",
            )
        except Exception as error:
            return ArchiveExtractionResult(
                status="failed",
                archive_type="zip",
                member_count=0,
                extracted_count=0,
                skipped_count=0,
                failed_count=0,
                total_extracted_size=0,
                members=[],
                error=str(error),
            )

        members: list[ArchiveMemberResult] = []

        extracted_count = 0
        skipped_count = 0
        failed_count = 0
        total_extracted_size = 0

        try:
            infos = archive.infolist()

            if len(infos) > MAX_ARCHIVE_MEMBERS:
                return ArchiveExtractionResult(
                    status="rejected",
                    archive_type="zip",
                    member_count=len(infos),
                    extracted_count=0,
                    skipped_count=0,
                    failed_count=0,
                    total_extracted_size=0,
                    members=[],
                    error=(
                        "Archive contains too many members: "
                        f"{len(infos)} > {MAX_ARCHIVE_MEMBERS}"
                    ),
                )

            declared_total_size = sum(
                info.file_size
                for info in infos
                if not info.is_dir()
            )

            if declared_total_size > MAX_TOTAL_EXTRACTED_SIZE:
                return ArchiveExtractionResult(
                    status="rejected",
                    archive_type="zip",
                    member_count=len(infos),
                    extracted_count=0,
                    skipped_count=0,
                    failed_count=0,
                    total_extracted_size=0,
                    members=[],
                    error=(
                        "Declared extracted archive size is too large: "
                        f"{declared_total_size} bytes"
                    ),
                )

            output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_root = output_dir.resolve()

            for info in infos:
                if info.is_dir():
                    continue

                validation_error = self._validate_member(
                    info=info,
                )

                if validation_error is not None:
                    skipped_count += 1

                    members.append(
                        ArchiveMemberResult(
                            archive_name=info.filename,
                            safe_name=None,
                            relative_path=None,
                            content_type=None,
                            file_size=info.file_size,
                            compressed_size=info.compress_size,
                            checksum_sha256=None,
                            status="skipped",
                            error=validation_error,
                        )
                    )

                    continue

                safe_relative_path = self._safe_relative_path(
                    info.filename
                )

                if safe_relative_path is None:
                    skipped_count += 1

                    members.append(
                        ArchiveMemberResult(
                            archive_name=info.filename,
                            safe_name=None,
                            relative_path=None,
                            content_type=None,
                            file_size=info.file_size,
                            compressed_size=info.compress_size,
                            checksum_sha256=None,
                            status="skipped",
                            error="Unsafe archive path.",
                        )
                    )

                    continue

                destination = (
                    output_dir
                    / safe_relative_path
                )

                resolved_destination = (
                    destination.resolve()
                )

                try:
                    resolved_destination.relative_to(
                        output_root
                    )
                except ValueError:
                    skipped_count += 1

                    members.append(
                        ArchiveMemberResult(
                            archive_name=info.filename,
                            safe_name=None,
                            relative_path=None,
                            content_type=None,
                            file_size=info.file_size,
                            compressed_size=info.compress_size,
                            checksum_sha256=None,
                            status="skipped",
                            error="Archive path escapes extraction directory.",
                        )
                    )

                    continue

                try:
                    destination.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    sha256 = hashlib.sha256()
                    actual_size = 0

                    with archive.open(
                        info,
                        "r",
                    ) as source:
                        with destination.open(
                            "wb",
                        ) as target:
                            while True:
                                chunk = source.read(
                                    1024 * 1024
                                )

                                if not chunk:
                                    break

                                actual_size += len(chunk)

                                if (
                                    actual_size
                                    > MAX_SINGLE_FILE_SIZE
                                ):
                                    raise ValueError(
                                        "Extracted member exceeds "
                                        "maximum allowed file size."
                                    )

                                if (
                                    total_extracted_size
                                    + actual_size
                                    > MAX_TOTAL_EXTRACTED_SIZE
                                ):
                                    raise ValueError(
                                        "Archive exceeds maximum "
                                        "total extracted size."
                                    )

                                sha256.update(
                                    chunk
                                )

                                target.write(
                                    chunk
                                )

                    total_extracted_size += (
                        actual_size
                    )

                    content_type = (
                        mimetypes.guess_type(
                            destination.name
                        )[0]
                        or "application/octet-stream"
                    )

                    relative_path = (
                        destination
                        .relative_to(output_dir)
                        .as_posix()
                    )

                    extracted_count += 1

                    members.append(
                        ArchiveMemberResult(
                            archive_name=info.filename,
                            safe_name=destination.name,
                            relative_path=relative_path,
                            content_type=content_type,
                            file_size=actual_size,
                            compressed_size=info.compress_size,
                            checksum_sha256=sha256.hexdigest(),
                            status="extracted",
                            error=None,
                        )
                    )

                except Exception as error:
                    failed_count += 1

                    try:
                        if destination.exists():
                            destination.unlink()
                    except Exception:
                        pass

                    members.append(
                        ArchiveMemberResult(
                            archive_name=info.filename,
                            safe_name=destination.name,
                            relative_path=None,
                            content_type=None,
                            file_size=info.file_size,
                            compressed_size=info.compress_size,
                            checksum_sha256=None,
                            status="failed",
                            error=str(error),
                        )
                    )

        finally:
            archive.close()

        if failed_count > 0:
            status = "partial"
        elif skipped_count > 0:
            status = "partial"
        else:
            status = "extracted"

        return ArchiveExtractionResult(
            status=status,
            archive_type="zip",
            member_count=len(infos),
            extracted_count=extracted_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            total_extracted_size=total_extracted_size,
            members=members,
            error=None,
        )

    def clear_output_directory(
        self,
        output_dir: Path,
    ) -> None:
        output_dir = Path(output_dir)

        if output_dir.exists():
            shutil.rmtree(
                output_dir
            )

    def _validate_member(
        self,
        *,
        info: zipfile.ZipInfo,
    ) -> str | None:
        if info.file_size < 0:
            return "Invalid negative file size."

        if info.file_size > MAX_SINGLE_FILE_SIZE:
            return (
                "Member exceeds maximum allowed "
                f"file size: {info.file_size} bytes."
            )

        if (
            info.compress_size > 0
            and info.file_size > 0
        ):
            compression_ratio = (
                info.file_size
                / info.compress_size
            )

            if (
                compression_ratio
                > MAX_COMPRESSION_RATIO
            ):
                return (
                    "Suspicious compression ratio: "
                    f"{compression_ratio:.2f}"
                )

        return None

    def _safe_relative_path(
        self,
        archive_name: str,
    ) -> Path | None:
        normalized_name = (
            archive_name
            .replace("\\", "/")
        )

        path = PurePosixPath(
            normalized_name
        )

        if path.is_absolute():
            return None

        safe_parts: list[str] = []

        for part in path.parts:
            if part in {
                "",
                ".",
            }:
                continue

            if part == "..":
                return None

            if ":" in part:
                return None

            safe_parts.append(
                part
            )

        if not safe_parts:
            return None

        return Path(
            *safe_parts
        )