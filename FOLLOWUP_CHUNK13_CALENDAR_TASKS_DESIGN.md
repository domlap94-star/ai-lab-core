# FOLLOW-UP CHUNK 13 — Calendar / Tasks / Realizations / Notes design

Status: **IMPLEMENTED / ACCEPTED**

Date: 2026-08-20

Extended-design source baseline: `fe2f9fecc4bdd365380de5e32cfe13faa64a7b7f`

Production DB head audited read-only: `followup_change_history_entity_types_20260820`

Approval gate: supplied by owner; migration and bounded implementation completed

This document began as the production design and now also records the accepted
implementation evidence. It includes the
owner-approved extension for the operational month calendar, absence workflow,
Dashboard quick actions and Android Home Screen Widget. No model, API, Flutter
or Android source, migration file, production schema or business row was
changed as part of either design step.

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

Employee absence is deliberately not a sixth WorkItem type. Its requester,
date-range and approval workflow require the separate `absence_requests`
contract in section 8.

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

- `(start_at, id)` and `(due_at, id)` for the two bounded month-range query
  branches;
- `(status, due_at, id)` and `(assignee_user_id, status, due_at, id)` for task
  and agenda filters;
- `(client_id, item_type, created_at DESC, id DESC)` for Client projection.

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

### `absence_requests`

Absence is one inclusive date range, not one row per day.

| Column | Definition |
|---|---|
| `id` | `BIGINT` primary key, autoincrement |
| `requester_user_id` | `BIGINT NOT NULL`, FK `users.id ON DELETE RESTRICT` |
| `absence_type` | `VARCHAR(24) NOT NULL` |
| `start_date` | `DATE NOT NULL` |
| `end_date` | `DATE NOT NULL` |
| `status` | `VARCHAR(24) NOT NULL DEFAULT 'requested'` |
| `note` | `TEXT NULL` |
| `reviewed_by_user_id` | `BIGINT NULL`, FK `users.id ON DELETE RESTRICT` |
| `reviewed_at` | `TIMESTAMPTZ NULL` |
| `review_note` | `TEXT NULL` |
| `cancelled_by_user_id` | `BIGINT NULL`, FK `users.id ON DELETE RESTRICT` |
| `cancelled_at` | `TIMESTAMPTZ NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `version` | `INTEGER NOT NULL DEFAULT 1` |

CHECK constraints:

- absence type in `vacation|day_off|sick_leave|other`;
- status in `requested|approved|rejected|cancelled`;
- `end_date >= start_date`, version greater than zero;
- note at most 5,000 and review note at most 2,000 characters;
- approved/rejected requires reviewer and reviewed timestamp; requested has no
  review or cancellation fields; cancelled requires canceller and cancellation
  timestamp. A cancelled formerly approved request may retain its review
  provenance.

There is no archive/delete endpoint: cancellation is the historical-preserving
domain transition. Regular users may cancel only their own `requested` row.
Administrators may cancel a requested or approved row. Approved dates are not
edited silently; correction means cancellation and a new request.

Active `requested|approved` ranges cannot overlap for the same requester.
Create/update performs a transaction-scoped PostgreSQL advisory lock keyed by
requester ID and then an overlap query. This covers the empty-range race without
adding `btree_gist` or a broad table lock. A conflict returns typed HTTP 409
`absence_overlap`; rejected/cancelled rows do not block.

Indexes:

- `(requester_user_id, status, start_date, end_date, id)`;
- `(status, start_date, end_date, id)`.

### Change History constraint extension

In the same revision, replace `ck_change_history_events_entity_type` while
preserving every current value and add only:

- `work_item`
- `work_item_note`
- `work_item_document`
- `absence_request`

The current action CHECK already supports all required actions and is not
changed. Work item lifecycle uses `created`, `updated`, `status_changed`,
`deleted` and `restored`; notes use created/updated/deleted/restored; attachment
relations use created/deleted; absence review/cancellation uses
`status_changed`. Descriptions, work-item notes, absence notes and review notes
are represented by bounded length/hash descriptors in audit, never copied
verbatim. No file path, STT audio, token or secret enters Change History.

### Migration behavior and rollback

- Upgrade creates the four empty tables, constraints and indexes, then extends
  the Change History entity CHECK. There is no backfill and no rewrite of
  Project, Inspection, Client, Document, Activity or historical note data.
- Isolated acceptance must perform upgrade → downgrade → re-upgrade from the
  exact parent, verify one Alembic head, original counts unchanged, FK/CHECK/
  index behavior, and invalid enum/time/ownership combinations rejected.
- Downgrade restores the exact prior Change History CHECK and drops only the
  four new tables in dependency order. Because that destroys feature data,
  production downgrade is allowed only while all four tables and matching
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

### Calendar and absence requests

- `GET /api/v1/calendar/month?year=2026&month=8` — one bounded operational
  calendar projection shared by Dashboard, Tasks and the Android snapshot.
- `GET /api/v1/absence-requests` — own history for User; bounded all-user
  history/filtering for Administrator.
- `POST /api/v1/absence-requests` — submit own request.
- `GET /api/v1/absence-requests/{id}` — requester or Administrator detail.
- `PATCH /api/v1/absence-requests/{id}` — requester may edit only a still
  requested row with `expected_version`.
- `POST /api/v1/absence-requests/{id}/approve`
- `POST /api/v1/absence-requests/{id}/reject`
- `POST /api/v1/absence-requests/{id}/cancel`

Approval/rejection is Administrator-only and self-review is forbidden. Notes
and review notes are absent from calendar DTOs and visible only to the requester
and Administrators in the dedicated detail/history API.

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
- Workspace has `Miesiąc` and `Lista/Agenda` views. Month is the primary visual
  overview and synchronizes its selected day with a bounded agenda. Workspace
  also supports create/detail/edit, explicit status changes, archive/restore
  and filters matching the server contract.
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
a live month calendar, selected/current-day agenda and links to `/tasks`.
Directly below it are `Dodaj zadanie` and `Dodaj absencję`. The first opens the
normal WorkItem form where the user chooses Zadanie, Zlecenie, Realizacja,
Przypomnienie or Wydarzenie; absence has its own request form. This may replace
the existing dead `Zadania: 0` placeholder additively. Removing/reordering the
other cards, menu cleanup and the full Dashboard composition remain CHUNK 12.

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

## 7. Operational Monthly Calendar

The NEXT Stabil calendar is the central operational calendar. It is not Google
Calendar, Android Calendar Provider or system-calendar synchronization.

### Reusable month UX

One shared Flutter `OperationalMonthCalendar` is used by Tasks and Dashboard.
It provides:

- current month/year header, previous/next month and return to today;
- Monday-first six-week grid, today highlight and persistent selected-day state;
- bounded, readable labels/chips in each day cell rather than dots alone;
- a selected-day agenda below the grid on narrow screens and beside it where
  width permits;
- at most 2 labels at 360/390, 3 at 600 and 4 at 1200 logical px per cell, then
  a truthful `+N więcej` affordance opening the day agenda;
- range items projected on each covered day, without creating per-day rows;
- keyboard/focus semantics, high-contrast selected/today states, tooltips and
  screen-reader labels.

The month grid stays bounded even when a day is busy: cell height does not grow
with the number of entries and long labels use one-line ellipsis. Agenda rows
carry the complete safe title and navigation action.

### Shared presentation contract

Domain semantics are defined once in a versioned
`CalendarPresentationContract`, consumed by the shared Flutter component and
serialized into the native widget snapshot. Dashboard does not define its own
mapping and native Android does not reinterpret WorkItem types.

| Kind | Label | Semantic token | Icon token |
|---|---|---|---|
| `task` | Zadanie | `action_primary` | `task` |
| `order` | Zlecenie | `action_secondary` | `order` |
| `realization` | Realizacja | `execution` | `realization` |
| `reminder` | Przypomnienie | `attention` | `reminder` |
| `event` | Wydarzenie | `event` | `event` |
| `absence_requested` | Absencja — oczekuje | `absence_pending` | `absence` |
| `absence_approved` | Absencja | `absence_approved` | `absence` |

Tokens resolve through the current light/dark color scheme with WCAG-readable
foregrounds. Related WorkItem colors are deliberately adjacent rather than six
unrelated bright colors; icon+text always conveys type without relying on
color.

Cancelled WorkItems and rejected/cancelled absences are hidden by default.
Completed WorkItems remain available with a subdued completed treatment.

## 8. Absence Requests

### Workflow and privacy

- Types: `vacation` (Urlop), `day_off` (Dzień wolny), `sick_leave`
  (Chorobowe), `other` (Inne). CHUNK 13 performs no payroll, leave-balance or HR
  entitlement calculation.
- Statuses: `requested`, `approved`, `rejected`, `cancelled`.
- A User and Administrator submit only their own request. Administrator reviews
  requests, but no user—including an Administrator—may review their own row.
- User sees own full request history and the safe shared-calendar projection of
  all approved absences. User additionally sees their own pending request in
  calendar. Administrator sees all requested and approved rows in calendar and
  a bounded pending queue.
- Rejected/cancelled rows remain in history but are absent from the operational
  month by default.
- Calendar displays requester name and absence type inside the authenticated
  app, never the note/review reason. Detail notes are limited to requester and
  Administrators. Change History stores only dates/type/status/technical actor
  IDs plus note length/hash descriptors.

### Self-service and admin UX

`Dodaj absencję` opens a dedicated form: Od, Do, Typ, optional Notatka. It is
not routed through WorkItem creation. A regular employee may edit or cancel an
own `requested` row. After approval, dates/type/note are immutable; correction
requires cancellation and a new request. Administrator has a bounded pending
view with requester, dates, safe type, Approve and Reject. No complex manager
hierarchy or HR subsystem is introduced.

One inclusive `DATE` range is projected onto every covered calendar day.
Overlap protection and audit semantics are defined in the migration section.

## 9. Calendar Projection API

### Month query

`GET /api/v1/calendar/month?year=2026&month=8&timezone=Europe%2FWarsaw`
returns the requested calendar month plus leading/trailing grid dates, using a
server allowlist/ZoneInfo validation for timezone. Year is restricted to
`2000..2100`; month to `1..12`. The server does not accept an arbitrary date or
query expression.

WorkItem inclusion uses explicit branches, never `created_at`:

- start+due: a non-zero half-open interval overlaps grid (`start < grid_end`
  and `due > grid_start`); equal start/due is treated as one instant;
- start-only: start instant is inside grid;
- due-only: due instant is inside grid;
- all-day: stored half-open local-midnight interval is projected in its IANA
  timezone and does not leak onto the end date.

Absence inclusion is `start_date <= grid_end_date AND end_date >=
grid_start_date`. The service projects the single row across inclusive days.

The response contains no descriptions or notes:

```text
year, month, timezone, grid_start, grid_end, generated_at
items[]:
  entity_type, id, calendar_kind, title, start, end, is_all_day
  status, priority, assignee{id, display_name}?
  client{id, name}?
  requester{id, display_name}?, deep_link
day_counts{}, total, truncated
```

The authenticated in-app DTO may contain bounded Client/requester display
names. The Android snapshot sanitizer strips them. WorkItems are capped at
1,000 and absence rows at 500 per grid response. `total`, per-day counts and
`truncated=true` remain truthful; overflow directs to the paginated agenda
rather than silently omitting workload.

The service uses joined/batched User and Client projections—no row-by-row
lookup. Month WorkItems are selected as a `UNION` of indexed start, due and
interval branches, deduplicated by ID. Separate partial B-tree indexes on
`start_at` and `due_at` support this mixed-date contract without prematurely
adding PostgreSQL range/GiST types. Query plans and normal-month response time
must be measured before migration acceptance.

## 10. Dashboard Calendar Contract

CHUNK 13 inserts the live shared month calendar and selected/current-day agenda
into the existing Dashboard. Immediately below are:

- `Dodaj zadanie` → authenticated `/tasks/new`, with choice of Zadanie,
  Zlecenie, Realizacja, Przypomnienie or Wydarzenie;
- `Dodaj absencję` → authenticated `/absences/new`.

The component and provider are exactly the same as the Tasks month view; only
the responsive container is different. CHUNK 13 does not remove/reorder other
Dashboard cards, remove menu sections or perform the broader CHUNK 12 rebuild.

## 11. Android Home Screen Widget

### Audited native baseline and technology

The Android app uses application ID `pl.ailab.app`, namespace/Kotlin package
`com.example.frontend`, a minimal Kotlin `FlutterActivity`, AndroidX,
Java/Kotlin 17, Flutter minSdk 24 and compile/target 36. There is no
Compose/Glance setup, AppWidget, native MethodChannel, WorkManager,
SharedPreferences plugin or external deep-link intent filter.

Use the platform `AppWidgetProvider` plus `RemoteViews`, `GridView`/
`RemoteViewsService` and a bounded agenda collection. This adds no Compose or
Glance dependency and works across the existing API range. Required future
source is limited to Kotlin provider/snapshot/deep-link bridge classes,
receiver registration, widget-provider XML and RemoteViews layouts. At least
4x3 and 4x4/resizable layouts show current month header, compact grid with
markers/short labels, today highlight and a short upcoming agenda. Header/day/
item taps are useful; no destructive action is available.

### Snapshot and update model

Authenticated Flutter calls the month endpoint, applies a dedicated
`WidgetSnapshotSanitizer`, and sends versioned JSON over a narrow MethodChannel
to Android private app-UID SharedPreferences. The snapshot contains only:

- schema version, generated/last-success time and displayed month;
- date, presentation/icon/color token, bounded short title, status/priority;
- entity type, technical ID and allowlisted internal deep-link route.

It never contains JWT/refresh token, Client name/ID, requester name/ID,
absence/work-item notes, descriptions, contacts, email, Document content or
storage paths. Adding the widget is an explicit user action and permits bounded
work titles on the launcher/lock-visible surface; absence labels remain generic
(`Absencja`/`Absencja — oczekuje`). Client and employee names are omitted in the
baseline. The contract assumes launchers may render the widget while the device
is locked; it does not falsely rely on an unlock check. A later title-hiding
preference may tighten this further, but is not required for the safe baseline.

Snapshot refresh occurs after successful work-item/absence mutations and month
refresh, and when the authenticated app enters foreground. `AppWidgetProvider`
system updates redraw the last snapshot and stale timestamp only; they do not
call the backend. No raw token is copied out of secure storage and no periodic
network WorkManager is introduced. Consequently Android background limits do
not produce false real-time promises. Offline/error state displays the last
safe snapshot with `Ostatnia aktualizacja …`; empty/no-snapshot states are
explicit.

### Deep links and cold start

Widget taps use explicit immutable/update-current `PendingIntent`s addressed to
`MainActivity`; no exported arbitrary URL handler is required:

- header → `/tasks?view=month`;
- day → `/tasks?view=month&date=YYYY-MM-DD`;
- item → `/tasks/{id}`;
- absence → `/absences/{id}`;
- optional `+ Zadanie`/`+ Absencja` → `/tasks/new` or `/absences/new`.

The future `MainActivity` bridge retains one validated pending route for cold
start and emits later `onNewIntent` routes. Flutter validates an exact route/
ID/date allowlist. If session restoration/login is required, an auth navigation
coordinator retains the pending destination and consumes it once after active
authentication; it never falls back to performing a write. Widget quick
actions only open forms.

## 12. Authorization Matrix

| Action | User | Administrator |
|---|---:|---:|
| View shared work calendar/work items | Yes | Yes |
| Create/edit shared WorkItem | Yes | Yes |
| Assign another active user | Yes | Yes |
| Submit own absence | Yes | Yes |
| View own absence history/detail | Yes | Yes |
| See all approved absences in safe calendar | Yes | Yes |
| View all absence histories/notes | No | Yes |
| View pending requests of other users | No | Yes |
| Approve/reject absence | No | Yes, except own |
| Cancel own requested absence | Yes | Yes |
| Cancel another requested/approved absence | No | Yes |

This matches the current shared CRM visibility model without inventing managers
or ownership ACLs. Actor/requester/reviewer identity is server-derived.

## 13. Revised Migration Summary

The proposed revision remains `followup_calendar_tasks_20260820`, parent
`followup_change_history_entity_types_20260820`. It now creates exactly:

1. `work_items`;
2. `work_item_notes`;
3. `work_item_documents`;
4. `absence_requests`;
5. the expanded Change History entity CHECK, preserving all existing values and
   adding `work_item`, `work_item_note`, `work_item_document`,
   `absence_request`.

No local-widget database table is needed. Widget snapshots are derived client
cache, not business state. There is no backfill, legacy Project conversion,
historical Activity conversion or per-absence-day row generation. Exact table,
constraint and rollback details earlier in section 3 remain authoritative.

## 14. Data Safety and Performance

- No Client, Project, Inspection, Candidate, historical note or Activity
  backfill.
- No Client creation/matching from `party_name`; no Qdrant write, Vision replay,
  Gmail/n8n action, system-calendar sync or background location.
- Document bytes remain canonical and are not duplicated. Detach/archive does
  not remove bytes.
- Month/list/detail and Client projections use bounded queries and eager/batched
  User/Client/Document data to prevent N+1 behavior.
- Private widget storage contains sanitized projection only and no credential or
  detailed PII.
- Database and service checks jointly protect enum, time, version, note
  ownership, absence overlap and cross-Client attachment invariants.

## 15. Implementation Acceptance Plan

### Backend and migration

- Isolated migration upgrade/downgrade/re-upgrade, single head, four tables
  empty, exact CHECK/FK/index verification, Change History original/new values,
  and invalid constraint cases.
- Create each WorkItem type; optional Client/party/assignee; inactive assignee;
  actor derivation; all-day validation; completion transitions; optimistic
  conflict; archive/restore; server-side filters and stable pagination.
- Create own absence, date validation, requester advisory lock and concurrent
  overlap conflict; approve/reject Administrator; non-admin and self-review
  rejection; own/admin cancellation; approved-edit rejection; optimistic
  conflict; history pagination and privacy.
- Month projection for start-only, due-only, ranged/all-day WorkItems and
  multi-day requested/approved absences; role visibility; rejected/cancelled
  exclusion; result caps, truthful overflow and joined query-count/performance
  assertions.
- Note and canonical Document lifecycle, Client realization/Documents/Timeline
  projections, deep links, Change History safe descriptors and audit-failure
  rollback.
- Regression: Projects, Inspections, Documents/Image Preview, Client Details,
  Timeline, Change History, Auth, Matching V2, Mail and Agent read-only.

### Flutter calendar and absence

- Shared month component at 360/390/600/1200: navigation, today, selected day,
  same-day density, bounded labels, `+N więcej`, agenda sync and all presentation
  kinds/statuses.
- Tasks list/month forms, filters, assignee/Client picker, stale conflicts,
  Client realization and Back/context preservation.
- Dashboard shared month/provider, `Dodaj zadanie`, `Dodaj absencję`, and proof
  no unrelated CHUNK 12 composition change.
- Own absence create/edit/cancel/history; Administrator pending/approve/reject;
  no notes/reasons in calendar cells.
- Notes, STT append, file/image/camera/gallery, GPS denial/error continuing
  upload, thumbnail/internal viewer and retry states.

### Android widget

- Kotlin snapshot sanitizer/codec rejects unknown schema, oversize fields,
  forbidden PII/token keys and non-allowlisted routes.
- Native month rendering, today, tasks, multi-day absence, `+N`, agenda, empty
  and stale/offline states, 4x3/4x4 resizing and RemoteViews collection IDs.
- Cold/warm deep links to calendar day, WorkItem and absence; unauthenticated
  route preservation through login; quick actions open forms only.
- Static/runtime proof that widget SharedPreferences contains no JWT, Client
  PII, employee names, notes or descriptions.
- Flutter analyze, focused and full suite; Kotlin unit/Robolectric tests and
  Android instrumentation where available. Physical device smoke covers add/
  resize/refresh/offline/cold-start taps. If absent, report
  `PHYSICAL_ANDROID_WIDGET_SMOKE = UNVERIFIED` and
  `PHYSICAL_ANDROID_CHUNK13_SMOKE = UNVERIFIED` truthfully.

## 16. Approval Boundary

Approval of the next step would authorize drafting/testing the exact expanded
additive migration and implementing this bounded domain. It would not authorize
a production migration apply, historical backfill, CHUNK 12/14, Android or
Google Calendar sync, notification scheduling, release, Qdrant/Vision work or
destructive cleanup unless the next prompt explicitly says so.

## 17. Implementation evidence

- Migration `followup_calendar_tasks_20260820` was tested on the explicitly
  isolated `ai_lab_chunk13_20260820` database (upgrade/downgrade/re-upgrade)
  and applied to production. Production has one Alembic head and zero rows in
  `work_items`, `work_item_notes`, `work_item_documents` and
  `absence_requests`; existing CRM counts did not change.
- The backend follows this document's single WorkItem model, separate absence
  workflow, canonical Document links, safe Change History descriptors and
  derived Client Timeline. Month projection is joined/bounded (1000 work
  items, 500 absences), and Timeline work-item events use one bounded union
  query with an exact window-count rather than N+1 queries.
- Flutter reuses one operational month widget on Dashboard and in Zadania at
  360/390/600/1200 widths. It provides list/month, selected-day agenda,
  create/edit/detail, Client and assignee selection, realization-from-Client,
  notes/STT, canonical attachments, foreground GPS, internal image preview and
  employee/Admin absence actions.
- Android uses an `AppWidgetProvider` with `RemoteViews` and MODE_PRIVATE local
  snapshot. Snapshot generation strips absence/employee labels, Client PII,
  notes, descriptions and tokens, is capped, retains last safe state and uses
  non-destructive deep links. Android debug compilation passed; no physical
  ADB device was connected, so physical widget and field-intake smoke is
  unverified.
- CHUNK 12 and CHUNK 14 were not started. No release, Gmail/n8n operation,
  Vision job, Qdrant write or historical backfill was performed.

**NEXT PLANNED WORK: FOLLOW-UP CHUNK 12 — DASHBOARD REBUILD. A new owner prompt
is required.**
