# R04 / D-21 — ONE-ENTRY-COLD logon/cold pass

Status: `ONE_RESTART_COMPLETE / LOGON_COLD_PASS /
WAITING_OWNER_MANUAL_CRM_CONFIRMATION`.

The owner confirmed current readiness and authorized exactly one Windows
restart for the same operation
`R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z` on published HEAD
`0564edf26dd65aaa9cd80a87222c4707f8d2c241`. Open work was saved and temporary
RustDesk disconnection was accepted.

The resume point was updated with `restart_authorized=true` and authorized
count `1`. Exactly one `shutdown.exe /r /t 0` was issued. Windows booted at
`2026-09-26T10:29:06.5000000Z`, after authorization at
`2026-09-26T10:29:02.5062796Z`. No second restart and no manual NEXT Stabil
start occurred.

The existing Host logon task ran at `2026-09-26T10:29:25Z` and finished with
result `0`. It produced new recorder attempt
`20260926T102936229Z-abc29611`:

- recorder `BASE_READY_LIMITED_CAPTURED`, exit `0`;
- launcher exited and settled, exit `0`;
- stdout/stderr capture `COMPLETE`, untruncated, stderr empty;
- launcher result `BASE_READY_LIMITED`, `base_ready=true`;
- PostgreSQL and the pinned base set were preserved/confirmed ready;
- Docker Desktop, Public Gateway and Private Gateway used bounded `START_ONCE`;
- Supervisor remained `INTENTIONALLY_STOPPED`;
- Windows client used `START_ONCE` after the base readiness path.

After settlement, exactly one canonical client existed: PID `3516`, created
`2026-09-26T10:31:52.244688+02:00`; foreign client count was zero. Public
`/control` and `/control/` both returned `404`, and the Supervisor listener on
`127.0.0.1:8787` was absent. Host was `Ready`, enabled, and last result `0`.

The resume point now records
`COLD_LOGON_PASS_WAITING_OWNER_MANUAL_CRM_CONFIRMATION`, actual restart count
`1`, and the exact post-boot attempt. The remaining gate in this OP is only the
owner's manual confirmation that the client list and one client detail open
correctly. No retry, extra restart, manual start or new OP is authorized.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Anti-loop footer: one authorized restart and the real logon/cold path passed;
the operation pauses only for the prescribed manual CRM confirmation; no new
OP, package, review or K2/K3 campaign opened.
