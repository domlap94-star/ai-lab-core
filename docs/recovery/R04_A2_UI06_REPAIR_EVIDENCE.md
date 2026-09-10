# R04-A2 UI06-REPAIR — dowód źródłowy i granica Web

## Zakres i werdykt

Właściciel decyzją D-18 zaakceptował wcześniejszy WEB-FIRST wyłącznie jako
dowód częściowy i dopuścił minimalną naprawę `R04-A2-UI06`, testy oraz jeden
ograniczony Web A/B na zachowanym syntetycznym backendzie A2.

Wynik: `SOURCE_FIXED / WEB_NOT_VERIFIED / BLOCKED_TOOLING`.

- source/test fix: `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`;
- deployment: `NOT_DEPLOYED`;
- fizyczne scenariusze Web A/B: `NOT_RUN`, ponieważ dozwolona powierzchnia
  Browser Use odmówiła dostępu do lokalnego originu;
- Android: `DEFERRED_BY_OWNER / NOT_TESTED`;
- W-02: `WAITING_OWNER_VISUAL_EVIDENCE`;
- D-15/D-16 i odbiór AI: `NOT_RUN`.

## Historyczny symptom i rozstrzygnięta przyczyna

Przeczytano historyczne dowody `LOCAL_ONLY`:

- `raw/web-ui06-disconnect-error.png`, SHA-256
  `7470163E29E17E288A2A0C919DC565FB90CBE95EE9A12F16DF3E345833ED7C9B`;
- `raw/web-ui06-recovered.png`, SHA-256
  `E1CD682BD9B196162A306D8CA96133D49700D66BD3E4495AFB2E65D8FED597E9`;
- `raw/web.stdout.log`, SHA-256
  `2D8D4F8CF9B9741B0582152A46058C24411567C933AA6362D006D79A39F44208`.

Screenshot błędu pokazuje `LateInitializationError: Field '_repository' has
already been initialized` na ekranie **Repozytorium dokumentów**. Zachowany log
Web nie zawiera stacka, więc sam screenshot nie dowodzi klasy. Deterministyczny
test prawdziwego `documentsControllerProvider` wykazał jednak dokładnie ten sam
mechanizm: pierwszy `DioException` uruchamia retry/invalidation Riverpod 3.4.2,
po czym ta sama instancja `DocumentsController` ponownie wykonuje `build()` i
przypisuje `late final _repository`.

Fail-before zakończył się stackiem
`DocumentsController._repository=` → `DocumentsController.build`; to uzasadnia
zmianę `DocumentsController` zamiast wskazanego w hipotezie `ClientsController`.
Analogiczny wzorzec w `ClientsController` pozostaje code-supported ryzykiem,
lecz nie został zmieniony bez osobnego dowodu. Test potwierdza mechanizm
historycznego ekranu, ale brak historycznego stacka nie pozwala twierdzić, że
była to jedyna przyczyna tamtego incydentu.

## Minimalna poprawka

Zmiana obejmuje dokładnie:

1. `frontend/lib/features/documents/application/documents_controller.dart` —
   usunięcie przechowywanego `late final` oraz odczyt bieżącego
   `documentsRepositoryProvider` w każdym `_load()`;
2. `frontend/test/features/documents/documents_controller_test.dart` — realny
   lifecycle providera, retry po pierwszym błędzie, refresh z zachowaniem scope,
   brak sesji i widgetowy przycisk `Spróbuj ponownie`.

Nie zmieniono widoku produktu, backendu, API, schema, auth, filtrowania,
paginacji ani operacji zapisu. Ponowny odczyt nie wykonuje create/update/delete.
Bieżące repository jest odczytywane przy każdej próbie, więc nowa sesja nie jest
zastępowana klientem/tokenem zachowanym przez kontroler.

## Testy source

Środowisko: Flutter `3.44.8`, Dart `3.12.2`, `flutter_riverpod 3.4.2` i
`riverpod 3.4.2` z istniejącego lock/cache; bez `pub upgrade` i bez
`flutter clean`.

| Dowód | Polecenie | Wynik |
|---|---|---|
| fail-before | `flutter test --no-pub test/features/documents/documents_controller_test.dart` na kodzie przed poprawką z dodanym testem | exit `1`; `6` testów, `1` FAIL; `LateInitializationError` w realnym providerze |
| focused pass-after | to samo polecenie po poprawce | exit `0`; `7/7 PASS` |
| regresja Documents/Clients/Auth | `flutter test --no-pub test/features/documents/documents_controller_test.dart test/features/documents/documents_page_test.dart test/features/clients/client_hotfix_test.dart test/auth_session_expiration_test.dart test/login_session_regression_test.dart` | exit `0`; `37/37 PASS` |
| pełny Flutter | `flutter test --no-pub` | exit `0`; `347/347 PASS` |
| analiza | `flutter analyze --no-pub` | exit `0`; `No issues found` |

Pierwsza analiza po zmianie wykryła tylko nieużywany import i niepotrzebną nazwę
ignorowanego argumentu. Usunięto je bez zmiany semantyki i analiza została
powtórzona. Czysty fail-before ma SHA-256 `03EA6C2D...`; focused pass-after
`B1DABB9C...`; regresja `E8D9868F...`; pełny Flutter `82981C8C...`; analyze
`FF94BD35...`. Pełne hashe i rozmiary są w
`docs/recovery/R04_A2_LOCAL_EVIDENCE_MANIFEST.csv`.

## Ograniczona próba Web

Przygotowano nową kopię frontend z SOURCE_PASS:

- root `LOCAL_ONLY`:
  `C:\\ai-lab-core-staging\\recovery\\R04_A2_REAL_APP_20260909T131617Z\\ui06-repair-20260910T072822Z`;
- archiwum źródeł: `3684502 B`, SHA-256
  `F37C2BDD20A1791EA94C2D9AE1FC9F1EF0AE34F7C1ADAF0989871605354FFE41`;
- frontend source: `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`;
- zachowany backend source: `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`;
- backend image ID: `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`;
- syntetyczna DB: `ai_lab_r04_a2_20260909`, head
  `followup_assistant_chat_history_20260829`.

Przed startem potwierdzono pełne ID/owner/run, obrazy, mounty, sieci i porty
trzech zachowanych kontenerów. Read-only DB potwierdziła dwóch klientów, jeden
dokument, jeden marker `R04-A2-WEBFIRST-0910-ONE` oraz zero Assistant/Analysis
jobs. Nie wykonano migracji ani seeda. Flutter Web zwrócił HTTP 200 na
`127.0.0.1:18005`.

Dozwolona przeglądarka została wybrana dla tego URL i przejęła zachowaną kartę,
lecz jej polityka URL zablokowała lokalny origin przed odświeżeniem i kontrolą
DOM. Zgodnie z bramką narzędzia nie użyto alternatywnej powierzchni, raw CDP,
DevTools ani bezpośredniego obejścia auth. Dlatego:

| Scenariusz | Wynik | Skutek |
|---|---|---|
| A: pierwszy load przy backend down → recovery | `NOT_RUN / BLOCKED_TOOLING` | zero kontrolowanych stop/start backendu dla scenariusza |
| B: lista loaded → backend down → retry → recovery | `NOT_RUN / BLOCKED_TOOLING` | zero kontrolowanych stop/start backendu dla scenariusza |

Nie powstał nowy screenshot aplikacji, trace UI ani żądanie mutujące. Nie wolno
przenosić wcześniejszego W-05 jako nowej regresji poprawionego source.

## Zasoby i skutki

Monitor zebrał `96/96` próbek PASS od `2026-09-10T07:46:44Z` do
`2026-09-10T07:56:02Z`. Minima: Windows available `6.077 GiB`, commit reserve
`37.060 GiB`, pool available `13.852 GiB`; swap pozostał `1.9 MiB`, wzrost
`0.0 MiB`. Hash CSV: `9C036860...`.

Skutki tej sesji:

- uruchomiono i zatrzymano tę samą trójkę kontenerów A2; ich wolumen/DB/storage
  zachowano;
- uruchomiono i zatrzymano jeden proces Flutter Web;
- utworzono i usunięto jeden exact-name kontener telemetryczny po kontroli
  pełnego ID/owner/run;
- porty `18004/18005` są wolne;
- produkcja, zasoby R03, main, rescue, Android APK/AVD/cache są niezmienione;
- modele, KB, Vision, Temporary Chat, Qdrant, Gmail, n8n i kolejki: `NOT_RUN`;
- nowe biznesowe zapisy w syntetycznej DB: `0`; produkcyjne zapisy: `0`.

R04 pozostaje `IN_PROGRESS`; R03 pozostaje
`WAITING_APPROVAL / WAITING_ESCROW_DECISION`. Następna bezpieczna czynność to
odbiór source/test fixu i osobna decyzja o jednym fizycznym A/B w dozwolonym
narzędziu mogącym sterować lokalnym originem.

## Odbiór source/test i bramka obserwacji UI — 2026-09-10 UTC

Właściciel zaakceptował source/test
`48fbecae0a76edb25f60e9dd314bb8d65bfbae4b` wyłącznie dla potwierdzonego
błędu `DocumentsController`. Nie zaakceptował analogicznego ryzyka
`ClientsController`, fizycznego Web, całego A2, R04 ani R16. Stan źródła to
`UI06 SOURCE_ACCEPTED@48fbecae0a76edb25f60e9dd314bb8d65bfbae4b / NOT_DEPLOYED`.

Przed uruchomieniem stacku sprawdzono zainstalowane instrukcje powierzchni
przeglądarkowej i dostępne mechanizmy uprawnień. Instrukcje przewidują lokalne
testy Web, ale nie udostępniają formalnego allowlist/approval override dla
wcześniejszego odrzucenia dokładnego originu `http://127.0.0.1:18005`.
Nie powtórzono tego samego dostępu ani nie użyto alternatywnego browsera,
raw CDP, proxy, innego hosta/portu lub Computer Use. Tryb
`AUTOMATED_ALLOWED` nie został więc ustanowiony.

Tryb `OWNER_OPERATED` także nie został ustanowiony: samo zlecenie nie jest
bieżącym potwierdzeniem obecności i gotowości właściciela przy tym komputerze.
Z tego powodu nie uruchomiono zachowanego stacku, serwera Web ani przeglądarki;
nie wykonano stop/start backendu i nie powstały nowe logi, screenshoty ani
mutacje. Fizyczne scenariusze A/B pozostają
`WEB_NOT_VERIFIED / WAITING_ALLOWED_UI_OR_OWNER_SESSION`. Dokładna procedura
wznowienia znajduje się w checkpointcie
`docs/recovery/checkpoints/20260910T094722Z-R04-A2-UI06-SOURCE-ACCEPTANCE.md`.

## OWNER_OPERATED Web A/B — 2026-09-10 UTC

Właściciel ustanowił bieżący tryb `OWNER_OPERATED / OWNER_OBSERVED` przez
istniejący RustDesk. Codex nie sterował RustDesk ani browserem i nie używał
Browser tool, CDP, Selenium/Playwright, DevTools lub profilu/cookies. Kod
frontendu pozostał `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`, a zachowany
backend `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`. Archiwum frontend zachowało
`3684502 B` i SHA-256 `F37C2BDD20A1791EA94C2D9AE1FC9F1EF0AE34F7C1ADAF0989871605354FFE41`;
kontroler w serwowanej kopii miał SHA-256
`53D3F2D8D52E8A36AF8174EED50624D2AF62E8F5148B4B87C33D13D251B095CC`.
Po próbie Git blob kontrolera i `pubspec.lock` nadal odpowiadały commitowi
frontendu; powstały wyłącznie zewnętrzne generowane dane `.dart_tool`/build.

### Scenariusz B — po wcześniejszym odczycie

Logi pokazały, że pierwsza sesja zdążyła wykonać rzeczywiste odczyty listy,
contentu i szczegółów dokumentu, mimo deklaracji operatora, że nie otworzył
jeszcze repozytorium. Nie przedstawiono więc tej sesji jako A; wykorzystano ją
wyłącznie jako B, gdzie wcześniejszy odczyt był wymaganym warunkiem.

- testowy backend o pełnym ID `15e12852...` zatrzymano o
  `2026-09-10T13:03:17.9234791Z`;
- właściciel zobaczył „Nie udało się pobrać dokumentów. Spróbuj ponownie.”;
  screenshot `scenario-b-outage.jpg`: `274703 B`, SHA-256
  `21E3B76EB08502C2C62E723A9A33CF73FE6BCB3E8BB2E3107ABB7CC6C526B208`;
- ten sam backend uruchomiono ponownie o `2026-09-10T13:26:25.9669855Z`;
  `/health=ok`, a `component_identity.backend.source_revision` pozostało
  `f4ea20c...`;
- po jednym `Spróbuj ponownie` właściciel zgłosił PASS, a log backendu zawierał
  wyłącznie udane odpowiedzi dokumentów, bez 5xx, `LateInitializationError`
  lub tracebacku;
- screenshot `scenario-b-recovered.jpg`: `291363 B`, SHA-256
  `D0CFB1A74F2BD5D39AD2C328ABD73A3753765AC97AA4F8C19B87E3AE6CAC5101`,
  pokazuje jedną pozycję `synthetic-document.txt`, `204 B` i dostępne filtry.

Funkcjonalny wynik B: `PASS / OWNER_OPERATED_RUSTDESK`. Nie jest to odbiór
`ClientsController`, Androida, całego A2/R04/R16 ani deploymentu.

### Scenariusz A — prefetch uniemożliwił pierwszy odczyt

Po zamknięciu starych kart nowa sesja początkowo pokazała biały ekran. Serwer
Web i assety zwracały 200, backend miał `health=ok`, a od rozpoczęcia sesji nie
było loginu ani żądania dokumentów. Screenshot `scenario-a-web-blank.jpg` ma
`124329 B`, SHA-256
`A475BA8582665CECDDD1140B839803A96DBDFE3CF5818173E2C146EBEA9010DE`.
Wykonano jeden kontrolowany restart tylko procesu Flutter Web z tych samych
źródeł i z `--no-pub`; backend nie był restartowany. Po tym operator zobaczył
login i zalogował się bez wchodzenia do repozytorium.

Mimo braku działania operatora klient wykonał o
`2026-09-10T15:20:34.298643639Z` żądanie
`GET /api/v1/documents` zakończone 200. Warunek „pierwsze ładowanie przy
backend down” był więc zanieczyszczony przez prefetch. Zgodnie z bramką nie
wykonano drugiego outage, refreshu ani serii prób do skutku.

Wynik A: `NOT_VERIFIED / PREFETCH_CONTAMINATED`. To ograniczenie dowodu, nie
potwierdzona regresja zaakceptowanej poprawki.

### Zasoby, ograniczenia i zakończenie

Siedem plików pomiarowych zawiera łącznie `998` próbek PASS. Minima z próbek
PASS: Windows available `4.750 GiB`, commit reserve `32.620 GiB`, Docker/WSL
pool available `13.790 GiB`; maksymalne użycie swap `1.9 MiB`. Jedna dodatkowa
końcowa obserwacja `DOCKER_READ_FAILED` powstała po intencjonalnym zatrzymaniu
kontenera telemetrycznego podczas shutdownu i nie była naruszeniem progu.

Próba przekroczyła uzgodnione 25 minut i zawierała przerwy świeżych pomiarów
większe niż 30 sekund podczas oczekiwania na odpowiedzi operatora. Zasoby nie
zostały automatycznie zatrzymane po pięciu minutach. Jest to jawne odstępstwo
proceduralne, dlatego nawet poprawnego B nie rozszerza się na pełny PASS całej
procedury. Pierwsza próba uruchomienia monitora przez zagnieżdżony Windows
PowerShell 5.1 zatrzymała się przed zapisem na marshallingu argumentu Docker;
niezmieniony helper działał następnie przez bieżący host PowerShell. Dwa późne
błędy lokalnej ścieżki monitora także zakończyły się przed zapisem i nie
wpłynęły na aplikację.

Wykonano jeden stop/start testowego backendu (B), dwa uruchomienia procesu Web
(drugie po białym ekranie) oraz wielokrotne ograniczone okna tego samego
kontenera telemetrycznego. Końcowa próbka była PASS. Następnie zatrzymano
wyłącznie Web i trzy zachowane kontenery A2, usunięto wyłącznie telemetry
`5d45b3de...`; porty `18004/18005` mają zero listenerów. Syntetyczna
DB/volume/storage, cache, APK i dowody pozostały zachowane `LOCAL_ONLY`.
Preflight potwierdził 2 klientów, 1 dokument i właściwy DB head; żaden log HTTP
tej próby nie zawierał biznesowego POST/PATCH/DELETE. Logowanie może mieć
techniczne skutki audytowe, których nie utożsamia się z brakiem wszystkich SQL
writes. Końcowy read-only SQL wykonano przed shutdownem, ale jego stdout nie
wrócił z procesu orkiestrującego, więc nie użyto go jako niezależnego dowodu
końcowego countu.

Produkcja, R03, modele, KB, Vision, Temporary Chat, Qdrant, Gmail, n8n,
kolejki, migracje, backup, escrow, main i rescue nie zostały zmienione ani
uruchomione. Testy aplikacyjne: `NOT_RUN`, ponieważ source/test nie zmieniono.
Werdykt: `SOURCE_ACCEPTED / WEB_AB_PARTIAL`; A `NOT_VERIFIED`, B `PASS`;
`UI_OBSERVER=OWNER_OPERATED_RUSTDESK`; `NOT_DEPLOYED`.

## Powtórzenie A zlecone przez właściciela — 2026-09-10 UTC

Właściciel poleceniem `powtorz A` zatwierdził dokładnie jedną dodatkową próbę
A na zachowanym zestawie. Start dokumentacji:
`25c30e7dd9e3d451772eee812bdef190665e1b8d`; frontend i backend pozostały
odpowiednio `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b` oraz
`f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`. Nie zmieniono source, testów,
DB ani fixture.

Pierwsze podejście użyło zachowanej sesji oraz pełnego przeładowania przy
zatrzymanym testowym backendzie. Aplikacja zatrzymała się wcześniej, na
odtworzeniu sesji, i pokazała: „Nie udało się sprawdzić sesji. Sprawdź
połączenie i spróbuj ponownie.” Screenshot
`scenario-a-auth-gate.jpg` ma `198361 B` i SHA-256
`FFA564DDD065F7F6738829DAA5ECA41EAAE8DBDDA51CB4F24135E556C8D69ED6`.
Nie był to błąd `DocumentsController`, ponieważ strona dokumentów nie została
osiągnięta.

Po uruchomieniu tego samego pełnego ID backendu operator przeładował aplikację
i potwierdził Dashboard bez kliknięcia Dokumentów. Log zawierał jednak:

```text
GET /api/v1/auth/me HTTP/1.1 200
GET /api/v1/documents?link_state=ALL&skip=0&limit=6 HTTP/1.1 200
```

Źródło potwierdza, że właściwy `DocumentsController` jest tworzony przy trasie
`/documents` i pobiera stronę z limitem 50; odczyt z limitem 6 pochodzi z
wcześniejszego widoku Dashboard. Ścisły kontrakt ręcznej próby wymagał jednak,
aby lista dokumentów nie była wcześniej pobrana w tej sesji. Bramka nie
przeszła, więc backendu drugi raz nie zatrzymano, operator nie klikał Dokumenty
i nie wykonywano kolejnych prób do skutku.

Wynik powtórzenia: `A=NOT_VERIFIED / AUTH_GATE_THEN_DASHBOARD_PREFETCH`.
Jest to ograniczenie obecnej procedury, nie `WEB_REGRESSION_FAIL` i nie
unieważnia funkcjonalnego `B=PASS`.

Izolowany monitor zapisał `68/68` próbek PASS. Minima: Windows available
`4.539 GiB`, commit reserve `33.645 GiB`, pool available `13.808 GiB`;
swap maksymalnie `1.9 MiB`. Wykonano jeden stop/start testowego backendu dla
próby auth gate. Końcowa kontrola wymagała nadal 2 klientów, 1 dokument i head
`followup_assistant_chat_history_20260829`; log nie zawierał biznesowych
POST/PUT/PATCH/DELETE. Logowanie i kontrola sesji mogą mieć techniczne skutki
audytowe.

Po próbie trzy zachowane kontenery A2 są `exited`, Web zatrzymany, dokładnie
utworzona telemetria usunięta, a porty `18004/18005` są wolne. Dowody pozostają
`LOCAL_ONLY` pod
`...\owner-ui06-a-repeat-20260910T173258Z`. Produkcja, R03, modele, kolejki,
backupy, escrow, main i rescue nie zostały użyte ani zmienione. Testy
aplikacyjne: `NOT_RUN`, ponieważ kod pozostał niezmieniony.
