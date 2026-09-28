# R26 krok 2 — hotfix PS5.1 publiczny, UAC anulowany, brak mutacji

## Wynik

- product/build source: `67b867ee279fe0bf7617c05b7d61fff0b337cab3`;
- backup runner hotfix source:
  `7dff894b09facc9e8763296a2bf7ea5e03117535`;
- operacja: `R26-STEP2-HOTFIX-20260928T163858Z`;
- planowany OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-HOTFIX-20260928T163858Z`;
- UAC: `CANCELLED_BEFORE_CREATEPROCESS`;
- OutputRoot: `ABSENT`;
- produkcyjna mutacja: `NONE`;
- status: `R26_STEP2_IN_PROGRESS / CONSOLIDATED_K1 /
  UAC_CANCELLED_NO_MUTATION / QDRANT_HELPER_NOT_INSTALLED`.

## Source i testy

Fail-before uruchomiony pod dokładnym Windows PowerShell 5.1 na blobie sprzed
poprawki zwrócił `FAIL_BEFORE_PROPERTY_NOT_FOUND_STRICT`.

Minimalny fix:

- wymusza `[string[]]$selectedCollections = @(...)`;
- iteruje jawnie po wejściowej tablicy;
- wylicza `[int]$selectedCollectionCount`;
- używa jawnego count w walidacjach liczby;
- nie zmienia nazw kolekcji, duplikatów, LegacyV1, RecoveryPointV2, proof mode,
  destination ani StrictMode.

Pass-after:

- PS5.1 parser: `0` błędów;
- macierz selection: `7/7 PASS`;
- default/single: `string[]`, count `1`;
- RecoveryPointV2: count `2`, obie wymagane nazwy;
- duplicate/invalid/legacy-two/recovery-missing: oczekiwane błędy;
- Qdrant helper contract: `PASS`;
- secret/business-content scan: `PASS`.

## Binding audit

- installed startup manifest: brak aktywnego bindingu runnera;
- historyczne startup candidates/installery: `HISTORICAL_EVIDENCE`, bez zmiany;
- recovery tool manifest `1.2.0`: `INDEPENDENT_PINNED_TOOL_VERSION`, bez zmiany;
- ACL/hardening references: path-only, bez hash bindingu.

## UAC i readback

Windows zwrócił `Operacja została anulowana przez użytkownika` przed
utworzeniem procesu podniesionego. Nie wykonano retry ani alternatywnego kanału.

Readback:

- aktywny runner: `36724` B,
  `25BD1F12B237A603D2C19323C175E3220ECFA2E8B97FAB48B05D3DE3CCEB4DDE`;
- DB revision: `r25_external_scope_20260927`;
- `scheduled_date`: absent (`0` kolumn);
- backend ID:
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest:
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- active backup: `0`;
- planowany checkpoint `F:\dump\20260928T164058Z`: absent;
- migracja/backend/Web/Windows/Android/live smoke/fixture: `NOT_RUN`.

## Dodatkowy materialny blocker pełnego backupu

Aktywny root zawiera validator, lecz nie zawiera:

`C:\ai-lab-core\operations\hardening\invoke-qdrant-backup-helper.ps1`.

Obecny `backup-production.ps1` wymaga tego pliku przed Qdrant stage. Pełny
RecoveryPointV2 z dwiema wymaganymi kolekcjami nie może przejść. Faza A
bieżącej zgody zezwalała na instalację wyłącznie runnera, dlatego helpera nie
zainstalowano.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` · D-22:
`NOT_RUN`
