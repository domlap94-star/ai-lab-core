# R04 / D-21 — ONE-ENTRY-COLD manifest binding UAC cancelled

Status: `MANIFEST_DERIVATIVE_VALIDATED / UAC_CANCELLED_BEFORE_PROCESS /
NO_MANIFEST_WRITE / NO_HOST_START / NOT_READY_FOR_RESTART`.

The owner authorized continuation of the same operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z` on published HEAD
`22c6010ffecee3c374eae306d5d8235941be411d`.

The current installed manifest was read once and met every authorized input
condition: `NEXT_STABIL_STARTUP_SET_V1`, `APPROVED_FOR_START`, installation and
startup authorized, matching approval/set IDs, non-empty decision `D-21`,
canonical root, and the exact old launcher/recorder bindings. Its preserved
preimage is `33551` bytes / SHA-256
`6219F891E8C1CB50088C8E2262E7935E329A9B0198E0179815BBA23001A90BBA`.

A deterministic derivative was saved under the existing OP OutputRoot. Its
only semantic changes are the authorized top-level and approval set ID plus
the hash, size and evidence values for the already-installed launcher and
recorder. Reverting that allowlist made the parsed manifests semantically
identical. Candidate identity is `33571` bytes / SHA-256
`53CA6E98F81915D62C7695D8F077FACC95E394D897BD2E9D12000143B6972EC9`.

Windows PowerShell 5.1 loaded the unchanged installed
`Read-StartupSetManifest` and `Test-StartupSetManifest`. Candidate read was
`OK`; validation was `valid=true`, errors `0`, root/set/approval bindings
matched, and the actual installed file bindings passed.

The single authorized `Start-Process -Verb RunAs` request was then cancelled
before Windows created the elevated process. The exact returned error was
`Operacja została anulowana przez użytkownika`; elevated PID is absent and the
manifest-install `result.json` is absent. Therefore the installed manifest was
not written, Host was not started, and no repeat or rollback was attempted.
The temporary recovery operator was removed; candidate and exact preimage
remain only as OP evidence under OutputRoot.

The UAC authorization is consumed. Launcher/recorder remain on their new
installed bytes while the installed approved manifest remains on its old
bindings, so cold-start/restart is not ready. Another exact owner decision is
required for the already validated one-manifest installation; completed
preflight, candidate creation/validation, launcher/recorder installation and
historical Host attempts must not be repeated.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Anti-loop footer: exact derivative and validation completed; the sole UAC was
consumed by cancellation before process creation; product writes, Host starts,
retry, rollback and restart were zero; no new OP, package or review opened.
