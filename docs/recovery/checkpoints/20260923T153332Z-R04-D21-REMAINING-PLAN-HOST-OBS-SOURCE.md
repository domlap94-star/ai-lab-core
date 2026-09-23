# R04 / D-21 — remaining plan and host-service observation source

- UTC: `2026-09-23T15:33:32.4797364Z`
- Entry documentation HEAD: `fa4a1dc6e577ca235a936ba18e5a73287b356d37`
- Source commit: `49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc`
- Scope: owner-authorized SOURCE / LOCAL FILE READ / OFFLINE TEST / COMPLETE
  R04 PLAN only

## Source result

The two previously proved host-service blockers were closed together:

1. process identity compares only the one code token by its canonical path
   below the approved root; executable, token count and every other argument
   remain exact;
2. the bounded worker reads one complete
   `Get-NetTCPConnection -State Listen -ErrorAction Stop` snapshot without a
   port selector and filters the exact service port locally. Only a successful
   complete no-match proves listener absence. Error, timeout and incomplete
   evidence remain `UNKNOWN`.

Final source identity:

- `operations/runtime/start-host-services.ps1`: `79010` B, SHA-256
  `686F4EC877AADC93D46D2B67858864BF9C728B00093037A266B257099BA14B66`;
- `operations/runtime/test-startup-real-adapters.ps1`: `46371` B, SHA-256
  `2EB93F7C328C10CAEF79EF7779B0CDE61FEFC1F300E3CA8770B743218512750F`;
- `operations/runtime/README.md`: `14323` B, SHA-256
  `43ED2730D05399F77221129E0581DE635EB6D4D1EA6614D413210CF80FE14869`.

Windows PowerShell 5.1 final tests:

| Scope | Assertions | Exit |
|---|---:|---:|
| production real adapter + complete plan through lower fakes | 53 | 0 |
| direct startup-plan regression | 57 | 0 |

Parser PASS. Docker, Task Scheduler, CIM, TCP, HTTP, UAC, service starts/writes,
installation and rollback calls against production: `0`.

## Inactive binding and operational state

The repository draft is now
`R04-D21-P4A-HOST-OBS-SOURCE-20260923T153332Z`, `30818` B, SHA-256
`967E9C2C17D7E512B11F0B8D4E9847DD3D2C18138958DBD5D5ED5AA92F400457`.
It binds the new launcher bytes and remains `NOT_APPROVED`; no active manifest
or package was changed. Frozen recipe `CA6A5DCC...87157` remains historical and
cannot install these new bytes unchanged.

Installed run01 remains untouched on its historical bytes: Host
disabled/no-trigger, warm `0/2`, Supervisor historically
`INTENTIONALLY_STOPPED`. Containers, backend flags, junction, data and backup
schedules were not read or changed. D-22 remains `NOT_RUN`.

## Complete remaining R04 path

`R04_SINGLE_ROOT_STARTUP_PLAN.md` §8 now fixes four coherent windows:

1. `R04-P4B-USABLE-WARM`: exact derivative + fresh preflight, then only after a
   separate current owner confirmation one UAC, four-file/Host narrow update,
   two warm runs `Private 1 -> 0` and one logon trigger. This yields usable
   CRM/Web through the preserved separate client shortcut, not one-click R04.
2. `R04-ONE-ENTRY-COLD`: minimal `OPEN_AFTER_BASE_READY`, manual entry and one
   controlled logon/cold-start.
3. `R04-DATA-BACKUP`: bounded physical backing/schedule evidence, followed only
   by exact owner-approved relocations or one controlled backup proof.
4. `R04-COMPATIBILITY-ACCEPTANCE`: component compatibility manifest and
   adequate Web-first/Windows/Android checks without blanket rebuilds.

P5/R24 cleanup is later and does not block the first usable segment. None of
these future windows is authorized by this checkpoint.

Status:
`HOST_SERVICE_PROCESS_AND_LISTENER_OBSERVATION_SOURCE_READY_FOR_REVIEW /
OFFLINE_TESTS_PASS / COMPLETE_REMAINING_R04_PLAN_RECORDED /
INACTIVE_CANDIDATE_NOT_APPROVED / NOT_DEPLOYED / STAGE_B_NOT_AUTHORIZED`.

> **ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT**
>
> Przed oceną przeczytaj roadmapę §0, `ANTI_EXCESSIVE_WORK`, kartę R04 i ten
> checkpoint na pełnym opublikowanym SHA. Zachowaj odbiory i D-23 `2/2`; nie
> otwieraj K2/K3.
>
> K0/K1 blokujące następny krok: `BRAK NOWEJ WADY SOURCE`; operacyjnie nowy
> exact package, fresh preflight i bieżące potwierdzenie przed UAC nie istnieją
> jeszcze. Efekt użytkowy: source usuwa dwa udowodnione fałszywe wyniki, ale
> run01 nadal nie ma udanego warm runu. Następny krok: jedno owner-approved
> `R04-P4B-USABLE-WARM` window; bez automatycznej zgody na hosta.
