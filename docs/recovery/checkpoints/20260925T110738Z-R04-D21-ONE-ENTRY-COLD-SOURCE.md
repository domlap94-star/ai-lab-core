# R04 / D-21 — ONE-ENTRY-COLD source/offline

## Wynik

- Status: `OPEN_AFTER_BASE_READY_SOURCE_AND_OFFLINE_READY_FOR_REVIEW / NOT_DEPLOYED / NOT_APPROVED`.
- Zachowany odbiór: `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE`.
- Operacje hosta tej sesji: instalacja `0`, starty `0`, UAC `0`, zapisy taska/skrótu `0`, logoff/reboot `0`, Docker/Task/CIM/TCP/HTTP `0` poza jedną wcześniej autoryzowaną ograniczoną projekcją metadanych wejścia.
- D-23 pozostaje `2/2`; D-22 pozostaje `NOT_RUN`; R04 pozostaje `IN_PROGRESS`.

## Odczyt wejścia

Ograniczony odczyt z `2026-09-25T10:31:56.3011683Z` potwierdził:

- `C:\Users\domai\Desktop\NEXT Stabil.lnk`, 1288 B, SHA-256 `8B46D106A8AD2DB3AC39E57A6E879104C77BA7C8D7AEEC9008577E1F9BA9FBDD`;
- target `C:\Users\domai\AppData\Local\Programs\NEXT Stabil\frontend.exe`, bez argumentów, CWD równe katalogowi pliku;
- klient 140288 B, SHA-256 `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`, wersja `1.0.2+29`, proces `frontend`;
- Startup wrapper `NEXT-Stabil-Host.cmd` nie istnieje;
- istniejący Host jest wspólną ścieżką: PS5.1 → recorder, jeden trigger logon, `InteractiveToken`, `LeastPrivilege`, `IgnoreNew`, `PT15M`.

Skrót, Host i instalacja pozostały bez zmian.

## Zmienione źródła

| Rola | Rozmiar | SHA-256 |
|---|---:|---|
| launcher | 86218 B | `491531FB8926D67AEDB404024C1EE7659376AC6911AC551D9B94A52F47C322D2` |
| runtime | 85291 B | `8265D4E48415179503CD892116ABF50E90BA69799DE5685E1550F0066B10B4F3` |
| recorder | 18535 B | `45CBC5D9CD1677A2299F1FF3D2DF58517778D001E4C16AE83300DFC0E9CA63A7` |
| inactive manifest draft | 32730 B | `A55243DFF4AE6781568E0D48B69B5E4870FB2A81FC2F1B2B0E0BBDE4C06D2804` |

Kandydat wiąże exact klient jako `external_tools/windows_client`, otwiera go dopiero po `BASE_READY_LIMITED`, zachowuje istniejący exact proces na repeat, odmawia przy stanie nieznanym/obcym/wielokrotnym i zapisuje bezpieczne `client_status`/`user_message`. Recorder przenosi te pola i może pokazać wyłącznie bezpieczny komunikat w zalogowanej sesji; błąd powiadomienia nie zmienia wyniku planu.

## Testy końcowych bajtów

Windows PowerShell 5.1, `-NoProfile`, granice produkcyjne `0`:

- `test-start-host-services.ps1`: `62` asercje PASS;
- `test-startup-real-adapters.ps1`: `55` asercji PASS;
- `test-host-evidence-capture.ps1`: `35` asercji / `8` rzeczywistych child cases PASS;
- `test-startup-data-junction.ps1`: `44` asercje PASS;
- `test-p4-startup-package.ps1`: `41` asercji PASS;
- parser PS5.1: `8/8` plików PASS.

Jedno wcześniejsze, niekońcowe wywołanie real-adapter harnessu zwróciło wewnętrzne `Stack empty`; nie było kontaktu z produkcją. Te same bajty przeszły izolowane ponowienie i kompletną końcową kampanię `55/55`; timeoutów, asercji i kodu produktu nie zmieniano dla uzyskania PASS.

## Pakiet nieaktywny

- chroniony katalog: `C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\one-entry-cold-20260925T110216Z`;
- package index: 5584 B, SHA-256 `9C1A60AA50965E4419C9B6021A8C4F60EA8FEF67C685F37D026CCAF60EBBB06C`;
- review ZIP: 119733 B, SHA-256 `B8D33DD14CEF2491160A50F241EE58B7679729D3DAE304810729565295C48876`;
- ZIP roundtrip: `13/13`, missing/mismatch/extra `0/0/0`;
- secret scan: brak dopasowań;
- ACL istniejącego stagingu odziedziczono bez zmiany.

Manifest i indeks pozostają `NOT_APPROVED` / `PROPOSED_AWAITING_SEPARATE_OWNER_OPERATIONAL_APPROVAL`; wszystkie operacyjne zgody w indeksie są `false`. Pakiet nie zawiera instalatora ani produkcyjnych logów/danych.

## Jedno przyszłe okno

Proponowany `WINDOW_ID`: `R04-D21-ONE-ENTRY-COLD-WINDOW-20260925T110738Z`.

Jedna przyszła decyzja ma objąć łącznie:

1. bounded preflight exact plików, Host, klienta, sześciu pinned kontenerów, PostgreSQL, gatewayów, HTTP/public control, stanu backup/maintenance i dostępu lokalnego/RustDesk;
2. instalację tylko trzech skryptów i manifestu z powyższych hashów;
3. zachowanie istniejącego Host i zastąpienie skrótu dopiero po walidacji przez `schtasks.exe /Run /TN "\NEXT Stabil - Host"`, z exact preimage skrótu zachowanym do rollbacku;
4. manual entry i repeat: gotowy klient, zero duplikatów stosu/klienta;
5. jeden Windows reboot i logon — rzeczywisty cold test — po ponownym potwierdzeniu, że właściciel odzyska dostęp lokalny albo przez unattended/start-with-Windows RustDesk;
6. post-check jednego Host logon, istniejących pinned zasobów, publicznego `/control*` 404 i ręcznego CRM/lista/szczegóły;
7. ograniczony rollback tylko ze znanego, bezczynnego stanu do exact czterech accepted USABLE-WARM preimages, Host XML i skrótu; bez legacy Startup/Compose/Supervisor i bez restore danych.

Reboot zatrzyma procesy Windows, Docker Desktop i bieżące kontenery. Po restarcie wolno uruchomić tylko istniejące przypięte zasoby; `compose up/create/recreate/build/pull`, nowe kontenery, migracje i Supervisor pozostają poza zakresem. Dokładne installed preimages do przyszłego preflightu: launcher `686F4EC877AADC93D46D2B67858864BF9C728B00093037A266B257099BA14B66`, runtime `959768E297BCB93FF1AF3D7EE5A174313F9DC053707EDE8C45D3A84D024B0732`, recorder `D21A3E6B5D49E68711C5584138C47C2201B861A80DD4A4F89F173DC57217452A`, manifest `38D7C529FD7CE37E25E32A58CC9CF46075FF5E97D7E60F3618D088653C492BDE`.

Do nowej bieżącej odpowiedzi właściciela: `INSTALL/MANUAL_ENTRY/UAC/REBOOT/LOGON/COLD_START=NOT_RUN`.

## Dane, backupy i retencja

`R04-DATA-BACKUP` pozostaje następnym zakresem po odbiorze ONE-ENTRY-COLD. Obowiązuje: C: OS/kod; D: aktywne rosnące dane przez exact junction `C:\ai-lab-core\data -> D:\ai-lab-data`; backup tylko do jawnie wybranej lokalizacji poza C:/D:, bez fallbacku na C:/D:/E:; duże dumpy/archiwa rozliczone przed aktywacją. Memory retention i backup retention pozostają oddzielnymi, niezmienionymi politykami. Backup/restore/purge/relokacja tej sesji: `0`.

## Klasyfikacja zakresu

Nowych nierozliczonych K0/K1 o wykazanym istotnym wpływie w tym SOURCE/OFFLINE zakresie nie stwierdzono. Jednorazowy błąd harnessu ma końcowy dowód PASS tych samych bajtów i nie był awarią produktu. Nie wykonano ponownego review USABLE-WARM.
