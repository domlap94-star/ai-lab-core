from __future__ import annotations

import re


PRODUCTION_QDRANT_COLLECTIONS = frozenset({
    "ai_lab_document_chunks",
    "ai_lab_knowledge_base_chunks",
})
PRODUCTION_QDRANT_ENDPOINTS = frozenset({
    ("qdrant", 6333),
    ("host.docker.internal", 6333),
    ("127.0.0.1", 6333),
    ("localhost", 6333),
})
_SAFE_TEST_COLLECTION = re.compile(r"^ai_lab_test_[a-z0-9]+(?:_[a-z0-9]+)*$")


class UnsafeTestQdrantCollectionError(RuntimeError):
    """Raised before a destructive test can mutate a non-test collection."""


def assert_test_qdrant_collection(collection_name: str) -> str:
    normalized = collection_name.strip()
    if normalized in PRODUCTION_QDRANT_COLLECTIONS:
        raise UnsafeTestQdrantCollectionError(
            "Refusing destructive Qdrant test against production collection "
            f"{normalized!r}. Use an ai_lab_test_* collection."
        )
    if not _SAFE_TEST_COLLECTION.fullmatch(normalized):
        raise UnsafeTestQdrantCollectionError(
            f"Refusing destructive Qdrant test against unsafe collection {normalized!r}. "
            "Use an ai_lab_test_* collection."
        )
    return normalized


def assert_test_qdrant_target(host: str, port: int, collection_name: str) -> tuple[str, int, str]:
    normalized_host = host.strip().lower()
    normalized_port = int(port)
    normalized_collection = assert_test_qdrant_collection(collection_name)
    if (normalized_host, normalized_port) in PRODUCTION_QDRANT_ENDPOINTS:
        raise UnsafeTestQdrantCollectionError(
            "Refusing destructive Qdrant test against the production endpoint "
            f"{normalized_host}:{normalized_port}. Use an explicit isolated Qdrant target."
        )
    return normalized_host, normalized_port, normalized_collection
