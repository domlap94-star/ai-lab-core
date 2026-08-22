from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from qdrant_client import QdrantClient, models

from app.ai.clients.ollama_embedding_client import OllamaEmbeddingClient
from app.services.document_chunking_service import DocumentChunkingService
from test.support.qdrant_safety import assert_test_qdrant_target


POINT_NAMESPACE = uuid.UUID("67fd12be-0dbc-51f6-9d6f-f43606910744")
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "chunk18_semantic_search_benchmark.json"
)
SCORE_THRESHOLD = 0.60


@dataclass(frozen=True)
class ChunkVariant:
    name: str
    max_characters: int
    overlap_characters: int


VARIANTS = (
    ChunkVariant("current_v1", 1800, 250),
    ChunkVariant("smaller_900_150", 900, 150),
    ChunkVariant("larger_3000_300", 3000, 300),
    ChunkVariant("current_overlap_450", 1800, 450),
)


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_point_id(
    *,
    document_id: str,
    client_id: int,
    document_checksum: str,
    page: int,
    chunk_index: int,
    chunk_checksum: str,
    embedding_version: str,
    chunking_version: str,
) -> str:
    identity = "|".join(
        (
            "source_type=document",
            f"document_id={document_id}",
            f"client_id={client_id}",
            f"document_checksum={document_checksum}",
            f"page={page}",
            f"chunk_index={chunk_index}",
            f"chunk_checksum={chunk_checksum}",
            f"embedding_version={embedding_version}",
            f"chunking_version={chunking_version}",
        )
    )
    return str(uuid.uuid5(POINT_NAMESPACE, identity))


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def expanded_pages(document: dict[str, Any]) -> list[str]:
    pages = list(document["pages"])
    repetitions = int(document.get("repeat_last_page", 1))
    if repetitions > 1:
        pages[-1] = "\n\n".join([pages[-1]] * repetitions)
    return pages


def build_chunks(
    documents: Iterable[dict[str, Any]],
    variant: ChunkVariant,
) -> list[dict[str, Any]]:
    # The benchmark deliberately calls the canonical splitter without a DB
    # session; it never creates DocumentChunk rows.
    splitter = object.__new__(DocumentChunkingService)
    chunks: list[dict[str, Any]] = []
    for document in documents:
        pages = expanded_pages(document)
        document_checksum = sha256_text("\n\f\n".join(pages))
        document_chunk_index = 0
        for page_number, page_text in enumerate(pages, start=1):
            page_chunks = splitter._split_text(
                text=page_text,
                max_characters=variant.max_characters,
                overlap_characters=variant.overlap_characters,
            )
            for page_chunk_index, content in enumerate(page_chunks):
                chunk_checksum = sha256_text(content)
                point_id = deterministic_point_id(
                    document_id=document["id"],
                    client_id=int(document["client_id"]),
                    document_checksum=document_checksum,
                    page=page_number,
                    chunk_index=page_chunk_index,
                    chunk_checksum=chunk_checksum,
                    embedding_version="qwen3-embedding-0.6b-v1",
                    chunking_version=variant.name,
                )
                chunks.append(
                    {
                        "point_id": point_id,
                        "document_id": document["id"],
                        "client_id": int(document["client_id"]),
                        "filename": document["filename"],
                        "page": page_number,
                        "chunk_index": page_chunk_index,
                        "document_chunk_index": document_chunk_index,
                        "content": content,
                        "document_checksum": document_checksum,
                        "chunk_checksum": chunk_checksum,
                        "embedding_version": "qwen3-embedding-0.6b-v1",
                        "chunking_version": variant.name,
                    }
                )
                document_chunk_index += 1
    return chunks


def lexical_results(
    query: dict[str, Any],
    documents: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[tuple[str, float]]:
    needle = normalized(query["text"])
    matches: list[tuple[str, float]] = []
    for document in documents:
        if query.get("client_id") is not None and int(document["client_id"]) != int(
            query["client_id"]
        ):
            continue
        filename = normalized(document["filename"])
        text = normalized(" ".join(expanded_pages(document)))
        if needle in filename:
            matches.append((document["id"], 1.0))
        elif needle in text:
            matches.append((document["id"], 0.90))
    return sorted(matches, key=lambda item: (-item[1], item[0]))[:limit]


def semantic_results(
    client: QdrantClient,
    collection_name: str,
    query: dict[str, Any],
    vector: list[float],
    *,
    limit: int = 5,
) -> list[tuple[str, float, int]]:
    query_filter = None
    if query.get("client_id") is not None:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="client_id",
                    match=models.MatchValue(value=int(query["client_id"])),
                )
            ]
        )
    response = client.query_points(
        collection_name=collection_name,
        query=vector,
        query_filter=query_filter,
        limit=20,
        with_payload=True,
        with_vectors=False,
        score_threshold=SCORE_THRESHOLD,
    )
    best: dict[str, tuple[float, int]] = {}
    for point in response.points:
        payload = dict(point.payload or {})
        document_id = str(payload["document_id"])
        score = float(point.score)
        page = int(payload["page"])
        previous = best.get(document_id)
        if previous is None or score > previous[0]:
            best[document_id] = (score, page)
    ordered = sorted(best.items(), key=lambda item: (-item[1][0], item[0]))
    return [(document_id, score, page) for document_id, (score, page) in ordered[:limit]]


def hybrid_results(
    lexical: list[tuple[str, float]],
    semantic: list[tuple[str, float, int]],
    *,
    limit: int = 5,
) -> list[tuple[str, float]]:
    # Mirrors the existing GlobalSearch merge contract: retain the strongest
    # score for a document and de-duplicate, without a second search index.
    merged: dict[str, float] = {document_id: score for document_id, score in lexical}
    for document_id, score, _page in semantic:
        merged[document_id] = max(merged.get(document_id, 0.0), score)
    return sorted(merged.items(), key=lambda item: (-item[1], item[0]))[:limit]


def metric_summary(
    queries: list[dict[str, Any]],
    ranked: dict[str, list[str]],
) -> dict[str, float | int]:
    positive = [query for query in queries if query["relevant"]]
    negative = [query for query in queries if not query["relevant"]]
    recalls: dict[int, float] = {}
    for k in (1, 3, 5):
        total = 0.0
        for query in positive:
            relevant = set(query["relevant"])
            total += len(relevant.intersection(ranked[query["id"]][:k])) / len(relevant)
        recalls[k] = total / len(positive)
    reciprocal_rank = 0.0
    for query in positive:
        relevant = set(query["relevant"])
        first = next(
            (index for index, item in enumerate(ranked[query["id"]], start=1) if item in relevant),
            None,
        )
        reciprocal_rank += 0.0 if first is None else 1.0 / first
    negative_correct = sum(not ranked[query["id"]] for query in negative)
    return {
        "recall_at_1": round(recalls[1], 6),
        "recall_at_3": round(recalls[3], 6),
        "recall_at_5": round(recalls[5], 6),
        "mrr": round(reciprocal_rank / len(positive), 6),
        "negative_queries": len(negative),
        "negative_correct_no_result": negative_correct,
        "negative_precision": round(negative_correct / len(negative), 6),
    }


def run_benchmark(
    *,
    qdrant_host: str,
    qdrant_port: int,
    collection_prefix: str,
) -> dict[str, Any]:
    fixture = load_fixture()
    documents = fixture["documents"]
    queries = fixture["queries"]
    embedder = OllamaEmbeddingClient()
    client = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=60)

    query_started = time.perf_counter()
    query_response = embedder.embed([query["text"] for query in queries])
    query_seconds = time.perf_counter() - query_started
    if any(len(vector) != 1024 for vector in query_response.embeddings):
        raise RuntimeError("benchmark_embedding_dimension_invalid")

    lexical_ranked = {
        query["id"]: [item[0] for item in lexical_results(query, documents)]
        for query in queries
    }
    results: dict[str, Any] = {
        "schema_version": fixture["schema_version"],
        "documents": len(documents),
        "queries": len(queries),
        "embedding_model": query_response.model,
        "embedding_dimensions": 1024,
        "score_threshold": SCORE_THRESHOLD,
        "query_embedding_seconds": round(query_seconds, 4),
        "lexical": metric_summary(queries, lexical_ranked),
        "variants": {},
    }

    for variant in VARIANTS:
        collection_name = f"{collection_prefix}_{variant.name}"
        assert_test_qdrant_target(qdrant_host, qdrant_port, collection_name)
        chunks = build_chunks(documents, variant)
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )
        embed_started = time.perf_counter()
        response = embedder.embed([chunk["content"] for chunk in chunks])
        embed_seconds = time.perf_counter() - embed_started
        points = []
        for chunk, vector in zip(chunks, response.embeddings, strict=True):
            payload = {key: value for key, value in chunk.items() if key not in {"point_id"}}
            payload["source_type"] = "document"
            points.append(
                models.PointStruct(id=chunk["point_id"], vector=vector, payload=payload)
            )
        client.upsert(collection_name=collection_name, points=points, wait=True)
        # Exact idempotency proof: the same deterministic IDs do not grow the collection.
        client.upsert(collection_name=collection_name, points=points, wait=True)
        exact_count = client.count(collection_name=collection_name, exact=True).count
        if exact_count != len(chunks):
            raise RuntimeError("benchmark_idempotency_failed")

        semantic_ranked: dict[str, list[str]] = {}
        hybrid_ranked: dict[str, list[str]] = {}
        leakage = 0
        for query, vector in zip(queries, query_response.embeddings, strict=True):
            semantic = semantic_results(client, collection_name, query, vector)
            semantic_ranked[query["id"]] = [item[0] for item in semantic]
            lexical = lexical_results(query, documents)
            hybrid_ranked[query["id"]] = [item[0] for item in hybrid_results(lexical, semantic)]
            if query.get("client_id") is not None:
                expected_client = int(query["client_id"])
                by_id = {document["id"]: int(document["client_id"]) for document in documents}
                leakage += sum(
                    by_id[document_id] != expected_client
                    for document_id in semantic_ranked[query["id"]]
                )

        results["variants"][variant.name] = {
            "max_characters": variant.max_characters,
            "overlap_characters": variant.overlap_characters,
            "chunks": len(chunks),
            "embedding_seconds": round(embed_seconds, 4),
            "chunks_per_minute": round(len(chunks) * 60 / max(embed_seconds, 0.001), 2),
            "semantic": metric_summary(queries, semantic_ranked),
            "hybrid": metric_summary(queries, hybrid_ranked),
            "client_scope_leakage": leakage,
            "idempotent_point_count": exact_count,
        }

    sample_texts = [
        chunk["content"]
        for chunk in build_chunks(documents, VARIANTS[0])[:20]
    ]
    batch_results: dict[str, Any] = {}
    for size in (5, 10, 20):
        started = time.perf_counter()
        count = 0
        for offset in range(0, len(sample_texts), size):
            response = embedder.embed(sample_texts[offset : offset + size])
            count += len(response.embeddings)
        elapsed = time.perf_counter() - started
        batch_results[str(size)] = {
            "inputs": count,
            "seconds": round(elapsed, 4),
            "inputs_per_minute": round(count * 60 / max(elapsed, 0.001), 2),
        }
    results["batch_sizes"] = batch_results
    return results


def quality_threshold_met(result: dict[str, Any], variant_name: str) -> bool:
    lexical = result["lexical"]
    variant = result["variants"][variant_name]
    semantic = variant["semantic"]
    hybrid = variant["hybrid"]
    return all(
        (
            hybrid["recall_at_3"] >= 0.80,
            hybrid["mrr"] >= lexical["mrr"] + 0.10,
            hybrid["recall_at_1"] >= lexical["recall_at_1"] - 0.05,
            semantic["negative_precision"] >= 0.80,
            hybrid["negative_precision"] >= 0.80,
            variant["client_scope_leakage"] == 0,
        )
    )


def ensure_finite_metrics(result: dict[str, Any]) -> None:
    for variant in result["variants"].values():
        for method in ("semantic", "hybrid"):
            for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr"):
                if not math.isfinite(float(variant[method][key])):
                    raise RuntimeError("benchmark_metric_not_finite")
