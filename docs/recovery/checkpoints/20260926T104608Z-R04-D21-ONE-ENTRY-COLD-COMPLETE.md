# R04 / D-21 — ONE-ENTRY-COLD complete and owner-confirmed

Status: `ONE_ENTRY_COLD_COMPLETE / OWNER_CONFIRMED`.

Operation `R04-D21-ONE-ENTRY-COLD-COMPLETE-20260925T183020Z` completed its
authorized scope:

- approved manifest V2 was atomically installed and validated;
- pre-restart repeat produced a complete settled recorder result with zero new
  service/container starts and exactly one client;
- exactly one Windows restart was performed;
- the real Host logon trigger completed with result `0`;
- post-boot recorder attempt `20260926T102936229Z-abc29611` captured
  `BASE_READY_LIMITED`, complete streams, empty stderr, base readiness,
  Supervisor `INTENTIONALLY_STOPPED`, and one client started through the cold
  path;
- exactly one canonical client remained, with no foreign/duplicate client;
- public `/control` and `/control/` remained `404`, and Supervisor listener was
  absent;
- no manual start, retry or second restart occurred.

The owner then manually confirmed that the client list and the details of one
client open correctly. The OutputRoot resume record is
`ONE_ENTRY_COLD_COMPLETE_OWNER_CONFIRMED`, manual CRM confirmation
`PASS_OWNER_CONFIRMED`, actual restart count `1`.

This completes and owner-confirms the exact ONE-ENTRY-COLD OP. It does not
complete all of R04, authorize D-22, or change backup, relocation, retention,
data, container, Supervisor, firewall, Tailscale or credential scope.

`USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` remains accepted. R04 remains
`IN_PROGRESS`; D-23 remains `2/2`; D-22 remains `NOT_RUN`.

Anti-loop footer: the agreed ONE-ENTRY-COLD result is complete and confirmed;
no new OP, package, review or K2/K3 campaign is opened by this checkpoint.
