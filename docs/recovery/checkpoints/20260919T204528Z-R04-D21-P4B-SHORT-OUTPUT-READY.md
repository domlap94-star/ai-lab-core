# Checkpoint — R04 / D-21 / P4-B short output ready

Checkpoint UTC: `2026-09-19T20:45:28Z`

Entry HEAD: `6cb706741d3e35afb2d790bf399a91e93a2d3202`

Branch: `recovery/next-stabil-repair-completion`

## Stan

Przygotowanie objęte jednorazową zgodą odczytową zakończyło się wynikiem:

`SHORT_OUTPUT_DERIVATIVE_READY_FOR_REVIEW / TASKINFO_6_OF_6 /
CURRENT_DRIFT_PASS_WITH_RESOURCE_LIMITATION / NO_UAC / NOT_INSTALLED`.

Nowa LOCAL_ONLY pochodna recepty ma SHA-256
`F65DF7232ADC3DBFE6B35FC08D255D385748ED17CC3078CACB93501FB9BF8C9A`.
Jej package index ma SHA-256
`36623A0384F400D10D9FF0714FE7ED67B0090FC872C19751ED195D2E52C8D49E`.
Review ZIP ma 75,385 B i SHA-256
`407A872A9B0504F35F2141992E3F84132198175A0146B5B0D1925B0F878D7272`;
roundtrip `17/17`, mismatch `0`.

## Dowody wykonania

- poprawka TaskInfo: PowerShell 5.1, `16` przypadków, `126` asercji,
  `14/14` workerów, real system calls `0`;
- live TaskInfo: `6/6`, `6/6` workerów, bez startu lub zmiany taska;
- input/index: `14/14`, `110` asercji;
- orkiestracja/rollback: `15/15`, `96` asercji, `437/437` workerów;
- ścieżki/I/O: maksimum `206 <= 220`, root/event/result `52/75/79`,
  roundtrip wymaganych API `PASS`;
- VerifyInputsOnly: `29/29` wejść, sześć baseline'ów, exit `0`, bez host calls;
- bieżący drift: sześć tasków i sześć kontenerów zgodne, PostgreSQL healthy,
  backend/Public Gateway `200`, publiczne `/control*` `404`, Windows/disk gates
  przeszły; Docker/WSL pool available i swap-used `UNKNOWN`.

Bezpieczna projekcja driftu: 55,768 B, SHA-256
`72788969A6AEB0B15EB4F25E1A98158274A5F925E5A555B83A605DA126E7C012`.
TaskInfo summary SHA-256:
`40D40B85B87EEAD3536246A2EF4675F11F25162313C8B85FB07DF94FB7A88B4D`.

## Skutki i STOP

`out\run01` pozostaje nieobecny. UAC/RunAs/Install, zmiany tasków, zapis plików
instalacji, start usług, warm runs, rollback i mutacje danych wynoszą `0`.
Supervisor pozostaje `INTENTIONALLY_STOPPED`, globalny manifest
`NOT_APPROVED_FOR_START`, P4/B `PARTIAL_SAFE_INACTIVE / NOT_INSTALLED`.

External resume ID przygotowany do osobnej decyzji:
`R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z`.

Następny krok: przed jednym RunAs/UAC właściciel musi w tej samej rozmowie
zaakceptować dokładną pochodną, indeks, krótki output, dwa warm runs i warunkowy
SAFE_INACTIVE rollback wraz z ograniczeniami WSL/swap, HKCU Run, UI i relokacji.
Ten checkpoint sam nie udziela takiej zgody.

D-22 i kolejność po R04 pozostają niezmienione oraz `NOT_RUN`.
