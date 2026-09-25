# R04 / D-21 — ONE-ENTRY-COLD manifest replace blocked before mutation

Status: `MANIFEST_PREIMAGE_VERIFIED / ATOMIC_REPLACE_ARGUMENT_BLOCKED /
NO_MANIFEST_MUTATION / NO_HOST_START / NOT_READY_FOR_RESTART`.

The owner authorized exactly one new UAC for the same operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z`, using the unchanged
validated candidate SHA-256
`53CA6E98F81915D62C7695D8F077FACC95E394D897BD2E9D12000143B6972EC9`.
No preflight, candidate validation, service read, launcher/recorder install or
Host attempt was repeated.

The UAC was accepted and elevated PID `49688` started. It verified the current
installed manifest as the exact authorized preimage: `33551` bytes / SHA-256
`6219F891E8C1CB50088C8E2262E7935E329A9B0198E0179815BBA23001A90BBA`.
It also reached the same-directory temporary candidate step. The subsequent
PowerShell 5.1/.NET call `[IO.File]::Replace(temp, target, $null)` failed before
replacement with `Ścieżka ma niedozwolony format.` The operator recorded
`OPERATION/FAILED` but exited `1` before writing its final `result.json`.

Because the parent initially had no result, the authorized limited readback
checked only the installed manifest and the operation journal. The installed
manifest still exactly matched the preimage (`33551` bytes / `6219F...0BBA`),
so the attempt is now conclusively `NO_MANIFEST_MUTATION`, not pending. Host,
manual entry, repeat and rollback were not started. The transient operator was
removed and no automatic retry was performed.

This UAC is consumed. The validated candidate and exact preimage remain
unchanged under the existing OP OutputRoot. A future exact decision may use a
PowerShell 5.1-compatible atomic replacement with a concrete same-volume
backup path, without repeating preflight, candidate construction/validation,
launcher/recorder installation or historical Host attempts.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Anti-loop footer: elevated execution and exact preimage verification occurred;
atomic replace failed before mutation and readback resolved the state; Host,
retry, rollback and restart were zero; no new OP, package or review opened.
