from __future__ import annotations

import re


PRODUCTION_QDRANT_COLLECTIONS = frozenset({"ai_lab_document_chunks"})
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
