# CHUNK22 final operations acceptance — COMPLETE

Date: 2026-08-24

Source HEAD at audit: `ca27b7d1e4c0a4ac2b41013db1d6ebaa3d36b1ad`

Stable: NEXT Stabil `1.0.2+29`

State: `CHUNK22 COMPLETE / OWNER MANUAL +32 PHYSICAL ACCEPTANCE PASS`

## Follow-up state

- CHUNK20: COMPLETE
- CHUNK21: COMPLETE
- CHUNK22: COMPLETE; owner manual +32 physical acceptance passed
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
- production DB at schema gate: `followup_contact_person_20260822`; current
  head after approved apply: `followup_backup_planner_retention_20260824`
  (pending migrations 0)
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

## Approved planner implementation checkpoint

The schema approval was consumed for revision
`followup_backup_planner_retention_20260824`. Its isolated upgrade/downgrade/
re-upgrade proof passed, then production advanced to that exact head. Existing
schedule rows remain 4, existing backup runs remain 7, managed backups are 0,
deletion events are 0, and no historical V1 checkpoint was rewritten/adopted.

Durable outbox reconciliation is revision-aware and restart-driven. The three
enabled V2-owned tasks are Ready with last result 0; the disabled fourth plan
has no task. Manual V2 destination preflight/picker, independent planner
policies, managed catalog, dry-run retention and synthetic-only deletion safety
are implemented. Real deletion remains blocked by the unconsumed
`FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED` gate.

Flutter analyze, focused Backup UI and full `293/293` pass. Backend planner,
legacy Backup/Restore, security/auth, System Control, scheduler, storage and
PowerShell checks pass. Backend/Supervisor/arbiter and Qdrant 57/0 remain
healthy.

The signed non-stable Android `1.0.2+30` candidate was built, but ADB has no
attached physical device. CHUNK22 is therefore not complete. Exact next action:
same-device install over +29 with data preserved, followed by Backend,
Supervisor, NEXT Stabil, refresh, network recovery, session restoration,
logout/login and force-close/reopen acceptance.

Decision: `CHUNK22_PHYSICAL_RECHECK_REQUIRED`. Do not start CHUNK23 or Release F.

## Remote control and legacy-backup remediation — 2026-08-24

Physical candidate +30 proved Backend, Supervisor, NEXT Stabil, Postgres,
Qdrant, Ollama, backend container, n8n and Open WebUI ONLINE. The former false
OFFLINE projection defect is therefore closed. Owner acceptance identified two
remaining product gaps: control buttons were host-only and verified historical
V1 checkpoints could not be added to the V2 catalog.

The additive control path is now Android/Web -> authenticated admin backend ->
short-lived command/session-bound single-use token -> exact loopback Supervisor
command -> bounded post-command verification. Only `start`, `stop` and
`restart` are accepted. Public `/control` remains 404, unauthenticated preflight
returns 401, and direct unauthenticated Supervisor status returns 401. The
Supervisor controls only the fixed Qdrant/Ollama/n8n/Open WebUI workload set;
backend and Postgres remain available as the command/result control plane. A
live authenticated RESTART returned accepted/succeeded/verified after an
observed stop/start transition. No task definition, firewall or exposure was
changed.

Legacy management is explicit and one-at-a-time. Discovery is bounded to
recognized backup roots and exposes opaque adoption tokens. A selected V1
checkpoint is fully manifest/checksum verified immediately before catalog
insertion; root, manifest hash and optional plan destination must still match.
The insert is idempotent and creates metadata only. It does not move, rename,
rewrite or delete the backup. Production currently remains at zero managed
backups and zero deletion events; no production checkpoint was adopted during
this implementation run. `BACKUP_RETENTION_DELETE_ENABLED=false` and
`FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED` remains unconsumed.

The apparent indefinite checkpoint spinner was caused by serial full checksum
verification of every historical checkpoint during inventory. Inventory now
uses bounded manifest/path/declared-size/reparse checks and deduplicates
canonical paths; a selected restore/adoption still invokes the full verifier.
Read-only production inventory resolved 19 unique valid checkpoints in 0.136 s;
legacy preview exposed 19 adoptable and 8 invalid/unverified unique directories
without making invalid items restore candidates. Flutter distinguishes loading,
loaded-empty and bounded error states and offers retry.

Acceptance gates passed: Supervisor boundary test, backend authorization/token/
replay tests, isolated legacy adoption and duplicate/mismatch tests, Backup
Planner/legacy restore/security/auth/Qdrant guards, Flutter analyze, focused UI
tests and full Flutter `295/295`. DB head remains
`followup_backup_planner_retention_20260824`, Qdrant remains 57/0, and production
backup file mutations/deletions are 0/0.

Non-stable candidate
`NEXT-Stabil-1.0.2+31-chunk22-final-candidate.apk` was built with application ID
`pl.ailab.app`, version `1.0.2+31`, SHA-256
`0549EA6B6CC472E815C8B7B02CFF4EDB9DF96DE13632717832A460F4D0BF1DFE`,
the established signer SHA-256
`5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`,
release cleartext disabled and no debuggable flag. It is not published. ADB
reported no attached device, so install-over, mobile button/adoption UI and
same-device session acceptance remain pending. CHUNK22 is not marked complete.

## Cross-platform backup administration and asynchronous verification — 2026-08-24

Physical +31 acceptance closed the System Control status defect: Backend,
Supervisor and NEXT Stabil display ONLINE, Start is disabled, and Restart/Stop
are enabled. It also exposed the remaining CHUNK22 defects: host backup was
presented as Windows-only, selected legacy verification held an HTTP/database
request open for multi-gigabyte checksum work, failures collapsed to a generic
message, and one verification state could block unrelated Backup sections.

The repaired product rule is Administrator capability parity. Windows, Web and
Android now use the same authenticated backend-mediated host-storage selector.
It returns opaque location capabilities and bounded metadata, permits browsing
only beneath validated registered roots, supports local/mounted and UNC roots,
and never exposes file contents or NAS credentials. Manual backup V3 uses the
same preflight on every platform and binds its short-lived token to the admin,
scope, location and normalized resolved path. No backup was started in this
acceptance run.

Legacy discovery is metadata-only. The observed 27 candidates classified as
11 already managed, 8 needing verification and 8 invalid; unknown dates were
caused by missing/invalid manifests or non-checkpoint directories, not hidden
valid dates. Full verification is now an asynchronous Supervisor job with
per-item states/progress, cancellation, safe restart interruption and retry.
Managed backups, legacy discovery, jobs, checkpoints and history have separate
UI states, so one checksum job cannot create a page-wide spinner. Invalid and
already-managed entries are separated and bounded error codes replace the
generic adoption failure.

The largest retained candidate was 7,986,915,249 bytes (about 7.44 GiB). Its
first uncached checksum proof reached READY_TO_ADOPT in 34.228 seconds while
the managed endpoint remained responsive (8.3 ms p95); a cached verification
completed in 2.013 seconds. No catalog adoption or file mutation was performed
by this runtime proof. Current production managed rows remain 11, reflecting
the owner's earlier +31 attempts; deletion events remain 0.

Repeated bounded endpoint timings were: managed 6.0/14.0 ms p50/p95, legacy
27.7/31.8 ms, checkpoints 25.7/27.2 ms, history 6.7/7.3 ms and storage
11.6/12.0 ms. Initial rendering performs no multi-gigabyte checksum.

Capability source/widget acceptance matrix:

| Administrator capability | Windows | Web | Android |
| --- | --- | --- | --- |
| Manual backup | PASS | PASS | PASS |
| Select host destination | PASS | PASS | PASS |
| Plan CRUD | PASS | PASS | PASS |
| Retention configuration/dry-run | PASS | PASS | PASS |
| Legacy discovery/verification/adoption | PASS | PASS | PASS |
| System status and bounded control | PASS | PASS | PASS |

Backend security/auth, isolated adoption/recovery, Supervisor storage/job,
Backup Planner, Flutter analyze, 15 focused Backup/System Control tests, and
the full Flutter 296/296 suite pass. Production DB head remains
`followup_backup_planner_retention_20260824`; Qdrant remains green at 57/0.
Production backup deletions, adoption-time file mutations, business writes,
AI changes and n8n changes are 0.

The signed, non-stable candidate
`NEXT-Stabil-1.0.2+32-chunk22-cross-platform-candidate.apk` has application ID
`pl.ailab.app`, version `1.0.2+32`, SHA-256
`5AC7EDA17B16231891D1A9FEFDD380A8364BA0F43049DAE8D7D41E1AD8F986DA`,
signer SHA-256
`5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`,
cleartext disabled and no debuggable flag. It is not published. At that
checkpoint ADB reported no attached physical device; the subsequent owner
manual result is recorded below. Stable remains `1.0.2+29` and
`FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED` remains unconsumed.

## Owner manual +32 physical acceptance — PASS

Evidence class: `OWNER MANUAL PHYSICAL ACCEPTANCE`.

On 2026-08-24 the owner completed physical acceptance of the non-stable Android
candidate NEXT Stabil `1.0.2+32` (versionCode 32) and explicitly reported the
overall result as PASS. Automated ADB evidence was unavailable and is not
required because the owner directly exercised and accepted the actual device.
No repeat physical test was performed.

The owner-observed PASS covers truthful Backend, Supervisor and NEXT Stabil
status; absence of the false-OFFLINE defect; correct Start/Restart/Stop states
and Administrator remote-control availability; Android access to host backup
administration and host destination selection; cross-platform planner
administration; responsive V1 discovery and asynchronous per-item
verification/adoption; distinguishable bounded failures; and usable
checkpoint/history loading without a multi-gigabyte page block.

CHUNK22 is complete. Completed scope includes Android/System Control,
authenticated bounded remote control, Administrator capability parity,
transactional scheduler reconciliation, independent multi-destination plans,
cross-platform host selection, manual backup without a fixed default, managed
catalog, explicit V1 adoption, asynchronous verification jobs, checkpoint
loading performance, retention dry-run/free-space planning and synthetic-only
deletion safety.

The candidate remains non-stable and was not published. Stable remains NEXT
Stabil `1.0.2+29`; versionCodes 30, 31 and 32 are consumed. Production backup
deletion remains disabled (`BACKUP_RETENTION_DELETE_ENABLED=false`), production
backup deletions remain 0, and
`FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED` remains unconsumed. The
next owner-directed work is PRE-CHUNK23 Unified Assistant implementation in a
separate bounded execution; CHUNK23 remains BLOCKED / NOT STARTED.
