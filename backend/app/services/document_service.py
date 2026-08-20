from __future__ import annotations

import hashlib
import re
import uuid

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository


class DocumentStorageError(Exception):
    pass


class EmptyDocumentError(DocumentStorageError):
    pass


class DocumentTooLargeError(DocumentStorageError):
    pass


class InvalidDocumentSourceTypeError(DocumentStorageError):
    pass


class MissingLocationMetadataError(DocumentStorageError):
    pass


class InvalidLocationMetadataError(DocumentStorageError):
    pass


class UnsafeDocumentStoragePathError(DocumentStorageError):
    pass


class DocumentContentUnavailableError(DocumentStorageError):
    pass


@dataclass(frozen=True)
class StoredDocumentResult:
    document: Document
    created: bool
    matched_by: str | None = None


class DocumentService:
    MAX_DOCUMENT_BYTES = 250 * 1024 * 1024

    ALLOWED_SOURCE_TYPES = {
        "manual_upload",
        "gmail_attachment",
        "camera_photo",
        "camera_video",
    }

    CAMERA_SOURCE_TYPES = {
        "camera_photo",
        "camera_video",
    }

    def __init__(self, db: Session) -> None:
        self.repository = DocumentRepository(db)

        self.documents_directory = (
            Path(settings.data_dir)
            / "documents"
        )

    def store_document(
        self,
        *,
        content: bytes,
        original_filename: str,
        content_type: str,
        source_type: str,
        external_id: str | None = None,
        gmail_message_id: str | None = None,
        gmail_thread_id: str | None = None,
        candidate_id: int | None = None,
        client_id: int | None = None,
        project_id: int | None = None,
        inspection_id: int | None = None,
        captured_at: datetime | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        location_accuracy_m: float | None = None,
        location_source: str | None = None,
        inspection_session_id: str | None = None,
        intake_metadata: dict[str, object] | None = None,
        commit: bool = True,
    ) -> StoredDocumentResult:
        self._validate_source_type(source_type)

        if not content:
            raise EmptyDocumentError(
                "The uploaded document is empty."
            )

        if len(content) > self.MAX_DOCUMENT_BYTES:
            raise DocumentTooLargeError(
                "The uploaded document exceeds the 250 MB limit."
            )

        self._validate_location_metadata(
            source_type=source_type,
            captured_at=captured_at,
            latitude=latitude,
            longitude=longitude,
            location_accuracy_m=location_accuracy_m,
        )

        normalized_external_id = self._normalize_optional_string(
            external_id,
        )

        normalized_gmail_message_id = (
            self._normalize_optional_string(
                gmail_message_id,
            )
        )

        normalized_gmail_thread_id = (
            self._normalize_optional_string(
                gmail_thread_id,
            )
        )

        normalized_location_source = (
            self._normalize_optional_string(
                location_source,
            )
        )

        normalized_inspection_session_id = (
            self._normalize_optional_string(
                inspection_session_id,
            )
        )

        if (
            source_type in self.CAMERA_SOURCE_TYPES
            and normalized_location_source is None
            and latitude is not None
            and longitude is not None
        ):
            normalized_location_source = "device_gps"

        if normalized_external_id:
            existing_document = (
                self.repository.get_by_external_id(
                    source_type=source_type,
                    external_id=normalized_external_id,
                )
            )

            if existing_document is not None:
                return StoredDocumentResult(
                    document=existing_document,
                    created=False,
                    matched_by="external_id",
                )

        resolved_candidate_id = candidate_id
        resolved_client_id = client_id
        automatic_match_method: str | None = None

        if (
            source_type == "gmail_attachment"
            and resolved_candidate_id is None
            and resolved_client_id is None
            and normalized_gmail_message_id
        ):
            candidate = (
                self.repository
                .find_candidate_by_gmail_message_id(
                    normalized_gmail_message_id,
                )
            )

            if candidate is not None:
                resolved_candidate_id = candidate.id
                resolved_client_id = candidate.matched_client_id
                automatic_match_method = "gmail_message_source"

        checksum_sha256 = hashlib.sha256(content).hexdigest()

        if source_type in {
            "manual_upload",
            "camera_photo",
            "camera_video",
        }:
            existing_document = self.repository.get_by_checksum(
                checksum_sha256,
            )

            if existing_document is not None:
                return StoredDocumentResult(
                    document=existing_document,
                    created=False,
                    matched_by="checksum_sha256",
                )

        safe_original_filename = self._sanitize_filename(
            original_filename,
        )

        stored_filename = (
            f"{uuid.uuid4().hex}_"
            f"{safe_original_filename}"
        )

        storage_directory = self._build_storage_directory(
            source_type=source_type,
        )

        storage_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        absolute_storage_path = (
            storage_directory
            / stored_filename
        )

        relative_storage_path = (
            absolute_storage_path.relative_to(
                Path(settings.data_dir)
            )
        )

        matched = (
            resolved_candidate_id is not None
            or resolved_client_id is not None
        )

        if automatic_match_method is not None:
            match_method = automatic_match_method
        elif matched:
            match_method = "explicit_relation"
        else:
            match_method = None

        document = Document(
            filename=stored_filename,
            original_filename=safe_original_filename,
            content_type=self._normalize_content_type(
                content_type,
            ),
            file_size=len(content),
            storage_path=str(
                relative_storage_path.as_posix()
            ),
            checksum_sha256=checksum_sha256,
            source_type=source_type,
            external_id=normalized_external_id,
            gmail_message_id=normalized_gmail_message_id,
            gmail_thread_id=normalized_gmail_thread_id,
            candidate_id=resolved_candidate_id,
            client_id=resolved_client_id,
            project_id=project_id,
            inspection_id=inspection_id,
            captured_at=captured_at,
            latitude=latitude,
            longitude=longitude,
            location_accuracy_m=location_accuracy_m,
            location_source=normalized_location_source,
            inspection_session_id=normalized_inspection_session_id,
            metadata_raw=(
                {"intake": dict(intake_metadata)}
                if intake_metadata
                else None
            ),
            processing_status="stored",
            processing_error=None,
            vision_auto_eligible=True,
            vision_status="not_evaluated",
            match_status=(
                "matched"
                if matched
                else "unmatched"
            ),
            match_confidence=(
                1.0
                if matched
                else None
            ),
            match_method=match_method,
            matched_at=(
                datetime.now(UTC)
                if matched
                else None
            ),
        )

        try:
            absolute_storage_path.write_bytes(content)

            created_document = self.repository.create(
                document,
            )

            if commit:
                self.repository.commit()

            return StoredDocumentResult(
                document=created_document,
                created=True,
                matched_by=match_method,
            )

        except Exception as error:
            self.repository.rollback()

            if absolute_storage_path.exists():
                absolute_storage_path.unlink(
                    missing_ok=True,
                )

            raise DocumentStorageError(
                "Could not store the document."
            ) from error

    def discard_uncommitted_file(self, document: Document) -> None:
        """Remove only a just-created, uncommitted file after outer rollback."""
        if not document.storage_path:
            return
        root = Path(settings.data_dir).resolve()
        target = (root / document.storage_path).resolve()
        if root not in target.parents:
            raise DocumentStorageError("Refusing to remove a path outside data_dir.")
        target.unlink(missing_ok=True)

    def get_document(
        self,
        document_id: int,
    ) -> Document | None:
        return self.repository.get(document_id)

    def get_absolute_storage_path(
        self,
        document: Document,
    ) -> Path | None:
        if not document.storage_path:
            return None

        return resolve_document_storage_path(
            storage_path=document.storage_path,
            data_root=Path(settings.data_dir),
        )

    def find_candidate_for_gmail_message(
        self,
        gmail_message_id: str,
    ) -> ClientCandidate | None:
        return (
            self.repository
            .find_candidate_by_gmail_message_id(
                gmail_message_id,
            )
        )

    def _build_storage_directory(
        self,
        *,
        source_type: str,
    ) -> Path:
        now = datetime.now(UTC)

        return (
            self.documents_directory
            / source_type
            / f"{now.year:04d}"
            / f"{now.month:02d}"
        )

    def _validate_source_type(
        self,
        source_type: str,
    ) -> None:
        if source_type not in self.ALLOWED_SOURCE_TYPES:
            raise InvalidDocumentSourceTypeError(
                "Unsupported document source type: "
                f"{source_type}"
            )

    def _validate_location_metadata(
        self,
        *,
        source_type: str,
        captured_at: datetime | None,
        latitude: float | None,
        longitude: float | None,
        location_accuracy_m: float | None,
    ) -> None:
        if source_type in self.CAMERA_SOURCE_TYPES:
            if captured_at is None:
                raise MissingLocationMetadataError(
                    "Camera uploads require captured_at."
                )

        if (latitude is None) != (longitude is None):
            raise InvalidLocationMetadataError(
                "Latitude and longitude must be provided together."
            )

        if latitude is not None:
            if latitude < -90 or latitude > 90:
                raise InvalidLocationMetadataError(
                    "Latitude must be between -90 and 90."
                )

        if longitude is not None:
            if longitude < -180 or longitude > 180:
                raise InvalidLocationMetadataError(
                    "Longitude must be between -180 and 180."
                )

        if (
            location_accuracy_m is not None
            and location_accuracy_m < 0
        ):
            raise InvalidLocationMetadataError(
                "Location accuracy cannot be negative."
            )

    @staticmethod
    def _sanitize_filename(
        filename: str,
    ) -> str:
        normalized = filename.strip()

        if not normalized:
            normalized = "document.bin"

        normalized = Path(normalized).name

        # Python \w obsługuje Unicode, więc zachowujemy m.in.
        # ą ć ę ł ń ó ś ź ż.
        normalized = re.sub(
            r"[^\w.\-() ]+",
            "_",
            normalized,
            flags=re.UNICODE,
        )

        normalized = re.sub(
            r"\s+",
            "_",
            normalized,
        )

        normalized = normalized.strip("._")

        if not normalized:
            return "document.bin"

        return normalized[:255]

    @staticmethod
    def _normalize_content_type(
        content_type: str,
    ) -> str:
        normalized = content_type.strip().lower()

        if not normalized:
            return "application/octet-stream"

        return normalized[:255]

    @staticmethod
    def _normalize_optional_string(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


def resolve_document_storage_path(
    *,
    storage_path: str,
    data_root: Path,
) -> Path:
    try:
        resolved_root = data_root.resolve(strict=True)
        resolved_path = (resolved_root / storage_path).resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as error:
        raise DocumentContentUnavailableError(
            "Document content is unavailable."
        ) from error

    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise UnsafeDocumentStoragePathError(
            "Document content is unavailable."
        ) from error

    if not resolved_path.is_file():
        raise DocumentContentUnavailableError(
            "Document content is unavailable."
        )

    return resolved_path
