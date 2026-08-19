# FOLLOW-UP CHUNK 06 — CLIENT ACTIVITY LOG + TIMELINE V2 — DESIGN

Audit date: 2026-08-19

Source HEAD: `2679f0b2b253574336ebc3f5074386fb8ad3a2a3`

Release: `NEXT Stabil 1.0.2+21`

Live DB revision: `followup_candidate_merge_audit_20260819`

Status: **DESIGN COMPLETE / ACTIVITY AUDIT MIGRATION APPROVAL REQUIRED**

This document is a schema and implementation design only. No migration,
production Activity row, historical backfill, phone call or business write was
performed.

## 1. Current Timeline audit

Current endpoints:

- `GET /api/v1/clients/{client_id}/timeline`,
- `GET /api/v1/projects/{project_id}/timeline`.

Both require the existing JWT dependency. `TimelineService` is a bounded,
read-only projection. For every source it obtains at most `skip + limit` rows,
merges them in memory, sorts by `(occurred_at, stable_key)` descending and
returns an offset page. Flutter loads 20 events initially and increases the
server-side limit for `Pokaż więcej`.

| Timeline event | Canonical source | Timestamp | Actor | Current deep link |
|---|---|---|---|---|
| `client_created` | `clients` | `created_at` | unavailable | Client |
| `project_created` | `projects` | `created_at` | `created_by_user_id` | Project |
| inspection create/schedule/start/complete | `inspections` | corresponding domain timestamp | created/updated user where known | Inspection |
| `document_added`, `photo_captured` | `documents` | `created_at` / `captured_at` | unavailable | Document |
| `email_received`, `email_sent` | deduplicated Gmail `candidate_sources` | `message_at` / `created_at` | incoming/outgoing user is not reliably known | exact Client email source |
| document link/move/unlink | `document_client_link_events` | `created_at` | required actor | Document |

The email projection stores no Activity copy. It returns a subject bounded to
500 characters and bounded sender metadata, but never `text`, `body`,
`extracted_text` or `raw_payload`. Gmail source deduplication and stable source
keys prevent repeated derived email events.

Live read-only evidence:

- Clients `3243`, Documents `5915`, Inspections `3`, Gmail sources `4262`,
- workflow status rows `3`, document link events `1`, Candidate merge events
  `0`, user lifecycle events `1`, Agent executions `1`,
- `client_activity_events` does not exist,
- representative Client: 127 Gmail sources; repeated first-page reads returned
  20 out of 127 in 82.048–127.701 ms, with zero duplicate stable keys and zero
  forbidden body/raw-payload metadata keys,
- DB locks `0`; production writes `0`.

Major gaps:

1. `call_initiated` has no canonical source and cannot be reconstructed.
2. `client_workflow_statuses` keeps one active row per Client. It overwrites
   the previous status and therefore cannot provide status history.
3. Candidate merge audit is canonical but is not projected into Timeline.
4. Timeline exposes actor IDs where available but no bounded actor display
   projection.
5. There is no generic idempotency primitive for future manual business
   actions.

## 2. Existing audit tables are not reusable as a generic log

- `candidate_merge_events` is an immutable, operation-idempotent audit of one
  domain write and must remain its canonical source.
- `document_client_link_events` audits link/move/unlink and includes reversal
  semantics specific to Documents.
- `user_lifecycle_events` is an Admin authentication/user-lifecycle audit.
- `agent_executions` is a sanitized operational trace for read-only Agent
  requests.
- `client_workflow_statuses` is current state, not history.

Writing calls, statuses or future Tasks into any of these tables would corrupt
their contracts. A minimal generic persistent model is required for business
actions that otherwise have no durable canonical source.

## 3. Architecture decision: hybrid Timeline V2

Timeline V2 combines two categories without copying canonical records:

### Persistent Activity events

Used only when the business fact does not otherwise exist durably:

- `call_initiated`,
- future `client_status_changed` events emitted transactionally by the
  canonical workflow-status service,
- future manual actions that have no canonical domain table.

### Derived domain events

Read from their existing sources:

- Gmail emails,
- Documents and photos,
- Inspections and legacy Projects,
- document Client-link events,
- Candidate merge events.

No email, Document, Inspection or Candidate merge row is copied into the new
table. No historical email/status backfill is part of CHUNK 06.

## 4. Proposed additive migration

Proposed revision: `followup_client_activity_20260819`

Parent: `followup_candidate_merge_audit_20260819`

Create only `client_activity_events`:

| Column | Type / policy |
|---|---|
| `id` | `BIGINT`, primary key, identity/autoincrement |
| `client_id` | `BIGINT NOT NULL`, FK `clients.id`, `ON DELETE RESTRICT` |
| `actor_user_id` | existing User ID type, nullable, FK `users.id`, `ON DELETE RESTRICT` |
| `event_type` | `VARCHAR(64) NOT NULL`, bounded check constraint |
| `direction` | `VARCHAR(16) NULL`, check `incoming` / `outgoing` |
| `entity_type` | `VARCHAR(64) NULL`, bounded check constraint |
| `entity_id` | `BIGINT NULL` |
| `occurred_at` | timezone-aware timestamp, `NOT NULL` |
| `summary` | `VARCHAR(500) NULL` |
| `metadata` | repository-standard JSON, `NOT NULL`; ORM attribute named `event_metadata` to avoid SQLAlchemy's reserved `metadata` attribute |
| `source_key` | `VARCHAR(160) NOT NULL`, unique, contains no customer content |
| `created_at` | timezone-aware timestamp, `NOT NULL`, server current timestamp |

Initial event-type contract reserves:

- `call_initiated`, `client_status_changed`,
- `email_received`, `email_sent`, `document_added`, `inspection_created`,
  `candidate_merged` for compatible projection/source semantics,
- `task_created`, `task_completed`, `realization_created`, `note_added` for the
  explicitly planned future domains.

Only `call_initiated` and `client_status_changed` are writable by CHUNK 06
services. Reserving future values does not expose an endpoint or implement
Tasks/Realizations.

Constraints and indexes:

- unique constraint on `source_key`,
- index `(client_id, occurred_at, id)`; PostgreSQL can scan it backwards for
  the required newest-first order,
- check constraints for event type, direction and compatible nullability,
- JSON object check where supported by the repository's PostgreSQL convention,
- no global event-type index without measured evidence.

Upgrade performs `CREATE TABLE`, constraints and indexes only. There is no
default Client event, trigger, history rewrite or backfill. Downgrade drops
only the new indexes/table. Production downgrade is not part of approval; the
round-trip must first pass on an isolated restored/test database.

## 5. Strict metadata policy

The application validates metadata per event type before persistence. Unknown
keys are rejected.

`call_initiated` allows only:

```json
{
  "contact_id": 123,
  "contact_kind": "phone",
  "contact_reference": "contact_point"
}
```

For a legacy primary phone without a persisted contact point, `contact_id` is
null and `contact_reference` is `primary_phone`. The phone number itself is
not copied into metadata.

`client_status_changed` allows only old/new canonical status codes and the
bounded effective date. It stores no arbitrary before/after object.

Forbidden for every event: email/document body, extracted text, OCR/Vision
content, contact value, raw payload, password/token/cookie, Authorization,
SQL, stack trace, environment or arbitrary client-supplied JSON.

## 6. Call action contract

Proposed explicit endpoint:

`POST /api/v1/clients/{client_id}/activities/call-initiated`

Request:

```json
{
  "operation_id": "UUID",
  "contact_id": 123
}
```

Rules:

1. JWT is mandatory; `actor_user_id` always comes from `get_current_user`.
2. The Client must be active under existing Client authorization semantics.
3. A supplied contact must be an active phone contact belonging to that
   Client. Null is allowed only when the Client has a legacy primary phone.
4. `source_key = call:<operation_id>`; same operation and same target returns
   the existing event, while payload/Client mismatch returns typed HTTP 409.
5. Flutter cannot submit event type, actor, timestamp, summary or arbitrary
   metadata.
6. A double tap is disabled while the request is pending and reuses the same
   operation ID on retry.

The existing Flutter action uses `url_launcher` with a `tel:` URI and currently
has only the phone value. Implementation will select the primary
`ClientContactPoint.id` when available. It will attempt the audit write and
open the dialer even if the audit request fails, with a bounded, non-blocking
warning. The event is named `call_initiated`; it never claims that a call was
connected or completed. Acceptance must mock `url_launcher`; no real phone
call is permitted.

## 7. Status, email and domain projections

- The canonical workflow-status backend, not Flutter, emits
  `client_status_changed` in the same DB transaction as a genuine state
  change. An exact repeated request that changes nothing emits no second event.
- Existing historical status cannot be reconstructed and is not backfilled.
- Gmail remains derived and idempotent by its existing source identity. Subject
  is bounded; body is excluded. Incoming actor is null/external. Outgoing actor
  remains null unless a future canonical send record identifies a real user.
- Candidate merges are projected read-only from `candidate_merge_events` using
  `target_client_id`, event actor and a stable merge-event key.
- Documents, Inspections, Projects and document link audit remain derived from
  their canonical tables.
- Future Mail/Task implementations may either derive events from their own
  canonical tables or emit a strict Activity event when no other durable fact
  exists. They receive no arbitrary generic write endpoint.

## 8. Timeline API/UI V2

The existing GET response changes additively only. Proposed additions:

- `actor_display_name` (projected from the User table, never stored in JSON),
- optional `entity_type` and `entity_id`,
- event types `call_initiated`, `client_status_changed`, `candidate_merged`.

Actor names are loaded in one bounded query after final page selection to
avoid N+1. External/unknown actors render a neutral label and are never
guessed.

Ordering remains `(occurred_at DESC, stable_key DESC)`. Source queries remain
bounded before the final merge. Offset pagination stays server-side; Flutter
must not fetch the full history or sort a partial page locally. The existing
expandable Timeline card gains grouped choices for Telefon, Maile, Dokumenty,
Oględziny, Status and Inne. Dates reuse `dd.MM.yyyy, HH:mm` in the local UI
timezone.

Deep links:

- email → exact Client email source,
- Document → Document,
- Inspection → Inspection,
- Candidate merge → Candidate context when available,
- call/status → no external action required.

The reusable `TimelineService` remains the source for Client AI, Business AI,
Technical AI and the existing read-only Agent `get_client_timeline` tool. No
new Agent tool or write capability is added.

## 9. Transaction and failure rules

- Activity insert and workflow status update commit atomically.
- Call events are independent writes initiated by an explicit user action.
- Unique `source_key` provides idempotency under retries/concurrency.
- Validation, scope or metadata failure writes nothing.
- A failed call-audit request does not block launching the phone dialer.
- Derived source deletion/soft deletion follows current Timeline visibility;
  immutable persisted Activity events are not cascaded with Client/User rows.
- Activity Log is user-facing business history. It does not contain Admin
  before/after diffs; CHUNK 07 remains a separate audit model.

## 10. Required migration and implementation test specification

Before production apply:

1. isolated upgrade from current head,
2. table/constraints/index/FK verification,
3. zero historical rows and unchanged business counts,
4. downgrade to current head,
5. re-upgrade and single-head verification.

Implementation acceptance matrix:

1. call event creation,
2. actor derived from JWT,
3. invalid/deleted Client rejected,
4. foreign/non-phone contact rejected,
5. operation replay idempotent,
6. operation mismatch returns typed conflict,
7. incoming email projection,
8. outgoing email projection with unknown actor preserved,
9. email body/raw payload absent,
10. Document projection,
11. Inspection projection,
12. genuine status change emitted atomically,
13. repeated unchanged status emits no duplicate,
14. Candidate merge projection,
15. chronological deterministic ordering,
16. pagination boundary without duplicates/missing keys,
17. soft-deleted derived source behavior,
18. unauthenticated request rejected,
19. Client/contact isolation,
20. local full-year timestamp formatting,
21. deep links and Android Back,
22. representative large-history latency/query-count bound,
23. strict metadata rejection and no PII/content leakage,
24. call write failure still invokes mocked dialer,
25. no real phone call, email send, historical backfill or unrelated write.

Required regressions: Clients/workflow, Timeline, Gmail/email source,
Documents, Inspections, Candidate merge, Auth, Agent timeline tool, Client AI,
Business Assistant and Technical AI. Flutter implementation requires analyze,
focused responsive tests at 360/390/600/1200 and the full suite.

## 11. Rollout and human gate

The schema is additive and needs no historical backfill. After isolated PASS,
production apply requires the explicit token:

`FOLLOWUP_ACTIVITY_AUDIT_MIGRATION_APPROVAL_REQUIRED`

Until that approval, no Alembic revision/model/API/UI implementation may be
created and no Activity row may be written. Release remains a separate prompt
and stays at `NEXT Stabil 1.0.2+21`.
