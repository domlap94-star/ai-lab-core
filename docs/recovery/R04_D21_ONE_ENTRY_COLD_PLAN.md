# R04 / D-21 — ONE-ENTRY-COLD source/offline package

Status: `OPEN_AFTER_BASE_READY_SOURCE_AND_OFFLINE_READY_FOR_REVIEW / NOT_DEPLOYED`.

This is the one preparation package for the remaining one-entry/cold segment.
It preserves `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE`; it is not an
installation approval, a logon test, a reboot approval or `R04_ACCEPTED`.

## Observed entry and client identity

The bounded read-only projection at `2026-09-25T10:31:56.3011683Z` found:

- `C:\Users\domai\Desktop\NEXT Stabil.lnk`, 1288 B, SHA-256
  `8B46D106A8AD2DB3AC39E57A6E879104C77BA7C8D7AEEC9008577E1F9BA9FBDD`;
- target `C:\Users\domai\AppData\Local\Programs\NEXT Stabil\frontend.exe`,
  no arguments, working directory equal to the target parent;
- client 140288 B, SHA-256
  `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`,
  version `1.0.2+29`, process name `frontend`;
- the Startup-folder `NEXT-Stabil-Host.cmd` is absent and must not be restored;
- the existing `\NEXT Stabil - Host` action invokes the installed evidence
  recorder, has one logon trigger, `InteractiveToken`, `LeastPrivilege`,
  `IgnoreNew`, `PT15M`, and was observed `Ready` with LastResult `0`.

The installed shortcut remains the fallback and is not changed by this source
package.

## Resulting single path

The candidate manifest binds the Windows client as an existing external tool by
absolute path and raw SHA-256. Its `OPEN_AFTER_BASE_READY` policy runs only after
the existing container, PostgreSQL-health, gateway and HTTP/public-control
gates. The launcher then:

1. refuses unknown, foreign or multiple client processes;
2. preserves one exact already-running client;
3. otherwise starts the exact client once with the exact parent working
   directory and waits within the existing service-stage deadline;
4. reports `client_status` and a safe `user_message` in the existing result;
5. never opens the client after a failed database/readiness gate.

The recorder preserves these fields and displays only the safe refusal message
through the logged-on user's existing Host task. Notification failure does not
change the primary result.

The future manual shortcut and logon both use the same Host/recorder/launcher
path. The manual shortcut replacement is:

| Field | Exact candidate |
|---|---|
| path | `C:\Users\domai\Desktop\NEXT Stabil.lnk` |
| target | `C:\Windows\System32\schtasks.exe` |
| arguments | `/Run /TN "\NEXT Stabil - Host"` |
| working directory | `C:\ai-lab-core` |

`IgnoreNew` blocks a concurrent second Host instance. After the first Host has
settled, a repeated entry performs fresh readiness checks and preserves the
already-running exact client, so it does not create another stack or client.

## Offline evidence

Windows PowerShell 5.1 ran the actual validator, plan, real adapters above only
their system boundaries, data-junction contract, P4 package contract and
recorder process/capture path. Final counts are recorded in the checkpoint and
package index; production boundary calls are zero. Covered paths include:

- base-ready then exact client start;
- repeat with zero duplicate client starts;
- database/readiness refusal before client start plus safe user message;
- foreign client identity refusal;
- real adapter start/preserve trace;
- recorder safe-field capture and injected notification boundary.

## One future operational window

The next operation is one indivisible owner-confirmed window, not a return to
USABLE-WARM planning:

1. create a protected preimage of the four installed files, the current Host
   XML and the current shortcut bytes; confirm no backup/maintenance task or
   unresolved Host attempt is active;
2. boundedly re-read the exact client, four installed preimages, Host identity,
   six pinned containers, PostgreSQL health, Public/Private/Supervisor and the
   existing HTTP/public-control gates; material drift stops before mutation;
3. install only the candidate launcher, runtime, recorder and manifest, verify
   exact hashes, and keep the existing Host principal/settings;
4. replace the desktop shortcut only after the files and Host binding validate;
   keep the original shortcut bytes in protected rollback;
5. invoke the new manual entry once, require a new complete recorder result,
   base readiness and exactly one client; invoke it again and require zero
   service/container/client duplicates;
6. after the manual result, obtain the owner's immediate confirmation for the
   disruptive part, then perform one controlled Windows reboot (required for a
   genuine cold/logon test, not merely a warm logoff); do not use Compose
   create/up/recreate/build/pull and do not start Supervisor;
7. after Windows returns, require one Host logon execution, existing pinned
   resources ready, one client, public `/control*` still blocked, and owner
   confirmation of CRM/Web client list and one client detail;
8. publish one combined result. A configured trigger alone is not a logon/cold
   PASS.

Expected interruption: the reboot stops Windows processes, Docker Desktop and
the running containers, then the existing Docker/Host mechanisms may start only
the already pinned resources. RustDesk will disconnect. Before reboot the owner
must confirm local access or that RustDesk unattended/start-with-Windows access
is working; recovery must not depend on the client shortcut being tested.

Rollback is limited to a known, settled state: restore the exact four preimage
files, exact Host XML and original shortcut, leaving the accepted USABLE-WARM
entry available. It never restores the Startup wrapper, legacy Compose-up or a
Supervisor trigger and never restores data. Unknown/pending writes stop further
mutation rather than triggering a competing rollback.

## Data, backup and memory boundary

This window changes no data, junction, schedule, retention setting, backup or
memory policy. `R04-DATA-BACKUP` remains next and must preserve:

- C: for OS and code; D: for growing NEXT Stabil data, through the exact
  `C:\ai-lab-core\data -> D:\ai-lab-data` junction;
- backup destinations outside C: and D:, explicitly selected by the user;
- no fallback to C:, D:, E: or any default when selection is absent, cancelled
  or unavailable, with a descriptive result;
- automatic scheduled copies after one accepted destination choice, without
  repeated prompts;
- accounting for large temporary dump/archive placement before the final copy;
- existing backup retention and memory retention as separate unchanged
  policies; no purge or cleanup in this segment.

## Exact next decision boundary

One future confirmation must name the published source/package/checkpoint SHA,
the four payload hashes, manifest/index hashes, Host/shortcut before-to-after
identities, the bounded preflight, one UAC if required, two manual-entry checks,
one controlled reboot/logon and the limited rollback above. Until that response:
`INSTALL=NOT_RUN`, `MANUAL_ENTRY=NOT_RUN`, `REBOOT/LOGON=NOT_RUN`,
`COLD_START=NOT_RUN`, and the candidate remains `NOT_APPROVED_FOR_START`.

## Operational window result — 2026-09-25

The owner authorized the exact one-time window
`R04-D21-ONE-ENTRY-COLD-WINDOW-20260925T110738Z` against published SHA
`cf535cfab7a67e35c3a66b09c1619a0f40599175`, package index
`9C1A60AA50965E4419C9B6021A8C4F60EA8FEF67C685F37D026CCAF60EBBB06C`
and review ZIP
`B8D33DD14CEF2491160A50F241EE58B7679729D3DAE304810729565295C48876`.

The bounded preflight passed package, installed preimages, shortcut/client,
Host, maintenance, six pinned containers, host services and the required HTTP
gates. The operational derivative bound manifest
`6219F891E8C1CB50088C8E2262E7935E329A9B0198E0179815BBA23001A90BBA`
through index
`F2905BD6BD014B3F7E3BC4FD17A69CE91EEBD709B091E3EB07314066B5242535`.

The single UAC launched elevated PID `52112`. Four files were copied and
verified, then the post-copy validation stopped with exit `22` and the exact
error `Cannot bind argument to parameter 'ManifestPath' because it is an empty
string.` The failure occurred before shortcut or task writes and before Host,
service or container starts. One authorized rollback completed as
`SAFE_INACTIVE_COMPLETE`; the final exact readback confirmed all four installed
files and the shortcut at their five exact preimages. Host remained Ready with
the existing single logon trigger and unchanged last run.

Result:
`PRE_REBOOT_INSTALL_FAILED_VALIDATION_MANIFEST_PARAMETER_COLLISION /
SAFE_INACTIVE_COMPLETE / UAC_CONSUMED`. Manual entry/repeat, reboot/logon,
cold-start and the CRM/Web check are `NOT_RUN`. USABLE-WARM remains accepted and
unchanged. A future attempt requires a new owner decision after a minimal,
offline-verified correction of the validation-scope `ManifestPath` collision;
the present authorization must not be retried.

## Recorder capture/settlement completion — 2026-09-25

The later consumed operation
`R04-D21-ONE-ENTRY-COLD-EXEC-20260925T124854Z` installed its four files and
changed the shortcut. Its first manual entry opened one client, but recorder
attempt `20260925T133815236Z-2598b2ff` remained the historical failure
`LAUNCHER_PROCESS_UNSETTLED / OUTPUT_STREAMS_UNSETTLED`, exit `24`. Manual
repeat and cold/logon were not run. These facts are LOCAL_ONLY evidence and do
not rewrite the earlier published checkpoint or grant another execution.

Fresh PS5.1 fail-before proved that the long-lived client inherited the
launcher's redirected handles. The source fix separates the client with the
existing shell start boundary and separates launcher process state from stream
capture state. The full real process path passes seven scenarios while invalid
JSON, real stderr, exit 22, timeout and client-without-result remain fail-closed.

Exact production payload for the next operation is now only:

- launcher `86468` B / `41B2F9ACC11F0647F99F1B04DD2DB9E04CD33810EBF22AD43C576A726E44F910`;
- recorder `21282` B / `BC002D6DC2721BBEF84EC789633D473C34D955D1D42CC506161C60FFA3B5A801`.

Runtime and manifest are unchanged and must not be recopied. The complete new
operation is bound in `R04_D21_ONE_ENTRY_COLD_COMPLETION_OP.json` as
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z`, with OutputRoot
`C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-OEC-20260925T183020Z`.
It is `NOT_RUN / WAITING_OWNER_CONFIRMATION`; all approval flags remain false.
The operation definition is `6476` B /
`4FE4C3B1E03A7E785ED283E1D2F5627B4D715FD32FC2BDC472E94AF256D081B1`.

Status: `RECORDER_CAPTURE_SETTLEMENT_SOURCE_AND_OFFLINE_PASS /
NEW_ONE_ENTRY_COLD_OPERATION_NOT_RUN / WAITING_OWNER_CONFIRMATION`.
