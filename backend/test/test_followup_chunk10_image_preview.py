from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient
from PIL import Image

from app.api.auth import get_current_user
from app.database.session import get_db
from app.main import app
from app.models.document import Document
from app.services.document_read_service import DocumentReadService
from app.services.document_thumbnail_service import (
    DocumentThumbnailService,
    MalformedDocumentImageError,
    UnsupportedDocumentImageError,
)


class _Db:
    pass


def _image(format_name: str, size: tuple[int, int] = (800, 400)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (30, 90, 150)).save(output, format=format_name)
    return output.getvalue()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    service = DocumentThumbnailService()
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        for mime, format_name in (
            ("image/jpeg", "JPEG"),
            ("image/png", "PNG"),
            ("image/webp", "WEBP"),
        ):
            path = root / f"source-{format_name.lower()}"
            path.write_bytes(_image(format_name))
            thumbnail = service.create(path, mime, 200)
            with Image.open(BytesIO(thumbnail)) as rendered:
                require(rendered.format == "PNG", "Thumbnail MIME/encoding mismatch")
                require(rendered.width == 200, "Thumbnail width is not bounded")
                require(rendered.height == 100, "Aspect ratio was not preserved")

        tiny = root / "tiny.jpg"
        tiny.write_bytes(_image("JPEG", (40, 20)))
        with Image.open(BytesIO(service.create(tiny, "image/jpeg", 200))) as rendered:
            require(rendered.size == (40, 20), "Tiny image was upscaled")

        generic = root / "generic.bin"
        generic.write_bytes(_image("JPEG"))
        require(
            bool(service.create(generic, "application/octet-stream", 200)),
            "Safely decoded generic image was rejected",
        )

        large = root / "large.jpg"
        large.write_bytes(_image("JPEG", (6000, 4000)))
        started = perf_counter()
        large_thumbnail = service.create(large, "image/jpeg", 200)
        large_elapsed_ms = (perf_counter() - started) * 1000
        with Image.open(BytesIO(large_thumbnail)) as rendered:
            require(rendered.size == (200, 133), "Large image was not bounded")
        require(large_elapsed_ms < 5000, "Large thumbnail generation exceeded 5s")

        malformed = root / "malformed.jpg"
        malformed.write_bytes(b"not-an-image")
        try:
            service.create(malformed, "image/jpeg", 200)
        except MalformedDocumentImageError:
            pass
        else:
            raise RuntimeError("Malformed image was accepted")

        png_as_jpeg = root / "mismatch.jpg"
        png_as_jpeg.write_bytes(_image("PNG"))
        try:
            service.create(png_as_jpeg, "image/jpeg", 200)
        except MalformedDocumentImageError:
            pass
        else:
            raise RuntimeError("MIME mismatch was accepted")

        try:
            service.create(malformed, "application/pdf", 200)
        except UnsupportedDocumentImageError:
            pass
        else:
            raise RuntimeError("Non-image thumbnail was accepted")

        endpoint_path = root / "endpoint.jpg"
        endpoint_path.write_bytes(_image("JPEG"))
        document = Document(id=900001, content_type="image/jpeg")

        app.dependency_overrides[get_current_user] = lambda: object()
        app.dependency_overrides[get_db] = lambda: _Db()
        original = DocumentReadService.get_content
        DocumentReadService.get_content = lambda self, document_id: (
            document,
            endpoint_path,
            "endpoint.jpg",
        )
        try:
            http = TestClient(app)
            anonymous_app = TestClient(app)
            app.dependency_overrides.pop(get_current_user)
            require(
                anonymous_app.get("/api/v1/documents/900001/thumbnail").status_code == 401,
                "Anonymous thumbnail must be rejected",
            )
            app.dependency_overrides[get_current_user] = lambda: object()
            response = http.get("/api/v1/documents/900001/thumbnail?max_size=200")
            require(response.status_code == 200, response.text)
            require(response.headers["content-type"] == "image/png", "Bad response MIME")
            require("storage_path" not in response.text, "Storage path leaked")
            require(response.headers["cache-control"].startswith("private"), "Unsafe cache policy")
        finally:
            DocumentReadService.get_content = original
            app.dependency_overrides.clear()

    print("FOLLOW-UP CHUNK 10 IMAGE PREVIEW BACKEND: 11/11 PASS")
    print(f"large_thumbnail_ms={large_elapsed_ms:.3f}")


if __name__ == "__main__":
    main()
