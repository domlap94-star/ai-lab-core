# R04 / D-21 / P1 — startup source evidence

Status: `STARTUP_SOURCE_READY_FOR_REVIEW / OFFLINE_TEST_ONLY / NOT_DEPLOYED`

## Scope and identity

- accepted D-21 map/plan parent: `b6cb4c38d8c739ceda87feb2e0c18cf98117ed02`;
- tested source commit: `1bfb377a224499eda2366a7cc52814e55ab267fa`;
- target root after a later approved installation: `C:\ai-lab-core`;
- source location in this step: `C:\ai-lab-core-recovery` only;
- no production startup manifest was created or approved.

The owner explicitly authorized two future-semantics changes as source/offline
test work: remove the default Compose deployment path and wire real bounded
read/start adapters behind canonical-root and approved-manifest validation.
Neither adapter nor launcher was executed against a real service.

## Resulting contract

`operations/runtime/start-host-services.ps1` is the single proposed entrypoint.
Ordinary execution outside `C:\ai-lab-core\operations\runtime` returns
`RUNTIME_SOURCE_REFUSED`. Within the canonical root it must receive a manifest
using `NEXT_STABIL_STARTUP_SET_V1` and
`NEXT_STABIL_COMPONENT_COMPATIBILITY_V1`. Before adapter construction the
validator requires:

- `APPROVED_FOR_START`, matching set/decision IDs and the exact root;
- the manifest and in-root files to remain inside the root without reparse
  points, with matching SHA-256;
- pinned external-tool paths and SHA-256;
- Docker context/endpoint/tool references;
- exact Compose project/service, image ID/repo digest, mount and loopback-port
  declarations for every existing container;
- exact Task Scheduler action identity for host services: task path/name,
  executable, all arguments, working directory and loopback listener;
- bounded command/stage/output settings, required readiness checks, public
  `/control` expected as 404 and Supervisor `INTENTIONALLY_STOPPED`.

P1 deliberately accepts only exact task actions for host services. Direct
process launch and `OPEN_AFTER_BASE_READY` client launch fail validation. That
is a recorded P1 limitation, not a silent no-op or runtime approval.

The execution chain is manifest → static validation → single-instance mutex →
Docker context/Engine observation → exact existing-container observation/start
by the freshly observed full ID → exact host task/process/listener observation
→ readiness. A changed container full ID after start is refused. Timeout after
an accepted start is reported as unknown and is not retried blindly.

`operations/windows/start-compose-after-docker.ps1` now contains only the
shared existing-resource interface and refuses direct execution. It contains no
`docker compose up`, pull, build, create or recreate fallback. The installed
copy and its existing task were not changed.

## Offline verification

Final command, executed from the recovery worktree with Windows PowerShell 5.1:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-start-host-services.ps1
```

Final results on the exact source commit bytes:

| Check | Result |
|---|---|
| PowerShell parser: four changed/added `.ps1` files | `PASS` |
| `startup-set.example.json` parse | `PASS` |
| focused startup contract | `PASS`, 53 assertions, exit 0 |
| recovery ordinary entrypoint | `RUNTIME_SOURCE_REFUSED`, no adapters |
| direct legacy helper | `START_REFUSED`, no Docker/Compose call |
| real adapter definition contract | `PASS`, definitions created but not invoked |
| bounded harmless child | `PASS`; 150 ms configured timeout, owned PID checked and no child left running |
| simultaneous large stdout/stderr | `PASS`; both buffers capped without deadlock |
| cross-process mutex | `PASS`; one owner |

The focused matrix also covers missing/malformed/not-approved/out-of-root
manifests, wrong hashes, different cwd, unsupported client/process start,
ready/unavailable Engine states, Docker override/context conflicts, missing or
duplicate containers, image/mount/port/full-ID mismatches, exact observed-ID
start, container replacement, task executable/arguments/cwd/name mismatch,
foreign listener, task success without readiness, public `/control` 200,
Supervisor policy conflict, redaction and argument marshalling with spaces,
apostrophes and Go-template braces.

During test development, one run exposed PowerShell dynamic-scope clobbering of
the launcher `DefinitionOnly` flag; a distinct helper parameter fixed it. A
later PS5.1 run exposed deserialized-property and JSON-array behavior in mount
parsing; the final safe property reader and explicit array iteration fixed it.
Neither failure contacted a product boundary. The final 53-assertion run is the
acceptance evidence; earlier failed runs are not counted as passes.

LOCAL_ONLY raw evidence:

- directory:
  `C:\ai-lab-core-staging\recovery\R04_D21_SINGLE_ROOT_20260915T033112Z\p1-20260915T155038Z`;
- log: `p1-final-powershell51-tests.txt`;
- Windows PowerShell: `5.1.26100.8894`;
- size: 2,440 B;
- SHA-256: `614713C2EF458C687BAE1B4D63A844B8D8FB3D4A058F674686A6A322CF53FC9D`.

The test created only an exact-name directory under `%TEMP%` and short
`powershell.exe -NoProfile` children. The test removed only its own temp
directory after ownership/path checks. Docker, HTTP, Task Scheduler and product
process boundaries were complete synthetic adapters.

## Source inventory

| Path | Git blob | Bytes |
|---|---|---:|
| `operations/runtime/README.md` | `a3ebcdd78c5dcbddca809914c049992f260bc50b` | 3,315 |
| `operations/runtime/start-host-services.ps1` | `a9ca612acd904b09d874dc83ece3167d1f53f2eb` | 31,025 |
| `operations/runtime/startup-runtime.ps1` | `d1ecc3baf07548ee222de4acd1bd2e7ddf65137f` | 39,518 |
| `operations/runtime/startup-set.example.json` | `0a6127e2181214fbb29316cbc4be751090cfb662` | 4,148 |
| `operations/runtime/test-start-host-services.ps1` | `394c3574227c20b1c8b51d7d57de90cfddfad315` | 28,378 |
| `operations/windows/start-compose-after-docker.ps1` | `4ce9ef7dc27c2b417d57c3281e95dedd7c968458` | 880 |

## Boundaries and next decision

Real manual/logon/reboot startup, installation under the canonical root,
production manifest approval, Task Scheduler/Startup changes, live rollback,
cutover, relocation and cleanup are `NOT_RUN / NOT_AUTHORIZED`. Supervisor is
`INTENTIONALLY_STOPPED`; `BASE_READY_LIMITED` cannot mean AI/export readiness.
No backend/frontend/API/runtime data changed and no application test was run.

Next step: owner review of P1 source/evidence. P2 needs a separate decision and
must select and preserve a concrete installation candidate; it cannot infer an
approved set from the example manifest or current runtime names.
