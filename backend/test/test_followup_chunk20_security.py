from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.database.session import get_db
from app.main import app
from app.services.document_service import (
    DocumentContentUnavailableError,
    DocumentService,
    UnsafeDocumentStoragePathError,
    resolve_document_storage_path,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_rejected(storage_path: str, root: Path) -> None:
    try:
        resolve_document_storage_path(storage_path=storage_path, data_root=root)
    except (UnsafeDocumentStoragePathError, DocumentContentUnavailableError):
        return
    raise AssertionError(f"unsafe storage path accepted: {storage_path!r}")


def main() -> None:
    filename_matrix = (
        "../secret.txt",
        "..\\secret.txt",
        "C:\\Windows\\System32\\calc.exe",
        "\\\\server\\share\\payload.pdf",
        "..%2f..%2fsecret.txt",
        "report\r\nX-Injected: yes.pdf",
    )
    for raw in filename_matrix:
        normalized = DocumentService._sanitize_filename(raw)
        require(
            bool(normalized)
            and len(normalized) <= 255
            and not normalized.startswith(".")
            and all(character not in normalized for character in "/\\:\r\n"),
            f"unsafe filename normalization for {raw!r}: {normalized!r}",
        )

    with TemporaryDirectory() as temporary:
        root = Path(temporary) / "data"
        root.mkdir()
        safe = root / "documents" / "safe.txt"
        safe.parent.mkdir()
        safe.write_text("synthetic", encoding="utf-8")
        require(
            resolve_document_storage_path(
                storage_path="documents/safe.txt", data_root=root
            )
            == safe.resolve(),
            "safe document path was not resolved",
        )

        outside = Path(temporary) / "outside.txt"
        outside.write_text("synthetic", encoding="utf-8")
        for attack in (
            "../outside.txt",
            "..\\outside.txt",
            str(outside.resolve()),
            "\\\\server\\share\\outside.txt",
            "%2e%2e/outside.txt",
        ):
            require_rejected(attack, root)

    normal_user = SimpleNamespace(
        id=700020,
        username="chunk20-normal",
        is_active=True,
        auth_version=0,
        role=SimpleNamespace(name="User"),
    )

    def override_user():
        return normal_user

    def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        http = TestClient(app, raise_server_exceptions=False)
        for path in (
            "/api/v1/admin/users",
            "/api/v1/admin/backups/schedules",
            "/api/v1/admin/knowledge-base",
            "/api/v1/admin/trash",
            "/api/v1/admin/change-history",
        ):
            response = http.get(path)
            require(response.status_code == 403, f"normal user reached {path}")

        marker = "Bearer synthetic-secret C:\\private\\customer.txt"
        with patch(
            "app.api.ai.ChatService.chat",
            new=AsyncMock(side_effect=RuntimeError(marker)),
        ):
            response = http.post(
                "/api/v1/ai/chat",
                json={"model": "synthetic", "message": "public fixture"},
            )
            require(response.status_code == 500, "AI error response status changed")
            require(marker not in response.text, "AI error leaked internal details")

        with patch(
            "app.api.ai.RagService.answer",
            new=AsyncMock(side_effect=RuntimeError(marker)),
        ):
            response = http.post(
                "/api/v1/ai/rag",
                json={"model": "synthetic", "question": "public fixture"},
            )
            require(response.status_code == 500, "RAG error response status changed")
            require(marker not in response.text, "RAG error leaked internal details")
    finally:
        app.dependency_overrides.clear()

    print("CHUNK20_FILENAME_NORMALIZATION=PASS")
    print("CHUNK20_STORAGE_PATH_CONTAINMENT=PASS")
    print("CHUNK20_NORMAL_USER_ADMIN_REJECTION=PASS")
    print("CHUNK20_ERROR_LEAKAGE=PASS")


if __name__ == "__main__":
    main()
