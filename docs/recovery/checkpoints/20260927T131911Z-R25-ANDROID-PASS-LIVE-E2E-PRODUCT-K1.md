# R25 — Android PASS, live authenticated E2E product K1

UTC: `2026-09-27T13:19:11Z`

Status: `R25_IN_PROGRESS / LIVE_E2E_PRODUCT_K1 / CHANGES_REQUIRED`

## Anchory wejściowe i końcowe

- Branch: `recovery/next-stabil-repair-completion`.
- Dokumentacyjny HEAD wejściowy/local/tracking/remote: `fa2d2919f59c7cf600dcafe145a33c766e8ba37d`.
- Wdrożony source produktu: `16e8fcb5d311a20b703a74b1a9c966292b3499a8`.
- Backend: `021c33255883c37933dd68c8efc302f0c22348a5804199b39caf76f7e00d46f5`, `/health=200`.
- DB: `r25_external_scope_20260927 (head)`.
- Startup manifest: `APPROVED_FOR_START`, SHA-256 `7014D583910AAFBCCFF4CF3673ACC2DC647CE5AEF97194D42CC3B60FF69D429D`.
- Exact backend: `36/36`, mismatch `0`; Web `main.dart.js` SHA-256 `A6D708B2BF72664676F5232CD1208B3FB656FB275A65BCB927FEBC9AFDDCE80A`.
- Wszystkie sześć przypiętych container IDs zgodne; PostgreSQL healthy. Dodatkowy historyczny `app-postgres-postgres-1` nie jest częścią przypiętego zestawu i nie był zmieniany.
- Supervisor process/listener `0/0`; publiczne `/control=404`; pending `.r25tmp/.r25bak=0`.
- Windows działa nadal jako dokładnie jeden proces z preimage SHA-256 `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`.
- Nie wykonano backend/container/manifest mutation, restartu backendu, source patchu, Windows installer retry, R04 ani D-22.

## Windows — read-only trust diagnostic

Exact installer:

- ścieżka: `C:\Users\domai\AppData\Local\NEXT Stabil\BuildStaging\r25-16e8fcb\1.0.2+29-16e8fcb5d311\artifacts\NEXT-Stabil-Setup-1.0.2+29.exe`;
- bytes `13498751`;
- SHA-256 `EA69C1FF1DA1CB2E608FF49CABEB6ABBAEA763AB679B73B2FDBB55DF5EFA3CE9`;
- ProductVersion `1.0.2`, FileVersion `1.0.2.29`;
- Authenticode `NotSigned`; signer/timestamp brak;
- Zone.Identifier brak; origin claim i Managed Installer evidence brak.

Zainstalowany preimage `frontend.exe` jest również `NotSigned`, lecz zachowuje działające origin claim i Managed Installer evidence. R25 payload `frontend.exe` oraz siedem DLL są `NotSigned`: `flutter_windows.dll`, `file_selector_windows_plugin.dll`, `flutter_secure_storage_windows_plugin.dll`, `geolocator_windows_plugin.dll`, `permission_handler_windows_plugin.dll`, `speech_to_text_windows_plugin.dll`, `url_launcher_windows_plugin.dll`. Istniejący native hash manifest przypina wyłącznie `permission_handler_windows_plugin.dll` (`5CC6D938...DA2A`) i `geolocator_windows_plugin.dll` (`6C6B2B8F...5898`). Podpisanie zmieni ich oraz pozostałych PE hashe.

Read-only registry potwierdził `VerifiedAndReputablePolicyState=1`. Niepodniesione `CiTool.exe -lp -json` zwróciło access denied; nie użyto UAC, ponieważ wspierany równoważny dowód polityki i exact block evidence uzyskano z rejestru oraz Code Integrity Operational.

Exact eventy 3033/3077 z dwóch historycznych prób zawierają:

- politykę `VerifiedAndReputableDesktop`, ID `27555.1000.240208`;
- GUID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`;
- policy hash `2668895A5B233A80432D00D67251D7B7F52686A3FB13780F4B242C5A1F937A01`;
- exact installer path i flat SHA-256 `EA69C1FF...3CE9`;
- requested signing level `2`, validated signing level `1`;
- status `0xc0e90002`;
- blokadę przed utworzeniem procesu instalatora.

Read-only scan `CurrentUser\My` i `LocalMachine\My` znalazł `0` tożsamości spełniających łącznie Code Signing EKU, RSA, ważność/chain i dostępny private key. Nie odczytano ani nie zapisano prywatnego klucza, PIN-u, hasła, tokenu lub sekretnej konfiguracji providera.

Kanoniczny pipeline buduje unsigned Flutter payload i unsigned NSIS installer. Nie ma post-build signing step, `signtool`, `!finalize` ani `!uninstfinalize`; generated `Uninstall.exe` również nie ma hooka podpisującego. `windows-payload-fresh-manifest.json` oraz `windows-build-manifest.json` zapisują unsigned hashe. Przyszły signed-build plan musi:

1. uzyskać zatwierdzoną, zaufaną przez bieżącą politykę tożsamość RSA Code Signing bez eksportu klucza;
2. zachować deterministyczny unsigned reproducible payload manifest;
3. podpisać wszystkie dystrybucyjne EXE/DLL, ponownie policzyć signed hashes;
4. podpisać generated uninstaller przez NSIS hook i finalny installer;
5. zapisać oddzielny signed distribution manifest z cert fingerprint, algorytmem, RFC3161 timestamp i finalnymi hashami;
6. traktować timestampowane signed bytes jako niedeterministyczne i wykonywać install/installed-root acceptance dopiero w osobno zatwierdzonym oknie.

Klasyfikacja: `B. NO_TRUSTED_CODESIGNING_IDENTITY_AVAILABLE`.

## Android — kanoniczny signer i jedna instalacja

Read-only `adb devices -l` potwierdził dokładnie jeden online emulator `emulator-5554`, AVD `Pixel_8`, i zero urządzeń fizycznych.

Installed preimage:

- `pl.ailab.app`, version `1.0.0`, code `1`;
- APK SHA-256 `C9CCBAC0ECA4F942755BECDD1F3EBBA501A7694607A55FCB6EC92A759DEEEFD5`;
- signer SHA-256 `7A4397BF69CF0B21A6D028510C13FE84FAD7D3892B62F1C524B78D0B05CBE0F4` (`Android Debug`);
- v2 PASS; dane aplikacji około `85600 KiB`.

Exact R25 APK:

- SHA-256 `F24A250B5A32FDBF9DD9EAA15E62AAE378C06C766795E2D7179B856510B83E47`;
- version `1.0.2+29`;
- signer SHA-256 `5E223DA2DA7C893D089D7333E99AAEEE8D98C9CDF72BE80609020967368FE018`;
- v2 PASS;
- signer zgodny z historycznym kanonicznym manifestem Android R04.

Warunek Branch B został spełniony. Wykonano wyłącznie `adb -s emulator-5554 uninstall pl.ailab.app`, następnie dokładnie jedną instalację exact APK R25. ADB zwrócił `Success`; wrapper błędnie ocenił wieloliniowe stdout, dlatego nie wykonano retry i rozstrzygnięto wynik ograniczonym readbackiem. Readback potwierdził `pl.ailab.app`, `1.0.2+29`, canonical signer `5E223D...E018`, v2, zgodny installed/source APK hash, działający proces oraz normalny ekran logowania. Nie użyto `-d`, bypass flags, wipe/reset ani fizycznego urządzenia. Pulled APK usunięto z katalogu tymczasowego.

Android K1: `CLOSED / PASS`.

## Live authenticated E2E

Run ID: `R25_E2E_20260927T131429Z_2bc8101b`.

Operacja użyła wyłącznie syntetycznych rekordów oznaczonych własnym run ID i rzeczywistych endpointów login/JWT. Hasła i tokeny nie trafiły do terminala, repo ani checkpointu. Wynik macierzy do pierwszego materialnego defektu:

| Domena | Wynik | Dowód skrócony |
|---|---|---|
| A. Auth i role | PASS | login Administrator/User/External; JWT bez trwałej listy klientów |
| B. Grant management | PASS w wykonanym zakresie | admin grant, User idempotent grant, External denied |
| C. Klient i kontakty | PASS w wykonanym zakresie | A dostępne; B i direct B niewidoczne/404 |
| D. Project/realization | PASS w wykonanym zakresie | A positive; B negative |
| E. Inspection/site visit | PASS w wykonanym zakresie | A positive; B negative |
| F. Documents/files | PASS w wykonanym zakresie | syntetyczne A działa; B content/direct path niewidoczne |
| G. Mail | NOT RUN | stop na wcześniejszym materialnym defekcie |
| H. Task/calendar | PASS/PARTIAL | bezpośrednie work item A/B przeszło; pełny calendar nieosiągnięty |
| I. Timeline/notes/comments | PASS w wykonanym zakresie | A positive; B negative |
| J. Search/autocomplete/recent | FAIL / K1 | External `GET /api/v1/search?q=<prefix>` zwrócił 500 zamiast A-only 200 |
| K. Dashboard/counts/alerts | NOT RUN | stop po J |
| L. Notifications | NOT RUN | stop po J |
| M. Export/report | NOT RUN | stop po J |
| N. AI/retrieval | NOT RUN | stop po J; Ollama/Qdrant nie zmienione |
| O. Revoke/role/deactivation | NOT RUN w pełnej macierzy | stop po J; cleanup revoke wykonany |
| P. Regresje | PASS dla końcowych anchorów | health, control boundary, IDs, DB, manifest, Supervisor niezmienione |

Minimalny repro: rola `External`, owner client A, `GET /api/v1/search?q=<synthetic-prefix>`, expected `200` i A present/B absent, actual `500`. Traceback: `app/api/search/router.py:39`, `global_search_service.py:143`, `_documents:446`, następnie SQLAlchemy `InvalidRequestError: Select statement ... returned no FROM clauses due to auto-correlation`. Nie opublikowano response bodies ani danych firmy. Nie stwierdzono przecieku B; błąd uniemożliwia spełnienie wymaganej funkcji i pełnej macierzy, dlatego jest materialnym K1.

Zgodnie z decyzją właściciela nie wykonano source patchu ani restartu backendu. E2E zakończono po pierwszym materialnym defekcie.

## Cleanup i stan skutków

- active test grants: `0`;
- active test users: `0`;
- visible test clients: `0`;
- operation-owned files remaining: `0`;
- pulled APK: usunięte;
- lokalny test script/bytecode: usunięte;
- container temp script/result/journal: usunięte;
- Qdrant points: nie utworzono;
- pending mutation: `false`.

Lokalny exact-ID journal pozostaje poza repo wyłącznie jako dowód operacyjny. Do Git trafia wyłącznie zanonimizowany wynik.

## Otwarte K0/K1 i następna decyzja

K0: `BRAK`.

K1:

1. `R25_EXTERNAL_SEARCH_SQLALCHEMY_AUTOCORRELATION`: wymaga osobnej zgody na source fix, focused regressions, controlled deployment i pełne ponowienie live E2E od nowego run ID.
2. `WINDOWS_TRUSTED_SIGNING_REQUIRED`: wymaga osobnej zgody na pozyskanie/użycie zatwierdzonej zaufanej tożsamości RSA Code Signing, signed build, install i installed-root acceptance. Nie wolno rozpoczynać tego builda na podstawie bieżącej operacji.

Nie wolno nadać `R25_READY_FOR_OWNER_REVIEW` ani `R25_ACCEPTED`. R04 pozostaje organizacyjnie wstrzymane; D-22 pozostaje `NOT_RUN`.

Stopka anty-pętla: wynik zamyka Android K1 i klasyfikuje Windows bez retry. Następna praca dotyczy wyłącznie dwóch wykazanych K1; nie należy ponawiać preflightu, Android reinstallu ani diagnostyki Windows bez nowego dowodu regresji.
