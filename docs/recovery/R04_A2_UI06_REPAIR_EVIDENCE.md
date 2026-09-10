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
