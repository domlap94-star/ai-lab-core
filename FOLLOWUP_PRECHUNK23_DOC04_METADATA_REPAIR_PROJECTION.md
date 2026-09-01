# PRE-CHUNK23 DOC-04 metadata repair projection

Date: 2026-09-01

Blocker: `DOC-04` (`P1`)

Disposition: read-only projection; separate owner approval is required for any repair

## 1. Baseline and authority

- Canonical main: `aa4cb4dcadc2710870c9010fe72b2e8d350eab2d`.
- Audit branch parent: `b1dee3d0afff1aefb5235176502cf0256fe975ce`.
- Production database: `ai_lab`.
- Production Alembic head: `followup_assistant_chat_history_20260829`.
- Target row: Document ID `8903`.
- The canonical roadmap keeps DOC-04 `OPEN`; this step is only the read-only projection. A verified backup and separate owner approval remain mandatory before repair.

No customer metadata, filename, storage path, client identity, email identifier, document text, OCR, or file content is present in this report.

## 2. Production read-only fence

The bounded SQL inspection used a raw `psycopg` connection before any ORM load and established:

| Fence | Observed |
|---|---|
| `current_database()` | `ai_lab` |
| transaction mode | `REPEATABLE READ READ ONLY` |
| `transaction_read_only` | `on` |
| termination | explicit `ROLLBACK` |
| production `UPDATE/INSERT/DELETE` | `0/0/0` |
| write locks | `0` |
| temporary tables | `0` |
| advisory locks | `0` |

The later ORM/public-projection probe used a separate `REPEATABLE READ READ ONLY` transaction against `ai_lab`, verified `transaction_read_only=on`, suppressed serialized output, and ended with rollback.

## 3. Safe row snapshot

| Field | Safe value |
|---|---|
| ID | `8903` |
| source type | `gmail_attachment` |
| content type | `application/pdf` |
| processing status | `processed` |
| metadata status | `processed` |
| match status | `confirmed` |
| created at | `2026-08-26T10:32:29.850666+00:00` |
| updated at | `2026-08-28T07:45:15.227895+00:00` |
| metadata extracted at | `2026-08-26T10:33:38.172847+00:00` |
| file size | `1,569,764` bytes |
| checksum present | `YES` |
| `metadata_raw` | non-null object |
| `metadata_normalized` | non-null object |
| snapshot `xmin` | `144314` (diagnostic evidence only; must be freshly re-read for any future repair) |

## 4. Exact surrogate diagnosis

Both PostgreSQL columns are of type `JSON`, not `JSONB`. The diagnostic parsed their exact `::text` forms only in process memory. It distinguished valid high/low pairs from isolated high and low units.

| Column | UTF-8 bytes | exact before SHA-256 | raw `\\uXXXX` escapes | high units | low units | valid pairs | unpaired high | unpaired low |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `metadata_raw` | 362 | `c005357d385df268407ca49ecbea6e78e1d1620d4dbbb7cf462f3c051b649aea` | 2 | 0 | 2 | 0 | 0 | 2 |
| `metadata_normalized` | 325 | `b77df8ec47441c963a4812843a768f814ea3ba01e30f3bc627c314f663761420` | 2 | 0 | 2 | 0 | 0 | 2 |

The two invalid units in each representation are `U+DCC0` and `U+DC80`. They are adjacent isolated low surrogates, not a valid pair. The earlier shorthand description of a single lone low-surrogate escape was therefore incomplete; the bounded current snapshot establishes two invalid escapes in each of the two representations.

### 4.1 Safe structural locations

The dynamic key is not disclosed. Every dynamic path segment is represented by a deterministic hash prefix.

| Column | Path | Depth | Value type | Value code-point length | Invalid code point | Ordinal | Adjacent valid pair |
|---|---|---:|---|---:|---|---:|---|
| `metadata_raw` | `key_sha256:d1990f97a1f4fe7b` | 1 | string value | 26 | `U+DCC0` | 24 | `NO` |
| `metadata_raw` | `key_sha256:d1990f97a1f4fe7b` | 1 | string value | 26 | `U+DC80` | 25 | `NO` |
| `metadata_normalized` | `key_sha256:d1990f97a1f4fe7b` | 1 | string value | 26 | `U+DCC0` | 24 | `NO` |
| `metadata_normalized` | `key_sha256:d1990f97a1f4fe7b` | 1 | string value | 26 | `U+DC80` | 25 | `NO` |

Structural path-set fingerprints:

- `metadata_raw`: `556e54130188db5dce277a5e218d102f56af861bb3400d06b8625314a19aa8f4`.
- `metadata_normalized`: `bf6c8821e85b97684f01db02f0a790a77ca7c3975174806864375c5c07f718c5`.

### 4.2 Raw lexical offsets

Offsets are zero-based against the exact PostgreSQL `::text` representation. No surrounding value is reproduced.

| Column | Offset | Length | Class | Code point |
|---|---:|---:|---|---|
| `metadata_raw` | 155 | 6 | unpaired low | `U+DCC0` |
| `metadata_raw` | 161 | 6 | unpaired low | `U+DC80` |
| `metadata_normalized` | 159 | 6 | unpaired low | `U+DCC0` |
| `metadata_normalized` | 165 | 6 | unpaired low | `U+DC80` |

## 5. Bounded failure reproduction

Every SQL expression ran independently under a savepoint in the read-only transaction. Only stable classifications are recorded.

| Column | Expression | Result | SQLSTATE | Exception class/category |
|---|---|---|---|---|
| `metadata_raw` | cast to `jsonb` | FAIL | `22P02` | `InvalidTextRepresentation` / bounded database expression failure |
| `metadata_raw` | `json_typeof` | PASS | none | none |
| `metadata_raw` | harmless JSON operator | FAIL | `22P02` | `InvalidTextRepresentation` / bounded database expression failure |
| `metadata_normalized` | cast to `jsonb` | FAIL | `22P02` | `InvalidTextRepresentation` / bounded database expression failure |
| `metadata_normalized` | `json_typeof` | PASS | none | none |
| `metadata_normalized` | harmless JSON operator | FAIL | `22P02` | `InvalidTextRepresentation` / bounded database expression failure |
| whole-row ORM load | read-only probe | PASS | none | no output emitted |
| public Pydantic projection | suppressed serialization | PASS | none | no output emitted |

`json_typeof` can inspect the outer `JSON` form without forcing the invalid string into PostgreSQL's stricter `jsonb` Unicode representation. That PASS does not make the stored value operator-safe.

## 6. Table-wide bounded scope

- Documents scanned: `5,989`.
- Non-null metadata values scanned: `386`.
- Python JSON parse failures: `0`.
- Affected document count: `1`.
- Affected document IDs: `8903` only.
- Affected values: `metadata_raw` and `metadata_normalized` for ID `8903` only.
- Other documents with an unpaired high or low surrogate: `0`.

Classification: **single-row scope**, with two affected columns in that row.

## 7. Source and relation integrity

| Check | Result |
|---|---|
| storage path confined to the trusted data root | PASS |
| source file exists | PASS |
| recorded size equals actual size | PASS (`1,569,764` bytes) |
| recorded SHA-256 equals actual file SHA-256 | PASS |
| active/trash/purge | active; not trashed; not purged |
| parent documents | 0 |
| child documents | 0 |
| pages | 28 |
| assets | 0 |
| chunks | 0 |
| preparation jobs | 1 (`ready`) |
| intelligence artifacts | 0 |

The source-integrity gate passes. No source bytes were exposed or processed beyond a read-only size/SHA-256 comparison.

## 8. Source-code ownership and recurrence analysis

The audit used current-main source at `aa4cb4dcadc2710870c9010fe72b2e8d350eab2d`.

### 8.1 Canonical writers and consumers

- `DocumentMetadataService.extract()` is the canonical metadata extractor. For PDF input it uses `fitz`/PyMuPDF (`PyMuPDF==1.26.3`) and returns both raw and normalized dictionaries.
- Extractor identity for this projection is the current-main `backend/app/services/document_metadata_service.py` blob `82a128710e8d29069615faac22dda4d8dcfb440b`.
- `DocumentProcessingService._process_metadata()` calls the extractor, preserves any intake subobject, assigns all five metadata fields, and commits. Its source blob is `fc698b6d4b9e32b54998e79385d9b841491552c6`.
- `DocumentRepository.update_metadata()` is a metadata-only repository helper, but no production application call site currently invokes it; a test call exists.
- `DocumentService.store_document()` can seed `metadata_raw` with intake metadata.
- Archive import initializes metadata fields to pending/null. Trash purge clears raw/normalized/error metadata as part of destructive lifecycle handling.
- `GlobalSearchService` casts `metadata_normalized` to text for matching. Document processing/resolution can also consume loaded metadata.
- Public `DocumentRead` and `DocumentPublicRead` schemas do not expose `metadata_raw` or `metadata_normalized`. The suppressed public serialization probe passed. Thus the current public document response does not directly serialize the affected payload.

### 8.2 Recurrence gap

Current source does **not** prevent recurrence:

- `_json_safe()` returns every Python `str` unchanged.
- `_clean()` strips a string but does not validate or replace unpaired surrogate units.
- Dynamic dictionary keys are converted with `str(key)` without surrogate validation.
- The intake metadata path can also reach `metadata_raw` without a shared strict surrogate boundary.
- PostgreSQL `JSON` accepts the escaped units that later fail under `jsonb` conversion/operators.

The defect is therefore compatible with the current validation boundary; its precise historical creation point cannot be proven from the row alone.

### 8.3 Future hardening requirement (not implemented here)

A later source task should establish one shared metadata persistence boundary that:

1. detects isolated high and low surrogates in every string value and dynamic key;
2. preserves valid surrogate pairs and all other Unicode;
3. applies deterministically to extractor output and intake metadata;
4. either replaces invalid units with the documented `U+FFFD` policy or fails closed with a bounded error before commit;
5. proves round-trip compatibility with PostgreSQL `jsonb` operators;
6. adds focused tests for isolated high, isolated low, adjacent invalid lows, valid pairs, dynamic keys, and ordinary non-ASCII text;
7. keeps customer values out of exceptions and logs.

No source hardening was implemented in DOC-04.

## 9. Candidate strategies

### 9.1 Strategy A — deterministic re-extraction

| Gate | Assessment |
|---|---|
| source file present and checksum-current | YES |
| canonical extractor identifiable | YES: current-main `DocumentMetadataService`, PyMuPDF 1.26.3 |
| current extractor prevents the same invalid output | NO |
| exact output guaranteed deterministic and bounded | NO; external library metadata decoding can reproduce the same units |
| metadata-only production orchestration | NO canonical application path is currently used |
| unrelated state guaranteed unchanged | NO; `process_document()` can continue into page/render/text/asset/processing-state work |
| isolated clone rehearsal possible | YES, but it would not close the current sanitizer gap |
| eligibility as the DOC-04 repair | **NO** |
| risk | HIGH for a supposedly one-row/two-column correction |

Re-extraction is not selected. It requires customer file processing, can touch state outside metadata, and the current string sanitizer does not guarantee that the defect disappears.

### 9.2 Strategy B — minimal lexical surrogate repair

The in-memory JSON-string-aware scanner replaced only each isolated invalid `\\uXXXX` escape with `\\uFFFD`. It did not use a global regex. Valid pairs were preserved; keys, ordering, whitespace, numbers, booleans, nulls, and every unaffected lexical region remained byte-identical.

| Column | Replacements | Before bytes | After bytes | Before SHA-256 | Candidate after SHA-256 |
|---|---:|---:|---:|---|---|
| `metadata_raw` | 2 | 362 | 362 | `c005357d385df268407ca49ecbea6e78e1d1620d4dbbb7cf462f3c051b649aea` | `678d488f7380404fce8d0e8454af723b7d4efaf89a502a4d62c6a8db102642ef` |
| `metadata_normalized` | 2 | 325 | 325 | `b77df8ec47441c963a4812843a768f814ea3ba01e30f3bc627c314f663761420` | `c716b9d801e271a385b05c188b64518698ef5c264035d0261a7a4e838ad7136c` |

Changed spans are exactly the four entries in section 4.2; every six-byte escape remains six bytes after replacement.

Candidate validation results for both columns:

- Python JSON parse: PASS.
- Ephemeral isolated PostgreSQL `jsonb` cast: PASS; top-level type `object`.
- Remaining unpaired surrogates: 0.
- Top-level type unchanged: PASS.
- Object/array node cardinalities unchanged: PASS.
- Dynamic path set/fingerprint unchanged: PASS.
- Only affected decoded surrogate code points changed: PASS.
- All unaffected raw lexical regions identical: PASS by span-based construction.

The isolated database was named specifically for DOC-04, accepted no production data other than the two in-memory candidate parameters, ran the validation in `REPEATABLE READ READ ONLY`, rolled back, and was removed after the test.

### 9.3 Selected future strategy

**Minimal lexical surrogate repair** is selected for owner review. It is the smallest repair that is deterministic, rehearsable, limited to the two proven columns, and independent of wider document processing. It is not authorized for execution by this report.

## 10. Future owner-gated production transaction

The future repair must stop on any gate mismatch:

1. Recheck exact approved main SHA and exact production DB head.
2. Prove zero active backup and restore operations for the repair window.
3. Create and verify a fresh physical backup.
4. In a serializable or equivalent safely locked transaction, identify `current_database()='ai_lab'`.
5. Lock only Document `8903` with `SELECT ... FOR UPDATE`.
6. Re-read only safe scalars plus `metadata_raw::text`, `metadata_normalized::text`, `xmin::text`, and `updated_at`.
7. Recompute and require the exact two before hashes above, the expected non-null shape, fresh storage checksum match, and fresh concurrency tokens.
8. Re-run the table-wide read-only scope check and require exactly one affected document.
9. Generate the candidates in memory with the reviewed JSON-string-aware scanner and require the exact candidate hashes above.
10. Execute one parameterized update touching only `metadata_raw` and `metadata_normalized`.
11. Require exactly one returned/affected row; otherwise roll back.
12. Validate JSON operators, ORM load, zero unpaired surrogates, after hashes, file checksum, and unchanged relation counts before commit.
13. Commit only if every invariant passes; otherwise roll back.
14. Emit a customer-content-free one-row audit report. Do not retry preparation and do not invoke models, OCR, Vision, Visual, or Assistant.

Illustrative parameterized shape only; no payload is embedded:

```sql
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

SELECT id, xmin::text, updated_at,
       metadata_raw IS NULL, metadata_normalized IS NULL,
       metadata_raw::text, metadata_normalized::text
FROM documents
WHERE id = :document_id
FOR UPDATE;

-- The repair process verifies exact before SHA-256 values, current storage
-- checksum, expected non-null shape, updated_at and xmin before this statement.
UPDATE documents
SET metadata_raw = CAST(:candidate_raw_text AS json),
    metadata_normalized = CAST(:candidate_normalized_text AS json)
WHERE id = :document_id
  AND xmin::text = :expected_xmin
  AND updated_at = :expected_updated_at
  AND metadata_raw IS NOT NULL
  AND metadata_normalized IS NOT NULL
  AND metadata_raw::text = :expected_raw_text
  AND metadata_normalized::text = :expected_normalized_text
RETURNING id, xmin::text;

-- Require exactly one row, run all post-write checks, then COMMIT.
-- Any mismatch or failed check => ROLLBACK.
```

At execution time the parameter values must live only in protected process memory. Before mutation, create an exact encrypted/local one-row before package tied to the verified physical backup. Never print it, place it in chat, or commit it to Git. Rollback is transaction rollback until commit; after commit, recovery must use the verified backup/before package through a separately reviewed owner-approved procedure.

## 11. Isolated rehearsal matrix

| Rehearsal | Required result |
|---|---|
| isolated low-surrogate synthetic fixture | one bounded replacement per isolated unit |
| isolated high-surrogate synthetic fixture | one bounded replacement per isolated unit |
| two adjacent invalid low surrogates | two replacements; no pairing misclassification |
| valid high+low pair | preserved byte-for-byte |
| ordinary non-surrogate Unicode | preserved byte-for-byte |
| keys, arrays, nesting, numbers, booleans, nulls | structure and unaffected lexemes unchanged |
| Python parse and PostgreSQL `json`/`jsonb` behavior | repaired value accepted; original failure reproduced safely |
| exact candidate hashes | match the approved values in section 9.2 |
| compare-and-swap conflict | zero-row result and rollback |
| concurrent `updated_at` or `xmin` change | refusal and rollback |
| wrong before hash | refusal and rollback |
| zero-row target | refusal and rollback |
| intentionally broadened predicate/two-row outcome | refusal and rollback |
| post-update validation failure | rollback restores isolated database exactly |
| second repair run | no-op/idempotent refusal because before hash no longer matches |
| evidence output | IDs, counts, hashes, code points, statuses only |

A production-shape isolated clone rehearsal is required before real repair. It must use synthetic metadata of the same structural/surrogate class, the exact future repair executable and transaction logic, and the same PostgreSQL major/type behavior. It must not copy customer metadata into a test fixture or report.

## 12. Decision and safety

Every readiness condition for a single-row proposal is complete:

- exact scope check: complete, one affected document;
- exact before hashes: complete;
- exact deterministic candidate hashes: complete;
- candidate PostgreSQL `jsonb` validation: PASS;
- source size/checksum integrity: PASS;
- concurrency evidence captured for planning but explicitly requires fresh recheck;
- future backup/owner/transaction gates specified;
- no customer payload exposed.

**NO REPAIR WAS EXECUTED.**

Production safety:

- transaction mode: READ ONLY;
- production writes: 0;
- production Document changes: 0;
- production metadata changes: 0;
- production preparation-job changes: 0;
- production files processed: 0;
- model calls: 0;
- Vision/Visual jobs: 0;
- Temporary Chat calls: 0;
- Supervisor jobs: 0;
- migrations: 0;
- service restarts: 0;
- backup operations: 0;
- Gmail/Qdrant mutations: 0;
- roadmap updated: NO;
- main changed: NO;
- APK builds: 0;
- CHUNK23: NOT STARTED.

`DOC04_SINGLE_ROW_REPAIR_PLAN_READY_FOR_OWNER_REVIEW`
