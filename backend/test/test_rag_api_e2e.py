from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.main import app


API_PATH = "/api/v1/ai/rag"


def authenticated_user():
    return SimpleNamespace(
        id=1,
        username="rag-api-e2e",
        email="rag-api-e2e@example.local",
        is_active=True,
    )


def assert_grounded_response(
    data: dict,
) -> None:
    required_top_level = {
        "question",
        "answer",
        "model",
        "sources",
        "evidence",
        "claims",
        "cited_source_numbers",
        "generation_attempts",
    }

    missing = (
        required_top_level
        - set(data)
    )

    if missing:
        raise AssertionError(
            "Missing response fields: "
            f"{sorted(missing)}"
        )

    if not data["question"]:
        raise AssertionError(
            "question is empty"
        )

    if not data["answer"]:
        raise AssertionError(
            "answer is empty"
        )

    if not data["model"]:
        raise AssertionError(
            "model is empty"
        )

    if not data["sources"]:
        raise AssertionError(
            "sources are empty"
        )

    if not data["evidence"]:
        raise AssertionError(
            "evidence is empty"
        )

    if not data["claims"]:
        raise AssertionError(
            "claims are empty"
        )

    source_numbers = {
        item["source_number"]
        for item in data["sources"]
    }

    evidence_map = {
        item["evidence_id"]: item
        for item in data["evidence"]
    }

    for claim in data["claims"]:
        evidence_id = (
            claim["evidence_id"]
        )

        source_number = (
            claim["source_number"]
        )

        if evidence_id not in evidence_map:
            raise AssertionError(
                "Claim references unknown "
                f"evidence_id={evidence_id}"
            )

        evidence = (
            evidence_map[evidence_id]
        )

        if (
            evidence["source_number"]
            != source_number
        ):
            raise AssertionError(
                "Claim/evidence source "
                "mapping mismatch"
            )

        if (
            evidence["text"]
            != claim["quote"]
        ):
            raise AssertionError(
                "Claim quote differs from "
                "backend evidence text"
            )

        if (
            source_number
            not in source_numbers
        ):
            raise AssertionError(
                "Claim references unknown "
                f"source_number={source_number}"
            )

    for source_number in (
        data["cited_source_numbers"]
    ):
        if (
            source_number
            not in source_numbers
        ):
            raise AssertionError(
                "cited_source_numbers contains "
                "unknown source"
            )


def main() -> None:
    print()
    print("=" * 110)
    print("RAG API HTTP E2E")
    print("=" * 110)

    client = TestClient(app)

    # ========================================================
    # 1. Authentication boundary
    # ========================================================

    print()
    print("=" * 110)
    print("AUTHENTICATION TEST")
    print("=" * 110)

    unauthorized = client.post(
        API_PATH,
        json={
            "question": (
                "Co dokumentacja mówi "
                "o zarysowaniach ścian?"
            ),
        },
    )

    print(
        "status:",
        unauthorized.status_code,
    )

    print(
        "body:",
        unauthorized.json(),
    )

    if unauthorized.status_code != 401:
        raise AssertionError(
            "Unauthenticated RAG request "
            "must return HTTP 401."
        )

    print(
        "unauthenticated access rejected: OK"
    )

    # ========================================================
    # Override authentication only.
    #
    # This still sends a real HTTP request through FastAPI,
    # routing, request validation and response validation.
    # The actual RAG stack remains real:
    #
    # SemanticSearchService
    # -> Ollama embeddings
    # -> Qdrant
    # -> evidence selection
    # -> Ollama LLM
    # ========================================================

    app.dependency_overrides[
        get_current_user
    ] = authenticated_user

    try:
        # ====================================================
        # 2. Grounded RAG request
        # ====================================================

        print()
        print("=" * 110)
        print("GROUNDED RAG HTTP REQUEST")
        print("=" * 110)

        response = client.post(
            API_PATH,
            json={
                "question": (
                    "Co dokumentacja mówi "
                    "o pęknięciach lub "
                    "zarysowaniach ścian?"
                ),
                "model": "llama3.2",
                "retrieval_limit": 5,
            },
        )

        print(
            "status:",
            response.status_code,
        )

        if response.status_code != 200:
            print(
                "body:",
                response.text,
            )

            raise AssertionError(
                "Grounded RAG API request "
                "did not return HTTP 200."
            )

        data = response.json()

        assert_grounded_response(
            data
        )

        print()
        print("question:")
        print(
            data["question"]
        )

        print()
        print("model:")
        print(
            data["model"]
        )

        print()
        print("generation_attempts:")
        print(
            data[
                "generation_attempts"
            ]
        )

        print()
        print("answer:")
        print(
            data["answer"]
        )

        print()
        print(
            "sources:",
            len(data["sources"]),
        )

        print(
            "evidence:",
            len(data["evidence"]),
        )

        print(
            "claims:",
            len(data["claims"]),
        )

        print(
            "cited_source_numbers:",
            data[
                "cited_source_numbers"
            ],
        )

        print()
        print(
            "grounded HTTP response "
            "structure: OK"
        )

        print(
            "claim -> evidence -> "
            "source mapping: OK"
        )

        # ====================================================
        # 3. No-source behavior
        # ====================================================

        print()
        print("=" * 110)
        print("NO-SOURCE HTTP REQUEST")
        print("=" * 110)

        no_source = client.post(
            API_PATH,
            json={
                "question": (
                    "Jaki jest dokładny skład "
                    "atmosfery planety Neptun "
                    "według dokumentacji klienta?"
                ),
                "model": "llama3.2",
                "retrieval_limit": 5,
                "score_threshold": 0.95,
            },
        )

        print(
            "status:",
            no_source.status_code,
        )

        if no_source.status_code != 200:
            print(
                "body:",
                no_source.text,
            )

            raise AssertionError(
                "No-source RAG request "
                "did not return HTTP 200."
            )

        no_source_data = (
            no_source.json()
        )

        print(
            "answer:",
            no_source_data["answer"],
        )

        print(
            "sources:",
            len(
                no_source_data[
                    "sources"
                ]
            ),
        )

        print(
            "evidence:",
            len(
                no_source_data[
                    "evidence"
                ]
            ),
        )

        print(
            "claims:",
            len(
                no_source_data[
                    "claims"
                ]
            ),
        )

        if no_source_data["sources"]:
            raise AssertionError(
                "No-source response "
                "contains sources."
            )

        if no_source_data["evidence"]:
            raise AssertionError(
                "No-source response "
                "contains evidence."
            )

        if no_source_data["claims"]:
            raise AssertionError(
                "No-source response "
                "contains claims."
            )

        if (
            "Nie znaleziono"
            not in no_source_data[
                "answer"
            ]
        ):
            raise AssertionError(
                "No-source response does "
                "not contain safe message."
            )

        print(
            "safe no-source behavior: OK"
        )

        # ====================================================
        # 4. Pydantic validation
        # ====================================================

        print()
        print("=" * 110)
        print("REQUEST VALIDATION")
        print("=" * 110)

        invalid = client.post(
            API_PATH,
            json={
                "question": "",
                "retrieval_limit": 0,
            },
        )

        print(
            "status:",
            invalid.status_code,
        )

        if invalid.status_code != 422:
            print(
                "body:",
                invalid.text,
            )

            raise AssertionError(
                "Invalid request must "
                "return HTTP 422."
            )

        print(
            "Pydantic request validation: OK"
        )

    finally:
        app.dependency_overrides.clear()

    print()
    print("=" * 110)
    print("RAG API HTTP E2E: OK")
    print("=" * 110)


if __name__ == "__main__":
    main()
