# FOLLOW-UP CHUNK 16 — Knowledge Base vector design

Status: **PRODUCTION ENABLED / BOUNDED ACCEPTANCE PASS — 2026-08-22**

Gate `FOLLOWUP_KNOWLEDGE_BASE_VECTOR_WRITE_APPROVAL_REQUIRED` was consumed for
the bounded production enablement described below.

## Boundary

Knowledge Base retrieval uses a separate Qdrant collection. It never writes to
`ai_lab_document_chunks`, and a Knowledge Base result never masquerades as a
customer Document result.

| Property | Value |
|---|---|
| Collection | `ai_lab_knowledge_base_chunks` |
| Source type | `knowledge_base` |
| Embedding model | current canonical `qwen3-embedding:0.6b` |
| Dimensions | `1024` |
| Distance | `Cosine` |

The lexical and future vector paths return the same semantic result contract:
`knowledge_base_item_id`, title, publisher, version, effective date, category,
current/superseded status, source file, page, excerpt and retrieval method.

## Payload and ownership

Required payload fields:

- `source_type = knowledge_base`
- `knowledge_base_item_id`
- `knowledge_base_page_id`
- `source_file`
- `page`
- `chunk_index`
- `status`
- `version`
- `category`
- `checksum_sha256`
- `embedding_model`
- `embedding_version`

Point IDs are deterministic UUIDv5 values derived from the immutable tuple
`knowledge_base_item_id:knowledge_base_page_id:chunk_index:checksum_sha256`.
The entire item is the deletion/re-index ownership boundary. Any mismatch in
`source_type` or item ownership fails closed.

## Lifecycle

- Create/process: delete no points; upsert the deterministic complete point set
  only after extraction is successful.
- Metadata edit: update bounded payload fields when text/checksum is unchanged.
- File replacement/retry: build the new deterministic set, verify it, then
  remove the prior set by exact `source_type + knowledge_base_item_id` filter.
- Supersession: retain points and set `status=superseded`; default retrieval
  filters to current while an explicit historical query may include both.
- Archive/delete: remove only points matching both explicit ownership fields.
- Re-index: deterministic point IDs prevent duplicates.
- Rollback: delete the new item-owned set and restore the previous verified set;
  the customer collection is never part of the operation.

## Production acceptance

Production collection `ai_lab_knowledge_base_chunks` is active and healthy at
1024/Cosine using `qwen3-embedding:0.6b`. Two versions of one locally generated,
public-safe formula fixture exercised the real Admin upload, durable processing,
local acceptance, source-only indexing, lexical/vector/hybrid retrieval,
current/superseded filtering, deterministic re-index and exact ownership
deletion. Both versions were archived through the canonical API. Final active
KB items and KB points are zero; retained archive/audit rows preserve the
acceptance history. Customer collection `ai_lab_document_chunks` remained
unchanged at 57 points.

## Isolated proof

An isolated Qdrant `1.18.3` container with a dedicated temporary named volume
and non-production port proved: 1024/Cosine collection creation, deterministic
upsert, retry without duplicate points (`2 -> 2`), `source_type` plus status
filtering, and exact item-owned deletion (`2 -> 1`). The temporary container
and volume were removed. Production collection and points were not touched.
