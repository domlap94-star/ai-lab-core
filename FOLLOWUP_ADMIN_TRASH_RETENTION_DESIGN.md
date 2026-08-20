# PRE-CHUNK15 — Admin Trash / 7-day retention design

Status: **DESIGN COMPLETE — APPROVAL REQUIRED**

Release baseline: `NEXT Stabil 1.0.2+23`

Source baseline: `3bd9ad4bf3b8867ecdf7a6736fd47347b70206e4`

Database baseline: `followup_calendar_tasks_20260820`

Next gate: `FOLLOWUP_TRASH_RETENTION_SCHEMA_AND_SCHEDULER_APPROVAL_REQUIRED`

This is an owner-inserted hotfix gate before CHUNK 15. It is an audit and
design only. No migration, data mutation, file deletion, Qdrant write or
scheduler change was performed.

## Product contract and terminology

The lifecycle is:

`active -> trashed -> restored` or
`active -> trashed -> purge_eligible -> purging -> permanently_deleted`.

`trashed_at` is a timezone-aware server timestamp. `purge_after` is exactly
`trashed_at + interval '7 days'`. A row is eligible only when
`purge_after <= transaction_timestamp()`. Device time is never accepted.
Eligibility does not waive safety checks: a blocked purge remains in Trash
with a bounded technical error, never as a falsely successful deletion.

Permanent deletion is a product state, not necessarily SQL `DELETE`. The FK
audit proves that deleting Client and User rows would destroy or invalidate
historical attribution. Their safe permanent form is an irreversible,
non-login, non-searchable anonymized tombstone retaining the technical ID.
Documents likewise retain a minimal row tombstone so WorkItem and link audit
relations remain valid; their bytes, extracted content and derived artifacts
are what the purge removes. This is the only design that preserves the
approved history without broad cascade or silent detachment.

## Existing behavior audit

### Documents

- `documents` has no delete/archive/trash column and the authenticated API has
  no product delete endpoint.
- The canonical storage path is relative to `settings.data_dir` and
  `resolve_document_storage_path()` resolves it strictly, verifies it is under
  the resolved root and requires a regular file.
- Ordinary reads include repository/detail/content/thumbnail, Client and
  Candidate projections, Global Search, technical AI/search, Timeline,
  WorkItems and mail attachments. None currently has a trash predicate.
- Child `document_pages`, `document_assets` and `document_chunks` use
  `ON DELETE CASCADE`. Child Documents use `parent_document_id ON DELETE
  CASCADE`, so a physical parent delete could unexpectedly delete an archive
  family.
- `work_item_documents.document_id` and
  `document_client_link_events.document_id` are `RESTRICT`. The latter is
  durable provenance. Project/Inspection links are outbound RESTRICT FKs from
  Document. Client/Candidate links are outbound `SET NULL` FKs.
- Pages and assets contain render/storage paths, OCR and Vision state. Document
  contains extracted text, metadata, geolocation and Vision state. Chunks hold
  content and `vector_id` ownership. Production currently has 304 pages, 10
  assets, 57 chunks and 57 vectorized chunks.
- Existing filesystem unlink calls are failure cleanup for newly-created
  artifacts, not a canonical user delete operation.

### Clients

- `Client` inherits `BusinessBase`; `deleted_at` is already indexed.
- current `DELETE /api/v1/clients/{id}` is available to any authenticated user,
  locks the active row, sets server UTC `deleted_at`, writes Change History
  action `deleted`, and commits atomically. There is no restore or retention
  clock.
- Client repositories/search and most linked domain services filter
  `deleted_at IS NULL`. Production contains six legacy soft-deleted Clients.
  They predate this subsystem and must not be backfilled into 7-day Trash.
- Owned contacts/addresses and the following retained history make hard delete
  unsafe: activities, workflow statuses, Projects, Inspections, WorkItems,
  mail send ledger, merge/link events and document provenance.

### Users

- `User` has `is_active`, but no deleted/trash timestamp. Current admin-only
  deactivation uses an advisory transaction lock plus row locks, blocks self
  deactivation and the last active Administrator, sets `is_active=false`, and
  writes `user_lifecycle_events` atomically.
- There is no reactivation/restore operation. Production contains one inactive
  legacy User; it must not be backfilled into Trash.
- JWTs are stateless and identify `sub=username`; every request reloads the User
  and rejects `is_active=false`. This disables access immediately, but after a
  restore an old unexpired token could become usable again. Trash therefore
  needs a server-side token epoch/version bound into newly-issued JWTs and
  checked on every authenticated request. Increment it on trash and restore.
- Active assignee pickers already filter `is_active=true`.

## Exact dependency classification

### Document

| Dependency | Current FK | Purge treatment |
|---|---|---|
| pages/assets/chunks | CASCADE | delete content rows only after full preflight; keep Document tombstone |
| child Documents | CASCADE | block purge unless the complete archive family is independently eligible; never cascade implicitly |
| WorkItem document links | RESTRICT | retain; point to tombstone and display “Dokument usunięty” |
| Document Client link events | RESTRICT | retain as audit/provenance; point to tombstone |
| Client/Candidate/Project/Inspection | outbound FK | retain technical relation on tombstone; do not rewrite linked entity |
| storage/render/asset files | filesystem | canonical path validation and controlled quarantine protocol |
| Qdrant points | external, owned by chunk `vector_id` | hard blocker until exact point ownership and separate Qdrant purge approval |

### Client

| Class | Tables/relations | Recommendation |
|---|---|---|
| A — removable PII owned by Client | active contact points, addresses | purge/anonymize only as part of the approved Client tombstone transaction |
| B — must not be silently detached | Candidate matches, Documents | retain relation to tombstone; do not rely on current `SET NULL` hard-delete behavior |
| C — retained audit/business history | Activities, Change History, workflow statuses, mail ledger, merge/link events, Projects, Inspections, WorkItems | preserve and keep technical Client ID; normal UI resolves a safe deleted label |
| D — physical-delete blockers | all RESTRICT relations above | SQL hard delete is forbidden by this design |

Client permanent deletion is therefore an anonymized tombstone: retain ID and
`deleted_at`, set a non-PII name such as `Usunięty klient #<id>`, clear direct
Client PII and notes, and remove/anonymize owned contact/address PII. The exact
field scrub belongs to the implementation approval and must be transactionally
tested. It does not delete or relink Documents, Mail, Candidates, Projects,
Inspections, WorkItems, Activities or Change History.

### User

All these FKs intentionally preserve attribution and block SQL hard delete:
absence requester/reviewer/canceller, Agent executions, Candidate merge actor,
Change History actor, Client Activity actor, Document link actor, ignored-rule
actors, Inspection/Project/WorkItem/Note/Document actors and assignee, mail-send
actor, lifecycle actor/target and conversation ownership. The permanent result
must therefore be a tombstone:

- preserve User ID and all historical FKs;
- `is_active=false`, increment `auth_version`, clear reset flags;
- replace username with a unique bounded `deleted-user-<id>-<suffix>`;
- replace required email with a unique non-routable `.invalid` value;
- replace password hash with an unusable random hash;
- retain role only as technical history, never as active authority;
- remove any future optional PII fields;
- never put the previous username/email/password in purge audit.

This is irreversible and is the safe equivalent of permanent deletion. It
does not reset credentials on restore during retention; restore preserves the
same password but increments `auth_version`, so all prior tokens stay revoked.

## Chosen schema architecture

A hybrid model avoids both a polymorphic FK and repeated retention clocks.
`trash_entries` is the canonical lifecycle ledger; entity columns are only
fast visibility/tombstone markers.

Proposed Alembic revision:

- revision: `followup_admin_trash_retention_20260820`
- parent: `followup_calendar_tasks_20260820`
- no backfill; all existing entities remain as they are

### `trash_entries`

| Column | Definition |
|---|---|
| `id` | BIGINT primary key |
| `entity_type` | VARCHAR(16), CHECK in `document, client, user` |
| `entity_id` | BIGINT, deliberately no polymorphic FK so evidence survives purge |
| `state` | VARCHAR(16), CHECK in `trashed, purging, blocked, restored, purged` |
| `safe_display_label` | VARCHAR(255), sanitized bounded label, no path/content/email |
| `trashed_at` | TIMESTAMPTZ NOT NULL, server-set |
| `purge_after` | TIMESTAMPTZ NOT NULL, CHECK equals `trashed_at + interval '7 days'` |
| `trashed_by_user_id` | FK users.id RESTRICT NOT NULL |
| `restored_at` / `restored_by_user_id` | nullable TIMESTAMPTZ / users.id RESTRICT |
| `purge_started_at` | nullable TIMESTAMPTZ |
| `purged_at` / `purged_by_user_id` | nullable TIMESTAMPTZ / users.id RESTRICT; actor null means scheduler/System |
| `attempt_count` | INTEGER NOT NULL DEFAULT 0, non-negative CHECK |
| `last_error_code` | VARCHAR(100) nullable; typed code only |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL |

Indexes:

- partial unique `(entity_type, entity_id)` for states
  `trashed,purging,blocked`;
- `(state, purge_after, id)` for deterministic purge batches;
- `(entity_type, state, trashed_at DESC, id DESC)` for admin Trash.

Entity changes:

- `documents`: add `trashed_at TIMESTAMPTZ NULL`, `purged_at TIMESTAMPTZ NULL`,
  and indexes on each. Fields remain NULL for all existing Documents.
- `users`: add `trashed_at TIMESTAMPTZ NULL`, `purged_at TIMESTAMPTZ NULL`,
  `auth_version INTEGER NOT NULL DEFAULT 0` with non-negative CHECK and indexes
  on trash/purge timestamps. For compatibility, an old token without the claim
  is accepted only while the User row remains at version zero. Trash increments
  the version and sets `is_active=false`, so every old token is rejected even
  after restore. Every newly-issued token carries and must match the current
  `auth_version`.
- `clients`: reuse existing `deleted_at` as visibility marker and add only
  `purged_at TIMESTAMPTZ NULL` plus index. A `deleted_at` without an active
  `trash_entries` row remains legacy soft-delete, never purge eligible.

Change History CHECK changes:

- add entity type `document` (Client and User already exist);
- add actions `trashed` and `purged` (`restored` already exists);
- extend the service allowlist with safe lifecycle-only fields. No raw PII,
  paths, descriptions, extracted text, note, password or token.

`change_history_events.entity_id` is not an FK and actor is nullable, so purge
evidence survives tombstoning and scheduler events can truthfully use System.
The durable `trash_entries` row is additional technical purge evidence.

## Lifecycle services and APIs

One `TrashLifecycleService` owns transitions, locking, authorization,
Change History and entity-specific strategies. No router or scheduler writes
trash columns directly.

Proposed admin API:

- `POST /api/v1/documents/{id}/trash`
- `POST /api/v1/clients/{id}/trash`
- `POST /api/v1/admin/users/{id}/trash`
- `GET /api/v1/admin/trash?entity_type=&state=&skip=&limit=` with limit 1..100
- `POST /api/v1/admin/trash/{entry_id}/restore`

All endpoints require JWT. List/restore and User trash require Administrator.
Documents currently have no ownership model or delete permission, so baseline
Document trash is also Administrator-only; do not broaden permissions. The
current Client delete endpoint permits any authenticated User. Preserve that
authorization when it is changed from soft-delete to Trash; tightening it is a
separate product/API decision. Only Administrators can browse Trash or restore
the Client.

There is no public purge endpoint and no baseline “Usuń teraz na stałe”. The
owner requirement is automatic retention purge; adding manual early purge
would need a separate destructive approval and typed-name confirmation.

Trash runs in one DB transaction: acquire the existing lifecycle advisory lock
where appropriate, lock entity and any active Trash entry, verify guards, set
the visibility marker, create the ledger row with DB/server timestamps, write
audit, then commit. User trash also deactivates and increments token version.

Restore is allowed only while `transaction_timestamp() < purge_after`. It
locks entry and entity, rejects `purging/purged`, revalidates all entity rules,
clears the visibility marker, marks the ledger restored and audits atomically.
Document restore additionally validates every expected canonical byte/render/
asset path and checksum. Client relations reappear because none were changed.
User restore rechecks username/email uniqueness, active Administrator policy
and tombstone state; it reactivates the same ID/password and increments token
version. A purged tombstone cannot be restored.

Normal delete confirmation text is:

> Przenieś do kosza
>
> Element będzie można przywrócić przez 7 dni. Po tym czasie zostanie
> automatycznie usunięty na stałe.

## Visibility contract

Every active read must add the canonical entity predicate:

- Client: existing `deleted_at IS NULL`;
- Document: `trashed_at IS NULL AND purged_at IS NULL`;
- User: `is_active=true AND trashed_at IS NULL AND purged_at IS NULL` for
  pickers; admin active/inactive views distinguish ordinary inactive from Trash.

The Document predicate must be added to repository/detail/content/thumbnail,
Client/Candidate/Project/Inspection/WorkItem Documents, mail attachment reads,
Timeline/Recent Activity derived rows, Global Search, technical AI and Vision
dispatch. Normal content/thumbnail/detail returns 404 to avoid disclosure;
admin Trash may use a dedicated metadata endpoint. Trashing does not enqueue
Vision/OCR/reindex.

Semantic/Qdrant search currently trusts vector payloads. It must batch-load
canonical Document IDs and drop trashed/purged hits before returning results.
Lexical/global search filters in SQL. Restore makes DB-backed results visible
again without reindexing because vectors were retained during the seven-day
window. Purge of vectorized Documents is blocked until separately approved
exact vector deletion exists.

Trashed Clients remain hidden through existing Client predicates. Child
business data is not rewritten; views reached independently must resolve the
parent as deleted and avoid presenting it as active. A restore reveals the
same ID and links.

## Document permanent purge protocol

The strategy removes content and leaves a minimal Document tombstone. Before
any destructive step it locks the Trash entry and Document and verifies:

1. state is trashed/blocked, deadline reached and no concurrent restore;
2. every storage/render/asset path comes only from the DB and resolves beneath
   approved roots; no path is accepted from API or ledger;
3. checksums and expected identity match;
4. no active child archive family can be cascaded accidentally;
5. no active processing/Vision job exists;
6. all WorkItem/link-history references can remain pointed at tombstone;
7. no chunk owns a Qdrant `vector_id` unless a separately approved exact-point
   purge implementation is active.

Files are atomically renamed on the same volume into a controlled quarantine
directory first. A DB transaction then removes pages/assets/chunks, scrubs
content/metadata/geolocation/provider-sensitive fields, marks the minimal
Document row and ledger `purged`, and writes safe audit. After commit the
quarantined files are removed. Cleanup failure is recorded and retried; DB
failure causes files to be restored from quarantine. Any mismatch or failed
rollback sets `blocked` and emits an operator-visible error—never success.

Qdrant is explicitly fail-closed. If any owned vector exists, no bytes, DB
content or vectors are partially deleted. Activation of exact deterministic
point removal requires separate gate
`FOLLOWUP_TRASH_QDRANT_PURGE_APPROVAL_REQUIRED`.

## Client and User permanent purge

Client purge locks all dependent categories, verifies no active transaction is
creating a new link, then applies the approved PII scrub and marks Client and
ledger purged atomically. Historical rows and relations remain. Unknown/new FK
dependency blocks the purge. User purge takes the lifecycle advisory lock,
rechecks self/last-admin safeguards even though the target is inactive, applies
the irreversible User tombstone and writes audit. Neither strategy uses SQL
hard delete.

## Admin UI

Settings gains Administrator-only `Kosz`. The route and API reject normal
Users with 403; hiding the menu is not the security boundary. Tabs are
`Pliki`, `Klienci`, `Użytkownicy`. Rows show safe label, entity type,
`trashed_at`, server-derived deadline/time remaining, actor display and
`Przywróć`. No manual purge action in baseline. Responsive tests cover
360/390/600/1200, loading/error/empty states, expiry boundary and expired/
blocked explanations.

## Automated purge scheduler

Use the established Windows Task Scheduler operational pattern (the same host
class used by the daily backup and service startup), invoking a dedicated
signed repository PowerShell wrapper which calls a bounded backend management
command inside the backend container. Do not use n8n or a backend perpetual
loop. No secret appears on the command line or in logs.

Proposed cadence: every 4 hours. Exact-second deletion is not promised and no
row is processed early. Each run:

- acquires a singleton PostgreSQL advisory lock non-blockingly;
- selects at most 100 eligible entries ordered by `purge_after,id`;
- processes each entity in its own transaction;
- locks/rechecks state and deadline immediately before mutation;
- isolates failures, records typed error/attempt count, and continues only to
  the next independent entity;
- produces a bounded manifest/count report without PII or paths;
- is idempotent on rerun.

A concurrent restore wins only if committed before purge acquires the row
lock. Once `purging` is committed/locked, restore returns conflict. Purge
rechecks the current row after locking, so a stale selected row cannot delete a
restored entity. Unexpected FK, storage, audit, vector or state conditions fail
closed.

Scheduler activation is a separate explicit gate:
`FOLLOWUP_TRASH_PURGE_SCHEDULER_APPROVAL_REQUIRED`. Schema/manual Trash approval
does not activate it.

## Backups and rollback

Trash does not depend on future CHUNK 15. Existing backups may retain data
after live purge according to backup retention; the UI must state this
honestly. Purge does not delete or rewrite backup checkpoints.

Migration downgrade is safe only before any Trash lifecycle use. After entries
or tombstones exist, downgrade must refuse unless an explicit audited data
retention/export plan is approved. Application rollback while schema remains
is additive, but old binaries must not expose trashed entities; therefore the
deployment order is backend visibility support first, then UI, and scheduler
last.

## Test plan

Backend/isolated migration:

- linear upgrade/downgrade/re-upgrade, no backfill, legacy six deleted Clients
  and one inactive User never become eligible;
- CHECKs, partial uniqueness, exact server 7-day clock and invalid state;
- Change History accepts document/trashed/purged and rejects invalid values.

Documents:

- trash hides list/search/detail/content/thumbnail/Client/WorkItem/AI results;
- same ID/bytes/relations restore; missing/checksum/path traversal fails;
- before seven days skips, boundary/after is eligible;
- storage and derived artifacts are removed only during completed purge;
- archive children, active processing, WorkItem/link audit and Qdrant vectors
  follow the declared fail-closed rules; rerun is idempotent.

Clients:

- trash hides ordinary list/search while linked history remains;
- restore same ID and relations; no cross-client leakage;
- dependency matrix is exercised; unknown FK blocks;
- permanent tombstone scrubs approved PII but preserves audit/technical links.

Users:

- admin-only trash; self and last Administrator blocked;
- login and active sessions rejected, assignee picker hides target;
- historical actors remain; restore handles uniqueness and token epoch;
- old token remains rejected after restore; password is not reset;
- permanent tombstone is non-login and audit-valid.

Scheduler:

- `<7 days` skipped; exact/after eligible; restored-before-lock skipped;
- restore/purge race, singleton lock, batch 100, deterministic ordering;
- one blocked entity does not corrupt another; retry idempotent;
- scheduler unavailable causes no deletion; audit failure rolls back;
- no secrets/PII/path in report.

Flutter:

- Settings/Kosz Administrator-only and server 403 for normal User;
- tabs, safe labels, countdown/deadline, restore and blocked/empty states;
- trash confirmations use retention wording;
- 360/390/600/1200 no overflow and accessible tap/keyboard semantics.

## Approval split and data safety

This design proposes three distinct approvals:

1. `FOLLOWUP_TRASH_RETENTION_SCHEMA_AND_SCHEDULER_APPROVAL_REQUIRED` — owner
   review of this combined schema/domain/scheduler design before any migration
   or implementation;
2. `FOLLOWUP_TRASH_QDRANT_PURGE_APPROVAL_REQUIRED` — exact owned-vector removal
   before a vectorized Document can be purged;
3. `FOLLOWUP_TRASH_PURGE_SCHEDULER_APPROVAL_REQUIRED` — activation of the host
   task after schema, manual Trash/restore and isolated runner acceptance.

This design execution changed no schema or runtime state: Clients, Documents,
Users, files, Trash rows, Gmail, n8n, Vision, Qdrant and scheduler changes are
all zero. CHUNK 15 remains not started.
