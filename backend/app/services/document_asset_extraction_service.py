from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
import tempfile
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

        if force:
            self._clear_existing_assets(
                document.id
            )

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
            )

        if extension == ".doc":
            return self._extract_legacy_doc(
                document=document,
                source_path=source_path,
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
    ) -> DocumentAssetExtractionResult:
        results: list[
            ExtractedAssetResult
        ] = []

        discovered_count = 0
        extracted_count = 0
        existing_count = 0
        skipped_count = 0
        failed_count = 0

        try:
            with zipfile.ZipFile(
                source_path,
                "r",
            ) as archive:
                members = [
                    member
                    for member
                    in archive.infolist()
                    if (
                        not member.is_dir()
                        and member.filename.startswith(
                            media_prefix
                        )
                    )
                ]

                discovered_count = len(
                    members
                )

                asset_index = 0

                for member in members:
                    try:
                        content = archive.read(
                            member
                        )

                        if (
                            len(content)
                            < self.MIN_IMAGE_FILE_SIZE
                        ):
                            skipped_count += 1
                            continue

                        checksum = (
                            hashlib.sha256(
                                content
                            ).hexdigest()
                        )

                        existing = (
                            self.asset_repository
                            .get_by_document_and_checksum(
                                document_id=(
                                    document.id
                                ),
                                checksum_sha256=(
                                    checksum
                                ),
                            )
                        )

                        if existing is not None:
                            existing_count += 1

                            results.append(
                                ExtractedAssetResult(
                                    asset_id=(
                                        existing.id
                                    ),
                                    asset_index=(
                                        existing.asset_index
                                    ),
                                    original_name=(
                                        existing.original_name
                                        or member.filename
                                    ),
                                    storage_path=(
                                        existing.storage_path
                                    ),
                                    mime_type=(
                                        existing.mime_type
                                    ),
                                    width=(
                                        existing.width
                                    ),
                                    height=(
                                        existing.height
                                    ),
                                    file_size=(
                                        existing.file_size
                                        or len(content)
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

                        image_info = (
                            self._inspect_image_bytes(
                                content
                            )
                        )

                        if image_info is None:
                            skipped_count += 1
                            continue

                        width, height, image_format = (
                            image_info
                        )

                        if (
                            width
                            < self.MIN_IMAGE_WIDTH
                            or height
                            < self.MIN_IMAGE_HEIGHT
                        ):
                            skipped_count += 1
                            continue

                        asset_index += 1

                        original_name = (
                            Path(
                                member.filename
                            ).name
                        )

                        suffix = (
                            Path(
                                original_name
                            ).suffix.lower()
                        )

                        if not suffix:
                            suffix = (
                                self._suffix_for_format(
                                    image_format
                                )
                            )

                        storage_directory = (
                            self.asset_root
                            / str(document.id)
                        )

                        storage_directory.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        stored_name = (
                            f"asset_"
                            f"{asset_index:04d}"
                            f"{suffix}"
                        )

                        absolute_path = (
                            storage_directory
                            / stored_name
                        )

                        absolute_path.write_bytes(
                            content
                        )

                        relative_path = (
                            absolute_path
                            .relative_to(
                                self.data_directory
                            )
                            .as_posix()
                        )

                        mime_type = (
                            Image.MIME.get(
                                image_format
                            )
                            or mimetypes.guess_type(
                                original_name
                            )[0]
                            or "application/octet-stream"
                        )

                        asset = DocumentAsset(
                            document_id=(
                                document.id
                            ),
                            asset_index=(
                                asset_index
                            ),
                            page_number=None,
                            container_name=(
                                member.filename
                            ),
                            asset_type="image",
                            source_format=(
                                source_format
                            ),
                            mime_type=(
                                mime_type
                            ),
                            original_name=(
                                original_name
                            ),
                            storage_path=(
                                relative_path
                            ),
                            width=width,
                            height=height,
                            file_size=len(
                                content
                            ),
                            checksum_sha256=(
                                checksum
                            ),
                            extraction_method=(
                                extraction_method
                            ),
                            ocr_text=None,
                            ocr_confidence=None,
                            vision_analysis=None,
                            processing_status=(
                                "extracted"
                            ),
                            processing_error=None,
                        )

                        created = (
                            self.asset_repository
                            .create(
                                asset
                            )
                        )

                        self.asset_repository.commit()

                        extracted_count += 1

                        results.append(
                            ExtractedAssetResult(
                                asset_id=(
                                    created.id
                                ),
                                asset_index=(
                                    created.asset_index
                                ),
                                original_name=(
                                    original_name
                                ),
                                storage_path=(
                                    relative_path
                                ),
                                mime_type=(
                                    mime_type
                                ),
                                width=width,
                                height=height,
                                file_size=len(
                                    content
                                ),
                                checksum_sha256=(
                                    checksum
                                ),
                                status="extracted",
                                created=True,
                                error=None,
                            )
                        )

                    except Exception as error:
                        self.asset_repository.rollback()

                        failed_count += 1

                        results.append(
                            ExtractedAssetResult(
                                asset_id=None,
                                asset_index=(
                                    asset_index + 1
                                ),
                                original_name=(
                                    Path(
                                        member.filename
                                    ).name
                                ),
                                storage_path=None,
                                mime_type=None,
                                width=None,
                                height=None,
                                file_size=(
                                    member.file_size
                                ),
                                checksum_sha256=None,
                                status="failed",
                                created=False,
                                error=str(error),
                            )
                        )

        except Exception as error:
            return DocumentAssetExtractionResult(
                document_id=document.id,
                status="failed",
                source_format=(
                    source_format
                ),
                discovered_count=0,
                extracted_count=0,
                existing_count=0,
                skipped_count=0,
                failed_count=1,
                assets=[],
                error=str(error),
            )

        if failed_count > 0:
            status = "partial"
        elif extracted_count > 0:
            status = "extracted"
        elif existing_count > 0:
            status = "existing"
        elif discovered_count > 0:
            status = "no_assets"
        else:
            status = "no_assets"

        return DocumentAssetExtractionResult(
            document_id=document.id,
            status=status,
            source_format=source_format,
            discovered_count=(
                discovered_count
            ),
            extracted_count=(
                extracted_count
            ),
            existing_count=(
                existing_count
            ),
            skipped_count=(
                skipped_count
            ),
            failed_count=(
                failed_count
            ),
            assets=results,
            error=None,
        )

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
    def _inspect_image_bytes(
        content: bytes,
    ) -> tuple[int, int, str] | None:
        from io import BytesIO

        try:
            with Image.open(
                BytesIO(content)
            ) as image:
                image.load()

                if not image.format:
                    return None

                return (
                    image.width,
                    image.height,
                    image.format,
                )

        except Exception:
            return None

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