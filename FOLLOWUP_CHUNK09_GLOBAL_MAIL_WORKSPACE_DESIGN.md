# FOLLOW-UP CHUNK 09 — GLOBAL MAIL WORKSPACE — AUDIT AND DESIGN

Date: 2026-08-19  
Release baseline: `NEXT Stabil 1.0.2+21`  
Source baseline: `51daa332b9f52cc995fd9c0f738b153e4498f0b4`  
DB baseline: `followup_change_history_20260819`

## Decision

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

## Required verification after schema approval

- At least 20 read cases covering list, search, filters, threads, detail,
  safe body, attachments, deep links, pagination, auth and Client Mail
  regression.
- Query timings for latest 50, search, Client filter, direction and thread;
  each normal UI request must remain below the configured receive timeout.
- Flutter analyze, focused responsive tests and full suite.
- Data-safety audit: zero email writes/sends, zero Client-link changes, zero
  n8n changes, zero historical relink.
