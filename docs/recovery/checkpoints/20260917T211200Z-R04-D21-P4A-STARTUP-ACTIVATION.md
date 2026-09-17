# Checkpoint R04 / D-21 / P4-A — startup activation package

- Checkpoint UTC: `2026-09-17T21:12:00Z`
- Parent HEAD: `c936643b0360cd5a78e72c9d1cc51467edbd83c1`
- Branch: `recovery/next-stabil-repair-completion`
- Decision: `D-21`
- Package ID: `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z`
- Status: `STARTUP_ACTIVATION_PACKAGE_READY_FOR_REVIEW / NOT_INSTALLED`

## Owner acceptance recorded

The owner accepted the completed P3 backend-only switch as
`CORE_BACKEND_SOURCE_SWITCH_ACCEPTED / LIMITED_RUNTIME_SCOPE` for OP_ID
`R04-D21-P3-CORE-SWITCH-20260917T141404Z`, source
`0ee0ea50943578e6e552aae23ce1688595ddc262`, phase-B evidence
`d792eb3886cacfeb80aa08d8cf03b872319d4b8b`, and runtime readback evidence
`c936643b0360cd5a78e72c9d1cc51467edbd83c1`.

The acceptance remains limited: it is not a direct in-memory `Settings`
observation, historical dispatcher audit, global no-write proof, full P3/R04
acceptance, or authorization for another runtime mutation.

## Work completed in P4-A

1. Read current metadata for the six known `ai-lab-core` containers. All were
   running with the recorded full IDs, image IDs, mounts, ports, one network,
   `unless-stopped`, and `RestartCount=0` at `2026-09-17T20:54:22Z`.
2. Read ten exact NEXT Stabil tasks. No `NEXT Stabil - Host` task exists.
   Public/Private/Supervisor tasks combine executor and logon-trigger roles;
   Backup 1/2/3 and Trash Purge remain separate schedules.
3. Read exact Startup wrapper and manual shortcut. The wrapper points to the
   currently absent canonical launcher, so it must be disabled before the file
   is installed. The manual shortcut remains the UI entry because
   `OPEN_AFTER_BASE_READY` is not implemented.
4. Prepared an inactive local package containing the three-file payload,
   rollback XML for five startup tasks, rollback copies of the two user
   entries, and a disabled host-task XML draft.
5. Prepared the review documents:
   - `docs/recovery/R04_D21_P4_STARTUP_ACTIVATION_PLAN.md`
   - `docs/recovery/R04_D21_P4_STARTUP_CHANGESET.csv`
   - `docs/recovery/R04_D21_P4_STARTUP_SET_DRAFT.json`

## Evidence boundaries

- Local package index SHA-256:
  `DC76525E49B77C7CA791B9724D38F9E26C2FC7FDA8513A2403B7D167481ACB72`
  for 16 payload/rollback/draft files.
- RepoDigest projection and the separate Qdrant volume-metadata projection did
  not yield usable values and were not retried. Those fields remain `UNKNOWN`.
- Listener/process projection did not produce a complete bounded snapshot;
  Public Gateway is supported by task state and HTTP `200`, while current
  listeners for 8787/8788 remain `NOT_OBSERVED` in P4-A.
- Safe HTTP results at `2026-09-17T21:00:51Z`: backend health `200`, public
  gateway health `200`, public `/control` `404`. A formatting loss in the new
  `/version` projection was not retried; the accepted P3 readback remains the
  source/schema evidence.
- No SQL, docker exec, service/task start, stop, restart, registration, import,
  launcher execution, backup, restore, data write, mount change, or junction
  change occurred.

## Open gates

- `GLOBAL_START_MANIFEST_NOT_APPROVED`.
- Container RepoDigests and Qdrant/Docker VHD physical backing unresolved.
- `OPEN_AFTER_BASE_READY_NOT_IMPLEMENTED`; manual UI shortcut remains separate.
- P4-B task/trigger/file installation and operational tests are not authorized.
- Scheduled backup success remains
  `SCHEDULED_BACKUP_OPERATION_NOT_YET_VERIFIED / REPAIR_PENDING`.
- VHD/profile/Qdrant relocation and full D-21 data placement remain open.
- Supervisor remains `INTENTIONALLY_STOPPED / NOT_STARTED_BY_THIS_SESSION`.

## Next safe step

Owner review of the exact P4-A package, followed by a separate P4-B decision
that names the precise trigger changes, file installation, manifest approval,
operational window, tests, and rollback. No part of that sequence is authorized
by this checkpoint.
