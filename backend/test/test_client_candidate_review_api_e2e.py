from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.main import app


def fake_current_user():
    return object()


def main() -> None:
    app.dependency_overrides[
        get_current_user
    ] = fake_current_user

    client = TestClient(app)

    try:
        print()
        print("=" * 110)
        print("CLIENT CANDIDATE REVIEW API E2E")
        print("=" * 110)

        response = client.get(
            "/api/v1/client-candidates",
            params={
                "status": "pending",
                "limit": 5,
            },
        )

        print()
        print("LIST STATUS:", response.status_code)

        if response.status_code != 200:
            print(response.text)

            raise RuntimeError(
                "Candidate list endpoint failed."
            )

        candidates = response.json()

        print(
            "LIST RESULTS:",
            len(candidates),
        )

        if not candidates:
            raise RuntimeError(
                "Candidate list returned no candidates."
            )

        first = candidates[0]

        candidate_id = first["id"]

        print(
            "FIRST CANDIDATE:",
            candidate_id,
            first.get("name"),
            first.get("status"),
        )

        detail_response = client.get(
            f"/api/v1/client-candidates/{candidate_id}"
        )

        print()
        print(
            "DETAIL STATUS:",
            detail_response.status_code,
        )

        if detail_response.status_code != 200:
            print(detail_response.text)

            raise RuntimeError(
                "Candidate detail endpoint failed."
            )

        detail = detail_response.json()

        if (
            detail.get(
                "candidate",
                {},
            ).get("id")
            != candidate_id
        ):
            raise RuntimeError(
                "Candidate detail returned wrong ID."
            )

        metadata = detail.get(
            "metadata",
            {},
        )

        print(
            "gmail_messages:",
            metadata.get(
                "gmail_message_count"
            ),
        )

        print(
            "sheets_rows:",
            metadata.get(
                "sheets_row_count"
            ),
        )

        print(
            "documents:",
            metadata.get(
                "document_count"
            ),
        )

        openapi = client.get(
            "/openapi.json"
        )

        if openapi.status_code != 200:
            raise RuntimeError(
                "OpenAPI request failed."
            )

        paths = (
            openapi.json()
            .get("paths", {})
        )

        required = {
            "/api/v1/client-candidates": {
                "get",
            },
            "/api/v1/client-candidates/{candidate_id}": {
                "get",
            },
            "/api/v1/client-candidates/{candidate_id}/accept": {
                "post",
            },
            "/api/v1/client-candidates/{candidate_id}/reject": {
                "post",
            },
        }

        for path, methods in required.items():
            if path not in paths:
                raise RuntimeError(
                    f"OpenAPI route missing: {path}"
                )

            actual_methods = {
                method.lower()
                for method
                in paths[path].keys()
            }

            if not methods.issubset(
                actual_methods
            ):
                raise RuntimeError(
                    "OpenAPI method missing "
                    f"for {path}: "
                    f"expected={methods}, "
                    f"actual={actual_methods}"
                )

        print()
        print(
            "OPENAPI ROUTES: OK"
        )

        print()
        print("=" * 110)
        print(
            "CLIENT CANDIDATE REVIEW API E2E: OK"
        )
        print("=" * 110)

    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
