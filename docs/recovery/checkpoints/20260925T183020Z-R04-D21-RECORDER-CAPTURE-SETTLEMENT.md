# R04 / D-21 — recorder capture/settlement and ONE-ENTRY-COLD completion operation

Status: `RECORDER_CAPTURE_SETTLEMENT_SOURCE_AND_OFFLINE_PASS / NEW_ONE_ENTRY_COLD_OPERATION_NOT_RUN / WAITING_OWNER_CONFIRMATION`.

## Exact fail-before and cause

Fresh Windows PowerShell 5.1 reproduced the real path through
`Invoke-BoundedHostEvidenceChildProcess`. The launcher emitted one complete
`NEXT_STABIL_STARTUP_RESULT_V1`, started one owned long-lived synthetic client
through the real `New-RealStartupAdapters` / `StartClient` boundary and exited.
The client retained the redirected handles, so `ReadToEndAsync` did not receive
EOF within the bounded cleanup interval. The preimage result was exactly
`LAUNCHER_PROCESS_UNSETTLED` with `OUTPUT_STREAMS_UNSETTLED`, while one client
remained running until fixture-owned cleanup.

The cause was not launcher nontermination. `UseShellExecute=false` at the
long-lived client boundary allowed the child to retain launcher recorder
handles, and the recorder then incorrectly coupled launcher settlement to pipe
EOF.

## Source result

- `StartClient` now uses the existing shell boundary so the long-lived GUI
  client does not retain the launcher's redirected handles; path, arguments,
  working directory, identity and start count are unchanged.
- Recorder process state and output capture state are distinct:
  `launcher_process_started`, `launcher_process_exited`,
  `launcher_process_settled`, `launcher_exit_code`,
  `output_capture_complete`, `stdout_capture_status`,
  `stderr_capture_status` and `long_lived_client_state` are persisted.
- Success still requires exited/settled launcher, known exit 0, complete and
  untruncated streams, empty stderr and one contract-valid JSON result.
  Incomplete capture remains fail-closed as
  `LAUNCHER_OUTPUT_CAPTURE_INCOMPLETE`; exit 22 remains
  `LAUNCHER_REFUSED_CAPTURED`; timeouts remain unknown/failure.

Windows PowerShell 5.1 results:

- full path `recorder -> launcher -> StartClient -> launcher result -> evidence`:
  `PASS`, 7 scenarios / 16 assertions, production boundaries `0`;
- existing recorder suite: 35 assertions / 8 actual child cases, PASS;
- launcher plan: 62 assertions, PASS;
- real adapters: 55 assertions, PASS;
- data junction: 44 assertions, PASS;
- P4 package: 41 assertions, PASS.

Changed production payload:

| Role | Target | Size | SHA-256 |
|---|---|---:|---|
| launcher | `C:\ai-lab-core\operations\runtime\start-host-services.ps1` | 86468 | `41B2F9ACC11F0647F99F1B04DD2DB9E04CD33810EBF22AD43C576A726E44F910` |
| recorder | `C:\ai-lab-core\operations\runtime\invoke-host-with-evidence.ps1` | 21282 | `BC002D6DC2721BBEF84EC789633D473C34D955D1D42CC506161C60FFA3B5A801` |

Runtime and installed manifest are not payload for the next operation and must
not be recopied.

## Preserved LOCAL_ONLY attempt evidence

Operation `R04-D21-ONE-ENTRY-COLD-EXEC-20260925T124854Z` and UAC PID `17772`
are consumed. Installation of four files and the shortcut change occurred. The
first manual entry opened exactly one observed client, PID `11924`, but recorder
attempt `20260925T133815236Z-2598b2ff` ended exit `24` as
`LAUNCHER_PROCESS_UNSETTLED / OUTPUT_STREAMS_UNSETTLED`. It remains a historical
failure, not a rewritten PASS. Second manual entry, reboot/logon/cold and
rollback were not run. The then-observed post-check was 6/6 containers,
PostgreSQL healthy, one Public and one Private Gateway, Supervisor stopped,
HTTP `200/200/404/404`, with no detected duplicate. PID `11924` current state is
not inferred.

## New exact operation

- OP_ID: `R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z`;
- OutputRoot: `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-OEC-20260925T183020Z`;
- exact definition:
  `docs/recovery/R04_D21_ONE_ENTRY_COLD_COMPLETION_OP.json`;
- operation definition: `6476` B /
  `4FE4C3B1E03A7E785ED283E1D2F5627B4D715FD32FC2BDC472E94AF256D081B1`;
- updated package index: `6429` B /
  `819D478D3182240B36BAA6117CED1ECC2363A9B4A4A8A0D2A99F7EEFFD8C0C6B`;
- approval/UAC/install/manual-entry/reboot/logon flags: all false;
- operation status: `NOT_RUN / WAITING_OWNER_CONFIRMATION`.

It performs a fresh bounded preflight, installs only launcher and recorder with
operation-owned preimages, branches on freshly observed client state, completes
manual entry/repeat, pauses for the owner's immediate readiness confirmation,
then performs one restart and evaluates the real cold/logon path. It never uses
its OutputRoot, recovery, staging, a harness or an OP index as a runtime
dependency.

## Boundaries and current roadmap state

Production runtime remains under `C:\ai-lab-core`; active data and normal
startup evidence remain logically under `C:\ai-lab-core\data` through the
accepted junction to `D:\ai-lab-data`. Backup destination remains owner-chosen
outside C:/D: with no fallback. Memory and backup retention remain unchanged.
No UAC, host read/write, task/shortcut change, installation, manual entry,
reboot, Docker/CIM/TCP/HTTP operation or product mutation occurred in this
source/offline package.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Next step: owner review and one current confirmation of the exact published
commit and OP before any execution.

Anti-loop footer: complete authorized SOURCE/OFFLINE scope delivered; no K2/K3
campaign opened; operational continuation remains separately gated.
