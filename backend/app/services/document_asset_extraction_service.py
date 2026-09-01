from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
import tempfile
import warnings
import zipfile

from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.repositories.document_asset_repository import (
    DocumentAssetRepository,
)
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.services.document_office_archive_safety import (
    DEFAULT_OFFICE_ARCHIVE_POLICY,
    DocumentOfficeArchiveSafety,
    OfficeArchiveMember,
    OfficeArchiveSafetyError,
    OfficeArchiveSafetyPolicy,
)


@dataclass(frozen=True)
class ExtractedAssetResult:
    asset_id: int | None
    asset_index: int
    original_name: str
    storage_path: str | None
    mime_type: str | None
    width: int | None
    height: int | None
    file_size: int
    checksum_sha256: str | None
    status: str
    created: bool
    error: str | None = None


@dataclass(frozen=True)
class DocumentAssetExtractionResult:
    document_id: int
    status: str
    source_format: str | None
    discovered_count: int
    extracted_count: int
    existing_count: int
    skipped_count: int
    failed_count: int
    assets: list[ExtractedAssetResult]
    error: str | None = None


@dataclass(frozen=True)
class _StagedOfficeAsset:
    member_path: str
    original_name: str
    staged_path: Path
    file_size: int
    checksum_sha256: str
    width: int
    height: int
    image_format: str


class DocumentAssetExtractionService:
    MIN_IMAGE_WIDTH = 16
    MIN_IMAGE_HEIGHT = 16
    MIN_IMAGE_FILE_SIZE = 100

    OOXML_MEDIA_PATHS = {
        ".docx": "word/media/",
        ".pptx": "ppt/media/",
        ".xlsx": "xl/media/",
    }

    def __init__(
        self,
        db: Session,
        office_archive_policy: OfficeArchiveSafetyPolicy = (
            DEFAULT_OFFICE_ARCHIVE_POLICY
        ),
        staging_parent: Path | None = None,
    ) -> None:
        self.db = db

        self.document_repository = (
            DocumentRepository(db)
        )

        self.asset_repository = (
            DocumentAssetRepository(db)
        )

        self.data_directory = Path(
            settings.data_dir
        )

        self.asset_root = (
            self.data_directory
            / "document-assets"
        )

        self.office_archive_policy = (
            office_archive_policy
        )

        self.office_archive_safety = (
            DocumentOfficeArchiveSafety(
                office_archive_policy
            )
        )

        self.staging_parent = (
            Path(staging_parent)
            if staging_parent is not None
            else None
        )

    def extract_document_assets(
        self,
        *,
        document_id: int,
        force: bool = False,
    ) -> DocumentAssetExtractionResult:
        document = (
            self.document_repository.get(
                document_id
            )
        )

        if document is None:
            return self._failed_result(
                document_id=document_id,
                error="Document not found.",
            )

        if not document.storage_path:
            return self._failed_result(
                document_id=document.id,
                error=(
                    "Document has no storage path."
                ),
            )

        source_path = (
            self.data_directory
            / document.storage_path
        )

        if not source_path.exists():
            return self._failed_result(
                document_id=document.id,
                error=(
                    f"Source file not found: "
                    f"{source_path}"
                ),
            )

        extension = Path(
            document.original_filename
            or document.filename
            or source_path.name
        ).suffix.lower()

        if extension in {
            ".docx",
            ".pptx",
            ".xlsx",
        }:
            media_prefix = (
                self.OOXML_MEDIA_PATHS[
                    extension
                ]
            )

            return self._extract_zip_media(
                document=document,
                source_path=source_path,
                source_format=(
                    extension.lstrip(".")
                ),
                media_prefix=media_prefix,
                extraction_method=(
                    "ooxml-media"
                ),
                force=force,
                policy_extension=extension,
            )

        if extension in {
            ".odt",
            ".odp",
            ".ods",
        }:
            return self._extract_zip_media(
                document=document,
                source_path=source_path,
                source_format=(
                    extension.lstrip(".")
                ),
                media_prefix="Pictures/",
                extraction_method=(
                    "odf-pictures"
                ),
                force=force,
                policy_extension=".odt",
            )

        if extension == ".doc":
            return self._extract_legacy_doc(
                document=document,
                source_path=source_path,
                force=force,
            )

        return DocumentAssetExtractionResult(
            document_id=document.id,
            status="unsupported",
            source_format=(
                extension.lstrip(".")
                if extension
                else None
            ),
            discovered_count=0,
            extracted_count=0,
            existing_count=0,
            skipped_count=0,
            failed_count=0,
            assets=[],
            error=None,
        )

    def _extract_legacy_doc(
        self,
        *,
        document: Document,
        source_path: Path,
        force: bool,
    ) -> DocumentAssetExtractionResult:
        try:
            with tempfile.TemporaryDirectory(
                prefix="ai-lab-doc-convert-"
            ) as temp_dir:
                temp_path = Path(
                    temp_dir
                )

                process = subprocess.run(
                    [
                        "libreoffice",
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        str(temp_path),
                        str(source_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=180,
                )

                converted_files = list(
                    temp_path.glob(
                        "*.docx"
                    )
                )

                if (
                    process.returncode != 0
                    or not converted_files
                ):
                    return DocumentAssetExtractionResult(
                        document_id=(
                            document.id
                        ),
                        status="failed",
                        source_format="doc",
                        discovered_count=0,
                        extracted_count=0,
                        existing_count=0,
                        skipped_count=0,
                        failed_count=1,
                        assets=[],
                        error=(
                            process.stderr.strip()
                            or process.stdout.strip()
                            or (
                                "LibreOffice did not "
                                "produce a DOCX file."
                            )
                        ),
                    )

                converted_path = (
                    converted_files[0]
                )

                return self._extract_zip_media(
                    document=document,
                    source_path=converted_path,
                    source_format="doc",
                    media_prefix="word/media/",
                    extraction_method=(
                        "libreoffice-doc-to-docx"
                    ),
                    force=force,
                    policy_extension=".docx",
                )

        except Exception as error:
            return DocumentAssetExtractionResult(
                document_id=document.id,
                status="failed",
                source_format="doc",
                discovered_count=0,
                extracted_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=1,
                assets=[],
                error=str(error),
            )

    def _extract_zip_media(
        self,
        *,
        document: Document,
        source_path: Path,
        source_format: str,
        media_prefix: str,
        extraction_method: str,
        force: bool,
        policy_extension: str,
    ) -> DocumentAssetExtractionResult:
        results: list[ExtractedAssetResult] = []
        discovered_count = 0
        skipped_count = 0
        failed_count = 0

        try:
            staging_parent = (
                str(self.staging_parent)
                if self.staging_parent is not None
                else None
            )
            with tempfile.TemporaryDirectory(
                prefix="ai-lab-office-assets-",
                dir=staging_parent,
            ) as temp_dir:
                staging_root = Path(temp_dir)
                staged_assets: list[_StagedOfficeAsset] = []
                actual_media_total = 0

                with zipfile.ZipFile(source_path, "r") as archive:
                    preflight = self.office_archive_safety.preflight(
                        path=source_path,
                        extension=policy_extension,
                        archive=archive,
                        media_prefix=media_prefix,
                    )
                    discovered_count = len(preflight.media_members)

                    for ordinal, member in enumerate(
                        preflight.media_members,
                        start=1,
                    ):
                        staged_path = (
                            staging_root
                            / f"member_{ordinal:04d}.bin"
                        )
                        actual_size, checksum = (
                            self._stream_media_member_to_stage(
                                archive=archive,
                                member=member,
                                staged_path=staged_path,
                                aggregate_bytes_before=actual_media_total,
                            )
                        )
                        actual_media_total += actual_size

                        if actual_size < self.MIN_IMAGE_FILE_SIZE:
                            skipped_count += 1
                            continue

                        image_info = self._inspect_image_file(
                            staged_path
                        )
                        if image_info is None:
                            failed_count += 1
                            results.append(
                                ExtractedAssetResult(
                                    asset_id=None,
                                    asset_index=ordinal,
                                    original_name=Path(
                                        member.normalized_path
                                    ).name,
                                    storage_path=None,
                                    mime_type=None,
                                    width=None,
                                    height=None,
                                    file_size=actual_size,
                                    checksum_sha256=checksum,
                                    status="failed",
                                    created=False,
                                    error="OFFICE_MEDIA_IMAGE_INVALID",
                                )
                            )
                            continue

                        width, height, image_format = image_info
                        if (
                            width < self.MIN_IMAGE_WIDTH
                            or height < self.MIN_IMAGE_HEIGHT
                        ):
                            skipped_count += 1
                            continue

                        staged_assets.append(
                            _StagedOfficeAsset(
                                member_path=member.normalized_path,
                                original_name=Path(
                                    member.normalized_path
                                ).name,
                                staged_path=staged_path,
                                file_size=actual_size,
                                checksum_sha256=checksum,
                                width=width,
                                height=height,
                                image_format=image_format,
                            )
                        )

                (
                    persisted_results,
                    extracted_count,
                    existing_count,
                ) = self._persist_staged_assets(
                    document=document,
                    staged_assets=staged_assets,
                    source_format=source_format,
                    extraction_method=extraction_method,
                    force=force,
                )
                results.extend(persisted_results)

        except OfficeArchiveSafetyError as error:
            self.asset_repository.rollback()
            return DocumentAssetExtractionResult(
                document_id=document.id,
                status="failed",
                source_format=source_format,
                discovered_count=discovered_count,
                extracted_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=1,
                assets=[],
                error=error.code,
            )
        except (
            OSError,
            RuntimeError,
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
        ):
            self.asset_repository.rollback()
            return DocumentAssetExtractionResult(
                document_id=document.id,
                status="failed",
                source_format=source_format,
                discovered_count=discovered_count,
                extracted_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=1,
                assets=[],
                error="OFFICE_CONTAINER_MISMATCH",
            )
        except Exception:
            self.asset_repository.rollback()
            return DocumentAssetExtractionResult(
                document_id=document.id,
                status="failed",
                source_format=source_format,
                discovered_count=discovered_count,
                extracted_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=1,
                assets=[],
                error="OFFICE_MEDIA_EXTRACTION_FAILED",
            )

        if failed_count > 0:
            status = "partial"
        elif extracted_count > 0:
            status = "extracted"
        elif existing_count > 0:
            status = "existing"
        else:
            status = "no_assets"

        return DocumentAssetExtractionResult(
            document_id=document.id,
            status=status,
            source_format=source_format,
            discovered_count=discovered_count,
            extracted_count=extracted_count,
            existing_count=existing_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            assets=results,
            error=None,
        )

    def _stream_media_member_to_stage(
        self,
        *,
        archive: zipfile.ZipFile,
        member: OfficeArchiveMember,
        staged_path: Path,
        aggregate_bytes_before: int,
    ) -> tuple[int, str]:
        actual_size = 0
        checksum = hashlib.sha256()
        try:
            with archive.open(member.info, "r") as source:
                with staged_path.open("xb") as target:
                    while True:
                        chunk = source.read(
                            self.office_archive_policy.stream_chunk_bytes
                        )
                        if not chunk:
                            break
                        actual_size += len(chunk)
                        if actual_size > member.info.file_size:
                            raise OfficeArchiveSafetyError(
                                "OFFICE_MEDIA_ACTUAL_SIZE_MISMATCH"
                            )
                        if (
                            actual_size
                            > self.office_archive_policy
                            .max_media_member_uncompressed_bytes
                        ):
                            raise OfficeArchiveSafetyError(
                                "OFFICE_MEDIA_MEMBER_SIZE_LIMIT"
                            )
                        if (
                            aggregate_bytes_before + actual_size
                            > self.office_archive_policy
                            .max_total_media_uncompressed_bytes
                        ):
                            raise OfficeArchiveSafetyError(
                                "OFFICE_MEDIA_TOTAL_SIZE_LIMIT"
                            )
                        checksum.update(chunk)
                        target.write(chunk)
        except OfficeArchiveSafetyError:
            staged_path.unlink(missing_ok=True)
            raise
        except Exception as error:
            staged_path.unlink(missing_ok=True)
            raise OfficeArchiveSafetyError(
                "OFFICE_MEDIA_STREAM_INVALID"
            ) from error

        if actual_size != member.info.file_size:
            staged_path.unlink(missing_ok=True)
            raise OfficeArchiveSafetyError(
                "OFFICE_MEDIA_ACTUAL_SIZE_MISMATCH"
            )
        return actual_size, checksum.hexdigest()

    def _inspect_image_file(
        self,
        staged_path: Path,
    ) -> tuple[int, int, str] | None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter(
                    "error",
                    Image.DecompressionBombWarning,
                )
                with Image.open(staged_path) as image:
                    width = image.width
                    height = image.height
                    image_format = image.format
                    if (
                        width
                        > self.office_archive_policy.max_image_dimension_px
                        or height
                        > self.office_archive_policy.max_image_dimension_px
                    ):
                        raise OfficeArchiveSafetyError(
                            "OFFICE_MEDIA_IMAGE_DIMENSION_LIMIT"
                        )
                    if (
                        width * height
                        > self.office_archive_policy.max_image_pixels
                    ):
                        raise OfficeArchiveSafetyError(
                            "OFFICE_MEDIA_IMAGE_PIXEL_LIMIT"
                        )
                    if not image_format:
                        return None
                    image.verify()
                    return width, height, image_format
        except OfficeArchiveSafetyError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            raise OfficeArchiveSafetyError(
                "OFFICE_MEDIA_IMAGE_PIXEL_LIMIT"
            ) from error
        except Exception:
            return None

    def _persist_staged_assets(
        self,
        *,
        document: Document,
        staged_assets: list[_StagedOfficeAsset],
        source_format: str,
        extraction_method: str,
        force: bool,
    ) -> tuple[list[ExtractedAssetResult], int, int]:
        if force:
            self._clear_existing_assets(document.id)

        existing_assets = self.asset_repository.get_for_document(
            document.id
        )
        existing_by_checksum = {
            asset.checksum_sha256: asset
            for asset in existing_assets
            if asset.checksum_sha256
        }
        next_asset_index = max(
            (asset.asset_index for asset in existing_assets),
            default=0,
        )
        results: list[ExtractedAssetResult] = []
        created_paths: list[Path] = []
        extracted_count = 0
        existing_count = 0
        storage_directory = self.asset_root / str(document.id)

        try:
            for staged in staged_assets:
                existing = existing_by_checksum.get(
                    staged.checksum_sha256
                )
                if existing is not None:
                    existing_count += 1
                    results.append(
                        ExtractedAssetResult(
                            asset_id=existing.id,
                            asset_index=existing.asset_index,
                            original_name=(
                                existing.original_name
                                or staged.original_name
                            ),
                            storage_path=existing.storage_path,
                            mime_type=existing.mime_type,
                            width=existing.width,
                            height=existing.height,
                            file_size=(
                                existing.file_size
                                or staged.file_size
                            ),
                            checksum_sha256=(
                                existing.checksum_sha256
                            ),
                            status="existing",
                            created=False,
                            error=None,
                        )
                    )
                    continue

                next_asset_index += 1
                suffix = Path(staged.original_name).suffix.lower()
                if not suffix:
                    suffix = self._suffix_for_format(
                        staged.image_format
                    )
                storage_directory.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                absolute_path = (
                    storage_directory
                    / f"asset_{next_asset_index:04d}{suffix}"
                )
                if absolute_path.exists():
                    raise OfficeArchiveSafetyError(
                        "OFFICE_MEDIA_PERSISTENCE_FAILED"
                    )
                created_paths.append(absolute_path)
                shutil.copyfile(
                    staged.staged_path,
                    absolute_path,
                )
                relative_path = absolute_path.relative_to(
                    self.data_directory
                ).as_posix()
                mime_type = (
                    Image.MIME.get(staged.image_format)
                    or mimetypes.guess_type(staged.original_name)[0]
                    or "application/octet-stream"
                )
                asset = DocumentAsset(
                    document_id=document.id,
                    asset_index=next_asset_index,
                    page_number=None,
                    container_name=staged.member_path,
                    asset_type="image",
                    source_format=source_format,
                    mime_type=mime_type,
                    original_name=staged.original_name,
                    storage_path=relative_path,
                    width=staged.width,
                    height=staged.height,
                    file_size=staged.file_size,
                    checksum_sha256=staged.checksum_sha256,
                    extraction_method=extraction_method,
                    ocr_text=None,
                    ocr_confidence=None,
                    vision_analysis=None,
                    processing_status="extracted",
                    processing_error=None,
                )
                created = self.asset_repository.create(asset)
                existing_by_checksum[staged.checksum_sha256] = created
                extracted_count += 1
                results.append(
                    ExtractedAssetResult(
                        asset_id=created.id,
                        asset_index=created.asset_index,
                        original_name=staged.original_name,
                        storage_path=relative_path,
                        mime_type=mime_type,
                        width=staged.width,
                        height=staged.height,
                        file_size=staged.file_size,
                        checksum_sha256=staged.checksum_sha256,
                        status="extracted",
                        created=True,
                        error=None,
                    )
                )

            if extracted_count > 0:
                self.asset_repository.commit()
        except OfficeArchiveSafetyError:
            self.asset_repository.rollback()
            self._remove_uncommitted_files(
                created_paths,
                storage_directory,
            )
            raise
        except Exception as error:
            self.asset_repository.rollback()
            self._remove_uncommitted_files(
                created_paths,
                storage_directory,
            )
            raise OfficeArchiveSafetyError(
                "OFFICE_MEDIA_PERSISTENCE_FAILED"
            ) from error

        return results, extracted_count, existing_count

    @staticmethod
    def _remove_uncommitted_files(
        created_paths: list[Path],
        storage_directory: Path,
    ) -> None:
        for path in created_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            if storage_directory.exists() and not any(
                storage_directory.iterdir()
            ):
                storage_directory.rmdir()
        except OSError:
            pass

    def _clear_existing_assets(
        self,
        document_id: int,
    ) -> None:
        assets = (
            self.asset_repository
            .get_for_document(
                document_id
            )
        )

        for asset in assets:
            try:
                path = (
                    self.data_directory
                    / asset.storage_path
                )

                if path.exists():
                    path.unlink(
                        missing_ok=True
                    )
            except Exception:
                pass

        self.asset_repository.delete_for_document(
            document_id
        )

        self.asset_repository.commit()

        directory = (
            self.asset_root
            / str(document_id)
        )

        if directory.exists():
            shutil.rmtree(
                directory
            )

    @staticmethod
    def _suffix_for_format(
        image_format: str,
    ) -> str:
        mapping = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "GIF": ".gif",
            "BMP": ".bmp",
            "TIFF": ".tiff",
            "WEBP": ".webp",
        }

        return mapping.get(
            image_format.upper(),
            ".bin",
        )

    @staticmethod
    def _failed_result(
        *,
        document_id: int,
        error: str,
    ) -> DocumentAssetExtractionResult:
        return DocumentAssetExtractionResult(
            document_id=document_id,
            status="failed",
            source_format=None,
            discovered_count=0,
            extracted_count=0,
            existing_count=0,
            skipped_count=0,
            failed_count=1,
            assets=[],
            error=error,
        )
