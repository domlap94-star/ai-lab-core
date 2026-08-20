from __future__ import annotations

from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


class DocumentThumbnailError(Exception):
    pass


class UnsupportedDocumentImageError(DocumentThumbnailError):
    pass


class MalformedDocumentImageError(DocumentThumbnailError):
    pass


class DocumentThumbnailService:
    """Build a bounded, in-memory preview without creating derived files."""

    DEFAULT_MAX_SIZE = 200
    MAX_SIZE = 400
    MAX_SOURCE_PIXELS = 40_000_000
    _FORMATS_BY_MIME = {
        "image/jpeg": {"JPEG"},
        "image/png": {"PNG"},
        "image/webp": {"WEBP"},
        "application/octet-stream": {"JPEG", "PNG", "WEBP"},
    }

    def create(self, path: Path, content_type: str, max_size: int) -> bytes:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        expected_formats = self._FORMATS_BY_MIME.get(normalized_type)
        if expected_formats is None:
            raise UnsupportedDocumentImageError
        if not 32 <= max_size <= self.MAX_SIZE:
            raise ValueError("thumbnail_size_out_of_range")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as source:
                    if source.format not in expected_formats:
                        raise MalformedDocumentImageError
                    width, height = source.size
                    if width <= 0 or height <= 0 or width * height > self.MAX_SOURCE_PIXELS:
                        raise MalformedDocumentImageError
                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    oriented.thumbnail(
                        (max_size, max_size),
                        Image.Resampling.LANCZOS,
                    )
                    if oriented.mode not in {"RGB", "RGBA"}:
                        oriented = oriented.convert("RGBA")
                    output = BytesIO()
                    oriented.save(output, format="PNG", optimize=True)
                    return output.getvalue()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            raise MalformedDocumentImageError from error
