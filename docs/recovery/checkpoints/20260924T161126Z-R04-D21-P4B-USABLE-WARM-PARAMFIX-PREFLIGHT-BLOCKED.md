# R04 / D-21 / P4-B — USABLE-WARM param-fix, operacja zatrzymana w preflight

UTC wyniku: `2026-09-24T16:11:26.7964909Z`

Status: `P4B_USABLE_WARM_PARAM_FIX_OFFLINE_PASS / OPERATION_PREFLIGHT_BLOCKED_RUNTIME_IMPORT_VISIBILITY / NO_MUTATION / WARM_RUNS_0_OF_2 / LOGON_NOT_CONFIGURED / CRM_WEB_NOT_OPENED / UAC_CONSUMED`

## Zakres i wejście

- Window: `R04-D21-P4B-USABLE-WARM-CONTINUE-EXEC-PARAMFIX-20260924T155752Z`.
- Pinned continuation ID: `R04-D21-P4B-USABLE-WARM-CONTINUE-20260924T104156Z`.
- Preimage continuation: `25749` B / `D2F6D8490C39A3FF61A8D8D0DC5DDF260FC46DCF7EFF67E4F02A25A8482CF63B`.
- Derived continuation: `28361` B / `7511C8B9428FCBAF7C40FB8824C25F8C73E5D816EE7FD48527684105E7E91F34`.
- Derived continuation index: `5471` B / `968FC37EF85FEFB5C1BB2469856862E9838D650FC095818CD62D2B0981E87696`.
- Offline harness: `28035` B / `9E75337B0497C9F941C4BC3B986311C39E831AB987FF1949419FEC8E6081AD90`.
- Offline result: `PASS`, `9` scenarios, `43` assertions, production boundaries `0`; `811` B / `09A0ABA3FFFD5622175B5617CD0B64CD93278718DE2D120F0F8E9517751797E6`.

## Udowodniona poprawka

Fail-before wykazał, że dot-source bazowej recepty nadpisywał argumenty
kontynuacji (`DefinitionOnly=true`, puste index/id/output i acknowledgement
`false`). Import launchera nadpisywał również lokalny `ManifestPath`. Pochodna
zachowuje argumenty przed importami, wiąże ścieżkę manifestu niezależnie i na
czas dedykowanego procesu udostępnia exact funkcje hash-pinned recepty bazowej
wymagane przez closure-backed boundary. Oryginały pozostają bez zmian.

## Rzeczywiste wykonanie

Po bieżącym potwierdzeniu właściciela wykonano dokładnie jeden UAC. Elevated
PID `70972` zakończył się exit `22`. Nie wykonano drugiego wywołania.

LOCAL_ONLY dowody:

- `C:\Users\domai\AppData\Local\Temp\P4B-UWC-01\apply\result.json` — `3419` B / `C4C1863A3441B61FE551DBB77957D07DB9FC42666D0159061AA38BFD2714C51F`;
- `C:\Users\domai\AppData\Local\Temp\P4B-UWC-01\apply\preflight.json` — `6940` B / `8A47A3B5E975B4212DA65F6405B5A22A2E5A2E2E7738C989A3E2260D8F9DB7AF`.

Preflight potwierdził:

- cztery installed files: exact hash match;
- Host: `OBSERVED / Disabled / enabled=false / trigger_count=0 / idle`, exact accepted semantic/comparable identity;
- HTTP: backend `200`, Web `200`, Public Gateway `200`, public control boundary `404`;
- Docker/WSL pool i swap: zachowane `UNKNOWN_ACCEPTED_FOR_THIS_WINDOW`.

Blokada: runtime adapter po imporcie launchera nie widział
`Get-StartupProperty`. Z tego powodu Docker context/engine, sześć obserwacji
kontenerów i trzy obserwacje host services są `UNKNOWN`; nie są PASS ani
potwierdzonym brakiem zasobu.

## Skutki

- `mutation_started=false`, `pending_mutation=false`;
- journal `NOT_OPENED`, SAFE_INACTIVE `NOT_NEEDED`;
- Host transitions `0`, Host starts `0`, warm runs `0/2`;
- Private start `0`, logon `NOT_CONFIGURED`, CRM/Web shortcut `NOT_RUN`;
- Supervisor nie otrzymał startu;
- jeden UAC i zgoda są zużyte; brak retry, alternatywnego kanału i kolejnej mutacji.

R04/R05 pozostają `IN_PROGRESS`; pełne R04/P4-B nie jest `ACCEPTED`.
D-23 pozostaje `2/2`; bez K2/K3 i bez rozpoczęcia D-22.
