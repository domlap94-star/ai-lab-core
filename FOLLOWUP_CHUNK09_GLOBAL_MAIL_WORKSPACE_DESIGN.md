# FOLLOW-UP CHUNK 09 — GLOBAL MAIL WORKSPACE — AUDIT AND DESIGN

Date: 2026-08-19

Release baseline: `NEXT Stabil 1.0.2+21`

Source baseline: `51daa332b9f52cc995fd9c0f738b153e4498f0b4`

DB baseline: `followup_change_history_20260819`

## Initial decision

`FOLLOWUP_MAIL_WORKSPACE_SCHEMA_MIGRATION_APPROVAL_REQUIRED`

The read workspace must not filter one already-paginated page in Flutter. The
canonical Gmail source stores direction, Gmail labels/read state and message
time inside a large `candidate_sources.raw_payload` JSON value. Production has
4,262 canonical Gmail-message records. A bounded prototype returned the latest
50 with attachments in about 748 ms when ordered by the ingestion timestamp,
but queries evaluating direction/read fields over historical JSON exceeded the
10-second Flutter receive timeout. The existing Gmail GIN full-text index
supports body/header search, but no index supports direction, read state or the
canonical Gmail timestamp.

No production schema, rows, links, n8n workflow or email state were changed.
The unverified prototype was not retained.

## Canonical sources

- Message/source: `candidate_sources` with `source_type=gmail_message`.
- Client/review link: `client_candidates.matched_client_id` and Candidate
  status; unlinked/ambiguous records remain Candidates.
- Attachments: existing `documents` rows with
  `source_type=gmail_attachment` and `gmail_message_id`.
- Body projection and HTML safety: reuse `ClientEmailService`; HTML is reduced
  to bounded plain text, scripts/styles are discarded, and raw payload is not
  exposed.
- Existing Client Mail, Timeline V2 and Matching V2 remain canonical consumers.
- Read/unread is reliable only when Gmail `labelIds` is present; otherwise the
  response must use `null`, not invent a state.

## Minimal additive migration proposal

Proposed revision: `followup_mail_query_indexes_20260819`

Parent: `followup_change_history_20260819`

No columns, defaults, backfill, triggers or business-row rewrite. Create only
partial expression indexes for non-deleted Gmail sources:

1. deterministic direction expression (`sent`, `received`, `unknown`) derived
   from the existing explicit direction and Gmail labels;
2. nullable read-state expression derived from presence of labels and
   `UNREAD`;
3. safe canonical message-time expression using guarded ISO/millisecond casts,
   with `created_at` fallback;
4. reuse the existing `ix_candidate_sources_gmail_search_vector`; do not create
   a second search index.

The isolated round-trip must prove index creation/drop/recreation, unchanged
row counts and no data rewrite. Production index build must be timed and locks
observed before apply. If lock duration is material, use a separately approved
online/concurrent operational plan rather than an unsafe transactional build.

## Stage 1 contract after approval

- `GET /api/v1/mail`: bounded list (`50`, max `200`) with search, Client,
  direction, linked/unlinked, attachment, date, thread and reliable read-state
  filters; no body/raw payload.
- `GET /api/v1/mail/{source_id}`: explicit detail with safe bounded body and
  attachment/Client references.
- `GET /api/v1/mail/threads/{thread_id}`: bounded, deduplicated, oldest-first
  thread messages.
- Shared `GlobalMailService`/projection reuses Client Mail normalization.
- Flutter: `Maile` in menu and a minimal Dashboard entry; responsive
  list/detail, filters, paging, Client/Document deep links.
- No manual refresh/reconciliation (CHUNK 10), no relink and no second mail
  store.

## Stage 2 write design and gate

Compose/reply/forward require backend-controlled provider operations,
idempotency keys, explicit final confirmation, allowlisted attachments and
provider-confirmed success before a sent result is represented. Flutter never
receives Gmail credentials. The Agent remains read-only and receives no
`send_email` tool. No live send code or test email may be executed before:

`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`

## Stage 1 final outcome — 2026-08-19

Stage 1 READ is complete. Shared canonical SQL now handles absent/non-array
Gmail labels as unknown rather than read. Online revision
`followup_mail_nullable_read_state_20260819` installed the 184 KiB corrected
ordered V2 index and removed the incorrect ordered predecessor only after the
new index was valid/ready. The full-size isolated migration round-trip and
production application passed without row rewrites or waiting locks.

The production service orders filtered read-state pages by the complete index
key (constant state, canonical time, ID), avoiding the planner's bitmap/sort
choice. Median timings in milliseconds: latest 251, received 352, sent 1,371,
read 254, unread 30, unknown read 1.6, search 957, Client 3.8, thread 7.9 and
date range 222; maximum normal request was 3,826 ms and none exceeded 10 s.

Read-only endpoints `/api/v1/mail`, `/api/v1/mail/{source_id}` and
`/api/v1/mail/threads/{thread_id}` plus the responsive Flutter workspace are
implemented. No raw payload, executable HTML, remote content fetch or
filesystem path is exposed. No refresh, reconciliation, relink, provider
write, n8n change or email send was added. Stage 2 remains stopped at
`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`.

## Production supersession outcome and remaining blocker

Production revision `followup_mail_read_index_supersession_20260819`
concurrently removed the planner-conflicting legacy read-state index after a
verified isolated round-trip. All intended bounded queries pass the 10-second
gate except the strict nullable `unknown read-state` filter. The historical
expression treats a missing labels value as `read`; production contains one
such Gmail source. Correct semantics require a JSON scan and measured
13,364 ms. The API/Flutter prototype used for validation was removed before
commit. Stage 1 therefore remains blocked pending a corrected concurrent
nullable read-state index or separately approved canonical projection. Stage
2, CHUNK 10 and release have not started.

## Required verification after schema approval

- At least 20 read cases covering list, search, filters, threads, detail,
  safe body, attachments, deep links, pagination, auth and Client Mail
  regression.
- Query timings for latest 50, search, Client filter, direction and thread;
  each normal UI request must remain below the configured receive timeout.
- Flutter analyze, focused responsive tests and full suite.
- Data-safety audit: zero email writes/sends, zero Client-link changes, zero
  n8n changes, zero historical relink.

## Execution outcome — online-build gate

Revision `followup_mail_query_indexes_20260819` was applied with exactly the
three approved partial expression indexes. The production build took 49.57 s;
the correct isolated round-trip then measured approximately 46.6 s per build
and 1.6 s for downgrade. Counts were unchanged and no rows were rewritten.

The isolated command was initially configured with `DATABASE_URL`, while this
repository derives its URL from `POSTGRES_DB`. As a result, the first intended
isolated invocation applied the approved index-only migration to production
before the isolated proof. The system was immediately audited: backend 200,
zero pending locks and unchanged source/business/audit counts. A compensating
downgrade was deliberately not run because it would add another blocking DDL
operation without improving data safety.

Performance acceptance remains open. The independent indexes make rare
filters fast (`unknown` about 250 ms; `unread` about 70 ms), but PostgreSQL
cannot efficiently combine common direction/read selection with canonical
message-time ordering (`incoming` about 16 s; `read` about 18 s). A composite
query index is required. Because normal construction against the 524 MB table
is materially blocking, work stops before any additional DDL at:

`FOLLOWUP_MAIL_INDEX_ONLINE_BUILD_APPROVAL_REQUIRED`

Stage 1 API/Flutter code was not retained or committed. Stage 2 remains
separately gated by `FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`.

## Online composite-index execution outcome

Historical decision at this checkpoint:
`FOLLOWUP_CHUNK09_QUERY_ARCHITECTURE_BLOCKED`; see the final outcome below.

The approved online procedure used an explicitly verified isolated database
(`ai_lab_chunk09_online_20260819`) and checked `current_database()` before DDL.
The clone retained 4,262 Gmail sources / 6,984 total sources. Both candidate
designs were built concurrently and compared on the same data:

- partial received/time: 80 KiB, about 215 ms;
- composite direction/time: 208 KiB, about 242 ms;
- partial read/time: 152 KiB, about 107 ms on the clone;
- composite read-state/time: 184 KiB, about 105 ms on the clone.

Production required the partial received/time index and composite
read-state/time index. Revision `followup_mail_composite_indexes_20260819`
uses Alembic `autocommit_block()` and only concurrent create/drop operations.
Its updated isolated upgrade/downgrade/re-upgrade passed. Production indexes
are valid and ready; no waiting lock was observed, backend remained HTTP 200,
and no rows or counts changed.

After statistics refresh, received uses
`ix_candidate_sources_gmail_received_time` and returns 50 IDs in about 244 ms
(baseline exact clone plan: 27.3 s). The common read query still does not pass:
the planner chooses `ix_candidate_sources_gmail_read_state`, reads historical
TOAST JSON and sorts 4,242 rows. The exact query took about 18.5 s; adding the
full index key or a bounded optimizer-barrier subquery took about 19.9–25.4 s.
The new ordered read index remained ignored despite being valid/ready.

The explicit performance gate therefore stopped execution before Global Mail
API, Flutter workspace or UI tests. Source changes are limited to the applied
migration, its structural test and this truthful documentation. A further
architecture decision is required before Stage 1 can continue; likely options
must be evaluated under a new explicit approval because removing/superseding
the baseline read-state index or persisting a canonical projection was not in
this approval. Email sending remains separately gated by
`FOLLOWUP_EMAIL_SEND_APPROVAL_REQUIRED`.

## Isolated legacy-index supersession proof

Current gate: `FOLLOWUP_MAIL_LEGACY_READ_INDEX_DROP_APPROVAL_REQUIRED`.

The fresh full-size clone `ai_lab_chunk09_planner_20260819` was verified with
`current_database()` before any test DDL. After isolated `ANALYZE`, the exact
read query reproduced production behavior: the legacy single-expression index
scanned 4,242 rows, performed a top-N sort and completed in 17,907.796 ms.

Removing only `ix_candidate_sources_gmail_read_state` on the clone caused the
same query to select `ix_candidate_sources_gmail_read_time`, avoid the sort and
complete in 87.232 ms. Four pages / 200 ordered IDs had zero set or positional
differences. Unread (29.990 ms), nullable read state (0.039 ms), latest
(132.239 ms), received (205.964 ms) and sent/outgoing (2,878.154 ms) remained
below the UI timeout.

There are no PostgreSQL dependent objects and no runtime/script reference to
the legacy index name. Production was not changed. Exact plan evidence,
dependency results, production concurrent-drop design and concurrent recreate
rollback are recorded in `FOLLOWUP_CHUNK09_READ_PLANNER_REMEDIATION.md`.
