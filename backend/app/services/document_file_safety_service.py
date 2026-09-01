from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

from app.services.document_office_archive_safety import (
    DEFAULT_OFFICE_ARCHIVE_POLICY,
    DocumentOfficeArchiveSafety,
    OfficeArchiveSafetyError,
    OfficeArchiveSafetyPolicy,
)


@dataclass(frozen=True)
class FileSafetyResult:
    state: str
    detected_format: str | None = None
    error_code: str | None = None


class DocumentFileSafetyService:
    """Bounded signature/extension/MIME gate used before parser routing."""

    _EXECUTABLE_EXTENSIONS = {".exe", ".msi", ".bat", ".cmd", ".ps1", ".js", ".dll", ".apk"}
    _UNSUPPORTED_EXTENSIONS = {".rar", ".7z", ".mp4", ".avi", ".mov", ".mkv"}
    _TEXT_EXTENSIONS = {".txt", ".csv", ".tsv", ".rtf"}
    _IMAGE_SIGNATURES = {
        ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
        ".png": (b"\x89PNG\r\n\x1a\n",), ".bmp": (b"BM",),
        ".tif": (b"II*\x00", b"MM\x00*"), ".tiff": (b"II*\x00", b"MM\x00*"),
        ".webp": (b"RIFF",),
    }
    _MIME_BY_EXTENSION = {
        ".pdf": {"application/pdf", "application/octet-stream"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip", "application/octet-stream"},
        ".odt": {"application/vnd.oasis.opendocument.text", "application/zip", "application/octet-stream"},
        ".jpg": {"image/jpeg", "image/jpg", "application/octet-stream"},
        ".jpeg": {"image/jpeg", "image/jpg", "application/octet-stream"},
        ".png": {"image/png", "application/octet-stream"},
        ".bmp": {"image/bmp", "image/x-ms-bmp", "application/octet-stream"},
        ".tif": {"image/tiff", "application/octet-stream"},
        ".tiff": {"image/tiff", "application/octet-stream"},
        ".webp": {"image/webp", "application/octet-stream"},
        ".heic": {"image/heic", "image/heif", "application/octet-stream"},
        ".heif": {"image/heif", "image/heic", "application/octet-stream"},
        ".txt": {"text/plain", "application/octet-stream"},
        ".csv": {"text/csv", "text/plain", "application/octet-stream", "application/vnd.ms-excel"},
        ".tsv": {"text/tab-separated-values", "text/plain", "application/octet-stream"},
    }

    def __init__(
        self,
        office_archive_policy: OfficeArchiveSafetyPolicy = (
            DEFAULT_OFFICE_ARCHIVE_POLICY
        ),
    ) -> None:
        self.office_archive_safety = DocumentOfficeArchiveSafety(
            office_archive_policy
        )

    def classify(self, *, path: Path, original_filename: str | None, declared_mime: str | None) -> FileSafetyResult:
        extension = Path(original_filename or path.name).suffix.casefold()
        mime = (declared_mime or "application/octet-stream").split(";", 1)[0].strip().casefold()
        if extension in self._EXECUTABLE_EXTENSIONS:
            return FileSafetyResult("unsupported", error_code="UNSUPPORTED_EXECUTABLE_FORMAT")
        if extension in self._UNSUPPORTED_EXTENSIONS:
            return FileSafetyResult("unsupported", error_code="UNSUPPORTED_FORMAT")
        try:
            with path.open("rb") as stream:
                header = stream.read(8192)
        except OSError:
            return FileSafetyResult("failed", error_code="DOCUMENT_FILE_READ_FAILED")
        if header[:2] == b"MZ":
            return FileSafetyResult("integrity_failed", error_code="EXECUTABLE_SIGNATURE_REJECTED")
        allowed_mimes = self._MIME_BY_EXTENSION.get(extension)
        if allowed_mimes and mime not in allowed_mimes:
            return FileSafetyResult("integrity_failed", error_code="MIME_EXTENSION_MISMATCH")
        if extension == ".pdf":
            return FileSafetyResult("supported", "pdf") if header.startswith(b"%PDF-") else FileSafetyResult("integrity_failed", error_code="PDF_SIGNATURE_MISMATCH")
        if extension in {".docx", ".xlsx", ".pptx", ".odt"}:
            return self._classify_zip_container(path, extension)
        if extension in {".doc", ".xls"}:
            return FileSafetyResult("supported", extension[1:]) if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") else FileSafetyResult("integrity_failed", error_code="OFFICE_SIGNATURE_MISMATCH")
        if extension in self._IMAGE_SIGNATURES:
            signatures = self._IMAGE_SIGNATURES[extension]
            valid = any(header.startswith(signature) for signature in signatures)
            if extension == ".webp":
                valid = header.startswith(b"RIFF") and header[8:12] == b"WEBP"
            return FileSafetyResult("supported", "image") if valid else FileSafetyResult("integrity_failed", error_code="IMAGE_SIGNATURE_MISMATCH")
        if extension in {".heic", ".heif"}:
            valid = len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1"}
            return FileSafetyResult("supported", "image") if valid else FileSafetyResult("integrity_failed", error_code="IMAGE_SIGNATURE_MISMATCH")
        if extension in self._TEXT_EXTENSIONS or mime.startswith("text/"):
            if b"\x00" in header:
                return FileSafetyResult("integrity_failed", error_code="TEXT_BINARY_MISMATCH")
            return FileSafetyResult("supported", "text")
        if extension in {".eml"} or mime == "message/rfc822":
            return FileSafetyResult("supported", "email")
        if extension == ".zip":
            return FileSafetyResult("unsupported", error_code="ARCHIVE_REQUIRES_BOUNDED_IMPORT")
        guessed = mimetypes.guess_type(original_filename or path.name)[0]
        del guessed
        return FileSafetyResult("unsupported", error_code="UNSUPPORTED_FORMAT")

    def _classify_zip_container(self, path: Path, extension: str) -> FileSafetyResult:
        try:
            self.office_archive_safety.preflight(
                path=path,
                extension=extension,
            )
        except OfficeArchiveSafetyError as error:
            return FileSafetyResult(
                error.state,
                error_code=error.code,
            )
        return FileSafetyResult("supported", extension[1:])
