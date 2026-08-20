# FOLLOW-UP CHUNK 13 — Calendar / Tasks / Realizations / Notes design

Status: **DESIGN COMPLETE / MIGRATION APPROVAL REQUIRED**

Date: 2026-08-20

Source baseline: `c99df02e3aabe62830081ea4c0edd9dcde906dcf`

Production DB head audited read-only: `followup_change_history_entity_types_20260820`

Approval gate: `FOLLOWUP_CALENDAR_TASKS_MIGRATION_APPROVAL_REQUIRED`

This document is a production design, not an implementation. No model, API,
Flutter source, migration file, production schema or business row was changed
as part of this design step.

## 1. Existing architecture audit

### Existing business domains

- There is no canonical task, reminder, calendar-event, assignment or work-item
  table, backend API or Flutter workspace.
- `projects` is a legacy realization/project domain. A Project requires a
  Client, uses date-only `start_date`/`end_date`, supports only
  `planned|active|completed|cancelled`, and has no assignee, priority, notes or
  reminder/event semantics. Existing `/api/v1/projects`, Flutter Realizacje
  screens and global search must remain compatible.
- `inspections` is the existing field-inspection domain. It requires a Client,
  optionally links a Project, stores timezone-aware schedule/start/completion
  timestamps and foreground coordinates, and uses soft deletion.
- `clients.notes` is a single legacy Client text field, not a reusable notes
  model. It must not be repurposed for work-item notes.
- `users` supplies canonical assignees. Users are deactivated rather than hard
  deleted; roles are `Administrator` and `User` in the current admin contract.
- Primary business entities use `BusinessBase` (`BIGINT` ID, timezone-aware
  timestamps, `deleted_at`) and service/repository layers.

The new CHUNK 13 `realization` type is therefore a work-management item. It
does not replace or silently migrate the legacy `projects` domain. The Polish
UI may label both concepts carefully (`Realizacja — zadanie` versus an existing
project) until a later owner-approved convergence decision.

### Documents and field capture

- `documents` is the only canonical file store. It already owns authorized
  upload/content/thumbnail delivery, checksums, MIME, storage paths, Client,
  Project and Inspection associations, camera sources and foreground location
  metadata (`captured_at`, latitude, longitude, accuracy and location source).
- `DocumentIntakeDialog`, `image_picker`, `file_picker`, the canonical Document
  upload service and the shared internal image viewer already cover file,
  image, camera and gallery intake. Storage paths are not exposed to Flutter.
- Android speech-to-text and foreground geolocation are implemented in
  `inspection_field_services.dart`. STT first attempts an on-device Polish
  recognizer and falls back to the system recognizer; audio is not uploaded to
  NEXT Stabil. Location denial, permanent denial, disabled services and errors
  are already non-destructive result states.

Implementation should extract the inspection-specific interfaces into shared
field-intake services, retaining compatibility aliases/adapters for Inspection,
rather than creating a second STT/GPS implementation.

### Timeline and Change History

- `TimelineService` is a bounded, read-only projection of canonical Client,
  Project, Inspection, Document, email and selected Activity records. This is
  the correct integration pattern for Client-linked work items.
- `client_activity_events` contains old allowlisted names such as
  `task_created`, `task_completed`, `realization_created` and `note_added`, but
  the writable Activity service intentionally persists only explicit calls and
  Client status changes. CHUNK 13 must not persist a second Activity copy of a
  canonical work item.
- `change_history_events` currently allows entity types `client`,
  `client_contact`, `client_address`, `client_workflow_status`,
  `client_candidate`, `candidate_merge`, `ignored_mail_source` and `user`.
  Existing actions `created`, `updated`, `deleted`, `restored` and
  `status_changed` are sufficient, but the entity CHECK requires extension.

## 2. Canonical domain contract

### One core entity

Create one additive `work_items` table. Stable API/database type values are:

| Value | Polish label | Semantics |
|---|---|---|
| `task` | Zadanie | Ordinary actionable task. |
| `order` | Zlecenie | Work/order request; `zlecenie` is the UI label, not a second value. |
| `realization` | Realizacja | Execution record, optionally Client-linked. |
| `reminder` | Przypomnienie | Calendar-visible reminder with a required deadline. No OS notification in this baseline. |
| `event` | Wydarzenie | Calendar event with a required start and optional end. |

This avoids five near-identical tables and keeps filtering, assignment,
attachments, notes, auditing and calendar projection consistent.

### Status and priority

- Status allowlist: `todo`, `in_progress`, `completed`, `cancelled`.
- Priority allowlist: `low`, `normal`, `high`, `urgent`; default `normal`.
- Creating a `completed` item sets `completed_at` server-side. Moving into
  `completed` sets it once at the transition time; moving away clears it.
  Direct client input for `completed_at` is rejected.
- Archive/delete is soft (`deleted_at`). No production hard-delete endpoint is
  part of CHUNK 13. Restore is explicit and audited.

### Actor, assignee, Client and party

- `created_by_user_id` and `updated_by_user_id` are mandatory and server-derived.
- `assignee_user_id` is optional and references a real User with `ON DELETE
  RESTRICT`. Only active users may be newly assigned. Deactivation preserves
  historical assignments; unrelated edits need not clear them.
- `client_id` is optional and references an existing active Client with `ON
  DELETE RESTRICT`. Creating or updating a work item never creates or matches a
  Client.
- `party_name` is optional, trimmed, empty-to-null and bounded to 255
  characters. It is descriptive only and never becomes Client identity or
  Matching evidence.
- Current CRM permissions are shared rather than owner-scoped. All active,
  authenticated users can view/create/edit/assign work items. Actor IDs are
  always derived from JWT. A bounded authenticated assignee lookup exposes only
  active user IDs and display names; it does not reuse the admin-only user
  management response or expose credential fields.

### Time and concurrency

- `start_at` and `due_at` use `TIMESTAMPTZ` and are normalized to UTC at the API
  boundary. `due_at` is displayed as deadline for task/order/realization/
  reminder and as end for event.
- When both are present, `due_at >= start_at`.
- `event` requires `start_at`; `reminder` requires `due_at`. Other types may be
  unscheduled.
- `all_day` is explicit. An all-day item requires `start_at`, `due_at` and a
  valid IANA `timezone_name` (default UI choice `Europe/Warsaw`); the interval
  is half-open local-midnight to local-midnight. This prevents date shifts on
  UTC conversion. Other items may include a timezone for display, but offset
  timestamps remain canonical.
- `version` starts at 1. PATCH/status/archive/restore requests include
  `expected_version`; updates use an atomic ID/version predicate and return a
  typed HTTP 409 on stale state.

## 3. Exact proposed migration

Proposed revision: `followup_calendar_tasks_20260820`

Parent: `followup_change_history_entity_types_20260820`

No migration file is created at this gate.

### `work_items`

| Column | Definition |
|---|---|
| `id` | `BIGINT` primary key, autoincrement |
| `item_type` | `VARCHAR(24) NOT NULL` |
| `title` | `VARCHAR(255) NOT NULL` |
| `description` | `TEXT NULL` |
| `start_at` | `TIMESTAMPTZ NULL` |
| `due_at` | `TIMESTAMPTZ NULL` |
| `all_day` | `BOOLEAN NOT NULL DEFAULT false` |
| `timezone_name` | `VARCHAR(64) NULL` |
| `status` | `VARCHAR(24) NOT NULL DEFAULT 'todo'` |
| `priority` | `VARCHAR(16) NOT NULL DEFAULT 'normal'` |
| `assignee_user_id` | `BIGINT NULL`, FK `users.id ON DELETE RESTRICT` |
| `client_id` | `BIGINT NULL`, FK `clients.id ON DELETE RESTRICT` |
| `party_name` | `VARCHAR(255) NULL` |
| `created_by_user_id` | `BIGINT NOT NULL`, FK `users.id ON DELETE RESTRICT` |
| `updated_by_user_id` | `BIGINT NOT NULL`, FK `users.id ON DELETE RESTRICT` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `completed_at` | `TIMESTAMPTZ NULL` |
| `deleted_at` | `TIMESTAMPTZ NULL` |
| `version` | `INTEGER NOT NULL DEFAULT 1` |

CHECK constraints:

- item type in `task|order|realization|reminder|event`;
- status in `todo|in_progress|completed|cancelled`;
- priority in `low|normal|high|urgent`;
- non-empty trimmed title, description at most 20,000 characters, non-empty
  party when present, version greater than zero;
- due not before start;
- `completed_at` present exactly when status is `completed`;
- event has start; reminder has due;
- all-day has start, due and non-empty timezone. IANA validity is enforced by
  API/service validation because a CHECK cannot safely validate zone names.

Indexes (partial on `deleted_at IS NULL` where shown):

- `(status, due_at, id)`;
- `(assignee_user_id, status, due_at, id)`;
- `(client_id, created_at DESC, id DESC)`;
- `(item_type, start_at, id)`.

### `work_item_notes`

| Column | Definition |
|---|---|
| `id` | `BIGINT` primary key, autoincrement |
| `work_item_id` | `BIGINT NOT NULL`, FK `work_items.id ON DELETE RESTRICT` |
| `text` | `TEXT NOT NULL` |
| `created_by_user_id` | `BIGINT NOT NULL`, FK `users.id ON DELETE RESTRICT` |
| `updated_by_user_id` | `BIGINT NOT NULL`, FK `users.id ON DELETE RESTRICT` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `deleted_at` | `TIMESTAMPTZ NULL` |
| `version` | `INTEGER NOT NULL DEFAULT 1` |

Constraints: trimmed text is non-empty and at most 10,000 characters; version
is positive; `UNIQUE(id, work_item_id)` supports the same-item composite FK.
Index active notes by `(work_item_id, created_at, id)`.

### `work_item_documents`

This table links canonical Document bytes; it is not another store.

| Column | Definition |
|---|---|
| `id` | `BIGINT` primary key, autoincrement |
| `work_item_id` | `BIGINT NOT NULL`, FK `work_items.id ON DELETE RESTRICT` |
| `note_id` | `BIGINT NULL`, part of composite FK below |
| `document_id` | `BIGINT NOT NULL`, FK `documents.id ON DELETE RESTRICT` |
| `attached_by_user_id` | `BIGINT NOT NULL`, FK `users.id ON DELETE RESTRICT` |
| `detached_by_user_id` | `BIGINT NULL`, FK `users.id ON DELETE RESTRICT` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `detached_at` | `TIMESTAMPTZ NULL` |

- Composite FK `(note_id, work_item_id)` references
  `work_item_notes(id, work_item_id) ON DELETE RESTRICT`, ensuring that a
  note-specific attachment belongs to the same item. A null note means an
  item-level attachment.
- CHECK requires `detached_at` and `detached_by_user_id` to be both null or both
  present.
- A partial unique index on `(work_item_id, document_id)` where
  `detached_at IS NULL` prevents duplicate active links while preserving
  attach/detach provenance. Additional indexes cover active item listing and
  `document_id` lookup.
- Detach closes the relation; it never deletes Document bytes. Archiving a work
  item or note preserves links and Documents.

### Change History constraint extension

In the same revision, replace `ck_change_history_events_entity_type` while
preserving every current value and add only:

- `work_item`
- `work_item_note`
- `work_item_document`

The current action CHECK already supports all required actions and is not
changed. Work item lifecycle uses `created`, `updated`, `status_changed`,
`deleted` and `restored`; notes use created/updated/deleted/restored; attachment
relations use created/deleted. Descriptions and note text are represented by
bounded length/hash descriptors in audit, never copied verbatim. No file path,
STT audio, token or secret enters Change History.

### Migration behavior and rollback

- Upgrade creates the three empty tables, constraints and indexes, then extends
  the Change History entity CHECK. There is no backfill and no rewrite of
  Project, Inspection, Client, Document, Activity or historical note data.
- Isolated acceptance must perform upgrade → downgrade → re-upgrade from the
  exact parent, verify one Alembic head, original counts unchanged, FK/CHECK/
  index behavior, and invalid enum/time/ownership combinations rejected.
- Downgrade restores the exact prior Change History CHECK and drops only the
  three new tables in dependency order. Because that destroys feature data,
  production downgrade is allowed only while all three tables and matching
  Change History events are empty, or after a separately approved/exported
  rollback plan. The migration must fail closed when that precondition is not
  met.

## 4. Service and API contract

All endpoints require active-user JWT. Actor fields are never accepted from
the client.

### Work items

- `GET /api/v1/work-items` — paginated list, default 50, maximum 200.
- `POST /api/v1/work-items` — create.
- `GET /api/v1/work-items/{work_item_id}` — canonical detail.
- `PATCH /api/v1/work-items/{work_item_id}` — allowlisted update with
  `expected_version`.
- `POST /api/v1/work-items/{work_item_id}/status` — explicit status transition
  with `expected_version`.
- `DELETE /api/v1/work-items/{work_item_id}` — confirmed soft archive.
- `POST /api/v1/work-items/{work_item_id}/restore` — explicit restore.
- `GET /api/v1/work-items/assignees?search=...` — bounded active-user picker.

List filters are server-side and applied before pagination: repeated item type,
status and priority; assignee; Client; start/due ranges; search over title,
description and party; and `include_archived=false`. Sort allowlist is
`upcoming`, `created_newest`, `created_oldest`, `priority`; every sort has an ID
tie-break. No arbitrary field/order expression is accepted.

### Notes

- `GET /api/v1/work-items/{id}/notes`
- `POST /api/v1/work-items/{id}/notes`
- `PATCH /api/v1/work-items/{id}/notes/{note_id}`
- `DELETE /api/v1/work-items/{id}/notes/{note_id}` (soft archive)
- `POST /api/v1/work-items/{id}/notes/{note_id}/restore`

### Documents

- `GET /api/v1/work-items/{id}/documents`
- `POST /api/v1/work-items/{id}/documents` links an authorized existing
  Document, optionally to a note.
- `POST /api/v1/work-items/{id}/documents/upload` is a thin transactional
  adapter over the existing `DocumentService` upload/storage pipeline, not a
  second uploader/store.
- `DELETE /api/v1/work-items/{id}/documents/{document_id}` detaches only the
  active relation.

The service rejects cross-Client ambiguity: a Document canonically owned by a
different Client cannot be attached to a Client-linked work item. A new upload
for a Client-linked work item uses that Client in the canonical Document call
and creates the work-item relation atomically. An unlinked existing Document
can be projected into Client Documents through its active work-item relation
without rewriting the Document row. Responses reuse authorized Document IDs,
content and thumbnail endpoints and never expose storage paths.

## 5. Client, Documents and Timeline integration

- Client Details adds a reusable Work Items panel and an `Utwórz realizację`
  action. The create form receives only the Client ID/name as safe defaults.
- A Client-linked `realization` appears by querying `work_items` with
  `client_id` and `item_type=realization`; no copied row is created.
- The panel shows title, status, dates, assignee, priority and a deep link to
  `/tasks/{id}?return_to=/clients/{client_id}`.
- Client Documents expands its canonical query with active
  `work_item_documents → work_items` provenance. It deduplicates by Document ID
  and labels origin with technical WorkItem/note IDs. Existing direct Client
  documents remain unchanged.
- Timeline derives Client-linked work-item creation, status/completion and note
  events directly from canonical tables using stable keys such as
  `work-item:{id}:created`, `work-item:{id}:completed` and
  `work-item-note:{id}:created`. It extends the typed response with WorkItem ID
  and `/tasks/{id}` deep links. It does not persist matching
  `client_activity_events`, preventing duplicate timeline events.
- Attachment timeline projection must choose one source per Document: the
  existing canonical Document event when `documents.client_id` matches, or the
  relation event when visibility comes only through a WorkItem link.

## 6. Flutter contract

### Tasks and calendar workspace

- Add the primary navigation destination `Zadania` at `/tasks`, canonical detail
  `/tasks/:workItemId`, and preserve `return_to` for Client context and Android
  Back behavior.
- Workspace supports paginated list/agenda, month navigation, today/upcoming,
  indicators, create/detail/edit, explicit status changes, archive/restore and
  filters matching the server contract.
- Use Flutter SDK widgets (`DateUtils`, `GridView`, bounded agenda lists) unless
  implementation evidence demonstrates a missing capability. No calendar
  dependency is currently installed, so a heavy package is not justified.
- Create/edit forms expose type, title, description, start/end or deadline,
  all-day/timezone, status, priority, active assignee, optional searchable
  existing Client and optional party. They never create a Client.
- The shared internal routes are `/tasks` and `/tasks/:id`; Client and Document
  links reuse `/clients/:id` and `/documents?document_id=...`.

### Dashboard boundary with CHUNK 12

CHUNK 13 supplies a reusable `DashboardWorkItemsPanel` and its real data source:
compact calendar/agenda, today/upcoming tasks and a link to `/tasks`. It may
replace the existing dead `Zadania: 0` placeholder additively. The broader
Dashboard ordering/removal work remains CHUNK 12 and is not part of CHUNK 13.

### Notes and field intake

- Notes use a responsive editor and append final Android STT transcription at
  the cursor/with safe whitespace. Audio is never saved or uploaded.
- File/image selection and camera/gallery reuse Document intake. On explicit
  camera/gallery action the shared foreground location service attempts a
  position. Denied, permanently denied, disabled or failed location continues
  upload without GPS and without background permission.
- GPS metadata remains on the canonical Document columns; no latitude/longitude
  columns are added to work items or notes.
- Existing 100 px thumbnails and `InternalImageViewer` render supported images.
  Lists are lazy and responsive at 360/390/600/1200 widths.
- Reminder baseline means a calendar/task entity only. OS/local notification
  scheduling and platform permission UX require a separate scope and are not
  silently included.

## 7. Data safety and performance

- No Client, Project, Inspection, Candidate, historical note or Activity
  backfill.
- No Client creation/matching from `party_name`; no Qdrant write, Vision replay,
  Gmail/n8n action or background location.
- Document bytes remain canonical and are not duplicated. Detach/archive does
  not remove bytes.
- List/detail and Client projections use bounded queries and eager/batched
  assignee/Client/document data to prevent N+1 behavior.
- Database and service checks jointly protect enum, time, version, note
  ownership and cross-Client attachment invariants.

## 8. Implementation acceptance plan

### Backend and migration

- Isolated migration upgrade/downgrade/re-upgrade, single head, tables empty,
  exact CHECK/FK/index verification, Change History original/new values, and
  invalid constraint cases.
- Create each item type; optional Client/party/assignee; inactive assignee;
  inactive/missing Client; actor derivation; time/all-day validation; status and
  priority allowlists; completion timestamp transitions; optimistic conflict;
  archive/restore.
- Server-side pagination, stable sorting, search and every filter combination,
  including Client realization projection.
- Note create/edit/archive/restore, empty/oversized rejection, note ownership,
  attachment to correct note and no cross-item relation.
- Existing/new Document attachment, atomic upload failure, detachment preserving
  Document, Client Documents provenance/dedupe, cross-Client rejection, content
  authorization and no path disclosure.
- Derived Client Timeline entries, stable deep links and proof that no duplicate
  Activity event is persisted.
- Change History entity/actions, safe field descriptors and rollback when audit
  creation fails.
- JWT 401, inactive-user rejection and shared authenticated visibility. Verify
  no cross-Client filter leakage and no credential data in assignee responses.
- Regression: Projects, Inspections, Documents/Image Preview, Client Details,
  Timeline, Change History, Auth, Matching V2, Mail and Agent read-only.

### Flutter

- Tasks list, agenda/month calendar, today/upcoming, create/edit/detail,
  validation, filters/paging/sort, status transition, archive confirmation and
  stale-write conflict.
- Active assignee picker, searchable Client picker without Client creation,
  party-only item, and `Utwórz realizację` from Client with projection into both
  workspaces.
- Notes, STT append, file/image/camera/gallery, GPS success and GPS denial/error
  continuing upload, attachment thumbnail/internal viewer and retry states.
- Deep links and exact Back/context preservation from Client, Dashboard and
  Document.
- Responsive 360/390/600/1200 tests without overflow, plus Dashboard component
  integration without CHUNK 12 redesign.
- Flutter analyze, focused suite and full suite. Physical Android camera,
  gallery, STT and GPS smoke should be performed when an ADB device exists; if
  absent report `PHYSICAL_ANDROID_CHUNK13_SMOKE = UNVERIFIED` truthfully.

## 9. Approval boundary

Approval of the next step would authorize drafting/testing the exact additive
migration and implementing this bounded domain. It would not authorize a
production migration apply, historical backfill, CHUNK 12/14, notification
scheduling, release, Qdrant/Vision work or destructive cleanup unless the next
prompt explicitly says so.

**STOP: `FOLLOWUP_CALENDAR_TASKS_MIGRATION_APPROVAL_REQUIRED`.**
