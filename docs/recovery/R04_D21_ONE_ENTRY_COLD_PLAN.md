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
