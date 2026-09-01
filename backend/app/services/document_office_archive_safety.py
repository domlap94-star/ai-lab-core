from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


MAX_COMPRESSED_CONTAINER_BYTES = 256 * 1024 * 1024
MAX_CONTAINER_ENTRIES = 5000
MAX_MEMBER_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 500.0
MAX_MEDIA_MEMBERS = 512
MAX_MEDIA_MEMBER_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_TOTAL_MEDIA_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_IMAGE_DIMENSION_PX = 8192
MAX_IMAGE_PIXELS = 32_000_000
STREAM_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class OfficeArchiveSafetyPolicy:
    max_compressed_container_bytes: int = MAX_COMPRESSED_CONTAINER_BYTES
    max_container_entries: int = MAX_CONTAINER_ENTRIES
    max_member_uncompressed_bytes: int = MAX_MEMBER_UNCOMPRESSED_BYTES
    max_total_uncompressed_bytes: int = MAX_TOTAL_UNCOMPRESSED_BYTES
    max_compression_ratio: float = MAX_COMPRESSION_RATIO
    max_media_members: int = MAX_MEDIA_MEMBERS
    max_media_member_uncompressed_bytes: int = (
        MAX_MEDIA_MEMBER_UNCOMPRESSED_BYTES
    )
    max_total_media_uncompressed_bytes: int = (
        MAX_TOTAL_MEDIA_UNCOMPRESSED_BYTES
    )
    max_image_dimension_px: int = MAX_IMAGE_DIMENSION_PX
    max_image_pixels: int = MAX_IMAGE_PIXELS
    stream_chunk_bytes: int = STREAM_CHUNK_BYTES

    def __post_init__(self) -> None:
        integer_limits = (
            self.max_compressed_container_bytes,
            self.max_container_entries,
            self.max_member_uncompressed_bytes,
            self.max_total_uncompressed_bytes,
            self.max_media_members,
            self.max_media_member_uncompressed_bytes,
            self.max_total_media_uncompressed_bytes,
            self.max_image_dimension_px,
            self.max_image_pixels,
            self.stream_chunk_bytes,
        )
        if any(value <= 0 for value in integer_limits):
            raise ValueError("Office archive safety limits must be positive.")
        if self.max_compression_ratio <= 0:
            raise ValueError("Office archive compression-ratio limit must be positive.")


DEFAULT_OFFICE_ARCHIVE_POLICY = OfficeArchiveSafetyPolicy()


class OfficeArchiveSafetyError(ValueError):
    def __init__(self, code: str, *, state: str = "unsupported") -> None:
        super().__init__(code)
        self.code = code
        self.state = state


@dataclass(frozen=True)
class OfficeArchiveMember:
    info: zipfile.ZipInfo
    normalized_path: str


@dataclass(frozen=True)
class OfficeArchivePreflight:
    source_format: str
    members: tuple[OfficeArchiveMember, ...]
    media_members: tuple[OfficeArchiveMember, ...]
    declared_total_uncompressed_bytes: int
    declared_total_media_uncompressed_bytes: int


class DocumentOfficeArchiveSafety:
    """Metadata-only fail-closed preflight for bounded Office containers."""

    EXPECTED_ROOTS = {
        ".docx": "word/",
        ".xlsx": "xl/",
        ".pptx": "ppt/",
        ".odt": "mimetype",
    }

    MEDIA_PREFIXES = {
        ".docx": "word/media/",
        ".xlsx": "xl/media/",
        ".pptx": "ppt/media/",
        ".odt": "Pictures/",
    }

    def __init__(
        self,
        policy: OfficeArchiveSafetyPolicy = DEFAULT_OFFICE_ARCHIVE_POLICY,
    ) -> None:
        self.policy = policy

    def preflight(
        self,
        *,
        path: Path,
        extension: str,
        archive: zipfile.ZipFile | None = None,
        media_prefix: str | None = None,
    ) -> OfficeArchivePreflight:
        path = Path(path)
        normalized_extension = extension.casefold()
        self._validate_container_size(path)

        if normalized_extension not in self.EXPECTED_ROOTS:
            raise OfficeArchiveSafetyError(
                "OFFICE_CONTAINER_MISMATCH",
                state="integrity_failed",
            )

        if archive is not None:
            return self._preflight_archive(
                archive=archive,
                extension=normalized_extension,
                media_prefix=media_prefix,
            )

        try:
            with zipfile.ZipFile(path, "r") as opened:
                return self._preflight_archive(
                    archive=opened,
                    extension=normalized_extension,
                    media_prefix=media_prefix,
                )
        except OfficeArchiveSafetyError:
            raise
        except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
            raise OfficeArchiveSafetyError(
                "OFFICE_CONTAINER_MISMATCH",
                state="integrity_failed",
            ) from error

    def _validate_container_size(self, path: Path) -> None:
        try:
            compressed_size = path.stat().st_size
        except OSError as error:
            raise OfficeArchiveSafetyError(
                "OFFICE_CONTAINER_MISMATCH",
                state="integrity_failed",
            ) from error
        if compressed_size < 0:
            raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")
        if compressed_size > self.policy.max_compressed_container_bytes:
            raise OfficeArchiveSafetyError(
                "OFFICE_CONTAINER_COMPRESSED_SIZE_LIMIT"
            )

    def _preflight_archive(
        self,
        *,
        archive: zipfile.ZipFile,
        extension: str,
        media_prefix: str | None,
    ) -> OfficeArchivePreflight:
        try:
            infos = archive.infolist()
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise OfficeArchiveSafetyError(
                "OFFICE_CONTAINER_MISMATCH",
                state="integrity_failed",
            ) from error

        if len(infos) > self.policy.max_container_entries:
            raise OfficeArchiveSafetyError("OFFICE_CONTAINER_ENTRY_COUNT_LIMIT")

        members: list[OfficeArchiveMember] = []
        media_members: list[OfficeArchiveMember] = []
        normalized_seen: set[str] = set()
        declared_total = 0
        declared_media_total = 0
        selected_prefix = (
            media_prefix.replace("\\", "/")
            if media_prefix is not None
            else self.MEDIA_PREFIXES[extension]
        )

        for info in infos:
            normalized_path = self._normalized_member_path(info)
            duplicate_key = normalized_path.casefold()
            if duplicate_key in normalized_seen:
                raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")
            normalized_seen.add(duplicate_key)

            if info.flag_bits & 0x1:
                raise OfficeArchiveSafetyError("OFFICE_CONTAINER_ENCRYPTED")
            if info.file_size < 0 or info.compress_size < 0:
                raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")
            if info.file_size > 0 and info.compress_size == 0:
                raise OfficeArchiveSafetyError(
                    "OFFICE_CONTAINER_COMPRESSION_RATIO_LIMIT"
                )
            if info.file_size > self.policy.max_member_uncompressed_bytes:
                raise OfficeArchiveSafetyError(
                    "OFFICE_CONTAINER_MEMBER_SIZE_LIMIT"
                )
            if info.file_size > 0:
                compression_ratio = info.file_size / info.compress_size
                if compression_ratio > self.policy.max_compression_ratio:
                    raise OfficeArchiveSafetyError(
                        "OFFICE_CONTAINER_COMPRESSION_RATIO_LIMIT"
                    )

            if not info.is_dir():
                declared_total += info.file_size
                if declared_total > self.policy.max_total_uncompressed_bytes:
                    raise OfficeArchiveSafetyError(
                        "OFFICE_CONTAINER_TOTAL_SIZE_LIMIT"
                    )

            member = OfficeArchiveMember(
                info=info,
                normalized_path=normalized_path,
            )
            members.append(member)

            if not info.is_dir() and normalized_path.startswith(selected_prefix):
                if info.file_size > self.policy.max_media_member_uncompressed_bytes:
                    raise OfficeArchiveSafetyError(
                        "OFFICE_MEDIA_MEMBER_SIZE_LIMIT"
                    )
                declared_media_total += info.file_size
                if (
                    declared_media_total
                    > self.policy.max_total_media_uncompressed_bytes
                ):
                    raise OfficeArchiveSafetyError(
                        "OFFICE_MEDIA_TOTAL_SIZE_LIMIT"
                    )
                media_members.append(member)
                if len(media_members) > self.policy.max_media_members:
                    raise OfficeArchiveSafetyError("OFFICE_MEDIA_COUNT_LIMIT")

        self._validate_expected_structure(
            extension=extension,
            normalized_paths={member.normalized_path for member in members},
        )

        return OfficeArchivePreflight(
            source_format=extension.lstrip("."),
            members=tuple(members),
            media_members=tuple(media_members),
            declared_total_uncompressed_bytes=declared_total,
            declared_total_media_uncompressed_bytes=declared_media_total,
        )

    @staticmethod
    def _normalized_member_path(info: zipfile.ZipInfo) -> str:
        name = getattr(
            info,
            "orig_filename",
            info.filename,
        )
        if "\x00" in name:
            raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")
        normalized_name = name.replace("\\", "/")
        path = PurePosixPath(normalized_name)
        if path.is_absolute() or normalized_name.startswith("/"):
            raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")

        safe_parts: list[str] = []
        for part in path.parts:
            if part in {"", "."}:
                continue
            if part == ".." or ":" in part:
                raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")
            safe_parts.append(part)
        if not safe_parts:
            raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")

        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(unix_mode):
            raise OfficeArchiveSafetyError("OFFICE_CONTAINER_UNSAFE_MEMBER")
        return "/".join(safe_parts)

    def _validate_expected_structure(
        self,
        *,
        extension: str,
        normalized_paths: set[str],
    ) -> None:
        expected = self.EXPECTED_ROOTS[extension]
        if expected == "mimetype":
            valid = "mimetype" in normalized_paths
        else:
            valid = (
                "[Content_Types].xml" in normalized_paths
                and any(name.startswith(expected) for name in normalized_paths)
            )
        if not valid:
            raise OfficeArchiveSafetyError(
                "OFFICE_CONTAINER_MISMATCH",
                state="integrity_failed",
            )
