# NEXT Stabil single-start source (D21-P1)

This directory contains the source-only, offline-tested candidate for the one
future host entrypoint. It is not installed under `C:\ai-lab-core`, is not
registered in Task Scheduler, and is not approved for a live start.

## Interface and safety boundary

`start-host-services.ps1` is the sole proposed user/logon entrypoint. Its
ordinary execution resolves its own path and refuses to act unless installed
under `C:\ai-lab-core\operations\runtime`. Its real read/start adapters are
wired only after that root check and a complete `APPROVED` manifest validation.
The recovery copy therefore stops with `RUNTIME_SOURCE_REFUSED`, while a missing,
example-only or mismatched manifest stops before any adapter is constructed.
Tests import definitions with `-DefinitionOnly` and pass in complete synthetic
adapters; JSON can never carry executable adapter code.

`startup-set.example.json` is `NOT_APPROVED / EXAMPLE_ONLY`. Zero hashes and
example identities are placeholders, not observations and not a candidate set.
P2 must select, hash, review and separately approve a real set.

P1 accepts exact Task Scheduler action identities for host services. Direct
process launch and `OPEN_AFTER_BASE_READY` client launch remain fail-closed;
their rollout semantics require a later reviewed set rather than an arbitrary
executable surface.

The existing Compose helper exposes `Invoke-ApprovedExistingContainerPhase`
over the same shared phase used by the launcher. That interface only preserves
or starts a unique existing container after exact project/service,
image/digest, mounts and ports match.
It never creates, pulls, builds or recreates resources. Direct execution of the
helper now fails closed; there is no `docker compose up` fallback. Replacing the
installed task and activating the launcher remain later, separately approved
rollout steps.

## Machine result

Results use `NEXT_STABIL_STARTUP_RESULT_V1`. `BASE_READY_LIMITED` means only
the approved base checks passed. It always carries:

- `base_ready=true`;
- `supervisor_status=INTENTIONALLY_STOPPED`;
- `ai_export_ready=false`;
- `all_ready=false`.

Manifest/identity/port failures, native-command timeout, missing or duplicate
resources and policy conflicts are non-success results. A timeout after a
start request is `UNKNOWN` for that resource and is never retried blindly.

## Bounded native commands

`Invoke-BoundedNativeCommand` uses PowerShell 5.1-compatible
`ProcessStartInfo`, safe Windows argument quoting, concurrent stdout/stderr
reads, bounded diagnostic buffers and a monotonic timeout. On timeout it checks
the PID and process start time before terminating only that child. It does not
kill Docker Desktop, the Engine, tasks or services and cannot infer that a
timed-out client rolled back a requested operation.

## P1 verification

Run only from the recovery worktree:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-start-host-services.ps1
```

The test creates only synthetic files and short `powershell.exe -NoProfile`
children. Docker, HTTP endpoints, Task Scheduler and product processes are
represented by deterministic adapters. Live/manual/logon/reboot startup,
cutover, rollback and cleanup remain `NOT_RUN / REQUIRES_SEPARATE_APPROVAL`.
