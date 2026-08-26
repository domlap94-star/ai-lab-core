# P0 canonical file preparation and Assistant auto-resume

Date: 2026-08-26

Source baseline: `26e2b8e6a6b06df36dc9a8364a804f13eb607474`

Stable: `NEXT Stabil 1.0.2+29`

Decision: `FOLLOWUP_ASSISTANT_FILE_PIPELINE_SCHEMA_APPROVAL_REQUIRED`

## Outcome

The source and live read-only audit proves that the requested durable
preparation/auto-resume contract cannot be implemented safely on the current
schema. Knowledge Base has its own durable `knowledge_base_processing_jobs`,
but ordinary Documents have only state columns on `documents`; there is no
document preparation job/generation/lease ledger. `analysis_jobs` has neither
the original bounded Unified Assistant request/result nor a relationship to a
preparation job. Reusing `quality_signals` for those payloads would corrupt its
meaning and would not provide a safe contract.

An exact additive migration was prepared and proved on an isolated database:

- revision: `followup_assistant_file_pipeline_20260826`;
- parent: `followup_backup_planner_retention_20260824`;
- upgrade: PASS;
- downgrade: PASS;
- re-upgrade: PASS;
- historical Document job backfill: `0`;
- Assistant payload backfill: `0`;
- production apply: **NOT PERFORMED**.

No runtime worker, ingestion trigger, Assistant wait/auto-resume API, Flutter
polling UI or production single-document processing was enabled. This avoids
deploying code that assumes tables absent at the production head.

## Complete source ingress inventory

All analyzable non-KB bytes converge on `Document`/`DocumentService`, while
domain ownership remains represented by `client_id`, `candidate_id`,
`project_id`, `inspection_id`, Gmail identifiers, intake metadata, and
`work_item_documents`. Knowledge Base intentionally remains separate.

| Ingress | Domain | API/route or creator | Storage owner / canonical ID | Current trigger | Extraction / OCR / Vision / analysis / indexing | Provenance | Retry | Current gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Documents workspace upload | Document | `POST /api/v1/documents/user-upload` | `Document.id`, `/data/documents/*` | `vision_auto_eligible` row scanned by Vision dispatcher | `DocumentProcessingService`; OCR/render; Vision classifier; no guaranteed customer vector write | intake origin/user and optional Client/Project/Inspection | explicit Vision plus state retry | PARTIAL: no preparation job/generation/lease |
| Client upload | Client/Document | `POST /api/v1/clients/{id}/documents/upload` and workspace dialog with `client_id` | `Document.id` | same | same | exact `client_id` | same | PARTIAL |
| Candidate/import upload | Candidate/Document | import-key `POST /api/v1/documents/upload` with `candidate_id`; Gmail reconciliation | `Document.id` | same for new rows | same | candidate/Gmail external IDs | same | PARTIAL; no separate Candidate file table exists |
| Incoming Mail attachment | Mail/Candidate/Document | `MailReconciliationService._ingest_attachments()` | `Document.id`, source `gmail_attachment` | same; subsequent email matching waits on processing status | extraction/OCR/Vision; attachment reconciliation | Gmail message/thread and Candidate/Client binding | dispatcher retry states | PARTIAL; mail commit and preparation lack one durable job contract |
| Manually sent Mail attachment | Mail send | existing `Document` IDs are attached; no new byte-ingress path | existing `Document.id` | not applicable | reuses existing prepared state | send ledger/document relation | not applicable | No new file is created |
| Task attachment | Work item/Document | `POST /api/v1/work-items/{id}/documents/upload` | `Document.id` + `work_item_documents` | same after outer transaction commit | same | work item, optional note, Client/Project | same | PARTIAL |
| Note attachment | Work item note/Document | same route with `note_id` | same | same | same | exact note/work item relationship | same | PARTIAL |
| Realization/Project attachment | Project/Document | workspace upload with `project_id`; realization work item can bind the same Project | `Document.id` | same | same | exact Project and inherited Client | same | PARTIAL; no separate byte store |
| Visit/Inspection/local-vision file | Inspection/Document | workspace/Inspection upload with `inspection_id` | `Document.id` | same | documents use extraction/OCR; photos use controlled Vision | exact Inspection/Project/Client and capture metadata | same | PARTIAL |
| Camera/gallery photo or video | Document plus owning domain | user/work-item upload with `camera_photo` or `camera_video` | `Document.id` | same | images are OCR/Vision eligible; video has no validated preparation parser | capture/domain provenance | same | PARTIAL; video is unsupported for AI preparation and needs truthful state |
| Archive child | Derived Document | bounded `DocumentArchiveImportService` | child `Document.id`, parent/archive member provenance | child is `stored` and Vision eligible | child routed by its detected filename MIME | parent and member path | same | PARTIAL; only ZIP has an existing bounded policy |
| Knowledge Base upload | Knowledge Base | `POST /api/v1/admin/knowledge-base` | `KnowledgeBaseItem.id`, separate storage | durable job in same transaction | extraction/OCR, local analysis, KB indexing | KB item/page/artifact | exact item retry | YES — durable; remains separate CHUNK16 adapter |
| Internal Document assets/renders | Derived evidence | processors only, not user ingress | `DocumentAsset` / `DocumentPage` | processor-owned | OCR/Vision as designed | parent Document/page | processor retry | Not an independent business ingress |

Actual byte creators under `backend/app` are limited to `DocumentService`,
Knowledge Base storage, bounded ZIP member import, derived asset extraction and
the Vision spool copy. No independent Client/Candidate/Project/Inspection file
store was found. Project, Inspection and workspace UI all use the shared
Document intake dialog. Tasks/notes use a dedicated API adapter but still
store a canonical Document.

### Current automatic-preparation classification

- Knowledge Base: `YES — durable`.
- New Document-backed uploads with Vision automation enabled: `PARTIAL` — the
  persisted Document row is discoverable and the dispatcher is asynchronous,
  but there is no independently claimable job, checksum generation, priority,
  lease, bounded stage history or durable Assistant consumer.
- Existing/historical documents: `NO` by design; no bulk scan is authorized.
- Outgoing Mail attachments: no new file is created.

Production read-only evidence at audit time:

- DB head: `followup_backup_planner_retention_20260824`;
- Vision automation: enabled;
- KB processing: enabled;
- active Documents: `processed=139`, `stored=5795`;
- historical `stored` rows are overwhelmingly `vision_auto_eligible=false`;
- KB jobs: `completed=5`;
- `document_preparation_jobs`: absent;
- Assistant wait table/relationship: absent.

No historical row was changed or queued.

## Existing processing engines

The implementation must compose, not replace, these services:

- `DocumentProcessingService`: canonical Document metadata, extraction,
  rendering, OCR, page and asset preparation;
- `DocumentExtractionService`: PDF, DOCX, ODT, XLSX, PPTX, RTF, TXT/CSV/TSV,
  RFC822 and image-to-OCR classification;
- `UnifiedDocumentContentService`: read-only READY evidence access and
  checksum-gated ephemeral native fallback;
- `VisionDispatcher` / `VisionProcessingService`: controlled image/page Vision;
- `KnowledgeBaseService` / dispatcher: separate durable KB pipeline;
- `DocumentArchiveService`: bounded ZIP extraction with member/path/size/ratio
  guards;
- `EmailAttachmentReconciliationService`: post-preparation mail ownership
  matching, not a file processor;
- `AnalysisJob`: durable local/Advanced reasoning lifecycle, extended by the
  proposed migration rather than replaced.

There are currently two preparation mechanisms: durable KB jobs and a
Document-state/vision dispatcher. The approved implementation should add one
durable Document preparation adapter, not a fourth extraction engine.

## Normalized preparation contract

The proposed `document_preparation_jobs` projects the owner-required stages:

`received`, `validating`, `queued`, `extracting`, `rendering`, `ocr_required`,
`ocr_processing`, `vision_processing`, `local_analysis`, `indexing`,
`ready_for_ai`, `failed`, `unsupported`, `integrity_failed`, `cancelled`.

Terminal job status is separately bounded to `ready`, `failed`, `unsupported`,
`integrity_failed`, or `cancelled`. `READY_FOR_AI` is a computed guarantee over
the authoritative checksum plus usable page/text/OCR or validated visual
evidence and provenance. Customer vector indexing is not required for READY;
direct/page text remains valid and no CHUNK18 backfill is introduced.

The idempotency key is exactly:

`document_id + input_checksum + processor_generation`.

One row owns retries and attempts for that generation. A changed checksum
requires a new generation. The queue has explicit `P0..P3` priority, lease
expiry, bounded attempts, retryability and safe error code. Startup recovery
may reclaim only an expired lease and must revalidate checksum and ownership.

## Transaction and future-ingress design

For every Document-backed ingress, the file row/business relationship and its
`ingestion` preparation job must be inserted in the same DB transaction after
the file is safely stored. The API returns after commit. The worker owns a new
short-lived DB session and never inherits the request session. Existing
`commit=False` work-item upload remains compatible: both the relation and job
commit together or the newly written file is removed by its existing rollback
path.

The worker composes current processors. It must not hold Qwen while extracting,
rendering, OCR or Vision. Suggested bounded initial concurrency is two native
extractors and one heavy OCR/Vision slot, with the existing model/browser
arbiter respected. Priority order is user-waiting on-demand, interactive new
upload, incoming mail/background, then maintenance; fair aging must prevent
starvation. Queue saturation never rolls back Mail ingestion and projects
`queued` truthfully.

## File safety and format audit

Current native support is broader than the UI implies:

- PDF: native `pypdf`, bounded 250-page render/OCR fallback;
- DOCX: `python-docx`; DOC: existing bounded legacy service;
- XLSX: `openpyxl` plus existing asset/page preparation; XLS: legacy service;
- TXT/CSV/TSV: native text/CSV readers;
- ODT/PPTX/RTF/RFC822: existing native parsers;
- JPG/JPEG/PNG/BMP/TIFF/HEIC/HEIF/WebP: OCR/Vision preparation;
- ZIP: only the existing explicit bounded archive importer (500 members,
  250 MiB/member, 2 GiB total, ratio 500, nesting depth 5);
- RAR/7Z and video/unknown binary: unsupported for preparation;
- EXE/MSI/BAT/CMD/PS1/JS/DLL/APK and encrypted/unknown archives: never
  executed or automatically unpacked.

The general Document intake currently normalizes a declared MIME but does not
perform a full extension/MIME/magic match before storage. KB validates
extension/MIME but not a complete signature set. The implementation after the
schema gate must add one bounded signature classifier before parser routing:
PDF header, ZIP-container subtype for DOCX/XLSX/PPTX, common image signatures,
text safety checks and explicit executable/container rejection. Mismatch is
`INTEGRITY_FAILED`/`UNSUPPORTED_FORMAT` with Polish conversion/re-upload
guidance; no arbitrary codec or system parser is installed.

## Assistant wait and exact auto-resume design

The migration extends existing `analysis_jobs` additively with:

- validated `attempt_id`;
- bounded local-only `request_payload` (question, permitted conversation and
  target IDs; never tokens/secrets);
- `result_payload` for returning a completed answer after app close;
- FK to the exact `document_preparation_jobs` row;
- monotonic `resume_generation`;
- progress/cancel timestamps.

It adds states `document_preparation_queued`,
`document_preparation_running`, and `resume_queued` to the existing fail-closed
status contract and active-fingerprint uniqueness.

Initial ask flow after approval:

1. resolve the exact in-scope Document without Qwen;
2. compute READY from canonical evidence;
3. if not ready, create/get the exact preparation generation and persist an
   `AnalysisJob` consumer in one transaction;
4. return bounded status immediately;
5. worker prepares the file without generator residency;
6. resume dispatcher locks the waiting job, rechecks user authorization,
   target ownership, Document identity/checksum and generation;
7. increment generation and run reasoning once;
8. persist the bounded response and terminal state;
9. polling/reopen returns that response.

Cancellation stops the Assistant consumer and stale UI binding. It does not
cancel a shared canonical preparation job merely because one consumer leaves.
A late result may only bind to the same request ID, attempt ID, preparation
job, checksum and resume generation.

## Why approval is required now

Without the migration there is no safe place for:

- exactly one preparation job per file/checksum/generation;
- a durable queue lease, priority, attempt and stale recovery;
- multiple Assistant consumers of one shared preparation job;
- the original bounded request and completed response across app close;
- exact request/attempt/preparation/resume binding.

An in-memory queue or `BackgroundTasks` would be lost on restart. Encoding the
request into `quality_signals` would violate existing semantics and privacy
review. Keeping a multi-minute HTTP request open violates the product
decision. Therefore runtime implementation is correctly blocked on schema
approval.

## Migration proof and rollback

Migration file:
`backend/alembic/versions/followup_assistant_file_pipeline_20260826.py`.

The isolated test creates no data, checks the table, columns, queue indexes and
generation uniqueness, downgrades to the production parent, verifies exact
removal, and re-upgrades. Both disposable isolated databases used during proof
were removed. Production remains at the parent revision.

Downgrade removes only the seven added `analysis_jobs` columns/checks/index and
the new preparation table, then restores the exact previous AnalysisJob status
constraint and active-fingerprint index. Before any future production
downgrade, no active waiting jobs may exist and bounded request/result payloads
must be audited because downgrade discards only this newly introduced
operational state.

## Deferred implementation and acceptance

After the owner consumes
`FOLLOWUP_ASSISTANT_FILE_PIPELINE_SCHEMA_APPROVAL_REQUIRED`, the bounded next
execution may implement ORM/service/dispatcher/API/Flutter adapters, isolated
synthetic ingress tests, runtime reload and a new non-stable Android candidate
if Flutter changes. It must not bulk-process historical files. Only the exact
owner-selected historical document may be prepared in production during the
separately bounded physical acceptance flow.

PRE-CHUNK23 remains physical-acceptance blocked. CHUNK23 remains blocked/not
started. Stable and +39 are unchanged; no artifact was rebuilt or published.
