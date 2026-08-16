from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.documents.router import _parse_intake_metadata
from app.main import app
from app.services.document_service import (
    DocumentService,
    InvalidLocationMetadataError,
    MissingLocationMetadataError,
)


def main() -> None:
    response = TestClient(app).post(
        "/api/v1/documents/user-upload",
        files={"file": ("test.txt", b"test", "text/plain")},
    )
    assert response.status_code in {401, 403}
    parsed = _parse_intake_metadata('{"origin":"camera_capture","user_comment":"field","secret":"drop"}')
    assert parsed == {"origin": "camera_capture", "user_comment": "field"}
    try:
        _parse_intake_metadata("[]")
        raise AssertionError("non-object metadata accepted")
    except HTTPException as error:
        assert error.status_code == 422

    service = object.__new__(DocumentService)
    service._validate_location_metadata(
        source_type="camera_photo",
        captured_at=datetime.now(UTC),
        latitude=None,
        longitude=None,
        location_accuracy_m=None,
    )
    try:
        service._validate_location_metadata(
            source_type="camera_photo",
            captured_at=None,
            latitude=None,
            longitude=None,
            location_accuracy_m=None,
        )
        raise AssertionError("camera without captured_at accepted")
    except MissingLocationMetadataError:
        pass
    try:
        service._validate_location_metadata(
            source_type="manual_upload",
            captured_at=None,
            latitude=52.0,
            longitude=None,
            location_accuracy_m=None,
        )
        raise AssertionError("partial coordinates accepted")
    except InvalidLocationMetadataError:
        pass
    print("CHUNK 9 document intake tests: PASS (JWT auth, metadata, optional GPS)")


if __name__ == "__main__":
    main()
