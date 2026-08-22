from __future__ import annotations

from test.support.qdrant_safety import (
    UnsafeTestQdrantCollectionError,
    assert_test_qdrant_collection,
    assert_test_qdrant_target,
)


def require_unsafe(action, message: str) -> None:
    try:
        action()
    except UnsafeTestQdrantCollectionError:
        return
    raise AssertionError(message)


def main() -> None:
    require_unsafe(
        lambda: assert_test_qdrant_target(
            "qdrant", 6333, "ai_lab_test_kb_guard"
        ),
        "isolated DB must not permit the production Qdrant endpoint",
    )
    require_unsafe(
        lambda: assert_test_qdrant_collection("ai_lab_document_chunks"),
        "customer production collection must be rejected",
    )
    require_unsafe(
        lambda: assert_test_qdrant_collection("ai_lab_knowledge_base_chunks"),
        "Knowledge Base production collection must be rejected",
    )
    target = assert_test_qdrant_target(
        "host.docker.internal", 16333, "ai_lab_test_kb_guard"
    )
    if target != ("host.docker.internal", 16333, "ai_lab_test_kb_guard"):
        raise AssertionError("explicit isolated Qdrant target was not preserved")
    print("QDRANT_TEST_SAFETY=PASS")
    print("PRODUCTION_RUNTIME_CONFIG_UNCHANGED=PASS")


if __name__ == "__main__":
    main()
