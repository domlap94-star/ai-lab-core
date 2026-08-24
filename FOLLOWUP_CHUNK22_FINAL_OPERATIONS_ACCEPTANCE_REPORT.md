# CHUNK22 final operations acceptance — schema-gated checkpoint

Date: 2026-08-24

Source HEAD at audit: `ca27b7d1e4c0a4ac2b41013db1d6ebaa3d36b1ad`

Stable: NEXT Stabil `1.0.2+29`

State: `CHUNK22 IN PROGRESS / BACKUP PLANNER SCHEMA APPROVAL REQUIRED`

## Follow-up state

- CHUNK20: COMPLETE
- CHUNK21: COMPLETE
- CHUNK22: active; physical System Control recheck and owner-expanded backup
  operations acceptance remain incomplete
- PRE-CHUNK23 AI: F0 END-TO-END QUALIFIED / architecture ready for owner
  implementation decision
- CHUNK23: BLOCKED / NOT STARTED
- Release F: NOT STARTED

## System Control

Source architecture remains Android/Web -> authenticated public backend
`/api/v1/admin/system-status` -> private loopback Supervisor. Android/Web host
control stays disabled and public `/control` remains unavailable. A focused
in-container assertion confirms private Supervisor transport failure maps
Backend to `online` and Supervisor/NEXT Stabil to `unknown`, not false
`offline`. Public backend, Supervisor and public gateway health endpoints each
returned HTTP 200.

ADB was found at
`C:\Users\domai\AppData\Local\Android\Sdk\platform-tools\adb.exe`, but no
authorized physical device was attached. No Android candidate was built because
the required schema gate stops CHUNK22 before implementation and final physical
acceptance. The same-device recheck therefore remains pending.

## Scheduler audit

PostgreSQL `backup_schedules` is the intended canonical configuration and
Windows Task Scheduler is a bounded projection. Current live state is healthy:
three enabled NEXT Stabil-owned tasks are Ready under the unchanged `domai` /
Limited identity with last result `0`; the fourth disabled database schedule
has no task. The Node scheduler suite reports
`BACKUP_SCHEDULER_TESTS=PASS`.

The reliability defect is nevertheless proven in source: create, update and
delete call host reconciliation before database commit. A host success followed
by SQL rollback can create durable divergence. There is no committed revision
outbox, task projection can race an uncommitted create/delete, and a preview
failure collapses all rows to transient `sync_failed` without persisted last
sync/error/retry state. This must be repaired transactionally, not masked by UI
refresh timing.

## Manual backup and planner

Current manual backup has a fixed `C:\ai-lab-core-backups` default in both the
backend request schema and Flutter page. The existing `file_picker` dependency
can support a native Windows folder chooser, but the safe API change must be
additive for deployed +29 consumers. Android/Web must state that host-path
selection is Windows-host only.

The current schema cannot persist the requested per-destination identity,
availability, reserve, retention, protected/managed history, reconciliation or
deletion journal state. The approved implementation design, compatibility
boundary, migration fields and isolation rules are documented in
`FOLLOWUP_BACKUP_PLANNER_RETENTION_REPORT.md`.

## Retention/delete safety

No retention implementation or filesystem deletion ran. The design permits
automatic deletion only for positively cataloged, manifest-verified backup
objects owned by the exact plan/root. Automatic deletion defaults off. The
minimum keep floor, protected/current/restoring exclusions, oldest-first order,
wrong-root/reparse/cross-plan controls and an append-only deletion journal are
mandatory. Existing V1 checkpoints are not automatically adopted.

## Production health and safety

- backend health: PASS
- Supervisor health: PASS
- public gateway health: PASS
- production DB: `followup_contact_person_20260822` (head; pending migrations 0)
- customer Qdrant: green, 57 points
- Knowledge Base Qdrant: green, 0 points
- scheduler projection test: PASS
- focused System Control projection smoke: PASS
- full pytest rerun: unavailable in the production backend image (`pytest` is
  not installed); no test dependency was installed into production
- business/customer writes: 0
- production DB migrations: 0
- production backup deletions: 0
- synthetic backup deletions: 0
- Qdrant writes/deletes: 0/0
- Gmail/n8n/AI model changes: 0
- real-customer Temporary Chat/Vision: 0
- stable manifest/release writes: 0

## Decision

`BACKUP_PLANNER_SCHEMA_APPROVAL_REQUIRED`

Required owner token:

`FOLLOWUP_BACKUP_PLANNER_SCHEMA_MIGRATION_APPROVAL_REQUIRED`

CHUNK22 is not complete. Do not start CHUNK23 or Release F.
