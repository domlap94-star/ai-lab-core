from __future__ import annotations

from pathlib import Path

from test.run_client_notes_downstream_dependency_audit import DEPENDENCY_MATRIX


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    client_repository = (
        BACKEND_ROOT / "app/repositories/client_repository.py"
    ).read_text(encoding="utf-8")
    search_block = client_repository.split("if normalized_search:", 1)[1].split(
        "if client_type", 1
    )[0]
    assert "Client.notes" not in search_block

    document_repository = (
        BACKEND_ROOT / "app/repositories/document_repository.py"
    ).read_text(encoding="utf-8")
    assert "Client.notes" not in document_repository

    rag_paths = (
        "app/ai/services/rag_service.py",
        "app/services/semantic_search_service.py",
        "app/services/embedding_service.py",
        "app/services/document_chunking_service.py",
        "app/services/qdrant_vector_store.py",
    )
    for relative in rag_paths:
        source = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
        assert "Client.notes" not in source
        assert "client.notes" not in source

    notes_consumers = [row for row in DEPENDENCY_MATRIX if row["reads_client_notes"]]
    assert any(row["impact"] == "BLOCKING" for row in notes_consumers)
    assert any(
        row["consumer"] == "Stable Android/Windows 1.0.1+4"
        for row in notes_consumers
    )

    audit_source = (
        BACKEND_ROOT / "test/run_client_notes_downstream_dependency_audit.py"
    ).read_text(encoding="utf-8")
    assert ".upsert(" not in audit_source
    assert ".delete(" not in audit_source
    assert "UPDATE clients" not in audit_source

    print("CLIENT NOTES DOWNSTREAM DEPENDENCY AUDIT TESTS: OK")
    print("production database writes: 0")
    print("qdrant writes: 0")


if __name__ == "__main__":
    main()
