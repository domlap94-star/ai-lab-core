# R04 / D-21 — active data junction source handoff

UTC: `2026-09-16T06:24:47Z`

## Stan

- Parent wejścia: `f872cf9e548a7ec196289e0c1987b654b1017505`.
- P2: `PRESERVATION_AND_CANDIDATE_ACCEPTED / NOT_DEPLOYED` dla source
  `2e69622bc6a0b4888427f8ae5be119377aed26d9` i evidence parent powyżej.
- Source DATA_ONLY: `e4f298a46efa2ad29921fcf7cce0ca6a04f3d0fd`, tree
  `873d199ed43c5d6719a34f2158b0537f7e07a73b`, opublikowany na recovery.
- Status: `ACTIVE_DATA_D_JUNCTION_SOURCE_READY_FOR_REVIEW / OFFLINE_TEST_ONLY /
  NOT_DEPLOYED`.
- Dokładny układ właściciela: `C:\ai-lab-core\data -> D:\ai-lab-data`, Windows
  directory junction, `ACTIVE_DATA_ONLY`. Istniejącego linku ani danych nie
  zmieniono.

## Testy źródła

Windows PowerShell `5.1.26100.8894`:

- `operations/runtime/test-startup-data-junction.ps1`: exit `0`, `20/20`;
  stdout SHA-256 `D59D16D3B5EF1F46E4C896B875B411706DC8366E2B38F0D7B255469F16346A91`.
- `operations/runtime/test-start-host-services.ps1`: exit `0`, `53/53`;
  stdout SHA-256 `6B15018D1A1C7EFA831F7B3C6A6DCDBFFE2D4922A0C97B36925134DBAE55DD15`.
- `operations/runtime/test-startup-real-adapters.ps1`: exit `0`, `48/48`;
  stdout SHA-256 `6112F31AFB76A2D7F192C0DFB8149226CD06D45C22038E7ADDB67C9F53A8881D`.
- Parser pięciu właściwych `.ps1`: `0` błędów; JSON przykładu: PASS.
- Kandydat: JSON PASS; `NOT_APPROVED`; source/tree, pięć bindingów, hash
  `startup-runtime.ps1` i niezmienione pochodzenie Web zgodne.
- Preimage: exit `1`, `MANIFEST_REFUSED`,
  `CONTAINER_BIND_REPARSE_POINT:backend`; jest to zmiana polityki właściciela,
  nie regresja przyjętego P1.

Test użył wyłącznie własnej syntetycznej struktury i kompletnych atrap granic.
Nie wywołał Dockera, HTTP, CIM/TCP/Task Scheduler, aplikacji ani usług produktu.

## Dowody i ograniczenia

- Lokalny evidence root:
  `C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\active-data-junction-20260916T055951Z`.
- Snapshot SHA-256 `318A41F24F5B2949A06A24B38BB5D2B599E300734E67F1E91E0F5C59879CC6C3`
  pozostaje przypięty do starego source/tree; nie jest snapshotem `e4f298a...`.
- Web TEST_ONLY SHA-256
  `A99FB9E30FD66F815509434BD594050D82F4D5D1B6E45A36DB6DDECC085A4C41`
  i frontend tree `44998e7c6519ceb98c9dc1a61d4c2261af6ad373` są niezmienione;
  `git diff` dla `backend/app` i `frontend` między `2e69622...` i `e4f298a...`
  ma exit `0`; build/UI nie zostały ponowione.
- Tabela miejsc zapisów zachowuje klasy `CONFIRMED_D`,
  `CURRENT_C_REQUIRES_RELOCATION`, `UNKNOWN` i `NOT_APPLICABLE`. Nie ma
  deklaracji `ALL_LIVE_WRITES_ON_D_PASS`.
- Backup schedules, retencja, cele, dane i R03 nie zostały zmienione ani
  uruchomione. Supervisor pozostaje `INTENTIONALLY_STOPPED`.
- Manifest pozostaje `NOT_APPROVED_FOR_START`; P3–P5 są `NOT_RUN`.
- Rejestry: `108/36/61/16/25`, package details `25`, decyzje `21`, mapa D-21
  `33`; duplikaty ID `0`. CSV/JSON PASS, `git diff --check` PASS, secret scan
  trafienia `0`.

## Następny krok

Review source DATA_ONLY oraz osobna zgoda na minimalny P3: zachować (`KEEP`)
potwierdzone bindy na D:, rozliczyć Qdrant/VHD/tablespaces/logs/profile i exact
ID/image/mounty/flag, następnie oddzielić przełączenie wersji backendu od
relokacji pozostałych zapisów. Ten checkpoint nie udziela takiej zgody.
