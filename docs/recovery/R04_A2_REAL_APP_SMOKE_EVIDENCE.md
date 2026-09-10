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

## Kontynuacja C3 — 2026-09-09

Właściciel przyjął dowód C2 na
`6d715ddd0df01b95960951a5a8859003aaabf431` jako częściowy i dopuścił
wyłącznie jeden profil low-memory, najwyżej jeden build APK oraz Android UI
dopiero po sukcesie builda i ponownej bramce zasobów. Kod produktu pozostał
`f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`; main/rescue nie zostały
zmienione ani adoptowane.

### Profil i jeden build

Zewnętrzny `android-source` pozostał zwykłą kopią bez metadanych Git. Kontrola
316 tracked plików względem code-under-test wykazała wyłącznie dwie jawne
nakładki build-only: wcześniejszy `android/app/build.gradle.kts` oraz nowy
`android/gradle.properties`. Patch low-memory ma SHA-256
`199415DAE534690CC251707732C71C81BFF061257430AB17E38E2D75C1667666`, a
wynikowy plik właściwości
`E323EA871057548A1798B9BFF94BCE1B5774C492E92F22F62CB4D26922165D88`.
Apply/reverse-check obu nakładek = PASS.

Rzeczywisty wrapper Gradle 9.1.0 potwierdził efektywne parametry:
`-Xmx2048m`, metaspace `768m`, code cache `256m`, jeden worker,
`parallel=false`, offline, Kotlin `in-process`. Pierwsze dwie próby konfiguracji
ujawniły wyłącznie lokalne błędy przygotowania (`JAVA_HOME` i nazwa zadania
wchodząca w istniejący release-profile gate); żadna nie uruchomiła
`assembleDebug`. Po użyciu istniejącego JBR OpenJDK 21.0.10 i neutralnego
zadania guard zakończył się `BUILD SUCCESSFUL`.

Minimalnie sparametryzowany `measure-c2-resource-gate.ps1` zachowuje domyślne
dane C2 i nie zmienia progów. Parser PowerShell 5.1 = PASS; rzeczywisty odczyt
C3 = PASS, a osobne próby z błędnym pełnym ID, ownerem i run ID zakończyły się
odmową `TELEMETRY_IDENTITY_MISMATCH`.

Dokładnie jedna kompilacja `assembleDebug` rozpoczęła się
`2026-09-09T21:16:35.1906220Z` i zakończyła exit `0` po około 3 min 15 s.
Monitor zebrał 44 próbki. Minima wyniosły: Windows available `5.602 GiB`,
commit reserve `36.065 GiB`, Docker/WSL pool available `14.135 GiB`; swap
pozostał około `1.9 MiB` bez wzrostu. Wynikowy APK:

- package `pl.ailab.app.r04test`, version `1.0.2` (`29`);
- rozmiar `166479535 B`;
- SHA-256 `FAF545C0F6E6DD55DC48898A10714AA099FF3EBE78B648EADAC2B036C7AE325E`;
- Android debug certificate SHA-256
  `7A4397BF69CF0B21A6D028510C13FE84FAD7D3892B62F1C524B78D0B05CBE0F4`;
- testowy endpoint `http://10.0.2.2:18004` obecny w `kernel_blob.bin`.

### Bramka uruchomienia Androida

Po buildzie zachowany stos A2 przeszedł ponownie kontrolę pełnych ID,
`current_database()`, DB head i fixture: dwaj syntetyczni klienci, jeden
dokument `204 B`, backend source revision zgodna z code-under-test.
`component_identity.verification` pozostało uczciwie `UNVERIFIED`, a runtime
configuration `REVIEW_REQUIRED`.

Istniejący AVD ma nazwę `Pixel_8`, API 37.1, 4 CPU i zadeklarowane 2048 MiB
RAM. Po starcie rzeczywisty serial `emulator-5554` został potwierdzony przez
`adb emu avd name`. Zanim boot zakończył się, aktywny monitor o
`2026-09-09T21:28:29.6247112Z` odnotował Windows available `3.900 GiB`.
Commit reserve wynosił wtedy `33.024 GiB`, pool available `13.945 GiB`, swap
około `1.9 MiB`; jedyną naruszoną bramką był fizyczny RAM Windows. Dokładny
emulator zatrzymano do `21:28:56Z`. Nie wykonano retry, instalacji APK ani
Android UI-01–UI-06.

Android = `RAM_GATE_BLOCKED / NOT_RUN`. Zaobserwowany spadek podczas bootu z
około `7.949` do `3.900 GiB` uzasadnia wyłącznie ograniczoną propozycję
osobnego okna AVD-only rozpoczynającego się przy co najmniej `8.5 GiB`
Windows available, z tym samym już zbudowanym APK i bez zmiany dotychczasowych
bramek 4 GiB/commit/pool/swap. Nie jest to wykonana ani domyślnie zatwierdzona
próba.

### Stan końcowy C3

Web UI-03 nie było ponawiane: hash pobrania zachowuje wcześniejszy PASS, a
widoczna treść nadal `WAITING_OWNER_VISUAL_EVIDENCE`. `R04-A2-UI06` pozostaje
`PARTIAL / KNOWN_DEFECT_OPEN_R16`; D-15/D-16 oraz modele pozostają `NOT_RUN`.

Trzy exact-name kontenery A2 są `exited`; porty `18004/18005` nie nasłuchują,
`adb devices` nie wskazuje urządzenia, a procesy emulatora/Java/Dart/Flutter
uruchomione w C3 zakończyły się. Jedyny kontener telemetryczny został usunięty
po kontroli pełnego ID/owner/run. Testowe DB/storage/cache i APK pozostają
`LOCAL_ONLY`. Produkcyjne business writes, modele, kolejki, Qdrant, Gmail,
Vision, Temporary Chat, backup/snapshot, escrow, deploy i rescue adoption:
`0` działań C3.

Werdykt: `R04 A2 APP_SMOKE_PARTIAL / TEST_ONLY`; build APK jest PASS, lecz
Android UI-01–UI-06 pozostają `NOT_RUN` z powodu `RAM_GATE_BLOCKED` podczas
bootu AVD. C3 nie otwiera R16 ani dalszego podetapu R04.

## WEB-FIRST / D-17 — 2026-09-09 UTC

Właściciel przyjął C3 na
`a6e8f7f50a843c26334bff90440905e00f163d61` jako częściowy dowód i decyzją
D-17 wybrał Web jako pierwszą ścieżkę dalszego sprawdzania wspólnego API oraz
logiki aplikacji. Android runtime ma status `DEFERRED_BY_OWNER / NOT_TESTED`;
zachowany APK `FAF545C0...` nie został uruchomiony ani przebudowany.

### Preflight, izolacja i monitoring

- Recovery local/remote rozpoczęły na `a6e8f7...`; code under test pozostał
  `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`. Main `483f9bf8...`, rescue
  `5cd8f86e...` oraz 203 wpisy oryginalnego worktree nie zostały zmienione.
- `source-f4ea20c.tar` zachował SHA-256 `B93DF8FE...`; 316 tracked plików
  `web-source` było zgodnych z code-under-test po normalizacji Git. Sześć
  generowanych registrantów różniło się wyłącznie końcami linii.
- Pełne ID, obrazy, owner/run, mounty i sieci trzech zachowanych kontenerów
  odpowiadały chronionemu `raw/resource-manifest.json`. Wznowiono te same
  PostgreSQL/backend/transport bez Compose `up`, migracji i seeda.
- Syntetyczna DB zwróciła `ai_lab_r04_a2_20260909`, użytkownika
  `r04_a2_owner`, head `followup_assistant_chat_history_20260829`, dwa rekordy
  klientów i jeden dokument. Wszystkie allowlistowane flagi
  preparation/Assistant/Vision/Advanced/KB/vector writes/retention/restore
  miały wartość `false`; zewnętrzne cele wskazywały niedostępny loopback.
- Pierwszy realny test opublikowanego monitora ujawnił wadę harnessu:
  PowerShell 5.1 przekazywał `\"` literalnie do formatu Dockera, a helper
  odczytywał nieistniejące klucze `next.stabil.*` zamiast kontraktu
  `next-stabil.*`. To nie była wada produktu ani brak zasobów. Minimalna
  poprawka normalizuje tylko te cytowania i odczytuje dwa właściwe klucze.
  Parser PowerShell 5.1 = PASS, trzy realne próbki = PASS; błędny pełny ID,
  owner i run ID = trzy odmowy `TELEMETRY_IDENTITY_MISMATCH`.
- Monitor Web zebrał 203 próbki od `2026-09-09T22:59:24Z` do
  `2026-09-09T23:19:14Z`, wszystkie PASS. Minima: Windows available
  `5.875 GiB`, commit reserve `35.257 GiB`, Docker/WSL pool available
  `13.641 GiB`; maksymalne użycie swap puli `1.9 MiB`, bez przekroczenia
  progu wzrostu. SHA-256 CSV: `FC32E615...`.

### Wyniki jednego przebiegu W-01–W-05

| Test | Mapowanie | Nowy wynik | Dowód i ograniczenie |
|---|---|---|---|
| W-01 | UI-01 / UI-02 | PASS | Jedno błędne logowanie dało 401 i widoczny błąd; poprawne logowanie otworzyło syntetyczny dashboard, dwa rozróżnialne rekordy oraz `R04 A2 Primary Case`. Log backendu: 3 loginy, 2 sukcesy i 1 oczekiwana odmowa. |
| W-02 | UI-03 | PARTIAL / `WAITING_OWNER_VISUAL_EVIDENCE` | Przycisk `Otwórz plik` został użyty z listy filtrowanej do klienta. Zachowany plik z wcześniejszego rzeczywistego kliknięcia nadal ma 204 B i SHA-256 `C0EBC642...`. Ta przeglądarka nie zgłosiła nowego download eventu, a jej polityka bezpieczeństwa zablokowała lokalny `file://`; nie wykonano obejścia, bezpośredniego URL ani renderu fixture. Brak nowego czytelnego widoku jest ograniczeniem narzędzia, nie dowodem błędu backendu. |
| W-03 | UI-04 | PASS | Preimage `R04-A2-UI-MUTATION-ONE` zapisano przed operacją. Jedno pole zmieniono przez UI na marker `R04-A2-WEBFIRST-0910-ONE`; po innym ekranie i po restarcie odczytano tę samą wartość. Log zawiera dokładnie 1 udane żądanie mutujące klienta; read-only DB: `primary_rows=1`, `marker_rows=1`, klientów 2, dokumentów 1. |
| W-04 | UI-05 | PASS / TEST_ONLY | Rzeczywisty `/version` zachował osiem legacy pól, `component_identity.backend.source_revision=f4ea20c...`, `verification=UNVERIFIED` i `runtime_configuration=REVIEW_REQUIRED`; brak prywatnych ścieżek i secret-like pól. Klient Web działał dalej. Nie jest to odbiór stable/release. |
| W-05 | UI-06 | transport/lista/brak duplikatu PASS; UX PASS w tej sesji; historyczny defekt nadal OPEN | Jedno zatrzymanie wyłącznie pełnego ID backendu dało komunikat „Nie można połączyć się z serwerem NEXT Stabil”. Po uruchomieniu tego samego ID `Spróbuj ponownie` odtworzyło listę, a marker W-03 pozostał jeden. `LateInitializationError` nie odtworzył się w tym przebiegu; wcześniejszy dowód `R04-A2-UI06` nie jest przez to zamknięty i pozostaje `KNOWN_DEFECT_OPEN_R16` do odebranej poprawki/regresji. |

### Skutki i handoff

Trwałym skutkiem biznesowym jest dokładnie jedna mutacja w syntetycznej DB.
Operacyjnie wykonano jeden stop/start syntetycznego backendu, start/stop trzech
zachowanych kontenerów A2 oraz utworzenie i usunięcie jednego kontenera
telemetrycznego po kontroli pełnego ID/owner/run. Web i własne karty browsera
zamknięto; porty `18004/18005` są wolne. Wolumen DB, storage, download, APK,
cache i dowody pozostały zachowane.

Mały pakiet trzech zanonimizowanych screenshotów znajduje się `LOCAL_ONLY` pod
`web-first-20260909T223759Z/R04_A2_WEBFIRST_SAFE_SCREENSHOTS_20260909T223759Z.zip`;
ma `100983 B` i SHA-256 `1A679F4B6F439FA475194702FA3AE8161D61A1D9C6BBD9074D775F4FD47A5E79`.
Nie zawiera haseł, tokenów, HAR ani danych firmy.

Nie wykonano Android/Gradle/APK/install/AVD, modeli, Assistant/KB/Vision,
Temporary Chat, Qdrant/Gmail, backupu, escrow, deployu ani operacji produkcyjnej.
D-15/D-16 i odbiór AI pozostają `NOT_RUN`.

Werdykt: `R04 A2 WEB_EVIDENCE_READY_FOR_REVIEW / TEST_ONLY` z
`WEB_SMOKE_PARTIAL / KNOWN_UI_DEFECT_OPEN_R16`; Android runtime pozostaje
`DEFERRED_BY_OWNER / NOT_TESTED`. Cały R04 nadal `IN_PROGRESS`, a R03
`WAITING_APPROVAL / WAITING_ESCROW_DECISION`.

## UI06-REPAIR — 2026-09-10 UTC

Właściciel ograniczył D-18 do naprawy historycznego `R04-A2-UI06` i jednego
Web A/B. Source/test fix znajduje się na
`48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`; nowa próba fizycznego Web została
zablokowana przed scenariuszami przez politykę URL dozwolonej przeglądarki.
Pełny dowód, zakres niepewności i hashe znajdują się w
`docs/recovery/R04_A2_UI06_REPAIR_EVIDENCE.md`. Status tej kontynuacji:
`SOURCE_FIXED / WEB_NOT_VERIFIED / BLOCKED_TOOLING`; nie zmienia wcześniejszych
W-01–W-05 ani statusu W-02.

## UI06 — odbiór source/test i oczekiwanie na dozwoloną sesję

Właściciel zaakceptował source/test
`48fbecae0a76edb25f60e9dd314bb8d65bfbae4b` wyłącznie dla potwierdzonego
błędu `DocumentsController`; source pozostaje `NOT_DEPLOYED`. Przed kolejną
próbą nie ustanowiono ani formalnie dozwolonego trybu automatycznego dla
`http://127.0.0.1:18005`, ani bieżącej gotowości właściciela do trybu
operatorskiego. Stack nie został uruchomiony, dlatego fizyczne A/B ma status
`WEB_NOT_VERIFIED / WAITING_ALLOWED_UI_OR_OWNER_SESSION`. Nie zmienia to
historycznych wyników W-01–W-05, W-02 ani odroczenia Androida.

## UI06 OWNER_OPERATED — częściowy Web A/B, 2026-09-10 UTC

Właściciel ręcznie obsłużył Web przez istniejący RustDesk; Codex nie sterował
browserem ani RustDesk. Na zaakceptowanym frontendzie
`48fbecae0a76edb25f60e9dd314bb8d65bfbae4b` i zachowanym backendzie
`f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99` scenariusz B potwierdził
właściwy błąd przy zatrzymanym backendzie oraz powrót jednej właściwej pozycji
po jednym retry, bez `LateInitializationError`: `PASS / OWNER_OPERATED`.

Scenariusz A pozostał `NOT_VERIFIED / PREFETCH_CONTAMINATED`: po kontrolowanym
restarcie Web i świeżym logowaniu klient sam wykonał `GET /api/v1/documents`
bez wejścia właściciela do repozytorium. Drugiego outage nie wykonano. Dwa
screenshoty B i screenshot białego ekranu A są zachowane `LOCAL_ONLY` z
hashami w `R04_A2_LOCAL_EVIDENCE_MANIFEST.csv`.

Próba miała przerwy świeżych pomiarów >30 s i przekroczyła 25-minutowe okno,
więc wynik nie jest pełnym proceduralnym PASS. Po zakończeniu trzy kontenery A2
są `exited`, Web zatrzymany, telemetry usunięta, porty `18004/18005` wolne.
Pełny opis i ograniczenia: `docs/recovery/R04_A2_UI06_REPAIR_EVIDENCE.md`.
Status: `R04-A2 UI06 SOURCE_ACCEPTED / WEB_AB_PARTIAL / TEST_ONLY`;
R04 `IN_PROGRESS`, R03 `WAITING_APPROVAL / WAITING_ESCROW_DECISION`.

## Powtórzenie UI06 A — 2026-09-10 UTC

Na jawne polecenie właściciela wykonano jedną dodatkową próbę A bez zmiany
source/test. Pełny reload przy zatrzymanym backendzie zatrzymał aplikację na
wcześniejszym sprawdzeniu sesji. Po przywróceniu backendu operator potwierdził
Dashboard bez wejścia do repozytorium, lecz log wykazał dashboardowy
`GET /api/v1/documents?...limit=6`. Wymagany brak wcześniejszego pobrania listy
nie został spełniony; nie wykonano kolejnego outage ani prób do skutku.

Wynik pozostaje `A=NOT_VERIFIED / AUTH_GATE_THEN_DASHBOARD_PREFETCH`,
`B=PASS`, całość `WEB_AB_PARTIAL / TEST_ONLY`. Screenshot auth gate, logi i
`68/68` próbek zasobów PASS są zhashowane w
`R04_A2_LOCAL_EVIDENCE_MANIFEST.csv`. Pełny opis znajduje się w
`R04_A2_UI06_REPAIR_EVIDENCE.md`.

## UI06 A route-first — korekta procedury, 2026-09-10 UTC

Właściciel skorygował globalny warunek braku odczytu listy. Dashboardowy
preview `limit=6` jest dozwolony, ponieważ źródło
`48fbecae0a76edb25f60e9dd314bb8d65bfbae4b` używa osobnego
`dashboardRecentDocumentsProvider`; dopiero trasa `/documents` tworzy własny
override i nową instancję `DocumentsController`, której pierwsze `build()`
pobiera `limit=50`. Pełne uzasadnienie caller/provider/route znajduje się w
`R04_A2_UI06_REPAIR_EVIDENCE.md`.

Oba wcześniejsze A zachowują `NOT_VERIFIED`, a B zachowuje
`PASS / OWNER_OPERATED_RUSTDESK`. Nowy, pojedynczy test pierwszego ładowania
kontrolera ma stan `NOT_RUN / WAITING_OWNER_READY`; przed bieżącym
potwierdzeniem właściciela nie uruchomiono stacku, Web ani telemetrii.
