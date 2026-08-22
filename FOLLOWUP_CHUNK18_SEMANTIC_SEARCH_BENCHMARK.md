# FOLLOW-UP CHUNK 18 — Semantic Search Coverage V2 benchmark

Date: 2026-08-22

Scope: design, read-only production audit, and isolated public-safe benchmark

Production vector writes/deletes: **0 / 0**
Decision: **DO NOT RECOMMEND PRODUCTION BACKFILL IN THE CURRENT RETRIEVAL CONFIGURATION**

## Executive decision

Semantic retrieval adds material paraphrase value, but the current raw-query
`qwen3-embedding:0.6b` path cannot simultaneously meet the declared recall and
no-result precision thresholds. With the current `0.60` cutoff, hybrid
Recall@3 is only `0.500`. At `0.50`, hybrid Recall@3 rises to `0.795699`, but
negative-query precision falls to `0.60`. At the first tested cutoff with
perfect negative behavior (`0.54`), hybrid Recall@3 is `0.669355`.

The production backfill gate
`FOLLOWUP_QDRANT_BACKFILL_APPROVAL_REQUIRED` remains **unconsumed**. It should
not be requested until an isolated reranking/query-representation improvement
meets the benchmark threshold without client leakage or exact-query regression.

## Current-state audit

### Production data and Qdrant

| Item | Live value |
|---|---:|
| PostgreSQL revision | `followup_contact_person_20260822` |
| Documents total | 5,929 |
| Active Documents | 5,927 |
| Active processed Documents | 129 |
| Active Documents with any document text | 114 |
| Active Documents with at least 80 useful characters | 94 |
| Conservative client-scoped eligibility | 82 |
| `document_chunks` rows | 57 |
| Embedded chunks | 57 |
| Embedded Documents | 11 |
| Qdrant points | 57 |
| Qdrant unique Documents | 11 |
| Qdrant client-scoped usable points | 0 |
| Qdrant version | 1.18.3 |
| Vector configuration | 1,024 / Cosine |
| Collection status | green; optimizer `ok`; 6 segments |
| Payload indexes | none |

`stored` accounts for 5,798 active Documents and `processed` for 129. The
backfill estimate therefore uses the 82 currently processed, checksummed,
client-owned, non-Trash Documents with useful text—not the headline total of
5,929. No processing retry or historical scan was run.

### Point distribution and payload contract

The 57 points represent 11 Documents with per-document counts:
`2, 1, 1, 8, 1, 10, 6, 1, 2, 2, 23`.

| Field | Coverage | Classification |
|---|---:|---|
| `document_id` | 57/57 | required/present |
| `chunk_id` | 57/57 | legacy DB-row point ownership |
| `chunk_index` | 57/57 | required/present |
| `page_from`, `page_to` | 54/57 | provenance present where page extraction existed |
| `client_id` | 0/57 usable | **required/missing** |
| `content_hash` | 57/57 | useful chunk checksum |
| document checksum | 0/57 | **required/missing** |
| `chunking_version` | 57/57 | present (`v1`) |
| `embedding_version` | 0/57 | **required/missing in legacy payload** |
| `source_type` | 57/57 | present |
| `content_source` | 57/57 | native/OCR/combined provenance |
| `filename`, `content_type` | 57/57 | present |
| `candidate_id` | 56/57 | legacy ownership hint; not client scope |
| `content` | 57/57 | present; not printed by this audit |

Current integer point IDs are `DocumentChunk.id`. They are stable for an
unchanged DB row, but they do not encode document checksum, client ownership,
embedding version, or chunking version. The proposed V2 identity fixes that.

## Current search consumers

| Consumer | Current behavior |
|---|---|
| Global Search | SQL/ILIKE structured and lexical search for all result domains, plus optional Qdrant document results for semantic-looking queries; Qdrant/Ollama fail open to SQL results. |
| Client Search | `ClientSearchMatchingService` and SQL only; no independent vector engine. |
| Client Knowledge | `SemanticSearchService` requests a Qdrant-side `client_id` filter, then combines evidence locally. With 0 scoped points, semantic coverage is currently unavailable. |
| Technical AI | Reuses Global Search and `SemanticSearchService`; it does not own another vector collection. |
| Agent | Reuses `GlobalSearchService`; semantic document evidence follows the same path. |
| Business Assistant | Reuses Global Search; no separate semantic index. |
| RAG service | Wraps the same canonical semantic service. |
| Knowledge Base | Separate `ai_lab_knowledge_base_chunks` collection and KB retrieval contract; not part of this customer-document benchmark. |

Global Search's current “hybrid” behavior merges SQL lexical and semantic
Document results by `(type, id)` and retains the stronger bounded score. The
benchmark mirrors this de-duplication behavior rather than introducing a new
production scorer.

## Current chunking audit

Canonical `DocumentChunkingService` V1 uses:

- maximum 1,800 characters;
- 250-character overlap for split long blocks;
- minimum useful chunk size of 80 characters;
- whitespace normalization and paragraph-first splitting;
- sentence/word-aware long-block boundaries;
- strict page boundaries when `DocumentPage` data exists;
- native text preference, OCR fallback, and combined native/OCR evidence when
  the texts materially differ;
- whole-document fallback only when no useful page text exists;
- empty text produces no chunk.

No production chunking was changed.

## Public-safe benchmark

The committed fixture contains 17 entirely synthetic Documents and 36 queries:

| Group | Queries | Purpose |
|---|---:|---|
| Exact lexical | Q01–Q08 | product/model, standard code, formula value, invoice reference, exact measurement |
| Semantic/paraphrase | Q09–Q20 | different wording, technical concepts, OCR noise, formula meaning, table lookup |
| Client-scoped | Q21–Q26 | two synthetic clients with deliberately similar Documents |
| Negative | Q27–Q31 | no relevant source should be returned |
| Ambiguous | Q32–Q36 | multiple deterministically relevant sources |

Ground truth is stored explicitly in
`backend/test/fixtures/chunk18_semantic_search_benchmark.json`; the embedding
model does not generate or judge relevance labels. The corpus includes a
technical datasheet, inspection reports, formulas, a synthetic invoice,
current and superseded standards, a manual, OCR-noisy evidence, a long
multi-page ventilation source, similar-but-different products and defects,
client-specific procedures, phone/e-mail distractors, a short source, and a
technical table.

### Isolation

- temporary Qdrant: pinned 1.18.3 on host port `16333`;
- collections: `ai_lab_test_chunk18_*` only;
- mutation guard: explicit non-production endpoint and `ai_lab_test_*` name;
- embedding model: `qwen3-embedding:0.6b`;
- observed dimension: exactly 1,024;
- production collections were never passed to the runner;
- every variant was upserted twice with deterministic IDs; point count did not
  grow.

### Chunking variants

| Variant | Max / overlap | Points | Embed seconds | Points/min |
|---|---:|---:|---:|---:|
| current V1 | 1,800 / 250 | 26 | 15.6892 | 99.43 |
| smaller | 900 / 150 | 27 | 13.2305 | 122.44 |
| larger | 3,000 / 300 | 25 | 13.9739 | 107.34 |
| current + overlap 450 | 1,800 / 450 | 26 | 14.0970 | 110.66 |

All four variants produced the same retrieval metrics. The bounded chunk-size
changes are therefore not the missing quality lever for this corpus.

### Quality at the canonical `0.60` score cutoff

Recall is macro-averaged over each query's explicit relevant set; MRR uses the
first relevant Document. Negative precision is the share of negative queries
returning no result.

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | Negative precision |
|---|---:|---:|---:|---:|---:|
| Lexical baseline | 0.274194 | 0.274194 | 0.274194 | 0.290323 | 1.00 |
| Semantic | 0.306452 | 0.306452 | 0.306452 | 0.322581 | 1.00 |
| Hybrid | 0.500000 | 0.500000 | 0.500000 | 0.516129 | 1.00 |

Client-scope leakage was `0` for every chunking variant because Qdrant applied
the `client_id` filter before ranking.

### Score-cutoff tradeoff (current V1)

| Cutoff | Hybrid Recall@1 | Recall@3 | Recall@5 | MRR | Negative precision |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.733871 | 0.795699 | 0.811828 | 0.838710 | 0.60 |
| 0.52 | 0.685484 | 0.741935 | 0.741935 | 0.758065 | 0.60 |
| 0.54 | 0.653226 | 0.669355 | 0.669355 | 0.709677 | 1.00 |
| 0.55 | 0.653226 | 0.669355 | 0.669355 | 0.709677 | 1.00 |
| 0.56 | 0.580645 | 0.580645 | 0.580645 | 0.612903 | 1.00 |
| 0.58 | 0.500000 | 0.500000 | 0.500000 | 0.516129 | 1.00 |
| 0.60 | 0.500000 | 0.500000 | 0.500000 | 0.516129 | 1.00 |

Relevant and irrelevant top scores overlap, so a global similarity cutoff
cannot fix the quality gap.

### Predeclared acceptance threshold

Backfill can be recommended only when all conditions hold:

1. hybrid Recall@3 at least `0.80`;
2. hybrid MRR exceeds lexical MRR by at least `0.10`;
3. hybrid Recall@1 does not regress lexical by more than `0.05`;
4. semantic and hybrid negative precision at least `0.80`;
5. client-scope leakage exactly `0`;
6. resource cost is operationally safe.

The current path fails conditions 1 and 4 depending on cutoff. The threshold
is **not met**.

## Resource results and production estimate

Query embedding for 36 inputs took `7.2107 s`. A repeated 20-input throughput
sample produced:

| Batch size | Seconds | Inputs/min |
|---:|---:|---:|
| 5 | 13.4138 | 89.46 |
| 10 | 12.3205 | 97.40 |
| 20 | 11.8674 | 101.12 |

Batch 20 improves throughput only about 3.8% over 10, so a future runner should
default to **10** for more recovery granularity and memory margin. Batch 20 can
remain an opt-in ceiling after a resource precheck.

Post-benchmark host/container observations:

- host free RAM: about 6,854 MiB of 26,422 MiB;
- host free virtual memory: about 7,172 MiB;
- Ollama: 4.348 GiB; canonical embedding model loaded;
- production Qdrant: 106 MiB;
- isolated Qdrant: 72.4 MiB;
- backend: 235.4 MiB;
- no unsafe swap-pressure behavior was observed.

For the 82 currently eligible production Documents, a read-only page-aware
size calculation found 279 text units and 567,783 source characters:

| Chunk design | Estimated points |
|---|---:|
| current 1,800/250 | about 513 |
| smaller 900/150 | about 902 |
| larger 3,000/300 | about 362 |

At batch 10, current V1 requires roughly 52 embedding calls and 5–8 minutes of
pure embedding time. A conservative operational window is 10–20 minutes after
checkpointing, Qdrant writes, verification, and bounded retry. Raw float32
vectors are about 2.0 MiB; a conservative vector + payload + index allowance
is 5–15 MiB. These estimates cover only today's 82 eligible Documents.

## Proposed V2 point contract

Each point must contain:

```text
source_type = document
document_id
client_id (non-null and validated)
page
chunk_index
document_checksum_sha256
chunk_checksum_sha256
embedding_model = qwen3-embedding:0.6b
embedding_version
chunking_version
content_source
filename
content_type
status = active
```

Point ID is deterministic UUIDv5 over:

```text
source_type=document | document_id | client_id | document checksum |
page | chunk index | chunk checksum | embedding version | chunking version
```

This provides exact ownership, idempotent unchanged re-index, and version
separation. A changed document checksum creates a new current ownership set;
the prior set becomes explicitly stale and is removable only by its exact
recorded point IDs/ownership. No fuzzy delete is permitted.

Client-specific search must place a mandatory Qdrant `client_id` filter in the
query before ranking. A Document without a valid active Client relationship is
ineligible for this customer-scoped collection; it must not be indexed with a
null/global scope or filtered after retrieval.

## Lifecycle and eligibility

Eligible:

- active, non-Trash and non-purged Document;
- `processing_status=processed`;
- validated non-null `client_id`;
- source checksum present;
- at least 80 useful characters from canonical page/native/OCR or document
  fallback text;
- supported extraction path;
- not an exact duplicate of the same document version/chunk.

Excluded:

- stored but unprocessed, failed, empty, unsupported, Trash, purged;
- missing/invalid Client ownership;
- ambiguous duplicate ownership;
- obsolete vector version during default retrieval.

Default retrieval includes only active/current vectors. Archive/Trash must
remove the exact owned point set. Restore or changed content requires bounded
reprocessing and a version-correct re-index; it never resurrects stale points
implicitly.

## Future backfill runner design (not executed)

1. **Preconditions:** owner gate, fresh verified Database checkpoint, official
   Qdrant snapshot with structural validation, green collections, unchanged
   production baseline, disk/RAM margin.
2. **Dry run:** read-only eligibility projection, reason-coded exclusions,
   point/count/storage estimate, ownership conflicts, no embedding/upsert.
3. **Checkpoint:** durable local ledger keyed by document ID, document checksum,
   chunking version, embedding version, and batch number.
4. **Batch:** default 10 Documents/chunk groups; validate client ownership again
   immediately before embedding and upsert.
5. **Idempotency:** deterministic point IDs; unchanged retries produce no
   additional point; package/ownership conflict fails closed.
6. **Retry:** maximum bounded attempts per exact document; no retry-all or
   historical auto-scan; record error codes without document content.
7. **Resume:** continue only incomplete ledger entries whose source checksums
   and Client ownership still match.
8. **Post-audit:** expected/actual points per Document, zero null-client points,
   exact payload coverage, no customer-scope leakage, unchanged KB collection,
   benchmark smoke and collection health.
9. **Rollback:** stop writes, verify exact run-owned IDs, request explicit
   destructive rollback approval if point deletion is required; snapshot restore
   remains a disaster-recovery path, not routine acceptance.

## Risk analysis and recommendation

| Risk | Current evidence | Control |
|---|---|---|
| Cross-client leakage | Legacy payload unusable; isolated scoped benchmark 0 leaks | Mandatory non-null payload and Qdrant pre-ranking filter |
| False positive semantic matches | Relevant/negative score overlap | Do not backfill yet; evaluate bounded reranker/query representation |
| Exact-query regression | Lexical remains strong and must stay first-class | Additive hybrid merge, never semantic-only replacement |
| Orphan/stale points | Legacy ownership lacks version binding | UUIDv5 ownership, checksums, versions, durable ledger |
| Test leak to production | Prior guard exists and passed | Explicit isolated endpoint + `ai_lab_test_*` only |
| Resource pressure | Batch 20 gives marginal gain | Default batch 10 and pre-batch health gate |

**Recommendation: `DO_NOT_RECOMMEND_BACKFILL`.** Preserve the 57-point
collection read-only and keep structured/lexical fail-open behavior. A later
design may benchmark a bounded reranker or canonical query representation, but
must reuse this corpus/ground truth and pass the same threshold before asking
for `FOLLOWUP_QDRANT_BACKFILL_APPROVAL_REQUIRED`.

## Safety record

- production customer Qdrant writes/deletes: `0 / 0`;
- production KB Qdrant writes/deletes: `0 / 0`;
- production collection/index/config changes: `0`;
- production DB writes/migrations: `0 / 0`;
- Gmail/n8n/Vision/Temporary Chat: `0 / 0 / 0 / 0`;
- advanced analysis remained enabled and unaffected;
- isolated benchmark collections and container were temporary and removed
  after verification.
