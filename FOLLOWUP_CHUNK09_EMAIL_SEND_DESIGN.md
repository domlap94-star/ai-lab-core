# FOLLOW-UP CHUNK 09 — EMAIL SEND STAGE 2 DESIGN

Date: 2026-08-19

Status: **SEND IMPLEMENTED / CONTROLLED TEST TARGET REQUIRED**

Current gate: `FOLLOWUP_EMAIL_SEND_TEST_TARGET_REQUIRED`

No email, provider write, n8n workflow change, schema change, Client link change
or canonical Gmail-source write was performed during this design stage.

## Audited current state

The production send path does not exist today. Flutter and the authenticated
backend expose only Global Mail read operations. The backend has no Gmail OAuth
credential and its n8n configuration is limited to the existing ingestion API
key and internal n8n URL.

The single active n8n workflow uses the existing `gmailOAuth2` credential for
Gmail read/sync nodes and sends canonical ingestion requests to the backend. It
has no Webhook/Gmail-send branch. The installed n8n Gmail node supports provider
`message:send`, `message:reply` and native thread-aware reply behavior, so the
OAuth credential must remain isolated in n8n rather than being exported to the
backend or Flutter.

Canonical sent visibility remains `candidate_sources` with
`source_type=gmail_message`. The existing uniqueness constraint on import
source/type/external Gmail ID safely deduplicates canonical ingestion after a
provider ID exists. It cannot prevent a second external send when two requests
with the same operation ID race, when the backend restarts during a send, or
when Gmail accepts a message but the response/canonical ingest is interrupted.

Existing durable stores are not suitable:

- `change_history_events` is an admin data-diff audit, not an external-side-
  effect ledger;
- `client_activity_events` is the Client business timeline and must not contain
  email bodies or provider operation state;
- `candidate_merge_events` is domain-specific;
- `candidate_sources` has no unique operation ID and exists only after a
  provider-confirmed Gmail ID is available.

Therefore Stage 2 needs one additive, bounded operation ledger before any live
send implementation.

## Proposed migration

Revision: `followup_mail_send_ops_20260819`

Parent: `followup_mail_nullable_read_state_20260819`

Create only `mail_send_operations`:

| Column | Contract |
|---|---|
| `id` | BIGINT primary key |
| `operation_id` | UUID, unique, not null |
| `actor_user_id` | existing users ID type, FK users, RESTRICT, not null |
| `action` | VARCHAR(16), compose/reply/forward only |
| `payload_sha256` | CHAR(64), canonical request digest, not null |
| `status` | VARCHAR(24), bounded state machine |
| `source_message_id` | nullable FK to `candidate_sources.id`, RESTRICT |
| `client_id` | nullable FK to `clients.id`, RESTRICT |
| `provider_message_id` | nullable VARCHAR(1000), unique when present |
| `provider_thread_id` | nullable VARCHAR(1000) |
| `canonical_source_id` | nullable unique FK to `candidate_sources.id`, RESTRICT |
| `provider_execution_ref` | nullable VARCHAR(255), non-secret n8n execution reference |
| `recipient_count` | SMALLINT, bounded, not null |
| `attachment_count` | SMALLINT, bounded, not null |
| `attempt_count` | SMALLINT, bounded, not null |
| `error_code` | nullable VARCHAR(64), allowlisted code only |
| `provider_accepted_at` | nullable TIMESTAMPTZ |
| `created_at` | TIMESTAMPTZ, server `now()` |
| `updated_at` | TIMESTAMPTZ, server `now()`/application update |

Allowed statuses:

- `pending` — durable claim exists; no second caller may send;
- `provider_accepted` — Gmail returned a message/thread ID;
- `canonical_synced` — provider result has one canonical CandidateSource;
- `failed` — provider definitively rejected before acceptance;
- `unknown` — timeout/interruption where acceptance cannot be disproved;
  automatic resend is forbidden.

Indexes are limited to the unique operation/provider/canonical identifiers plus
`(status, updated_at)` for bounded recovery inspection and
`(actor_user_id, created_at)` for operational audit. There is no backfill,
trigger, default business payload, source rewrite or historical send import.
Downgrade drops only this empty/new operation table after an explicit
compatibility check; it never deletes Gmail messages or CandidateSource rows.

## Stored-data policy

The ledger stores no subject, body, quoted content, full recipient list,
attachment bytes/path, OAuth credential, access/refresh token, n8n secret,
raw provider response or arbitrary JSON.

`payload_sha256` is computed over a canonical server-side representation of:
action, normalized To/CC/BCC, subject, body digest, selected Document IDs,
source message ID and optional Client ID. It detects a changed payload under the
same operation ID without retaining message content in the audit ledger.

Only actor, action, counts, bounded references, status, provider IDs,
allowlisted failure code and timestamps are retained.

## Provider architecture after approval

1. Flutter shows compose/reply/forward and final confirmation, creates one UUID
   and disables Send while pending.
2. An authenticated explicit backend endpoint validates recipients, sizes,
   Client/source ownership and authorized Document IDs. Actor comes from JWT.
3. The backend atomically creates/claims `mail_send_operations` before calling
   any provider. A conflicting payload under the same UUID returns typed 409.
4. The backend calls a new, narrowly scoped internal n8n send webhook protected
   by a dedicated configured secret. Flutter never receives that secret or the
   Gmail credential. The workflow contains only validation/routing and Gmail
   send/reply nodes; existing ingestion schedules are unchanged.
5. n8n returns provider-confirmed Gmail message ID, thread ID, accepted status
   and a non-secret execution reference. Forward is an explicit new send;
   reply uses provider-native message/thread context.
6. The backend first persists `provider_accepted`, then performs bounded
   immediate canonical ingestion through the existing ImportIngest service.
   Successful ingest records `canonical_source_id` and `canonical_synced`.
7. If canonical ingest fails after provider acceptance, replay resumes ingest
   from the stored provider result and never calls Gmail again.
8. If provider outcome is unknown, the operation becomes `unknown`; retry is
   fail-closed until a bounded provider/execution reconciliation proves whether
   Gmail accepted it. No background/bulk retry is introduced in CHUNK 09.

The n8n send webhook change is limited to this send adapter. No Gmail refresh,
reconciliation schedule or CHUNK 10 behavior is included.

## API contract after approval

Add authenticated endpoints:

- `POST /api/v1/mail/send`
- `POST /api/v1/mail/{source_id}/reply`
- `POST /api/v1/mail/{source_id}/forward`

Requests contain a canonical UUID, bounded recipient lists, subject/body and
Document IDs only. They never accept actor, provider credentials, raw Gmail
headers, filesystem paths, provider message/thread IDs or arbitrary metadata.

Reply loads the canonical source server-side and uses its Gmail message/thread
identity. Forward recipients are always explicit and empty by default.
Subject prefix normalization avoids repeated `Re:`/`Fwd:` prefixes. Plain text
is canonical; any quoted prior content is server-generated, bounded and
sanitized.

Provider success is returned only after Gmail acceptance. `canonical_synced`
responses include the existing Global Mail source ID. `provider_accepted`
without canonical sync is truthful success with a bounded pending-visibility
state, never a fabricated mail row.

## Attachment policy

- existing authorized Document IDs only;
- no Flutter-provided paths, traversal, storage paths or arbitrary URLs;
- per-document Client/scope authorization before reading bytes;
- bounded count and aggregate encoded size checked before n8n/provider call;
- provider limit includes base64/MIME overhead;
- forwarding attachments is opt-in;
- canonical Document rows/files are not copied or deleted.

## UI and confirmation

Global Mail adds `Nowa wiadomość`; detail adds `Odpowiedz` and
`Przekaż dalej`. Every flow has a second, explicit confirmation showing bounded
To/subject/attachment summary. Opening compose/reply/forward, Back and Cancel
perform zero writes. Transient draft state stays in Flutter only; no draft
table is proposed.

The same operation UUID is reused for bounded retry. A pending/unknown request
cannot trigger another provider call. Agent tools remain read-only and no
send/reply/forward Agent tool is added.

## Acceptance after schema approval

Before any real provider test, an explicitly controlled owner/test mailbox must
be identified. None was assumed during this audit. If it is not supplied or
verified, execution stops at `FOLLOWUP_EMAIL_SEND_TEST_TARGET_REQUIRED`.

Maximum provider acceptance sends: one synthetic compose, one reply and one
forward, all to the controlled target and using synthetic content. Provider
failure, concurrency, replay, payload conflict and attachment authorization are
tested with mocks/isolated fixtures first. A real send is attempted only after
those tests pass.

Required hard outcomes:

- replay sends exactly once; changed payload under the UUID returns 409;
- provider failure creates no canonical sent source;
- provider accepted + ingest failure resumes ingest without resend;
- Global Mail, Client Mail and Timeline see exactly one canonical outgoing
  message where a verified Client relation exists;
- no duplicate Activity event and no Matching V2 relink;
- no Agent write tool, customer message, bulk/background send or release.

## Approved implementation outcome

- Revision `followup_mail_send_ops_20260819` passed isolated
  upgrade/downgrade/re-upgrade and was applied to production. The production
  ledger contains zero rows; Clients, Candidates and 4,262 Gmail sources were
  unchanged.
- Backend source implements authenticated compose/reply/forward, server-side
  recipient/body/attachment validation, durable claim, canonical payload hash,
  provider accepted/unknown/failed state handling and canonical ImportIngest
  continuation without a second provider call.
- The tracked inactive n8n workflow template exposes exactly compose, reply
  and forward, retains Gmail OAuth in n8n, validates a dedicated runtime secret
  and returns only bounded provider identifiers. It is intentionally not
  imported/activated until a controlled test target and runtime secret are
  supplied.
- Flutter implements compose, reply and forward entry points with a mandatory
  second confirmation. Double execution is bounded by the operation UUID and
  backend ledger. Draft state is transient.
- Mocked backend verification: migration/service/Auth and Stage 1 regressions
  PASS; provider replay count is one, changed payload conflicts, definitive
  failure is terminal, and unknown outcome is fail-closed. Flutter analyze
  PASS, focused Mail `9/9`, full suite `200/200`.
- Production provider calls, send-ledger rows, canonical sent sources, Client
  relinks, n8n workflow changes and emails sent: zero.

## Current decision

`FOLLOWUP_EMAIL_SEND_TEST_TARGET_REQUIRED`

No controlled mailbox is configured, so the provider workflow remains
inactive and live compose/reply/forward acceptance was not fabricated. CHUNK 09
is not complete. CHUNK 10 and release remain stopped.
