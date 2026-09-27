# R25 — forward recovery / consolidated K1

- Timestamp: `2026-09-27T12:44:57Z`
- Source revision: `16e8fcb5d311a20b703a74b1a9c966292b3499a8`
- Operation: `R25-DEPLOY-20260927T121935Z`
- Status: `R25_IN_PROGRESS / FINAL_CONSOLIDATED_K1 / NOT_ACCEPTED`

## Wynik wykonany

- Addytywna migracja pozostaje forward-only na `r25_external_scope_20260927`; tabela `client_access_grants` i rola `External` istnieją. Nie wykonano downgrade, stamp, restore ani usuwania historii.
- Exact `36/36` plików backendu z opublikowanego source jest zainstalowane i hash-bound.
- Backend-only replacement użył niezmienionego obrazu `sha256:6342b36f...d63702`, mountów, portu, networku, restart policy i credential names. Nowy container ID: `021c33255883c37933dd68c8efc302f0c22348a5804199b39caf76f7e00d46f5`.
- Runtime: source `16e8fcb5...`, schema R25, release `NEXT-STABIL-R25-f1771f66a37cfe3d`, `/health=200`, version `1.0.2`, API `1`, production, debug false, SAFE; dziewięć flag pozostaje false.
- PostgreSQL jest healthy; ID `postgres`, `qdrant`, `n8n`, `open-webui` i `ollama` pozostały bez zmian.
- Pochodny installed startup manifest jest `APPROVED_FOR_START`, wiąże faktyczny backend ID, exact 36 plików, runtime override i Web. SHA-256: `7014D583910AAFBCCFF4CF3673ACC2DC647CE5AEF97194D42CC3B60FF69D429D`.
- Web R25 został wdrożony; `main.dart.js` SHA-256 `A6D708B2BF72664676F5232CD1208B3FB656FB275A65BCB927FEBC9AFDDCE80A`; `/` i `/shared-clients` zwracają `200`; publiczne `/control*` pozostaje `404`.
- Bounded synthetic R25 workflow przeszedł: A/B scope, grant/regrant/revoke, role change, migracja, manager options i HTTP direct-ID 404. Live OpenAPI zawiera trzy endpointy `client-access`; bez tokena chronione endpointy zwracają `401`.
- Supervisor process/listener `0/0`, residue `.r25tmp/.r25bak=0`, `pending_mutation=false`.

## Materialne K1

1. `WINDOWS_APPLICATION_CONTROL_BLOCKED`: exact installer `EA69C1FF...3CE9` został zablokowany przez Windows Application Control przed startem procesu zarówno zwykłym wywołaniem, jak i jedynym dopuszczonym `RunAs`. Instalacja nie rozpoczęła się; klient pozostał na exact preimage `5BD959A3...B0865`. Nie użyto obejścia ochrony.
2. `ANDROID_SIGNATURE_OWNER_DECISION_REQUIRED`: standardowy update exact APK `F24A250B...E47` na jedynym emulatorze zakończył się `INSTALL_FAILED_UPDATE_INCOMPATIBLE`. Nie wykonano uninstallu, nie dotknięto fizycznego urządzenia i nie zmieniono danych emulatora.
3. `FULL_POST_DEPLOY_E2E_NOT_COMPLETE`: focused synthetic PASS pokrywa role, aktywny grant, idempotentny regrant, revoke, zmianę roli, listy klientów/projektów/inspections, manager options i direct client ID 404. Nie wykonano pełnego live authenticated fixture workflow obejmującego wszystkie wymagane zasoby plikowe, mail, task/calendar, timeline, search/count, notification, export i AI; nie użyto poświadczeń właściciela ani danych firmy do pozornego PASS.

## Następny krok

Jedna skonsolidowana decyzja właściciela powinna wskazać zaufany przez Application Control kanał instalacji exact Windows artifactu oraz osobno APK podpisany zgodnym kluczem albo jawnie zatwierdzony uninstall/install wyłącznie emulatora. Po wdrożeniu klientów wymagany pozostaje pełny live authenticated fixture E2E. Bez tego domknięcia nie wolno nadać `R25_READY_FOR_OWNER_REVIEW`, ponawiać instalacji, obchodzić ochrony, wznawiać R04 ani rozpoczynać D-22.
