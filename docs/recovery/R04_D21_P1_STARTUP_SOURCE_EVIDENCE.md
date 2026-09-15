# R04 / D-21 / P1 — startup source evidence

Status: `REAL_ADAPTERS_SOURCE_READY_FOR_REVIEW / OFFLINE_TEST_ONLY / NOT_DEPLOYED`

## Scope and identity

- accepted D-21 map/plan parent: `b6cb4c38d8c739ceda87feb2e0c18cf98117ed02`;
- original P1 source reviewed: `1bfb377a224499eda2366a7cc52814e55ab267fa`;
- corrected and tested source commit: `2e97b9f72bf2150cc395c19aa433174c0b2e933a`;
- target root after a later approved installation: `C:\ai-lab-core`;
- source location in this step: `C:\ai-lab-core-recovery` only;
- no production startup manifest was created or approved.

The owner explicitly authorized two future-semantics changes as source/offline
test work: remove the default Compose deployment path and wire real bounded
read/start adapters behind canonical-root and approved-manifest validation.
Neither adapter nor launcher was executed against a real service.
After the five review observations were reproduced, the owner separately and
explicitly approved a closed, bounded host-operation pipeline inside the same
launcher. That approval was source/offline-test only and did not authorize any
real CIM/TCP/Task Scheduler operation.

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
- one code-file argument whose resolved path is exactly the hashed file named
  by that service's `script_ref`;
- bounded command/stage/output settings, required readiness checks, public
  `/control` expected as 404 and Supervisor `INTENTIONALLY_STOPPED`.

P1 deliberately accepts only exact task actions for host services. Direct
process launch and `OPEN_AFTER_BASE_READY` client launch fail validation. That
is a recorded P1 limitation, not a silent no-op or runtime approval.

The execution chain is manifest → static validation → single-instance mutex →
Docker context/Engine observation → exact existing-container observation/start
by the freshly observed full ID → exact host task/process/listener observation
→ readiness. Configured container bindings are checked before starting a
stopped container; active bindings and the unchanged full ID are checked after
start. Host listener ownership is observed independently from process matching,
so a wildcard/foreign owner, extra arguments or unavailable evidence cannot be
mistaken for service absence. Timeout after an accepted start is reported as
unknown and is not retried blindly.

The host boundary supports only fixed `OBSERVE` and `START` operations selected
from an already validated manifest. It neither accepts commands from JSON nor
acts as a general executor. Its shared service-stage deadline covers initial
observation, the single exact-task start and readiness; the operation deadline
also covers pipeline setup, result mapping and bounded cancellation. A timeout
of an observation returns `UNKNOWN` and authorizes zero starts. A timeout after
a possible Task Scheduler handoff also returns `UNKNOWN`; stopping the local
supervising pipeline is not represented as rollback of the task.

`operations/windows/start-compose-after-docker.ps1` now contains only the
shared existing-resource interface and refuses direct execution. It contains no
`docker compose up`, pull, build, create or recreate fallback. The installed
copy and its existing task were not changed.

## Offline verification

Final command, executed from the recovery worktree with Windows PowerShell 5.1:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-start-host-services.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File operations/runtime/test-startup-real-adapters.ps1
```

Final results on the exact source commit bytes:

| Check | Result |
|---|---|
| PowerShell parser: five relevant `.ps1` files | `PASS` |
| `startup-set.example.json` parse | `PASS` |
| focused startup contract | `PASS`, 53 assertions, exit 0 |
| raw production-adapter mapping with complete lower-boundary fakes | `PASS`, 23 assertions, exit 0 |
| recovery ordinary entrypoint | `RUNTIME_SOURCE_REFUSED`, no adapters |
| direct legacy helper | `START_REFUSED`, no Docker/Compose call |
| missing one required lower-boundary fake | `PASS`, adapter construction refused without host fallback |
| real adapter host deadline | `PASS`, whole observe/start calls bounded; timeout remains `UNKNOWN` |
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

## Review observations D21-P1-RV01–05

The preimage was source commit
`1bfb377a224499eda2366a7cc52814e55ab267fa`. A one-off LOCAL_ONLY harness
called the real adapter functions with deterministic lower boundaries. An
initial harness invocation was invalid because of a PowerShell 5.1 module
autoload issue and is not counted. The corrected fail-before invocation exited
0 as a reproduction harness and recorded all five defects (its exit 0 is not a
protection PASS):

| Review item | Fail-before | Pass-after on `2e97b9f72bf2150cc395c19aa433174c0b2e933a` |
|---|---|---|
| RV01 — CIM `CreationDate` | `REPRODUCED`: a `[datetime]` reached DMTF-only conversion | `PASS`: DateTime/DateTimeOffset, explicit DMTF and invariant ISO supported; invalid value is `UNKNOWN` |
| RV02 — configured vs active container ports | `REPRODUCED`: stopped-state proof depended on active `NetworkSettings.Ports` | `PASS`: `HostConfig.PortBindings` required before one exact-ID start; active bindings and unchanged ID required after start |
| RV03 — foreign port / incomplete process evidence | `REPRODUCED`: wildcard foreign listener and extra arguments could appear as absence/match | `PASS`: all listeners on the port checked independently; conflicts and unavailable evidence start nothing |
| RV04 — `script_ref` binding | `REPRODUCED`: manifest/task could agree on a script different from the hashed role | `PASS`: tool → exact code argument → `script_ref` is validated before adapters |
| RV05 — whole host-adapter deadline | `REPRODUCED`: synthetic 25 ms operation returned `SUCCESS` after 327 ms | `PASS`: closed internal pipeline is bounded, late result is not success, observation/start timeout is `UNKNOWN`, and no retry occurs |

The raw-adapter suite uses the production parsing, observation and planning
functions. Docker CLI, HTTP, CIM, TCP, Task Scheduler and start are complete
lower-boundary fakes, including inside the bounded host-operation pipeline.
No missing fake can fall through to a host function. The positive matrix still
reaches one permitted fake task start for a truly absent service with a free
port and reaches readiness; this is not a design that passes by blocking every
start.

During test development, one run exposed PowerShell dynamic-scope clobbering of
the launcher `DefinitionOnly` flag; a distinct helper parameter fixed it. A
later PS5.1 run exposed deserialized-property and JSON-array behavior in mount
parsing; the final safe property reader and explicit array iteration fixed it.
Neither failure contacted a product boundary. The final 53- and 23-assertion
runs are the current review evidence; earlier failed runs are not counted as
passes and P1 has not been accepted by the owner.

LOCAL_ONLY raw evidence:

- directory:
  `C:\ai-lab-core-staging\recovery\R04_D21_SINGLE_ROOT_20260915T033112Z\p1-20260915T155038Z`;
- log: `p1-final-powershell51-tests.txt`;
- Windows PowerShell: `5.1.26100.8894`;
- size: 2,440 B;
- SHA-256: `614713C2EF458C687BAE1B4D63A844B8D8FB3D4A058F674686A6A322CF53FC9D`.

Review/fix evidence directory:
`C:\ai-lab-core-staging\recovery\R04_D21_SINGLE_ROOT_20260915T033112Z\p1-review-20260915T163536Z`.

| File | Bytes | SHA-256 |
|---|---:|---|
| `p1-review-final-plan-tests.txt` | 158 | `BF95021093A84E8ADBD297BB15513C33B5D01088DFFECAB32A1D87AB2AC0E781` |
| `p1-review-final-raw-adapter-tests.txt` | 172 | `21EA4C343793DDC0DFF9FF1298DB4BC3E8AD8F0BC59FDEEB0CA668FAF501D8D7` |
| `p1-review-final-parser-json.txt` | 581 | `58096FBDD8C7A10D9DDF25934E1CBFF1E27435E1CCCD7AF462FEF8F5C516DA91` |
| `p1-review-final-source.patch` | 53,302 | `575BC2097AAF5E816C9DC2DFF03E7139196F336CDC2E509BA988DF33E991BF31` |

The test created only an exact-name directory under `%TEMP%` and short
`powershell.exe -NoProfile` children. The test removed only its own temp
directory after ownership/path checks. Docker, HTTP, Task Scheduler and product
process boundaries were complete synthetic adapters.

## Source inventory

| Path | Git blob | Bytes |
|---|---|---:|
| `operations/runtime/README.md` | `800e4a7adbd62b79a0b3e05a394d5d65dc0b736a` | 4,969 |
| `operations/runtime/start-host-services.ps1` | `9c92353a122b3c056754547cd840b612bd93af85` | 47,407 |
| `operations/runtime/startup-runtime.ps1` | `b321ecb9c0eb975d0be6ab75bbe869fadc9d21b7` | 45,024 |
| `operations/runtime/startup-set.example.json` | `0a6127e2181214fbb29316cbc4be751090cfb662` | 4,148 |
| `operations/runtime/test-start-host-services.ps1` | `394c3574227c20b1c8b51d7d57de90cfddfad315` | 28,378 |
| `operations/runtime/test-startup-real-adapters.ps1` | `18eaabe1556b95e93389f912cc13bb9b8a0ef631` | 21,770 |
| `operations/windows/start-compose-after-docker.ps1` | `4ce9ef7dc27c2b417d57c3281e95dedd7c968458` | 880 |

## Boundaries and next decision

Real manual/logon/reboot startup, installation under the canonical root,
production manifest approval, Task Scheduler/Startup changes, live rollback,
cutover, relocation and cleanup are `NOT_RUN / NOT_AUTHORIZED`. Supervisor is
`INTENTIONALLY_STOPPED`; `BASE_READY_LIMITED` cannot mean AI/export readiness.
No backend/frontend/API/runtime data changed and no application test was run.

Next step: owner review of corrected P1 source/evidence. P2 needs a separate decision and
must select and preserve a concrete installation candidate; it cannot infer an
approved set from the example manifest or current runtime names.
