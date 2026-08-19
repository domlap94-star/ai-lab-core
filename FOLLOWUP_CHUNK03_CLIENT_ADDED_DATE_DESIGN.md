# FOLLOW-UP CHUNK 03 — CLIENT ADDED DATE DESIGN

Audit date: 2026-08-19  
Source HEAD: `c481d74f411d779978dc6ac963a665760e9290f9`  
Release: `NEXT Stabil 1.0.2+21`  
Design baseline DB revision: `chunk16audit_20260819`
Current DB revision: `followup_clientdate_20260819`

Status: **IMPLEMENTED / VERIFIED / NOT RELEASED**

Approved gate: `FOLLOWUP_CLIENT_SCHEMA_MIGRATION_APPROVAL_REQUIRED`

## Implementation result

The approved migration `followup_clientdate_20260819` passed an isolated
upgrade/downgrade/re-upgrade drill and is the live single Alembic head. It added
only `clients.client_added_at DATE NULL`; all 3243 historical rows remained
NULL and no Client data was backfilled.

The backend now exposes `client_added_at` and canonical
`effective_added_date`, validates set/clear and date bounds, and sorts newest or
oldest before pagination with Client ID as the deterministic tie-breaker.
`created_at`, source evidence, and workflow effective dates remain separate and
immutable under this update.

Flutter uses the server-projected effective date for list/details, offers a
bounded date picker and explicit clear action, and does not reproduce the
fallback hierarchy. Isolated backend tests, current read-only contracts,
Flutter analyze, focused `22/22`, full `174/174`, runtime API smoke, and the
production health aggregate passed. The client release remains
`NEXT Stabil 1.0.2+21`; publication is deferred to Release A.

## Evidence and semantic decision

The live `clients` table has no persisted, operator-editable business added
date. Its current date-related concepts are intentionally distinct:

| Field/projection | Meaning | Mutable | Source | Current use |
|---|---|---:|---|---|
| `clients.created_at` | Technical timestamp at which the CRM row was created | No | PostgreSQL `now()` through `TimestampMixin` | Technical record age and fallback display/sort date |
| `clients.updated_at` | Technical last-update timestamp | Indirect only | SQLAlchemy lifecycle | Technical recency; not an added date |
| `source_record_date` | Read-only projection of the earliest valid `DATA` value from a linked Google Sheets source row | No | `ClientSourceRecordDateService`; not a Client column | Current primary display/sort date where available |
| `client_workflow_statuses.effective_date` | Date on which a workflow status is effective | Yes through workflow operations | Workflow status record | Status semantics only |
| Candidate/source timestamps | Ingestion, message, or source-record evidence | No through Client edit | Candidate/source records | Provenance, reconciliation, ingestion |

`clients.created_at` is an immutable technical/audit timestamp and must not be
edited. `source_record_date` is source evidence and must not be overloaded with
an operator-entered value. `workflow_effective_date` describes another business
concept. Therefore a new persisted Client field is required.

Live, read-only evidence:

- Clients: 3243 total, 3237 active, 6 soft-deleted.
- Active Clients with a valid projected `source_record_date`: 1010.
- Active Clients using `created_at` as the current fallback: 2227.
- Active Clients with NULL `created_at`: 0.
- Source-date range: 2023-01-02 through 2026-08-17.
- No `client_added_at` or equivalent column exists in the live schema.
- Workflow effective dates exist for 2 workflow rows and remain separate.
- Ungranted database locks during the audit: 0.

No customer names, contact data, source payloads, or document content were read
into this report.

## Proposed additive migration

- Proposed revision: `followup_clientdate_20260819`.
- Parent: `chunk16audit_20260819`.
- Operation: add `clients.client_added_at DATE NULL`.
- Server default: none.
- Historical backfill: none.
- Existing rows remain NULL, preserving the distinction between an explicit
  operator value and a derived fallback.
- Index: none initially. With 3243 Clients and a composite fallback that also
  uses projected source evidence, an index on this nullable column alone does
  not cover the effective ordering and is not justified by current evidence.
- No trigger and no rewrite of existing rows.

The isolated migration test must verify upgrade, downgrade/re-upgrade, unchanged
Client counts and timestamps, NULL for all historical `client_added_at` values,
and a single Alembic head. Production apply requires the explicit human gate.

Downgrade drops only the new column. Before any real downgrade after users have
entered values, the deployment must first stop relying on the field and export
its explicit values because the downgrade necessarily discards that new data.
Production downgrade is not part of this design step.

## Canonical projection

One backend service/helper will expose `effective_client_added_date`:

1. explicit `client_added_at`, if set;
2. projected `source_record_date`, if valid;
3. `created_at.date()`.

The API, sorting service, Client list, and Client details must consume this one
projection. Flutter must not reimplement the fallback hierarchy.

The read response will be extended additively with:

- `client_added_at: date | null`,
- `effective_added_date: date`.

An optional bounded discriminator such as
`effective_added_date_source: explicit | source | created` may be added only if
needed to explain the clear/fallback behavior in UI. Existing fields, including
`source_record_date`, `created_at`, and workflow fields, remain unchanged for
deployed clients.

## Update and validation contract

`ClientUpdate` will accept `client_added_at: date | null`. Pydantic's existing
`exclude_unset=True` path distinguishes an omitted field from explicit NULL:

- omitted: do not change the value;
- ISO date: set the explicit business date;
- explicit NULL: clear the override and return to canonical fallback.

Validation permits a real calendar date no later than the current local
business date. A lower bound will be explicit in UI (proposed 1900-01-01) but
will not rewrite or reinterpret source dates. Permissions remain the same as
the existing authenticated Client edit endpoint. Full actor/change history is
deferred to FOLLOW-UP CHUNK 07; this chunk must not misuse Agent audit, user
lifecycle events, or document-link audit. The field-specific PATCH remains
compatible with future before/after change auditing.

Mandatory invariants for update tests:

- `created_at` is byte-for-byte/instant-equal before and after the business-date
  update;
- `source_record_date` source evidence is unchanged;
- workflow `effective_date` is unchanged;
- setting and clearing are both persisted correctly.

## Sorting contract

The existing paginated backend contract remains:

- `sort_order=newest` (default),
- `sort_order=oldest`.

Its semantics become ordering by `effective_client_added_date`, not a Flutter
local sort. The current backend already gathers filtered candidate IDs, orders
them server-side through `ClientSourceRecordDateService`, then applies
pagination. The implementation will extend that canonical service with the
explicit Client column and keep search/type/industry filters intact.

Deterministic keys:

- newest: effective date DESC, Client ID DESC;
- oldest: effective date ASC, Client ID ASC.

Because every active Client has non-NULL `created_at`, the projection is never
NULL and PostgreSQL-specific NULL ordering cannot affect pages. Existing rows
without an explicit value retain their current effective dates and ordering.

Required fixture matrix:

- explicit old date;
- explicit new date;
- NULL plus source date;
- NULL without source date (technical fallback);
- equal effective date with different IDs;
- ASC and DESC;
- pagination boundary;
- search plus each sort order.

## UI design after approval

- Client edit dialog: `Data dodania` date picker, formatted `dd.MM.yyyy`.
- Clear action: removes only the explicit override and explains that the
  source/technical fallback will be used.
- Client list: `Dodano: dd.MM.yyyy`, driven by `effective_added_date`.
- Client details: `Data dodania: dd.MM.yyyy`, driven by the same API projection.
- Sorting control retains `Data dodania: najnowsi/najstarsi`.
- Local timezone formatting changes presentation only; stored `DATE` has no
  time or timezone conversion.
- Responsive and Back behavior must be verified at 360, 390, 600, and 1200 px.

## Required implementation verification after approval

Backend:

- migration isolated upgrade/downgrade/re-upgrade and row preservation;
- Client create/read/update, explicit set, explicit clear, and fallback;
- future-date rejection;
- `created_at`, source evidence, and workflow effective date immutability;
- ASC/DESC, deterministic tie-break, pagination, and query plus sort;
- current permissions/auth, additive response compatibility, and CHUNK 02
  canonical workflow-status regression.

Flutter:

- date picker, save, clear, full-year display, list/details and sorting;
- responsive widths and navigation/Back;
- status display remains canonical;
- `flutter analyze`, focused tests, and full suite.

## Safety state of this design step

- Production Client writes: 0.
- Synthetic writes: 0.
- Migration created/applied: no.
- Historical rows touched: 0.
- Qdrant writes: 0.
- n8n changes: 0.
- Vision jobs: 0.
- Emails sent: 0.
- Cleanup: 0.
- Release: not performed; remains `NEXT Stabil 1.0.2+21`.
