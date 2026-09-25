# R04 / D-21 — ONE-ENTRY-COLD two-file install and manifest refusal

Status: `TWO_FILE_INSTALL_COMPLETE / RECORDER_COMPLETE /
MANIFEST_REFUSED / NO_RETRY / NOT_READY_FOR_RESTART`.

For the unchanged operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z`, the owner authorized one
new UAC while present at NEXT Stabil/RustDesk. The completed corrected
preflight `PASS_NO_MUTATION`, its raw artifacts and `http.json` were reused;
none of its Task Scheduler, Docker, HTTP, client, listener, shortcut or file
reads was repeated before mutation.

## Installation

The one UAC created elevated PID `43468`, which exited `0`. The preserved
two-file installer verified exact preimages and committed only:

- launcher `491531FB...C322D2` -> `41B2F9AC...44F910`;
- recorder `45CBC5D9...CA63A7` -> `BC002D6D...5A801`.

Its result is `INSTALLED_TWO_FILES`, `pending_mutation=false`, rollback
`NOT_NEEDED`. Runtime and manifest copies were false; task and shortcut writes
were zero. Exact preimages remain under the operation OutputRoot.

## One repeat entry

Because the preserved preflight had exactly one existing client, the OP's
existing-client branch required one new repeat only. The existing Host entry
accepted exactly one `/Run`. Recorder attempt
`20260925T203416504Z-7b650886` completed and settled without truncation:

- `launcher_process_exited=true`, `launcher_process_settled=true`;
- stdout/stderr capture `COMPLETE`, stderr empty;
- recorder/launcher exit `22`;
- result `LAUNCHER_REFUSED_CAPTURED / MANIFEST_REFUSED`;
- details: `FILE_HASH_MISMATCH:startup_launcher` and
  `FILE_HASH_MISMATCH:startup_evidence_recorder`;
- launcher events empty, base readiness false, Supervisor not observed and
  client start not requested.

The installed approved manifest was intentionally not recopied or changed, but
it still binds the two previous installed file hashes. The new launcher
therefore failed closed before readiness or any service/container/client
start. One bounded post-attempt reconciliation found exactly the preserved
client PID `11924` at the canonical path and zero foreign clients.

No retry, rollback, second entry or restart was performed. The two-file
installation is complete, but the required `BASE_READY_LIMITED_CAPTURED`
result was not obtained; the OP is not ready for cold-start or reboot. Any
manifest transition, rollback or further Host start requires a new exact owner
decision.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`. Docker/WSL pool and
swap remain `UNKNOWN`.

Anti-loop footer: one UAC and one repeat were consumed; the settled, complete
recorder result exposed an exact manifest-binding blocker; no retry, restart,
new OP, package, review or K2/K3 campaign opened.
