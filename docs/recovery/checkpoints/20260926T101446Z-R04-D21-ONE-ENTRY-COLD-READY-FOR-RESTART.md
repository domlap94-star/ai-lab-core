# R04 / D-21 — ONE-ENTRY-COLD ready for restart confirmation

Status: `MANIFEST_ATOMIC_INSTALL_PASS / REPEAT_PASS /
RECORDER_COMPLETE / READY_FOR_OWNER_RESTART_CONFIRMATION`.

The owner authorized continuation of the same operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z` on published HEAD
`7e462a09e69cb75a06007689dcb05e9e9254b294`.

## Corrected atomic manifest installation

One synthetic Windows PowerShell 5.1 `File.Replace` selftest under the existing
OutputRoot used a concrete, unique backup path. Target became `CANDIDATE`,
backup contained `PREIMAGE`, the temporary candidate was consumed, and both
hashes matched. All fixture files were removed.

The single UAC created PID `26228`, exit `0`. It verified the exact candidate
and installed-manifest preimage, wrote a same-directory temporary candidate,
and called the three-string `File.Replace` overload with a unique same-volume
backup path. Readback proved:

- installed manifest SHA-256
  `53CA6E98F81915D62C7695D8F077FACC95E394D897BD2E9D12000143B6972EC9`;
- replacement backup SHA-256
  `6219F891E8C1CB50088C8E2262E7935E329A9B0198E0179815BBA23001A90BBA`;
- `Read-StartupSetManifest` success and `Test-StartupSetManifest valid=true`,
  errors `0`;
- `APPROVED_FOR_START`, installation/startup authorized, matching set IDs;
- launcher `86468` / `41B2F9AC...44F910` and recorder `21282` /
  `BC002D6D...5A801` bindings matched actual installed bytes;
- no `FILE_HASH_MISMATCH`, `START_NOT_APPROVED` or
  `APPROVAL_SET_MISMATCH`;
- pending mutation false and other production file writes zero.

Only after validation PASS, the same-directory replacement backup was removed.
The exact preimage under OutputRoot remains preserved. There is no cleanup
residue.

## One repeat and recorder result

A fresh limited read found exactly one canonical client PID `11924`, no foreign
client, and Host `Ready`/enabled. Therefore the existing-client branch invoked
exactly one repeat through the existing Host task.

New recorder attempt `20260926T101258980Z-f60e3fd8` is complete:

- recorder `BASE_READY_LIMITED_CAPTURED`, exit `0`;
- launcher process exited and settled, exit `0`;
- output capture complete; stdout/stderr `COMPLETE` and untruncated;
- stderr empty;
- launcher result `BASE_READY_LIMITED`, `base_ready=true`;
- Supervisor `INTENTIONALLY_STOPPED`, client `RUNNING`;
- all stack/client events are observations or `PRESERVE_RUNNING`; new service
  or container starts `0`.

The final bounded gate confirmed Host `Ready`, last result `0`, exactly one
canonical client PID `11924`, foreign clients `0`, active named
backup/import/maintenance tasks and processes `0`, and no pending mutation.
The owner's current presence at NEXT Stabil/RustDesk confirms recovery access.

Resume point:
`C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-OEC-20260925T183020Z\resume-before-restart.json`.
It records `READY_FOR_OWNER_RESTART_CONFIRMATION` and explicitly has
`restart_authorized=false`.

Windows has not been restarted. The same OP must pause only for the owner's
current confirmation of readiness for exactly one restart.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Anti-loop footer: manifest install, one repeat and recorder settlement are
complete; the pre-restart gate is reached; no new OP, package, review or K2/K3
campaign opened.
