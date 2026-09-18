# R04 / D-21 / P4-B — exact recipe preflight blocked before UAC

Evidence window: `2026-09-18T16:30:31.3776242Z–2026-09-18T16:32:03.5469632Z`

Entry HEAD: `c02ac250aa3ef0406402bb67519b772e7bd4dc01`

Prepared external resume ID: `R04-D21-P4B-RESUME-20260918T163031Z`

## Result

The owner-approved read-only preflight confirmed the exact LOCAL_ONLY transport
recipe and index bytes:

- recipe: 45,009 B, SHA-256
  `5F310C64DFB21F55B4403E9A738B80344EB9CEC38536EE4FD2081F6422F1FD67`;
- recipe index: 7,454 B, SHA-256
  `43F285C2E82032F6914F5C5F8BA0653C85EC44F2A4F24E13D835A7C02162A2A9`;
- recipe-index entries: `17/17` present with matching size and SHA-256;
- referenced resume input-index entries: `29/29` present with matching size and
  SHA-256;
- `installer-execution` did not exist, so no result/event collision was found.

The exact reviewed recipe is nevertheless not executable as the requested
resume. `Assert-ContainersUnchanged` resolves each baseline record as
`Join-Path $resumeRoot "docker-container-<service>-pass2-command.json"`, where
`$resumeRoot` is the native-transport recipe directory. None of the six files
exists there. The indexed and hash-matched records instead remain under the
previous consumed resume directory
`r04-d21-p4b-resume-20260918t112015z`.

This is a deterministic input-path binding failure before Docker and before the
mutation boundary. Running the exact recipe would fail on the first baseline
`Get-Content`; copying or redirecting those inputs would change the reviewed
execution contract and was not authorized by this continuation.

## Effects and stop condition

- UAC / RunAs: `0`.
- Docker, Task Scheduler, HTTP, listener and resource calls: `0` in this
  continuation after the static blocker was proven.
- Host mutations, task/trigger changes, installed files and service starts:
  `0`.
- Warm runs remain `0/2`.
- Existing `PARTIAL_SAFE_INACTIVE` state is unchanged: Startup wrapper in
  rollback, Host disabled/no-trigger/never-run, five tasks on preimage,
  launcher/runtime/manifest absent and legacy helper retained.
- Supervisor remains `INTENTIONALLY_STOPPED` and was not probed.

The native argv transport repair is accepted only for its reviewed bytes and
previous transport evidence. It is **not** accepted as an exact executable
resume recipe. No §4 owner-confirmation sentence was requested because the
precondition for one UAC was not met.

Status: `P4B EXACT_RECIPE_PREFLIGHT_BLOCKED / BASELINE_PATH_BINDING_MISMATCH /
NO_UAC / NO_MUTATION`.

Next permissible step: prepare and test a new recipe/index that binds the six
baseline records to their indexed exact paths (or explicitly indexes an exact
new immutable bundle), then obtain a new owner review before any live drift
check or UAC. STOP before P4/B installation, warm runs, rollback, reboot/logoff,
Supervisor, backup/restore, relocation, P5 or R06.
