# R04 / D-21 / P4-B — native argument transport ready for review

Evidence window: `2026-09-18T15:27:10.3398256Z–2026-09-18T15:38:37.8656363Z`

Entry HEAD: `540c981e05ce5c868996fc06ac6aab339ac6d650`

Recipe ID: `R04-D21-P4B-RECIPE-TRANSPORT-FIX-20260918T152017Z`

## Result

The old native boundary was reproduced without Docker: the exact seven guard
arguments became 56 child arguments. The corrected LOCAL_ONLY recipe reuses the
accepted P1 serializer/bounded runner and retained 7/7 exact arguments.

Windows PowerShell `5.1.26100.8894` passed 17/17 cases and 120 assertions,
exit `0`. The final recipe is 45,009 B, SHA-256
`5F310C64DFB21F55B4403E9A738B80344EB9CEC38536EE4FD2081F6422F1FD67`.
Its new index is 7,454 B, SHA-256
`43F285C2E82032F6914F5C5F8BA0653C85EC44F2A4F24E13D835A7C02162A2A9`.

After offline PASS, exactly one non-elevated bounded Docker container inspect
was executed for backend
`686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854`.
It exited 0 and confirmed the expected ID, image, running state,
`RestartCount=0`, mounts, port, labels and network. Safe verdict SHA-256:
`FBFFA2C853565C539480B8C8F94355FD6E08C06D515653B3C201D9F9A7CF1A43`.
There was no second Docker invocation.

## Effects and retained state

- UAC/RunAs: `0`.
- Host mutations: `0`.
- Task/trigger/Startup/manifest changes: `0`.
- Service/container starts, stops, restarts or recreates: `0`.
- Warm runs: still `0/2`.
- All owned test processes: ended/accounted for.
- Product payload and XML/manifest bytes: unchanged and hash-matched.
- Startup wrapper remains in protected rollback; Host remains
  disabled/no-trigger/never-run; five existing tasks remain on preimage.
- Global manifest: `NOT_APPROVED_FOR_START`.
- Supervisor: `INTENTIONALLY_STOPPED`; not started or probed by this work.

Raw recipe/index/harness/logs remain LOCAL_ONLY under the existing P4/B staging
window. The committed review summary is
`docs/recovery/R04_D21_P4B_NATIVE_ARGUMENT_TRANSPORT_EVIDENCE.md`.

## Handoff

Status: `P4B RECIPE_NATIVE_ARGUMENT_TRANSPORT_FIXED /
TESTED_ON_POWERSHELL_51 / READY_FOR_REVIEW`.

Readback: `EXACT_DOCKER_READBACK_PASS` for one backend inspect only.

Installation remains `NOT_INSTALLED`; no new operational approval was used.
The next permissible step is owner review of the exact recipe/index and, only
if separately authorized later, one fresh bounded drift check and one new UAC
window. STOP before P4/B installation, warm runs, rollback, reboot/logoff,
Supervisor, backup/restore, relocation, P5 or R06.
