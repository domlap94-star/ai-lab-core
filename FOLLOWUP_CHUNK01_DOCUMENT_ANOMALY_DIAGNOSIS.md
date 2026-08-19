# FOLLOW-UP CHUNK 01 — Document Processing Anomaly Diagnosis

Audit date: 2026-08-19

Source HEAD: `1305a28dfc4a4bf3cc384419cc2956cecdb05525`

Release: `NEXT Stabil 1.0.2+21`

Database revision: `chunk16audit_20260819`

## Scope and safety

This was a read-only production diagnosis of Documents `1913` and `5626`.
Neither document was retried, reset, deleted, rewritten, or passed to Vision.
No migration, Qdrant write, n8n change, email action, or filesystem cleanup was
performed. Customer names and document contents were not inspected or recorded.

## Baseline

- backend and the aggregate production health check: `ok`,
- Documents / DocumentPages / DocumentAssets: `5915 / 271 / 10`,
- ungranted database locks: `0`,
- orphan Agent executions: `0`,
- Vision supervisor: `READY`, queue `0`, no active job,
- document processing statuses: `stored=5797`, `processed=116`,
  `extracting=1`, `failed=1`.

## Document 1913

### Evidence

- source type: `gmail_attachment`, PDF, 618,050 bytes,
- created: `2026-08-06T00:26:38.732641Z`, last status update:
  `2026-08-18T18:06:46.910560Z`,
- source file exists; size and SHA-256 match the database,
- PDF is readable, not encrypted, and contains 25 pages,
- metadata is already terminal `processed` and reports 25 pages,
- the page-render spool contains 25 PNG renders (3,795,107 bytes),
- the database contains 0 DocumentPages and 0 DocumentAssets,
- document processing status is `extracting` with no processing error,
- Vision is historical/ineligible: `vision_auto_eligible=false`,
  `vision_status=not_evaluated`.

### Root cause

`DocumentProcessingService.process_document()` commits `extracting` before
dispatching to the format-specific processor. `_process_pdf()` renders every
page to the filesystem before native-text extraction, OCR, page upserts, and
the final database commit. The complete render set combined with zero database
pages proves that processing was interrupted after render completion and before
the first page/result commit.

A normal Python `Exception` would be caught and would commit `failed` plus an
error. The surviving `extracting` state therefore indicates termination outside
that handler (for example a process/container stop, cancellation, or another
non-`Exception` interruption). Retained evidence cannot distinguish the exact
external stop event, so that narrower cause must not be asserted as fact.

The restart path does not scan historical extraction work. The only durable
scanner is the Vision dispatcher; it correctly ignores this record because
`vision_auto_eligible=false`. Thus the CHUNK 17 reboot did not and should not
implicitly retry Document 1913.

### Same-pattern search

With a stale threshold of 30 minutes, Document `1913` is the only
`processing_status=extracting` document. At audit time it was about 964 minutes
old, had no error, and had no database pages or assets.

## Document 5626

### Evidence

- source type: `gmail_attachment`, JPEG, 2,414,737 bytes,
- source file exists; size and SHA-256 match the database,
- database contains 0 DocumentPages and 0 DocumentAssets,
- status is `failed`; metadata stayed `pending` because the write rolled back,
- the exact PostgreSQL failure is `InvalidTextRepresentation`: invalid JSON
  token `NaN`, in GPS latitude EXIF metadata,
- the failing persistence fields were `documents.metadata_raw` and
  `documents.metadata_normalized`, both PostgreSQL `json` columns,
- Vision is historical/ineligible and was not involved.

### Root cause and current code state

The image metadata parser once allowed non-finite EXIF numeric values to reach
the JSON persistence boundary. Psycopg serialized the Python structure with
`NaN`; PostgreSQL JSON correctly rejected it. The transaction rollback explains
why metadata columns remained empty while `processing_error` preserved the
database error.

Commit `f676b12439c734afb91d2c1af0de3c725a22c70f` added finite-number checks to
`DocumentMetadataService._json_safe()`, mapping non-finite values to `None`.
A read-only extraction against the unchanged Document 5626 source now returns
`processed`, produces dictionaries, contains zero non-finite values, and passes
strict `json.dumps(..., allow_nan=False)`. The known parser defect is therefore
already fixed in current source. The failed historical row was never retried.

The row was updated after the source commit. The most plausible explanation is
that the already-running backend still had the pre-fix module loaded; source is
bind-mounted but imported Python code is not replaced without process reload.
Historical runtime provenance is insufficient to prove this, so it remains a
qualified inference.

### Same-pattern search

Document `5626` is the only failed document and the only processing error
matching JSON/`NaN` signatures.

## Systemic findings

### State transition and atomicity

Processing is not a single database/filesystem transaction:

1. metadata is committed separately,
2. `extracting` is committed before format work,
3. PDF renders are filesystem side effects created before page rows,
4. page results are committed at the format processor's terminal boundary,
5. asset extraction may commit individual assets.

Normal exceptions roll back pending database work and finalize the document as
`failed`, but filesystem renders remain. Abrupt termination can leave
`extracting`. This is a resumable design, not full atomicity.

### Idempotency

Non-force PDF retry reuses valid render files and upserts pages under the unique
`(document_id, page_number)` contract. Asset extraction checks document plus
checksum before insertion. This substantially bounds duplicate risk. A
`force=True` retry deletes page state and render artifacts and is therefore not
appropriate as the default remediation.

### Remaining hardening gap

The current health aggregate detects stale Vision work but not stale document
extraction. The metadata extractors sanitize the known JSON inputs, but the
persistence boundary still trusts `DocumentMetadataResult` rather than applying
one final strict type/finite-number validation. These are future-system
hardening opportunities; neither justifies changing production data during this
diagnostic step.

## Safe remediation design

No schema migration is required for these two records.

After explicit approval, use the normal single-document, non-force processing
service for each ID, only after rechecking source existence, size, and checksum:

- `1913`: reuse the 25 valid renders, finish extraction/OCR and idempotent page
  upserts, then reach `processed`, `partial`, or a truthful `failed` state;
- `5626`: run the current finite-number sanitizer, persist valid JSON metadata,
  process the image page, and reach a truthful terminal state.

Do not use direct SQL status resets, `force=True`, bulk retry, or historical
scans. Capture before/after projections and result logs by ID. Existing
processing contains intermediate commits, so exact transactional rollback is
not available; the safe recovery model is checksum-gated, idempotent forward
processing. On failure, preserve its new truthful `failed` state and evidence
rather than restoring stale status.

Recommended later source-hardening work, separate from record remediation:

- add a read-only stale-document detector to private/admin health,
- add an authenticated, audited, single-document non-force retry operation,
- strictly validate normalized JSON immediately before persistence,
- test interruption after `extracting`, malformed parser output, and a second
  idempotent attempt with no duplicate pages/assets,
- do not add automatic historical retry.

## Test evidence and proposed regression plan

Completed read-only checks:

- live production health and sanitized SQL projections: pass,
- original file existence, byte size, and SHA-256 checks: pass for both IDs,
- PDF structure/render reconstruction for `1913`: pass,
- current metadata extraction and strict JSON serialization for `5626`: pass,
- same-pattern database searches: complete.

The legacy `backend/test/test_heic_nan_metadata_fix.py` was intentionally not
run: it invokes `force=True` against fixed production document IDs and is an
operational mutation script, not an isolated unit test.

Before any future systemic implementation, add isolated tests for:

1. interruption immediately after entering `extracting`,
2. parser output containing `NaN` or a non-dict JSON root,
3. failure finalization without malformed JSON reaching PostgreSQL,
4. a second non-force attempt producing no duplicate pages or assets.

## Gate

Both documents still require a production processing write to become healthy.
The required token is:

`FOLLOWUP_DOCUMENT_REMEDIATION_APPROVAL_REQUIRED`
