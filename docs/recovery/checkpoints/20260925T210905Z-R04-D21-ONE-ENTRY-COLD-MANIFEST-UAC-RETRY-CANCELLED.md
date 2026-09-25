# R04 / D-21 — ONE-ENTRY-COLD manifest UAC retry cancelled

Status: `MANIFEST_DERIVATIVE_VALIDATED / NEW_UAC_CANCELLED_BEFORE_PROCESS /
NO_MANIFEST_WRITE / NO_HOST_START / NOT_READY_FOR_RESTART`.

The owner authorized exactly one new UAC for the same operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z` on published HEAD
`351e096e314e666c6a835d2c6eaa895e51f04480`, binding the already preserved
candidate SHA-256
`53CA6E98F81915D62C7695D8F077FACC95E394D897BD2E9D12000143B6972EC9`.

No preflight, HTTP, Task Scheduler, Docker, client, listener, shortcut, file
campaign, candidate regeneration/validation, or launcher/recorder installation
was repeated. A transient operator passed syntax parsing without reading the
candidate or production state.

The single `Start-Process -Verb RunAs` request remained pending for the user
decision and then returned `Operacja została anulowana przez użytkownika`
before Windows created the elevated process. Elevated PID is absent and
`manifest-v2\install02\result.json` is absent. Consequently the under-UAC
preimage check was not reached, the installed manifest was not written, and
Host/manual entry/repeat were not started. The transient operator was removed.

This new UAC authorization is consumed. The validated candidate and exact
preimage remain unchanged under the existing OP OutputRoot. Launcher and
recorder remain on their new installed bytes while the installed manifest
still has its old bindings, so restart/cold-start is not ready. Another exact
owner decision is required for one new UAC; no automatic retry is authorized.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Anti-loop footer: the sole newly authorized UAC was consumed by cancellation
before process creation; product reads/writes, Host starts, retry, rollback and
restart were zero; no new OP, package or review opened.
