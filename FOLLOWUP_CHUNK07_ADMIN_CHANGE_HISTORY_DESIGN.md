# FOLLOW-UP CHUNK 07 — ADMIN CHANGE HISTORY — DESIGN

Audit date: 2026-08-19

Source HEAD: `a59932c9db09f731a9f162af228f734c0bb22463`

Release: `NEXT Stabil 1.0.2+21`

Live DB revision: `followup_client_activity_20260819`

Status: **DESIGN COMPLETE / CHANGE HISTORY MIGRATION APPROVAL REQUIRED**

This document is an audit and implementation design only. No Alembic revision,
model, API, Flutter UI, production audit row, business write or historical
backfill was created.

## 1. Existing audit infrastructure

The live database has no generic change-history table. Read-only evidence at
the design gate showed zero ungranted locks and the following bounded counts:

| Table/source | Live rows | Domain and actor | Before/after | Admin visibility and sensitive-data policy |
|---|---:|---|---|---|
| `candidate_merge_events` | 0 | Candidate merge; required JWT actor | changed field names and relation counts, not values | Domain audit, currently consumed by merge/Timeline code; bounded counts only |
| `client_activity_events` | 0 | User-facing Client business timeline; JWT actor for call/status | no generic diff | Normal authenticated Client timeline; strict call/status metadata |
| `document_client_link_events` | 1 | Document link/move/unlink; required JWT actor | old/new Client IDs and bounded evidence kinds | Domain audit exposed in Document matching; no document content |
| `user_lifecycle_events` | 1 | Administrator user deactivation; required admin actor | action and target only | Admin domain audit; no password/hash values |
| `agent_executions` | 1 | Read-only Agent operational execution; required JWT user | no business diff | Sanitized tool names/outcomes/durations only |

`client_workflow_statuses` is current state, not history. `import_runs`,
`candidate_sources`, application logs and Docker logs are operational/source
records rather than an actor-attributed change audit. They must not be
reinterpreted as Change History.

The domain-specific tables remain canonical and keep their existing retention
policy. CHUNK 07 adds no deletion or retention automation.

## 2. Current write-surface audit

### Clients

- `ClientService.create_client`, `update_client` and `delete_client` currently
  do not receive an actor. `ClientRepository`/`BaseRepository` commit inside
  create/update/soft-delete, so a future audit insert cannot yet be guaranteed
  atomic with these writes.
- Client contacts and addresses are replaced inside the Client PATCH flow.
  Contacts are physically replaced through the ORM collection; addresses are
  soft-deleted and recreated. A diff must therefore be captured before the
  mutation, not reconstructed after commit.
- `client_added_at` is part of Client PATCH. `created_at` and
  `source_record_date` remain immutable/read-only and must never appear as
  user-edited fields.
- Client workflow status already receives the JWT actor and atomically writes a
  bounded `client_status_changed` Activity event. That Activity event is a
  business fact, not the richer admin diff required here.
- Single and bulk Client soft-delete flows lack actor-attributed change audit.
  No restore endpoint exists in the current API.

### Candidates

- Candidate accept/promotion and reject currently do not receive the JWT actor
  in their service calls and commit internally.
- Candidate promotion creates a Client, changes Candidate state and preserves
  sources, but has no actor-attributed generic history event.
- Candidate merge is already transactionally and idempotently audited by
  `candidate_merge_events`; it must be projected, not copied.

### Other current writes

- Document link/move/unlink is already transactionally represented by
  `document_client_link_events` and can be projected read-only.
- User deactivation is transactionally represented by
  `user_lifecycle_events` and can be projected read-only. User creation and
  password reset have no complete lifecycle audit; password values/hashes must
  never enter Change History.
- Documents, processing, Vision, Inspections and operational settings have
  separate domain semantics. They are not added to the first CHUNK 07 write
  integration merely because they mutate data.
- Ignored mail sources, backup settings, Tasks/Calendar and Knowledge Base do
  not yet exist. Their future services must integrate through the same strict
  Change History service after their own schema approvals.

## 3. Architecture decision

A new generic, admin-only and bounded persistent store is required. Existing
tables do not contain approved per-field before/after values and cannot be
extended without corrupting their contracts.

Proposed service split:

- `ChangeHistoryService`: validates entity/action allowlists, sanitizes an
  entity-specific snapshot, computes a deterministic diff, persists it in the
  caller's transaction and returns nothing to normal business UIs.
- `ChangeHistoryQueryService`: reads the generic table and projects compatible
  immutable domain audits into one stable admin response. It batch-loads actors
  and bounded entity labels to avoid N+1 queries.
- No generic public write endpoint is exposed. Business services call the
  writer server-side with the actor from JWT.

Activity Log and Change History remain separate:

- `client_activity_events` records user-facing business facts such as a call
  initiation or a status change.
- `change_history_events` records admin-only bounded field diffs.
- A status update writes both in the same transaction, with distinct contracts.
- Call initiation is not a data edit and is not copied to Change History.

## 4. Proposed additive migration

Proposed revision: `followup_change_history_20260819`

Parent: `followup_client_activity_20260819`

Create only `change_history_events`:

| Column | Type / policy |
|---|---|
| `id` | `BIGINT`, primary key, identity/autoincrement |
| `actor_user_id` | existing User ID type, nullable only for explicitly supported system events; FK `users.id`, `ON DELETE RESTRICT` |
| `entity_type` | `VARCHAR(64) NOT NULL`, DB check allowlist |
| `entity_id` | `BIGINT NOT NULL` |
| `action` | `VARCHAR(32) NOT NULL`, DB check allowlist |
| `changed_fields` | JSON array of unique sorted field names, `NOT NULL` |
| `before_values` | JSON object produced by the strict sanitizer, `NOT NULL` |
| `after_values` | JSON object produced by the strict sanitizer, `NOT NULL` |
| `operation_id` | `VARCHAR(64) NULL`, content-free request/domain operation reference |
| `source_key` | `VARCHAR(200) NOT NULL`, unique, content-free idempotency key |
| `created_at` | timezone-aware timestamp, `NOT NULL`, server current timestamp |

Initial entity allowlist:

- `client`, `client_contact`, `client_address`,
  `client_workflow_status`, `client_candidate`, `candidate_merge`.

Reserved future entity values are not added until their owning feature exists.
The migration does not pre-authorize arbitrary `task`, `settings` or
`knowledge_base` writes.

Initial action allowlist:

- `created`, `updated`, `deleted`, `restored`, `status_changed`, `accepted`,
  `rejected`, `merged`.

Indexes:

- `(created_at, id)` for newest-first admin pages,
- `(entity_type, entity_id, created_at, id)` for entity-scoped history,
- `(actor_user_id, created_at, id)` for actor filtering.

The unique `source_key` prevents duplicate audit rows on replay. For bulk
status it can include the content-free operation UUID and Client ID. No
backfill, trigger, server-generated business event or business-row rewrite is
part of the migration. Downgrade drops only the new table and its indexes.

Before production apply, an isolated database must pass:

`followup_client_activity_20260819 → followup_change_history_20260819 → downgrade → re-upgrade`

with unchanged business counts, an initially empty audit table and one Alembic
head.

## 5. Sanitizer and bounded-value policy

Each `(entity_type, action)` has an explicit Pydantic schema and field
allowlist. Unknown fields are rejected at the service boundary; arbitrary JSON
is never persisted. `changed_fields` is derived server-side from sanitized
snapshots, deduplicated and sorted.

Global limits proposed for the first version:

- at most 40 changed fields per event,
- scalar strings at most 255 characters unless a stricter field limit applies,
- serialized `before_values` and `after_values` at most 8 KiB each,
- no nested object except one documented descriptor shape,
- arrays only for explicitly documented bounded contact/address summaries.

Always forbidden:

- passwords and hashes, JWT/refresh tokens, cookies, API/OAuth keys and
  secrets, Authorization, environment values and credential material,
- email bodies, document/extracted/OCR/Vision text, raw source/candidate
  payloads, SQL, stack traces and unrestricted notes/JSON,
- fields matching token/secret/password/private-key patterns even if a caller
  accidentally supplies them.

Field policy:

- ordinary bounded Client identity/business fields (for example name, legal
  name, city, workflow status and `client_added_at`) retain their sanitized
  value only when that field changed;
- tax/registration identifiers are masked to a short suffix and accompanied
  by a SHA-256 digest, never stored raw in the generic audit;
- email values are normalized, partially masked and accompanied by a SHA-256
  digest; phone values retain only a safe suffix plus digest;
- address changes contain only the individual changed address fields, bounded
  to their schema lengths. No coordinates, source payload or unrelated Client
  snapshot is copied;
- Client notes and any future long text use a descriptor containing
  `changed=true`, old/new length and SHA-256 digest. No text prefix is stored;
- null set/clear is represented explicitly as JSON null for approved scalar
  fields.

This policy keeps the admin audit useful while minimizing duplicated contact
PII. The API never returns fields that were removed by the sanitizer.

## 6. Transactional integration plan

Implementation after approval must move commit ownership from generic Client
repositories into the relevant application-service transaction boundaries.
The repository may flush, but the service commits only after both the business
mutation and audit insert succeed.

Initial integrations:

1. Client create/edit/soft-delete: router passes JWT actor; service locks and
   snapshots approved fields, applies the mutation, computes the diff and
   inserts exactly one generic event. A no-op PATCH creates no event.
2. Contacts/addresses: entity-specific before/after sets are normalized and
   diffed without recording unrelated Client fields. Replacement semantics do
   not produce duplicate audit entries.
3. `client_added_at`: audit only the explicit field set/clear. Never claim that
   the derived `effective_added_date` fallback was directly edited.
4. Workflow status: the state row, CHUNK 06 Activity row and Change History row
   commit together. A no-op creates neither new history event.
5. Candidate accept/reject: router passes JWT actor; Candidate state and
   resulting Client reference are audited in the same transaction. Promotion
   does not serialize the Candidate raw payload.
6. Candidate merge: no generic row is inserted. The immutable
   `candidate_merge_events` record is projected into the admin query result.
7. Document link and user lifecycle: their immutable domain events may also be
   projected without duplicating storage.

If audit validation or insertion fails, the business mutation rolls back. A
repeated idempotent operation returns/reuses the existing domain result and
does not create another audit event.

## 7. Admin read contract

Proposed additive endpoint:

`GET /api/v1/admin/change-history`

JWT is mandatory. `require_admin` is enforced server-side: unauthenticated
requests return 401 and authenticated non-admin users return 403.

Filters:

- `entity_type`, `entity_id`, `actor_user_id`, `action`,
- `date_from`, `date_to`,
- `skip` and `limit` (default 50, maximum 200).

Ordering is `created_at DESC, stable_key DESC`; generic rows use
`change:<id>` and projected domain rows use disjoint prefixes such as
`candidate-merge:<id>`, `document-link:<id>` and `user-lifecycle:<id>`.

The response contains only:

- stable key, actor ID and permitted display name,
- timestamp, entity type/ID and bounded dynamic label,
- action, changed field names, sanitized before/after,
- an internal application route when the entity still exists.

Entity labels and actors are batch-projected. If a soft-deleted entity cannot
be read normally, the fallback is its type and numeric ID. No external URL or
raw ORM/JSON payload is exposed.

Candidate merge projection maps existing `changed_fields` and relation counts
to a bounded read model. It does not invent old/new values and is clearly
marked as a projected domain audit.

## 8. Planned Flutter UI

After schema approval, add an Administrator-only `Historia zmian` entry in the
existing Admin/Settings area. Hiding the entry is secondary to backend 403
enforcement.

The screen uses backend pagination and provides entity type, actor, action and
date-range filters. Each row shows date/time, actor, action, entity and changed
fields; an expandable panel renders only the sanitized before/after values.
It never requests full email/document content or arbitrary source payloads.

Deep links are internal and conditional. Missing/deleted entities remain
readable as type + ID. Responsive acceptance is required at 360, 390, 600 and
1200 px.

## 9. Required acceptance tests after approval

Migration:

- isolated upgrade/downgrade/re-upgrade, constraints/indexes/FKs, empty table,
  unchanged business counts and single head.

Sanitizer:

- bounded string/date/enum/null set-clear,
- masked/digested email, phone and tax ID,
- address field allowlist,
- long-note length/hash descriptor,
- nested/arbitrary JSON rejection,
- password/token/cookie/body/document/OCR/raw-payload field rejection,
- deterministic sorted changed fields and size limits.

Transactions:

- successful Client edit creates exactly one audit row,
- audit failure rolls back Client/contact/address/status/Candidate write,
- no-op edit creates zero rows,
- repeated idempotent operation creates no duplicate,
- status state, Activity and Change History are atomic,
- Candidate merge remains one projected domain event with no generic copy.

Authorization/query:

- unauthenticated 401, non-admin 403, admin 200,
- actor spoofing impossible,
- entity/action/actor/date filters and stable pagination,
- no secret, full email body, document text or raw payload leakage,
- batch actor/entity projection and measured latest-50/entity/actor queries.

Flutter implementation then requires analyze, focused admin-history tests,
responsive/Back/deep-link checks and the full suite. The current design stage
changes no Flutter source and therefore does not run Flutter tests.

## 10. Capacity, retention and rollout

The current write volume does not justify partitioning. The three proposed
indexes cover the required query paths. Change History remains persistent;
CHUNK 07 adds no destructive retention, purge task or historical reconstruction.

Release remains a separate prompt and stays at `NEXT Stabil 1.0.2+21`.
Implementation must stop until the owner supplies:

`FOLLOWUP_CHANGE_HISTORY_MIGRATION_APPROVAL_REQUIRED`
