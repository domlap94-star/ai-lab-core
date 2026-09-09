# R04-A2 — izolowany smoke rzeczywistej aplikacji

## Zakres i tożsamość

- Czas wykonania: `2026-09-09T13:16:17Z`–`2026-09-09T14:53:18Z`.
- Gałąź wykonawcza: `recovery/next-stabil-repair-completion`.
- Kod produktu objęty testem: `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.
- Pełny snapshot źródeł: `source-f4ea20c.tar`, SHA-256
  `B93DF8FE6F2D86EE32394D7DE08EF45DB44E99A97C9A38F6231A44200400F391`.
- Filtrowane blob IDs `backend/app/main.py`,
  `backend/app/services/version_identity_service.py`, `frontend/lib/main.dart`
  i `frontend/pubspec.lock` w rozpakowanym snapshotcie zgadzały się z Git dla
  `f4ea20c...`. Mutable Web copy zachowała blob IDs plików Flutter.
- Zewnętrzny chroniony root:
  `C:\ai-lab-core-staging\recovery\R04_A2_REAL_APP_20260909T131617Z`.
- Pełne logi, screenshoty, syntetyczne hasła i build cache są `LOCAL_ONLY`.
  Hasła i tokeny nie są częścią Git ani niniejszego raportu.

## Izolacja i wykonany zestaw

Uruchomiono wyłącznie exact-name zasoby właściciela `R04-A2`, run ID
`20260909T131617Z`:

- PostgreSQL `next-stabil-r04-a2-20260909t131617z-postgres`, obraz
  `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`;
- backend `next-stabil-r04-a2-20260909t131617z-backend`, obraz
  `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`;
- credential-free fixed-target transport
  `next-stabil-r04-a2-20260909t131617z-transport`;
- wolumen `next-stabil-r04-a2-20260909t131617z-postgres-data`;
- sieci `next-stabil-r04-a2-20260909t131617z-internal` (`internal=true`) i
  `next-stabil-r04-a2-20260909t131617z-ingress` (wyłącznie transport).

DB nie miała portu hosta. Backend nie miał portu hosta, sieci produkcyjnej,
Docker socketa, privileged/host PID ani produkcyjnych mountów; źródła były
read-only, storage był nowy i syntetyczny. Jedynym wejściem API był transport
`127.0.0.1:18004`; Web używał `127.0.0.1:18005`. Backend miał wyłączone
Document Preparation, Assistant V2, Vision, Advanced, KB processing/vector
writes, restore i retention delete; adresy Qdrant/Ollama/n8n/Supervisor
wskazywały nieosiągalny loopback wewnątrz odizolowanej sieci. Brak credentials
i brak egress backendu były oddzielnymi barierami.

Istniejące migracje wykonały schemat wyłącznie w DB
`ai_lab_r04_a2_20260909`; `current_database()` sprawdzono przed migracją, a
końcowy head był `followup_assistant_chat_history_20260829`. Dane utworzono
przez rzeczywiste uwierzytelnione API: dwa rozróżnialne syntetyczne rekordy
klienta, jedna wizja lokalna i jeden dokument. Bez danych firmy i bez direct
business-table writes.

## Wynik Web

Flutter `3.44.8`, Dart `3.12.2`; `flutter pub get --offline` wykorzystał lokalny
cache, nie zmienił lockfile. `flutter run -d web-server` z
`API_BASE_URL=http://127.0.0.1:18004` skompilował i wystawił rzeczywistą
aplikację. Żaden wynik CRM ani auth nie był mockowany.

| Próba | Wynik | Dowód |
|---|---|---|
| UI-01 login + błędne hasło | PASS | UI wysłał rzeczywisty `POST /api/v1/auth/login`; błędne hasło dało `401` i komunikat, poprawne `200` oraz Dashboard. |
| UI-02 właściwy klient/sprawa | PASS | Lista pokazała 2 różne rekordy; otwarto tylko `R04 A2 Primary Case`; timeline zwrócił 3 zdarzenia i dokument właściwego klienta. |
| UI-03 dokument | PARTIAL | UI otworzył szczegóły dokumentu ID 1 i akcja „Otwórz plik” wykonała `GET /api/v1/documents/1/content` `200`; odebrane bajty miały SHA-256 `C0EBC642C0AE14C7A3D8D4A4A6B5F9178E0370CDC3241E3155E710D88E7EB0F2`, identyczny z fixture. In-app browser nie zachował osobnej widocznej karty/podglądu po akcji, więc wizualnego renderu treści nie ogłoszono PASS. |
| UI-04 mutacja i ponowne otwarcie | PASS | UI zmienił syntetyczny numer rejestracyjny, `PATCH /api/v1/clients/1` dał `200`, snackbar potwierdził zapis; po wyjściu i ponownym otwarciu wartość była identyczna. Read-only SQL: dokładnie 1 rekord z markerem, brak duplikatu. |
| UI-05 `/version` + klient | PASS | Aplikacja pobrała `/version` i dalej działała. Legacy fields pozostały, a `component_identity.schema=NEXT_STABIL_COMPONENT_COMPATIBILITY_V1`; backend SHA i DB revision odpowiadały testowanemu zestawowi. `verification=UNVERIFIED` i `runtime_configuration=REVIEW_REQUIRED` są prawdziwym stanem testowego, niepełnego zestawu, nie fikcyjnym VERIFIED. Publiczna odpowiedź nie zawierała ścieżek hosta ani prywatnego inventory. |
| UI-06 utrata i powrót | PARTIAL / KNOWN_DEFECT_OPEN | Transport/lista odzyskały działanie po uruchomieniu tego samego exact-name backendu, a mutacja nadal występowała raz. Stan aplikacji i komunikat nie przeszły: UI ujawnił wewnętrzny `LateInitializationError: Field '_repository' has already been initialized`. To ustalenie wykonawcze `R04-A2-UI06` do R16; przyczyna i zakres wpływu nie są jeszcze dowiedzione, a produktu nie poprawiano w A2. |

Testowy backend zwrócił dla stable-update `404`, ponieważ A2 nie montowało ani
nie modyfikowało stable manifestu. Próba nie podnosi minimum klienta i nie jest
odbiorem stable channel.

## Android i pozostałe granice

`Pixel_8` istnieje (`2048 MiB`, 4 CPU, obraz Android 37.1 Google Play) i nie był
uruchomiony. Po zatrzymaniu Web Windows miał `5.29 GiB` available; projekcja po
samym przydziale RAM AVD wynosiła `3.29 GiB`, poniżej zachowanego progu rezerwy
`4 GiB`. WSL read zakończył się `E_ACCESSDENIED`, więc nie było pełnego drugiego
dowodu pojemności. Android: `BLOCKED_RESOURCE_GATE`, build/install/model calls
`NOT_RUN`. Wyniku Web nie przeniesiono na Android. Windows native nie był
wymagany i pozostaje `NOT_RUN`.

Estymacja przy niepełnych danych i samodzielny pełny odczyt sprawy są zapisanymi
kryteriami późniejszych pakietów, lecz bez Qwen/KB/Visual w A2 pozostają
`NOT_RUN`, nie PASS.

## Skutki i stan końcowy

- Testowe zapisy: migracje w jednej syntetycznej DB, seed przez API i jedna
  mutacja UI. Produkcyjne business writes: `0`.
- Qwen, embedding, Qdrant, Gmail, Temporary Chat, Vision, Advanced i kolejki:
  `0` wywołań.
- Backend został kontrolowanie zatrzymany i uruchomiony raz dla UI-06; dotyczyło
  to wyłącznie testowego kontenera. Na końcu PostgreSQL/backend/transport i Web
  są zatrzymane, porty `18004/18005` nie nasłuchują. Końcowa kontrola o
  `2026-09-09T15:25:51Z` powiązała zapisany w chronionym `web.pid` PID launchera
  z drzewem `cmd -> dart -> dartvm`, komendą Flutter `web-server` i portem
  `18005`, po czym zatrzymała wyłącznie te trzy procesy; pozostałość `0`.
- Testowy wolumen DB, testowy storage, snapshot/build caches i dowody zachowano
  do odbioru. Nie wykonano cleanupu ani zmian zasobów R03.
- Pierwszy pomocniczy odczyt HTTP użył błędnego formatu login body i został
  zachowany jako `LOCAL_ONLY_SETUP_ERROR`; nie był błędem produktu i nie
  zmienił danych. Prawidłowe sprawdzenie użyło formularza OAuth2.
- Compose structural validation: PASS. Parse test transportu: PASS. Dwa
  wcześniejsze wywołania tego parse testu nie utworzyły kontenera (błędne
  quoting/entrypoint); poprawna komenda użyła `--entrypoint python`, `--network
  none`, read-only mount i pozostawiła residue `0`.

Werdykt: Web potwierdził rzeczywistą ścieżkę UI→HTTP→backend→syntetyczna
DB/storage→UI, ale UI-03 ma ograniczenie widocznego renderu, Android nie przeszedł
bramki zasobów, a UI-06 ujawnił odtwarzalny błąd komunikatu. Dlatego R04-A2 to
`APP_SMOKE_PARTIAL / TEST_ONLY`, nie `READY_FOR_REVIEW` całego A2 i nie odbiór
R04. Następna bezpieczna czynność: właściciel ocenia dowód Web i wyznacza osobne
okno z wystarczającą rezerwą do dokończenia Android oraz powtórzenia tylko
ograniczonej wizualnej części UI-03; naprawa `LateInitializationError` należy do
osobno zleconego zakresu R16.

## Kontynuacja C1 — 2026-09-09

Właściciel przyjął powyższy dowód Web jako częściowy na
`5809350704916bf03aec9b8d39575fd0247fb7b8`. C1 wznowił te same zachowane
zasoby bez migracji, seeda lub zmiany danych i nie zmienił kodu produktu
`f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.

### Korekta recipe i bezpieczne RESUME

- Fail-before na zachowanej rzeczywistej odpowiedzi `/version` potwierdził, że
  opublikowane `$version.component_identity.source_revision` jest nieobecne,
  podczas gdy `component_identity.backend.source_revision` zawiera dokładne
  `f4ea20c...`. To błąd instrukcji, nie endpointu.
- Guard po poprawce akceptuje tylko niepusty 40-znakowy SHA równy oczekiwanemu;
  brak pola, `UNKNOWN`, niepoprawny format i inny SHA kończą się STOP.
- Windows PowerShell 5.1: rzeczywisty pozytywny response PASS, negatywne
  przypadki STOP `4/4`, normalizacja JSON array `2/2`; siedem bloków
  PowerShell w README ma `0` błędów parsera.
- `RESUME` sprawdza pełne ID, obrazy, owner/run labels, mounty, sieci i stan
  trzech zachowanych kontenerów, a następnie bazę, head, dwie rozróżnialne
  syntetyczne sprawy i dokument. Nie tworzy rootu, archiwum, migracji ani seeda.
- Dodatkowa korekta recipe normalizuje tablicę klientów zwracaną przez
  `Invoke-RestMethod` w PowerShell 7; bez niej poprawny JSON był traktowany jako
  jeden obiekt pipeline. Kontrakt produktu pozostał niezmieniony.

### Bieżące pomiary zasobów

| UTC / etap | Windows physical | Commit used / limit / reserve | Docker/WSL pool | Decyzja |
|---|---|---|---|---|
| `2026-09-09T16:21:49Z`, przed wznowieniem | `25.802 / 8.118 GiB` total/available | `31.629 / 70.802 / 39.174 GiB` | ten sam pool przez `/proc`: `17.563 GiB` total, `14.143 GiB` available; swap `8 GiB`, użyte ok. `2 MiB` | krótki Web dozwolony |
| `2026-09-09T16:32:46Z`, bezpośrednio przed Web | `8.465 GiB` available | reserve `39.226 GiB` | `14.313 GiB` available, swap użyty ok. `2 MiB` | Web start |
| `2026-09-09T17:24:30Z`, po Web | `7.398 GiB` available | `32.336 / 70.802 / 38.466 GiB` | odczyt bieżący niedostępny: Docker pipe access denied; WSL CLI wcześniej `E_ACCESSDENIED` | bez Android build/start |
| `2026-09-09T17:28:47Z`, final | `25.802 / 7.100 GiB` total/available | `32.099 / 70.802 / 38.703 GiB` | nadal brak wiarygodnego bieżącego odczytu tej samej puli | `RESOURCE_OBSERVABILITY_BLOCKED` |

Aktywne pagefile zmierzone przed testem: `C:\pagefile.sys` `13312 MiB`
przydzielone, `522 MiB` użyte, peak `2660 MiB`; `D:\pagefile.sys`
`32768 MiB` przydzielone, `677 MiB` użyte, peak `3485 MiB`. Konfiguracja:
C: system-managed, D: `32768–65536 MiB`. Późniejszy odczyt bieżącego użycia
został zablokowany przez uprawnienia i nie został sfabrykowany. Pagefile nie
był doliczany do physical available.

D: miał `854.43 GiB` wolne z `931.50 GiB`, health `Healthy/Online`; był na
fizycznym NVMe `WD Green SN3000 1TB`, innym niż C: (`TWSC NVMe`). Krótki
odczyt I/O przed testem: D `0 MiB/s`, queue `0`; C ok. `0.37 MiB/s`, queue `0`.
Dostępne Windows `HealthStatus` nie jest pełnym SMART; SMART pozostaje
`UNKNOWN`. Nie zmieniono pagefile, WSL, AVD, RAM, firewalla ani usług.

### Web UI-03 C1

Rzeczywisty klient Flutter zalogował się nową sesją do zachowanego backendu,
pokazał dwie odrębne syntetyczne sprawy, otworzył właściwy dokument ID `1` i
akcję „Otwórz plik”. Dwa kontrolowane kliknięcia diagnostyczne utworzyły dwa
lokalne pobrania po `204 B`; oba miały SHA-256
`C0EBC642C0AE14C7A3D8D4A4A6B5F9178E0370CDC3241E3155E710D88E7EB0F2`,
zgodny z fixture. Screenshot dialogu ma SHA-256
`874737B27AEF5D90B11D2ECFA952B98643E83FC95F8DB8A759003B477638CB9B`.

Treść pobranego pliku nie uzyskała wymaganego dowodu ekranowego: in-app
browser bezpiecznie odmówił renderu `file://`, a uruchomiony lokalny viewer w
nieinteraktywnym kontekście nie udostępnił okna do capture. Własne procesy
viewera zatrzymano. Wynik UI-03 pozostaje zatem
`PARTIAL / BLOCKED_TOOLING`, nie FAIL produktu i nie PASS wizualny. Nie
otwierano fixture z dysku zamiast akcji aplikacji ani bezpośredniego URL.

### Android i stan końcowy C1

`Pixel_8` nadal istnieje z `hw.ramSize=2048`, ale `adb devices -l` nie wskazał
uruchomionego urządzenia. Zachowana `android-source` była czysta, wciąż miała
produkcyjne `applicationId=pl.ailab.app`, więc nie zastosowano overlay,
nie wykonano build/install i nie uruchomiono emulatora. Windows RAM i commit
nie były blockerem w ostatnim odczycie, lecz wymagana obserwowalność właściwej
puli Docker/WSL zniknęła po Web; zgodnie z bramką Android =
`RESOURCE_OBSERVABILITY_BLOCKED / NOT_STARTED`.

Trzy zachowane kontenery zostały wznowione i ponownie zatrzymane po weryfikacji
pełnych ID. Porty `18004/18005` finalnie nie nasłuchują. C1 nie wykonał
migracji, seeda, mutacji UI/DB, modelu, kolejki, Qdrant, Gmail, Vision ani
Temporary Chat. Dwa pobrania syntetycznego pliku i nowe dowody `LOCAL_ONLY` są
jedynymi trwałymi skutkami poza dokumentacją i Git.

## Kontynuacja C2 — 2026-09-09

Właściciel przyjął ograniczony dowód C1 na
`e63ed05c6a9a31cb3657215dba548076e7f8297c` i zezwolił wyłącznie na C2.
Kod produktu pozostał `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`;
main/rescue nie były adoptowane ani zmieniane.

### Rozstrzygnięcie dostępu i ta sama pula Docker/WSL

Podstawowa próba o `2026-09-09T18:49:25Z` uruchomiła ten sam
`docker.exe`, użytkownika, SID/session i context `desktop-linux`, lecz została
odrzucona na `npipe:////./pipe/dockerDesktopLinuxEngine` z exit `1`. Jedyna
uzasadniona alternatywa — identyczny read-only `docker info` przez wąską bramkę
approval — o `18:49:48Z` zakończyła się exit `0`. Przyczyna to
`CODEX_EXECUTION_SANDBOX_NAMED_PIPE_BOUNDARY`; nie awaria engine, brak RAM ani
potrzeba administratora. Nie zmieniono użytkownika, grup, ACL pipe, kontekstu,
Dockera, WSL ani zabezpieczeń.

Engine ID `78446bed-994a-42ea-ad86-46f8232848a8`, Docker Desktop/Linux i
kernel `6.18.33.2-microsoft-standard-WSL2` zgadzały się po obu stronach.
Jedyny kontener pomiarowy miał ID `bdb22257...`, lokalny obraz
`sha256:4b12cf0e...`, boot ID `f2d33511...`, limit cgroup dokładnie 64 MiB i
brak mountów/sieci. `/proc` raportował `17.563 GiB` MemTotal, zgodne z
`18,858,258,432 B` engine memory i jawnie różne od limitu kontenera.
Trzy próbki z około 10 s dały MemAvailable `14.312`, `14.300`, `14.302 GiB`;
swap `8 GiB`, wolne `7.998 GiB`. Direct WSL CLI pozostaje
`WSL_CLI_UNAVAILABLE`, ale właściwa pula ma status
`POOL_OBSERVED_THROUGH_VERIFIED_DOCKER_ENGINE`.

Helper `measure-c2-resource-gate.ps1` ma parser PowerShell 5.1 PASS, pozytywny
realny odczyt PASS i odmowę przy złym pełnym container ID PASS. Pierwszy test
ujawnił locale-ambiguous przecinki dziesiętne; poprawiono wyłącznie serializację
CSV na invariant culture i ponownie uzyskano 10 poprawnych kolumn.

### Pomiary, build i bramka

| UTC / etap | Windows available | Commit reserve | Pool available / swap used | Wynik |
|---|---:|---:|---:|---|
| `2026-09-09T18:51:11Z`, przed telemetry | `8.476 GiB` | `39.531 GiB` | jeszcze nieuruchomiony helper | Windows gate PASS |
| `2026-09-09T18:58:43Z`, po wznowieniu DB/backend/transport | `8.113 GiB` | `39.317 GiB` | `14.080 GiB` / ok. `1.9 MiB` | RESUME PASS |
| `2026-09-09T19:09:33Z`, początek monitorowanego builda | `7.757 GiB` | `38.932 GiB` | `13.881 GiB` / `1.9 MiB` | build rozpoczęty |
| `2026-09-09T19:10:52Z`, STOP | `3.889 GiB` | `34.636 GiB` | `13.852 GiB` / `1.9 MiB` | `RAM_GATE_BLOCKED` |
| `2026-09-09T19:12:25Z`, po przerwaniu | `7.617 GiB` | `38.875 GiB` | `13.876 GiB` / `1.9 MiB` | obciążenie odzyskane, bez retry |
| `2026-09-09T19:17:35Z`, final | `7.760 GiB` | `39.014 GiB` | kontener pomiarowy już usunięty | test zatrzymany |

Monitor zebrał 24 próbki co około 5–7 s. Minimum pool MemAvailable wyniosło
`13.835 GiB`, minimum commit reserve `34.636 GiB`; obserwowalność nie została
utracona. Jedyną bramką był fizyczny RAM Windows poniżej 4 GiB. Aktywne
pagefile końcowo: C `13312 MiB`, used `521 MiB`, peak `2660`; D `32768 MiB`,
used `664 MiB`, peak `3485`. D nadal miał `854.43 GiB` wolne. Pagefile i swap
nie były doliczane do fizycznego RAM i nie zmieniono żadnych ustawień.

Zewnętrzny `android-source` przed overlay odpowiadał dokładnie source dla 316
tracked plików. Opublikowany build-only patch zmienił wyłącznie
`android/app/build.gradle.kts`: package `pl.ailab.app.r04test` oraz debug bez
odczytu produkcyjnego `key.properties`. Patch apply/reverse-check PASS;
`pubspec.lock` bez zmian; `flutter pub get --offline` exit `0`. Jedyny
`flutter build apk --debug --no-pub` osiągnął `assembleDebug`, ale został
przerwany natychmiast po `RAM_GATE_BLOCKED` (exit `1`). Nie powstał APK, nie
było retry, instalacji ani uruchomienia `Pixel_8`; Android UI-01–06 = `NOT_RUN`.
Wygenerowane cache/partial build pod zewnętrznym rootem zachowano zgodnie ze
scope, bez cleanupu.

### UI-03 i stan końcowy C2

Download z C1 nadal istnieje pod dokładną ścieżką z manifestu, ma 204 B i
niezmieniony SHA `C0EBC642...`. C2 nie uruchamiało Web/backendu dla tego
dowodu i nie wykonało trzeciego downloadu. Dostępne narzędzia nie zawierały
kontroli/screenshotu interaktywnego okna desktopowego; zgodnie z bramką nie
uruchomiono ponownie nieinteraktywnego Notatnika ani obejścia `file://`.
Widoczna treść = `WAITING_OWNER_VISUAL_EVIDENCE`, nie FAIL produktu.

Na końcu wszystkie trzy exact-name kontenery A2 są `exited`, porty
`18004/18005` nie nasłuchują, emulator nie był uruchamiany, a jedyny kontener
telemetrii został stop/remove po weryfikacji exact ID/owner/run. Wolumen DB,
storage, android-source/cache/partial build i dowody pozostają zachowane.
Produkcyjne business writes, modele, kolejki, Qdrant, Gmail, Vision, Temporary
Chat, backup/snapshot, escrow, deploy i rescue adoption: `0` działań C2.
`R04-A2-UI06` pozostaje `PARTIAL / KNOWN_DEFECT_OPEN_R16`; D-15/D-16 nadal
`NOT_RUN`.

Werdykt C2: `R04 A2 APP_SMOKE_PARTIAL / TEST_ONLY`; Android ma konkretny
`RAM_GATE_BLOCKED`, natomiast obserwowalność puli została domknięta. Pozostały
jeden krok właściciela dla Web UI-03: otworzyć dokładny zachowany download w
lokalnym viewerze i przekazać zrzut wyłącznie tego okna. Ponowienie Android
wymaga osobnego bezpiecznego okna/scope; C2 nie otwiera R16 ani dalszego R04.
