from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core.config import settings
from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.services.document_service import (
    DocumentContentUnavailableError,
    DocumentService,
    UnsafeDocumentStoragePathError,
    resolve_document_storage_path,
)


PATH = "/api/v1/documents"
PUBLIC_KEYS = {
    "id",
    "original_filename",
    "content_type",
    "file_size",
    "source_type",
    "client_id",
    "project_id",
    "client_name",
    "candidate_id",
    "candidate_name",
    "processing_status",
    "metadata_status",
    "match_status",
    "match_confidence",
    "captured_at",
    "parent_document_id",
    "archive_member_path",
    "archive_depth",
    "created_at",
    "updated_at",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def get_json(http: TestClient, headers: dict[str, str], **params):
    response = http.get(PATH, headers=headers, params=params)
    require(response.status_code == 200, response.text)
    return response.json()


def test_path_security() -> None:
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "data"
        root.mkdir()
        inside = root / "inside.txt"
        inside.write_bytes(b"inside")
        outside = base / "outside.txt"
        outside.write_bytes(b"outside")

        resolved = resolve_document_storage_path(
            storage_path="inside.txt",
            data_root=root,
        )
        require(resolved == inside.resolve(), "Safe file resolution failed")

        try:
            resolve_document_storage_path(
                storage_path="../outside.txt",
                data_root=root,
            )
        except UnsafeDocumentStoragePathError:
            pass
        else:
            raise RuntimeError("Traversal outside data root was accepted")

        symlink = root / "outside-link.txt"
        symlink.symlink_to(outside)
        try:
            resolve_document_storage_path(
                storage_path=symlink.name,
                data_root=root,
            )
        except UnsafeDocumentStoragePathError:
            pass
        else:
            raise RuntimeError("Symlink outside data root was accepted")

        try:
            resolve_document_storage_path(
                storage_path="missing.txt",
                data_root=root,
            )
        except DocumentContentUnavailableError:
            pass
        else:
            raise RuntimeError("Missing content was accepted")


def main() -> None:
    test_path_security()
    http = TestClient(app)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.is_active.is_(True)).first()
        require(user is not None, "No active user for JWT acceptance")
        token = create_access_token(data={"sub": user.username})
        headers = {"Authorization": f"Bearer {token}"}

        require(http.get(PATH).status_code == 401, "Anonymous list must be 401")

        total = db.query(func.count(Document.id)).scalar()
        linked = (
            db.query(func.count(Document.id))
            .filter(Document.client_id.is_not(None))
            .scalar()
        )
        candidate_only = (
            db.query(func.count(Document.id))
            .filter(
                Document.client_id.is_(None),
                Document.candidate_id.is_not(None),
            )
            .scalar()
        )
        unlinked = (
            db.query(func.count(Document.id))
            .filter(
                Document.client_id.is_(None),
                Document.candidate_id.is_(None),
            )
            .scalar()
        )

        first = get_json(http, headers, skip=0, limit=50)
        second = get_json(http, headers, skip=50, limit=50)
        require(first["total"] == total, "Document total mismatch")
        require(len(first["items"]) == min(50, total), "Bad first page")
        require(
            all(set(item) == PUBLIC_KEYS for item in first["items"]),
            "Unsafe or missing list fields",
        )
        require(
            {item["id"] for item in first["items"]}.isdisjoint(
                {item["id"] for item in second["items"]}
            ),
            "Duplicate IDs across pages",
        )

        all_page_items = first["items"] + second["items"]
        ordering = [
            (datetime.fromisoformat(item["created_at"]), item["id"])
            for item in all_page_items
        ]
        require(ordering == sorted(ordering, reverse=True), "Unstable ordering")

        last_skip = ((total - 1) // 50) * 50 if total else 0
        last = get_json(http, headers, skip=last_skip, limit=50)
        require(len(last["items"]) == total - last_skip, "Bad last page")

        target = second["items"][0]
        filename = target["original_filename"]
        require(filename, "Search target has no original filename")
        searched = get_json(http, headers, search=filename, limit=100)
        require(
            target["id"] in {item["id"] for item in searched["items"]},
            "Global filename search missed second-page document",
        )

        source = get_json(http, headers, source_type=target["source_type"], limit=100)
        expected_source = (
            db.query(func.count(Document.id))
            .filter(Document.source_type == target["source_type"])
            .scalar()
        )
        require(source["total"] == expected_source, "Source total mismatch")
        require(
            all(item["source_type"] == target["source_type"] for item in source["items"]),
            "Source filter leaked values",
        )
        matched = get_json(http, headers, match_status=target["match_status"], limit=100)
        expected_match = (
            db.query(func.count(Document.id))
            .filter(Document.match_status == target["match_status"])
            .scalar()
        )
        require(matched["total"] == expected_match, "Match total mismatch")
        require(
            all(item["match_status"] == target["match_status"] for item in matched["items"]),
            "Match filter leaked values",
        )
        processed = get_json(
            http,
            headers,
            processing_status=target["processing_status"],
            limit=100,
        )
        expected_processing = (
            db.query(func.count(Document.id))
            .filter(Document.processing_status == target["processing_status"])
            .scalar()
        )
        require(
            processed["total"] == expected_processing,
            "Processing total mismatch",
        )
        require(
            all(
                item["processing_status"] == target["processing_status"]
                for item in processed["items"]
            ),
            "Processing filter leaked values",
        )

        link_results = {}
        for state, expected in (
            ("LINKED", linked),
            ("CANDIDATE_ONLY", candidate_only),
            ("UNLINKED", unlinked),
        ):
            result = get_json(http, headers, link_state=state, limit=100)
            require(result["total"] == expected, f"{state} total mismatch")
            link_results[state] = result["total"]

        client_target = next(
            item for item in all_page_items if item["client_id"] is not None
        )
        by_client = get_json(
            http,
            headers,
            client_id=client_target["client_id"],
            limit=100,
        )
        expected_client = (
            db.query(func.count(Document.id))
            .filter(Document.client_id == client_target["client_id"])
            .scalar()
        )
        require(by_client["total"] == expected_client, "Client total mismatch")
        require(
            all(item["client_id"] == client_target["client_id"] for item in by_client["items"]),
            "Client filter leaked values",
        )

        combined = get_json(
            http,
            headers,
            search=filename,
            source_type=target["source_type"],
            match_status=target["match_status"],
            limit=100,
        )
        require(target["id"] in {item["id"] for item in combined["items"]}, "Combined filter failed")

        require(
            http.get(PATH, headers=headers, params={"limit": 101}).status_code
            == 422,
            "Limit above maximum must be 422",
        )

        detail_id = first["items"][0]["id"]
        require(http.get(f"{PATH}/{detail_id}").status_code == 401, "Anonymous detail must be 401")
        detail = http.get(f"{PATH}/{detail_id}", headers=headers)
        require(detail.status_code == 200, detail.text)
        require(set(detail.json()) == PUBLIC_KEYS, "Unsafe or missing public fields")
        require("storage_path" not in detail.text, "storage_path leaked")

        unknown_id = (db.query(func.max(Document.id)).scalar() or 0) + 100000
        require(
            http.get(f"{PATH}/{unknown_id}", headers=headers).status_code == 404,
            "Unknown detail must be 404",
        )
        require(
            http.get(f"{PATH}/{unknown_id}/content", headers=headers).status_code == 404,
            "Unknown content must be 404",
        )
        require(
            http.get(f"{PATH}/{detail_id}/content").status_code == 401,
            "Anonymous content must be 401",
        )

        download_document = None
        for document in (
            db.query(Document)
            .filter(
                Document.storage_path.is_not(None),
                Document.checksum_sha256.is_not(None),
            )
            .order_by(Document.file_size.asc(), Document.id.asc())
            .limit(200)
        ):
            try:
                path = DocumentService(db).get_absolute_storage_path(document)
            except DocumentContentUnavailableError:
                continue
            if path is not None:
                download_document = document
                break

        require(download_document is not None, "No downloadable checksum document")
        content = http.get(
            f"{PATH}/{download_document.id}/content",
            headers=headers,
        )
        require(content.status_code == 200, content.text)
        require(content.headers.get("content-type") == download_document.content_type, "Bad MIME")
        require(int(content.headers["content-length"]) == len(content.content), "Bad length")
        require("content-disposition" in content.headers, "Missing filename header")
        require(
            hashlib.sha256(content.content).hexdigest()
            == download_document.checksum_sha256,
            "Downloaded checksum mismatch",
        )

        missing_key = http.post(
            f"{PATH}/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        wrong_key = http.post(
            f"{PATH}/upload",
            headers={"X-Import-Api-Key": "wrong"},
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        valid_key = http.post(
            f"{PATH}/upload",
            headers={"X-Import-Api-Key": settings.n8n_ingest_api_key},
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        require(missing_key.status_code == 401, "Missing import key semantics changed")
        require(wrong_key.status_code == 403, "Wrong import key semantics changed")
        require(valid_key.status_code == 422, "Valid import key did not reach upload validation")

        print("DOCUMENT READ API E2E: OK")
        print(f"total={total}")
        print(f"linked={linked}")
        print(f"candidate_only={candidate_only}")
        print(f"unlinked={unlinked}")
        print(f"first_page={len(first['items'])}")
        print(f"last_page={len(last['items'])}")
        print(f"search_target_id={target['id']}")
        print(f"search_total={searched['total']}")
        print(f"source_total={source['total']}")
        print(f"match_total={matched['total']}")
        print(f"processing_total={processed['total']}")
        print(f"client_total={by_client['total']}")
        print(f"combined_total={combined['total']}")
        print(f"download_document_id={download_document.id}")
        print(f"download_bytes={len(content.content)}")
        print(f"link_totals={link_results}")
        print("path_security=OK")
        print("upload_auth_regression=OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
