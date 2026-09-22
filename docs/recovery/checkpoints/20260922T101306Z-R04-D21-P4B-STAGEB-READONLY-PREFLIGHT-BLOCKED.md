# R04 / D-21 / P4-B — VerifyOnly accepted, Stage-B read-only preflight partial

- UTC checkpoint: `2026-09-22T10:13:06Z`
- entry/evidence HEAD: `9370984f2d7437092928d566a866ee38c3bbcd1d`
- decision/window ID: `R04-D21-P4B-STAGEB-PREFLIGHT-20260922T094610Z`
- package operation ID: `R04-D21-P4B-HOST22-NUP-20260920T200422Z`
- result: `READ_ONLY_PREFLIGHT_PARTIAL / REQUIRED_HOST_SERVICE_LAYER_NOT_VALIDATED / STAGE_B_BLOCKED_NOT_AUTHORIZED`

## VerifyOnly acceptance

Owner acceptance is recorded only as
`P4B_VERIFYONLY_TASK_AND_FILE_EVIDENCE_ACCEPTED / READ_ONLY_SCOPE` for attempt
`R04-D21-P4B-VERIFYONLY-ZIP-RESTORED-20260922T074412Z`. The preserved result is
exit `0`, `55349.381 ms`, `VERIFIED_NO_MUTATION`, mutation/pending false, empty
changed roles/warm runs, journal `NOT_OPENED`, rollback `NOT_NEEDED`, and result
`544` B / `F0A51E55F354B97CDE9E4AC31C6FA61C078334A27661BA354B35D69DA20ED5A6`.
The attempt was not repeated.

## Read-only preflight

- frozen package: top-level `4/4`, payload bindings `8/8`;
- six exact pinned containers: `6/6` identity/state/image/digest/name/label/mount/
  port/network PASS; PostgreSQL `running+healthy`;
- backend remained the pinned ID
  `686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854`,
  image `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
  `/app` read-only and `/data` read-write;
- HTTP: backend `/health` `200`, `/version` `200`, gateway health `200`, public
  `/control` and `/control/health` `404`;
- Windows available memory, commit reserve, C: and D: free-space gates: PASS;
- Docker/WSL pool availability and current swap use: `UNKNOWN` and explicitly
  not promoted to PASS;
- future output `C:\Users\domai\AppData\Local\Temp\P4B-WIN-01\apply` was
  reserved as metadata and remains absent.

## Blocking evidence boundary

The host-service observations were invoked under PowerShell `7.6.5`, not the
required Windows PowerShell 5.1. Their saved Public
`CONFLICT / PORT_OWNERSHIP_CONFLICT`, Private `UNKNOWN / OBSERVATION_UNKNOWN`
and Supervisor `UNKNOWN / OBSERVATION_UNKNOWN` therefore do not establish the
current production state and cannot satisfy the Stage-B gate. The later resource
collector used exact
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`, but the successful
Docker/HTTP/resource operations and the failed host observation were not
repeated merely to repair orchestration/formatting.

This is a material K1 for the next operational decision only: Stage B requires
current, authoritative host-service identity/absence/port evidence. It is not a
new product defect and does not reopen Host22/NUP or D-23 review `2/2`.

## Evidence and effects

LOCAL_ONLY root `C:\Users\domai\AppData\Local\Temp\P4B-WIN-01` contains `52`
files / `85924` B. Safe summary: `9721` B /
`A609F946A792452A4F48013797CF7C00725B2DDF8DC343CF5AFF24BDC22E0FCF`.
Evidence index: `8624` B /
`1FD975C40C1DFF1A4844063C5429B8DAFD8DB3F567A6185AA5357D88871DD9E7`.
Raw logs and runtime payload are not committed.

Docker/task/Host/service writes or starts, UAC, installation, warm runs,
rollback, SQL and data changes: `0`. Installed run01 and its historical Host
disabled/no-trigger, warm `0/2`, Private `0`, Supervisor
`INTENTIONALLY_STOPPED` status are preserved; this checkpoint does not claim a
fresh authoritative host-service read.

## One next decision

Authorize one Windows PowerShell 5.1 host-services-only replacement read, using
the already reviewed normalization and without repeating VerifyOnly, Docker,
HTTP or resource gates. Until that read passes, do not present or consume the
Stage-B/UAC confirmation sentence.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Before evaluation and the next prompt, read [roadmap §0, ANTI_EXCESSIVE_WORK and
the active R04 card](../../../NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md) from the
full published SHA containing this checkpoint. Preserve accepted evidence and
do not search for K2/K3. K0/K1: `P4B-PREFLIGHT-HOST-RUNNER` — Stage B lacks an
authoritative PS5.1 host-service gate; evidence is the persisted runner context
and three nonauthoritative observations. Effect: no Stage-B confirmation or
mutation. Cycle: D-23 review `2/2` remains completed; no new general review.
Next step: one owner decision for the bounded PS5.1 host-services-only read.
