# R25 — External search fix i pełny post-deploy E2E PASS

Data: `2026-09-27`

Source: `34834c96443da619d051b66ea4ef37f055a6549b`

Status: `R25_IN_PROGRESS / FULL_POST_DEPLOY_E2E_PASS / ANDROID_PASS / WINDOWS_TRUSTED_SIGNING_REQUIRED / NOT_ACCEPTED`

## Wynik użytkowy

- External korzysta z pełnego klientowego workflow wyłącznie dla aktywnie udostępnionego klienta A; klient B pozostaje niewidoczny i nieenumerowalny przez listy, direct ID, pliki, search, agregaty i AI.
- Revoke działa od następnego requestu w backendzie, Web i Androidzie.
- Administrator i User zachowują istniejące zachowanie; grant management pozostaje niedostępny dla External.
- Backend, Web i Android są technicznie PASS. R25 nie jest gotowy do owner review wyłącznie z powodu `WINDOWS_TRUSTED_SIGNING_REQUIRED`.

## Przyczyna i source fix

Fail-before na izolowanym PostgreSQL odtworzył HTTP 500 jako SQLAlchemy `InvalidRequestError`: zewnętrzne joiny `Project`/`Inspection` oraz ponowne użycie tych samych mapped classes w `EXISTS` pozwalały auto-correlation usunąć wszystkie lokalne FROM. Minimalna poprawka w `global_search_service.py` używa osobnych aliasów scope i `.correlate(Document)`.

Bezpośrednie dowody:

- `test_r25_external_search_scope.py`: `5/5 PASS` — compile FROM, lexical, semantic, direct-ID 404, scope-before-limit i Admin/User unchanged;
- istniejący external scope suite: PASS;
- `test_chunk11_global_search.py`: `9/9 PASS`;
- `test_client_list_contract_e2e.py`: PASS dla 60 syntetycznych klientów;
- source commit opublikowany: `34834c96443da619d051b66ea4ef37f055a6549b`.

## Controlled deployment

Pierwsza próba osiągnęła zdrowy forward backend, ale lokalny harness błędnie czytał `release_id` i `runtime_configuration` z `component_identity.backend` zamiast `component_identity`. Zgłosił fałszywy timeout, przywrócił source/override i odtworzył backend. Ograniczony readback wykazał spójny runtime na preimage z nowym ID kontenera; operation-owned reconciliation zaktualizował wyłącznie manifest do faktycznej tożsamości i zakończył `FAILED_ROLLED_BACK_RECONCILED / pending_mutation=false`.

Po poprawieniu wyłącznie projekcji harnessu wykonano dotknięty deployment bez drugiego UAC. Wynik:

- backend container: `2e6e9e04aac2728ac84fed38078cb6e5628620525b83c848f850332b6b879e42`;
- image digest bez zmiany: `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`;
- source revision: `34834c96443da619d051b66ea4ef37f055a6549b`;
- release: `NEXT-STABIL-R25-searchfix-34834c96443da619`;
- schema: `r25_external_scope_20260927`;
- deployed source SHA-256: `CF1AB70B44D283A34C5138D7AC28EC9BBD83B8D1A88026EC4EF7FC40199D90B3`;
- version override SHA-256: `87C940B3B7C767C4DCF67EAA19D62E7978A0164DE96AC8E9905B763807E9B8B3`;
- startup manifest SHA-256: `F9C33CB404589309ED3CDE1D8956C96882DBB194654DA21DB0139B350E6BCCCA`;
- manifest: `APPROVED_FOR_START`, zgodne `set_id=approval.set_id`, walidator `valid=true`;
- pięć pozostałych pinned container IDs, obrazy, mounty i porty bez zmiany;
- `/health=200`, version `1.0.2`, API `1`, production, debug false, runtime `SAFE`, `/control` i `/control/status` = `404`;
- Supervisor process/listener `0/0`; pending mutation `false`.

## Pełny świeży live E2E

Run: `R25_E2E_20260927T150637Z_7b275f03`.

Rzeczywiste HTTP/JWT i operation-owned syntetyczne fixture potwierdziły PASS dla:

- auth/role i External bez grantów;
- idempotentnego grant, regrant, revoke i historii;
- clients, contacts, address, phone;
- projects i inspections;
- documents, version, preview, thumbnail, raw i download;
- mail, thread, attachment i walidacji send bez transportu;
- tasks, calendar, timeline i notes;
- lexical oraz semantic search z A i bez B;
- scoped aggregates, calendar-alert surface i scoped downloads;
- klientowego AI direct retrieval bez zewnętrznego modelu;
- deactivation, deleted-client deny, External→User i User→External;
- Admin/User regressions oraz admin boundary;
- identycznych 404 dla B, mixed i unknown direct IDs;
- braku cross-client leak.

Nie użyto danych klientów, real mail, Gmail, n8n, produkcyjnych kolejek ani zewnętrznego AI.

## Web i Android

Web potwierdził rzeczywisty login External, listę wyłącznie Client A, szczegóły A, manager grant/revoke/history UI oraz pustą listę po revoke.

Android:

- jedyny target `emulator-5554`; urządzeń fizycznych `0`;
- istniejący pakiet `pl.ailab.app`, `1.0.2+29`; bez reinstall, uninstall i clear-data;
- login External, lista wyłącznie A, szczegóły A i brak B: PASS;
- po backendowym revoke i close/reopen: `Brak udostępnionych klientów.`;
- crash: brak; aplikacja po teście zatrzymana.

## Exact cleanup i readback

Cleanup zwrócił:

- active grants `0`;
- active synthetic users `0`;
- visible synthetic clients `0`;
- documents `0`;
- work items `0`;
- mail sources `0`;
- files `0`;
- Qdrant points `0`;
- pending mutation `false`.

Operation-owned state z syntetycznymi poświadczeniami, container harness, screenshots i lokalne skrypty operatora usunięto. Historycznych danych biznesowych nie zmieniono.

Windows pozostał bez instalacji i bez obejścia ochrony: dokładnie jeden `frontend.exe` z `%LOCALAPPDATA%\Programs\NEXT Stabil\frontend.exe`, SHA-256 `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`.

## Otwarte K0/K1 i następna decyzja

K0: `BRAK`.

K1: wyłącznie `WINDOWS_TRUSTED_SIGNING_REQUIRED`. Potrzebna jest osobna zgoda i dostępna, zaufana tożsamość RSA Code Signing do podpisania wszystkich dystrybucyjnych PE, wygenerowanego uninstallera i finalnego NSIS, a następnie instalacji zgodnej z `VerifiedAndReputableDesktop` i installed-root acceptance. Nie wolno wykonywać unsigned retry ani obejścia ochrony.

Nie nadano `R25_READY_FOR_OWNER_REVIEW` ani `R25_ACCEPTED`. R04 pozostaje organizacyjnie wstrzymane; D-22 pozostaje `NOT_RUN`.

Stopka anty-pętla: search K1, pełny E2E, Web i Android są zamknięte technicznie i nie wymagają ponowienia bez nowego dowodu regresji. Następna praca dotyczy wyłącznie zaufanego signed Windows build/install/acceptance; nie należy wracać do migracji, search, backend deploymentu, fixture E2E ani Androida.
