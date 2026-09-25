# R04 / D-21 — ONE-ENTRY-COLD second UAC cancelled

Status: `CORRECTED_PREFLIGHT_PASS / SECOND_UAC_CANCELLED_BEFORE_PROCESS /
NO_INSTALL / NO_MUTATION`.

The owner authorized exactly one new UAC for the unchanged operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z` on published HEAD
`769b3b0d98e2838868dab97a429c9cd2409426c9`. The completed
`PASS_NO_MUTATION` preflight, its raw artifacts and `http.json` were reused.
No Task Scheduler, Docker, HTTP, client, listener, shortcut or installed-file
preflight read was repeated.

The exact preserved two-file installer was invoked once through
`Start-Process -Verb RunAs`. Windows returned `Operacja została anulowana przez
użytkownika` before creating the elevated process. Elevated PID is absent and
`install01\result.json` remains absent.

Result:

- newly authorized UAC requested/consumed: `1/1`;
- elevated process started: `false`;
- installation and preimage capture: `NOT_RUN`;
- launcher/recorder writes: `0`;
- runtime/manifest/task/shortcut/container/data writes: `0`;
- Host/manual entry/repeat/reboot: `0/0/0/0`;
- mutation started: `false`;
- automatic retry: `NOT_AUTHORIZED` and not performed.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`. The same OP remains
blocked before installation. A further UAC requires another exact owner
decision; the completed corrected preflight and HTTP batch must not be
repeated.

Anti-loop footer: the single new UAC was consumed by cancellation before
process creation; no installation, manual entry, repeat or restart occurred;
no new OP, package, review or K2/K3 campaign opened.
