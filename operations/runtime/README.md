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

The manifest validator also binds each host-service `script_ref` to the one
code-file argument actually selected by that service action. A task action
that consistently points at another in-root file (or at recovery/staging)
cannot make an internally inconsistent manifest valid.

`data_topology` is the only reparse-point exception. Version
`NEXT_STABIL_DATA_TOPOLOGY_V1` permits the exact directory junction
`C:\ai-lab-core\data -> D:\ai-lab-data` solely for declared `ACTIVE_DATA_ONLY`
container bindings. The validator reads the junction type and target, checks
the logical and physical path chains, and binds every allowed source to an
exact, case-sensitive container contract: `backend/APPLICATION_DATA=/data`,
`postgres/POSTGRESQL_DATA=/var/lib/postgresql/data`,
`n8n/N8N_DATA=/home/node/.n8n`,
`open-webui/OPENWEBUI_DATA=/app/backend/data`, or
`ollama/OLLAMA_DATA=/root/.ollama`. Matching declarations in two manifest
sections do not authorize another service, role or destination. In particular,
the Open WebUI path under `/app` does not authorize backend data under `/app`.
The exception never authorizes code, `script_ref`, an executable or a
host-service working directory through the data path. Missing or unreadable
metadata, another target/type, an unknown contract, a nested
reparse point or a path-boundary trick refuses startup before adapters. The
launcher never creates the junction, target, a replacement directory, a
volume, or an empty database.

The existing Compose helper exposes `Invoke-ApprovedExistingContainerPhase`
over the same shared phase used by the launcher. For a pinned package the
shared phase selects the exact 64-hex `container_id` first, then verifies the
name, project/service labels, image/digest, mounts and configured/active ports.
It never adopts a different current container by name or label when the pinned
ID is absent.
It never creates, pulls, builds or recreates resources. Direct execution of the
helper now fails closed; there is no `docker compose up` fallback. Replacing the
installed task and activating the launcher remain later, separately approved
rollout steps.

`NEXT_STABIL_STARTUP_PACKAGE_V1` adds the pinned P4/A contract without making
the draft executable. It requires the full 64-hex container ID independently
of the Compose service label and runtime container name, and it includes the
launcher, shared runtime and installed P3 backend override in the file-role
hash set. The normal image identity is an observed repository digest. A
separate `LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST` mode is allowed only for the
backend, only with the exact image and container IDs, and only when the image
adapter positively observes an empty `RepoDigests` list; timeout, read failure
or a nonmatching digest never selects that mode. The current production draft
remains `NOT_APPROVED` while its runtime name/digest projection is not
persisted.

The pinned package also carries an explicit unique `startup_order`, a
`health_requirement`, and `depends_on_healthy` links. PostgreSQL is started
before the backend and must become Docker-`healthy` within the shared bounded
stage deadline before a backend start can be submitted. `starting`, missing or
unknown health cannot be treated as ready. An already running backend is never
stopped to enforce this check. These fields order and gate only existing,
identity-verified containers; they do not add Compose create/up/recreate or an
unbounded dependency scheduler.

Container inspection uses a small JSON projection. The optional Docker
`State.Health` key is accessed through a safe map lookup and health logs, Env
and command lines are never projected. A missing/null Health key becomes
`NOT_CONFIGURED`: valid for a `RUNNING`-only component, never equivalent to
`healthy`. Missing State, invalid Running, malformed/truncated JSON, timeout or
nonzero exit remains an incomplete observation. A `HEALTHY` dependency such as
PostgreSQL accepts only the explicit `healthy` status.

The same-role list is a conflict check, not a selection pool. The retained
R03/A1 Qdrant client drills may be ignored only when their narrow documented
name pattern, `exited`/not-running state, empty mounts and empty configured and
active ports are all positively observed. This does not generalize to every
stopped container. Any other same-role object, active/paused/restarting object,
unknown state, name/port conflict or incomplete selector blocks the phase.
Readiness rechecks and a cold start use the same exact-ID selection, and only
the already verified pinned full ID can be passed to `docker start`.

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

Host observation/start uses a second, closed boundary inside
`start-host-services.ps1`. It supports only `OBSERVE` and `START` for the exact
Task Scheduler identity already selected from a validated manifest; JSON never
supplies executable code. Its deadline includes pipeline setup, result mapping
and bounded cancellation/settlement. An observation timeout is `UNKNOWN` and
cannot authorize a start. A timeout after a possible `Start-ScheduledTask`
handoff is also `UNKNOWN`, is not rollback, and is not retried automatically.
The command-level seam used by the offline regression is accepted only as a
complete, in-process harness object; it is not read from the manifest or the
ordinary launcher command line. Missing any task/CIM/TCP/start fake refuses the
operation before a system cmdlet can be selected.

Container identity distinguishes configured `HostConfig.PortBindings` from
active `NetworkSettings.Ports`: a stopped container must retain the approved
configuration before its one exact-ID start, and a running container must then
show the approved active mapping. Host observation examines all listeners on
the required port independently of process matching, rejects wildcard/foreign
owners and extra command-line arguments for the approved script. Multiple
services may share one interpreter such as `node.exe`: an unambiguously
different script that does not own the required port is not a conflict, while
the approved script with changed arguments, duplicate matching processes, or a
foreign port owner remains blocking. Only the documented structural no-match
results for `Get-Process` and the listener query become confirmed absence;
access denial, unavailable modules/providers, incomplete evidence and unknown
errors remain `UNKNOWN`. An exact process without its listener is present but
not ready and is never duplicated.

## P1 verification

Run only from the recovery worktree:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-start-host-services.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-startup-real-adapters.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-startup-data-junction.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-p4-startup-package.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-host22-container-observation.ps1
```

The test creates only synthetic files and short `powershell.exe -NoProfile`
children. The first command verifies the complete plan contract. The second
executes the production adapter mapping against raw, realistic lower-boundary
fixtures, including bounded in-process host-operation pipelines. Missing a
single Docker/HTTP/CIM/TCP/Task/start fake refuses adapter construction; there
is no fallback to the host. Live/manual/logon/reboot startup, cutover, rollback
and cleanup remain `NOT_RUN / REQUIRES_SEPARATE_APPROVAL`.
