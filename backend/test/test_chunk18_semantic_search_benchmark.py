from __future__ import annotations

from test.support.chunk18_benchmark import (
    VARIANTS,
    build_chunks,
    deterministic_point_id,
    hybrid_results,
    lexical_results,
    load_fixture,
    metric_summary,
)


def test_fixture_has_bounded_realistic_matrix() -> None:
    fixture = load_fixture()
    assert fixture["schema_version"] == "NEXT_STABIL_SEMANTIC_BENCHMARK_V1"
    assert len(fixture["documents"]) >= 16
    assert len(fixture["queries"]) >= 30
    assert {query["group"] for query in fixture["queries"]} == {
        "exact",
        "semantic",
        "client_scope",
        "negative",
        "ambiguous",
    }
    known = {document["id"] for document in fixture["documents"]}
    for query in fixture["queries"]:
        assert set(query["relevant"]).issubset(known)


def test_current_chunking_is_page_bounded_and_deterministic() -> None:
    documents = load_fixture()["documents"]
    first = build_chunks(documents, VARIANTS[0])
    second = build_chunks(documents, VARIANTS[0])
    assert first == second
    assert all(chunk["page"] >= 1 for chunk in first)
    assert all(len(chunk["content"]) <= VARIANTS[0].max_characters for chunk in first)
    assert len({chunk["point_id"] for chunk in first}) == len(first)


def test_point_identity_changes_for_ownership_or_version() -> None:
    common = {
        "document_id": "D01",
        "client_id": 101,
        "document_checksum": "a" * 64,
        "page": 1,
        "chunk_index": 0,
        "chunk_checksum": "b" * 64,
        "embedding_version": "embed-v1",
        "chunking_version": "chunk-v1",
    }
    original = deterministic_point_id(**common)
    assert original == deterministic_point_id(**common)
    assert original != deterministic_point_id(**{**common, "client_id": 202})
    assert original != deterministic_point_id(**{**common, "chunk_checksum": "c" * 64})
    assert original != deterministic_point_id(**{**common, "embedding_version": "embed-v2"})


def test_lexical_scope_is_applied_before_ranking() -> None:
    fixture = load_fixture()
    query = next(query for query in fixture["queries"] if query["id"] == "Q21")
    results = lexical_results(query, fixture["documents"])
    by_id = {document["id"]: document for document in fixture["documents"]}
    assert all(by_id[document_id]["client_id"] == 101 for document_id, _ in results)


def test_hybrid_keeps_strongest_existing_contract_score() -> None:
    results = hybrid_results(
        [("D01", 0.90), ("D02", 0.90)],
        [("D01", 0.75, 1), ("D03", 0.80, 2)],
    )
    assert results == [("D01", 0.90), ("D02", 0.90), ("D03", 0.80)]


def test_metric_summary_counts_negative_no_result() -> None:
    queries = [
        {"id": "positive", "relevant": ["D01"]},
        {"id": "negative", "relevant": []},
    ]
    summary = metric_summary(queries, {"positive": ["D01"], "negative": []})
    assert summary["recall_at_1"] == 1.0
    assert summary["mrr"] == 1.0
    assert summary["negative_precision"] == 1.0


def main() -> None:
    tests = (
        test_fixture_has_bounded_realistic_matrix,
        test_current_chunking_is_page_bounded_and_deterministic,
        test_point_identity_changes_for_ownership_or_version,
        test_lexical_scope_is_applied_before_ranking,
        test_hybrid_keeps_strongest_existing_contract_score,
        test_metric_summary_counts_negative_no_result,
    )
    for test in tests:
        test()
    print(f"CHUNK18_BENCHMARK_UNIT_TESTS={len(tests)}/{len(tests)} PASS")


if __name__ == "__main__":
    main()
