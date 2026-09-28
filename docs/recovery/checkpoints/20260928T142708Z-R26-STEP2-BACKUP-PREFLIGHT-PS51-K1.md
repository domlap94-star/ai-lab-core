# R26 krok 2 — UAC zaakceptowany, backup preflight K1, brak mutacji

## Wynik

- operation ID: `R26-STEP2-LIVE-20260928T142708Z`;
- OutputRoot:
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R26-STEP2-LIVE-20260928T142708Z`;
- UAC: `ACCEPTED`;
- operacyjny preflight: `PASS`;
- backup: `FAIL_BEFORE_CHECKPOINT`;
- `mutation_started=false`;
- `pending_mutation=false`;
- migracja/deployment/emulator/smoke/fixture: `NOT_RUN`;
- status: `R26_STEP2_IN_PROGRESS / CONSOLIDATED_K1 /
  BACKUP_PREFLIGHT_PS51_SCALAR_COUNT`.

## Bounded preflight

- local/tracking/remote:
  `df52e2a61fb3f19200a883ef2a2ab22d11ba25b0`;
- worktree przed przygotowaniem operation-owned instalatora: clean;
- implementation/build SHA:
  `67b867ee279fe0bf7617c05b7d61fff0b337cab3`;
- Web candidate:
  `F7013E8E5DE072B679703DE07989B34415D4D94BD383C06ACFFBC2B0CAC3D0CB`;
- Windows installer:
  `562DBE2E41838D4960459958442CE314D1EE5E5299D869F446923666F6841A89`;
- Android APK:
  `52D8AD6E259691F52CC80245A884DF322FEB3C02F374BB0CD6A26D98E445AFCF`;
- DB: `r25_external_scope_20260927`;
- `scheduled_date`: absent;
- backend ID:
  `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- startup manifest valid / `APPROVED_FOR_START`;
- Supervisor `0/0`, active backup `0`, fixture/residue `0`;
- `F:\dump` istnieje i ma `490183430144` wolnych bajtów;
- dokładnie jeden target Android: emulator `emulator-5554`, bez telefonu.

## Konkretna przyczyna

Backup zatrzymał się przed utworzeniem
`F:\dump\20260928T142708Z`. Produkcyjny skrypt
`operations/hardening/backup-production.ps1` przypisuje wynik wyrażenia
warunkowego do `$selectedCollections` (linia 291), a następnie używa
`$selectedCollections.Count` (linie 296, 303 i 317).

Read-only reprodukcja w wymaganym Windows PowerShell 5.1 wykazała, że przy
jednej domyślnej kolekcji wynik zostaje rozwinięty do skalarnego `String`.
Przy `Set-StrictMode -Version 2` odczyt `.Count` kończy się:

`PropertyNotFoundStrict: The property 'Count' cannot be found on this object.`

Jest to wada kontraktu produkcyjnego backup runnera, nie wada implementacji
R26 ani artefaktów `1.0.2+43`.

## Rozliczenie skutków

- checkpoint backupu: nie powstał;
- backup artifact/manifest: nie powstał;
- operation-owned probe residue: `0`;
- DB nadal `r25_external_scope_20260927`;
- `scheduled_date` nadal absent;
- backend i wszystkie pozostałe kontenery zachowały ID;
- startup manifest nadal
  `A86582B48A854D963F61327F139A27160057B1004AFB1B394613D0DC28E39AE8`;
- stable manifest nadal
  `F65CC51573D583C408413CCAAAA62BBED84C9862FA8BB2109F223C48461135E5`;
- live Web nadal
  `44A53C0BF821D31279294D017D4D12673A822AAFFBAAF301B8C90900E4A115EE`;
- installed Windows nadal
  `C0DE8E94FF2BF4280ACDC2C1FA0B65701CB3A19D3269226F6C2BDB664C134CD5`;
- emulator nadal `versionName=1.0.2 / versionCode=42`;
- stable artefakty `+43`: absent;
- active backup `0`, Supervisor `0/0`, fixture/residue `0`;
- repo worktree po usunięciu operation-owned instalatora: clean.

Drugi UAC nie był dozwolony, ponieważ mutacja/deployment nie rozpoczęły się.
Nie wykonano retry, obejścia elevation, częściowej migracji ani naprawy source.

---
R25: `ACCEPTED` · R26 krok 1: `ACCEPTED / OWNER_CONFIRMED` · R26 krok 2:
`IN_PROGRESS / CONSOLIDATED_K1` · R04: `IN_PROGRESS / WSTRZYMANE` · D-22:
`NOT_RUN`
