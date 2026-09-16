# R04 / D-21 — ACTIVE_DATA_ONLY destination guard handoff

UTC: `2026-09-16T08:30:44Z`

## Tożsamość

- Start local/tracking/remote: `be8ac25728e0b6c59a55b5b4d708edc0e124e726`.
- Preimage poprawki: `e4f298a46efa2ad29921fcf7cce0ca6a04f3d0fd`.
- Source: `cb6e22506a0fecc440400566293524536847b9b0`.
- Source tree: `c349a1d6ebfeb6077bc62181667f7f3c8f9d42cc`.
- Main: `483f9bf8b1a591ded8a42df5da87663c664ed5d4`.
- Rescue: `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`.

## Wynik

`RV-D21-DATA-01 = REPRODUCED`. Rzeczywisty walidator preimage dopuścił do
planu zarówno `backend/APPLICATION_DATA -> /app/app`, jak i wewnętrznie spójną,
ale obcą parę `postgres/N8N_DATA -> /home/node/.n8n`; oba fail-before zakończyły
się exit `1` na asercji odmowy.

Source wiąże teraz dokładny, case-sensitive kontrakt `service + role +
destination` dla pięciu zatwierdzonych wariantów. Zgodność dwóch dowolnych pól
manifestu nie nadaje zgody, a Open WebUI zachowuje prawidłowe
`/app/backend/data` wyłącznie dla własnej roli.

## Testy offline

Windows PowerShell `5.1.26100.8894`:

- destination guard/junction: `44/44`, exit `0`;
- host plan: `53/53`, exit `0`;
- real-adapter mapping: `48/48`, exit `0`;
- parser pięciu `.ps1` i JSON przykładu: błędy `0`, exit `0`.

Surowe logi i preimage pozostają LOCAL_ONLY pod
`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\active-data-junction-20260916T055951Z\destination-guard-20260916T082046Z`.

## Skutki i granice

- Zmieniono wyłącznie `startup-runtime.ps1`, test junctionu i README.
- Nie wywołano Docker/HTTP/CIM/TCP/Task Scheduler ani startu usług.
- Własny syntetyczny junction został rozliczony i usunięty przez test.
- Istniejący junction, dane D:, backup schedules, produkcja i Supervisor nie
  zostały zmienione; Supervisor pozostaje `INTENTIONALLY_STOPPED`.
- P2 pozostaje `PRESERVATION_AND_CANDIDATE_ACCEPTED / NOT_DEPLOYED`.
- Kandydat pozostaje `NOT_APPROVED_FOR_START`; P3–P5 są `NOT_RUN`.

## Status i następny krok

`R04 D21 ACTIVE_DATA_DESTINATION_GUARD_READY_FOR_REVIEW / OFFLINE_TEST_ONLY`.

Następny krok: review tej poprawki, a następnie osobna zgoda na przygotowanie
dokładnego P3: `KEEP` poprawnych zapisów D:, ograniczone rozliczenie brakujących
lokalizacji oraz oddzielne przełączenie wersji backendu. Ten checkpoint nie
upoważnia do P3, instalacji, startu, relokacji ani cleanupu.
