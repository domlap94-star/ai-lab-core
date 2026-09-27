# R25 — Windows owner-managed local installation PASS

## Wynik użytkowy

- Status: `R25_READY_FOR_OWNER_REVIEW / NOT_ACCEPTED`.
- Exact NEXT Stabil Windows `1.0.2+29` jest zainstalowany pod `%LOCALAPPDATA%\Programs\NEXT Stabil` i uruchamia się ze standardowego skrótu.
- Windows UI External potwierdził pusty stan, wyłącznie klienta A po grancie, szczegóły A, dozwoloną nawigację, brak B, natychmiastowy revoke, pusty stan po close/reopen oraz brak crasha.
- Technicznych K0/K1 brak. Wyłącznie właściciel może nadać `R25_ACCEPTED`.

## Polityka lokalnego hosta

Smart App Control zmienił stan `On -> Off` przez oficjalny interfejs Windows Security. Nie użyto edycji rejestru, CiTool, usuwania polityki, `Unblock-File` ani restartu. Końcowy readback:

- `VerifiedAndReputablePolicyState=0`;
- Bitdefender `productState=266240` i aktywny;
- Domain/Private/Public firewall aktywne;
- UAC `EnableLUA=1`.

Decyzja `SAC_OFF_OWNER_MANAGED_HOST` dotyczy wyłącznie tej lokalnej, właścicielsko zarządzanej maszyny. Historyczny `SAC_ON_INSTALLER_TRUSTED` pozostaje bez osłabienia. Publiczna dystrybucja na obce hosty wymagałaby osobnego modelu zaufania.

## Source i focused testy

Commit `a92a4238d118f7ea4a7698bea7e84ae2cb1ac1af` dodał jawny drugi tryb do `assert-windows-acceptance-ready.ps1` i testy obu trybów. Nowy tryb wymaga SAC Off, aktywnych Bitdefendera/firewalla/UAC, kanonicznego registered rootu, exact build manifestu, size/hash każdego payloadu, tylko jawnie dozwolonych generated files, poprawnych uninstall/shortcuts, braku reparse/path escape i braku szeroko zapisywalnego executable rootu.

- Windows PowerShell 5.1 focused tooling: PASS.
- Historyczny tryb na zachowanym preimage: PASS.
- Fail-before starego rootu w nowym trybie: `WINDOWS_UNEXPECTED_INSTALLED_FILE`, zgodnie z oczekiwaniem.
- `git diff --check` i ograniczony scan source: PASS przed publikacją.

## Instalacja i exact-root acceptance

- Installer: `NEXT-Stabil-Setup-1.0.2+29.exe`.
- Bytes: `13498751`.
- SHA-256: `EA69C1FF1DA1CB2E608FF49CABEB6ABBAEA763AB679B73B2FDBB55DF5EFA3CE9`.
- Product/File version: `1.0.2 / 1.0.2.29`.
- Authenticode: `NotSigned`.
- Install exit: `0`.
- Installed `frontend.exe`: `DF4683C67423276AA18BFD107F5238F3EFD5E27FD7FDA86EED23A0B7F9CBED51`.

Installer zachował stary `dartjni.dll`, którego exact R25 manifest nie zawierał. Plik został związany z preimage bieżącym hashem i operation-owned kopią rollback, następnie usunięty jako jedyny stale file. Finalny gate potwierdził 20 plików payloadu plus jawnie dozwolony `Uninstall.exe`, exact sizes/hashes, uninstall metadata, oba shortcut targets, ACL/reparse/path boundaries i brak dependency od recovery/staging/Temp.

Uruchomienie ze standardowego skrótu dało dokładnie jeden responsywny `frontend.exe`; `flutter_windows.dll`, `geolocator_windows_plugin.dll` i `permission_handler_windows_plugin.dll` zostały załadowane z kanonicznego installed rootu. Po początku okna nie było nowych nieoczekiwanych Code Integrity 3033/3077.

## Windows UI smoke i cleanup

Użyto wyłącznie efemerycznych syntetycznych użytkowników i klientów A/B:

1. login External przekierował do `/shared-clients`;
2. bez grantów widoczny był pusty stan;
3. syntetyczny User nadał A przez produkcyjne API;
4. po close/reopen Windows UI pokazał wyłącznie A, bez B;
5. szczegóły A otworzyły się prawidłowo;
6. zadania, realizacje, wizje lokalne, dokumenty i maile otworzyły się bez crasha i bez danych spoza scope;
7. revoke odciął A od następnego requestu;
8. close/reopen pokazał pusty stan i dokładnie jeden proces;
9. wylogowanie wróciło do ekranu logowania `NEXT Stabil 1.0.2+29`.

Cleanup usunął syntetyczne granty, klientów, użytkowników i poświadczenia; residue: `users=0`, `clients=0`, `grants=0`. Operacja `NEXT-STABIL-R25-WINDOWS-OWNER-INSTALL-20260927T161133Z` zakończyła się `PASS / pending_mutation=false`.

## Zachowane wyniki

Bez ponownego otwierania pozostają PASS: backend source `34834c96443da619d051b66ea4ef37f055a6549b`, schema `r25_external_scope_20260927`, release `NEXT-STABIL-R25-searchfix-34834c96443da619`, startup manifest `F9C33CB404589309ED3CDE1D8956C96882DBB194654DA21DB0139B350E6BCCCA`, Web `A6D708B2BF72664676F5232CD1208B3FB656FB275A65BCB927FEBC9AFDDCE80A`, Android `1.0.2+29` oraz pełny run `R25_E2E_20260927T150637Z_7b275f03` z exact cleanupem.

R04 pozostaje wstrzymane. D-22 pozostaje `NOT_RUN`.

---
Stan pakietu: `R25_READY_FOR_OWNER_REVIEW / NOT_ACCEPTED`

Ostatni zakończony krok: exact Windows install, owner-managed acceptance, UI smoke i cleanup PASS

Następny krok: wyłącznie merytoryczny odbiór właściciela; nie rozpoczynać D-22
