# NEXT Stabil — naprawa, dokończenie, odbiór i porządek

**Jedna roadmapa wykonawcza · wersja 1.1 · 2026-09-07**

**Status rejestracji: R00 ACCEPTED; wspólna roadmapa jest opublikowana na zatwierdzonej gałęzi recovery. Bieżący stan znajduje się wyłącznie w §0.**

Wersja 1.1 nie dodaje pakietów produktu. Rozszerza R00 o kontrolowaną publikację planu i checkpointy. Jednorazowe metadane dostarczonego pliku nie są deklaracją bieżącego stanu repo; aktualny stan jest w §0.

## 0. Bieżący stan i punkt wznowienia — czytać przed pracą

Ten plik jest jedyną roadmapą; §0.2 jest jedynym autorytatywnym rejestrem
bieżących statusów pakietów. Załączniki są mapowaniem i dowodami, nie kolejnym
sterowaniem. Poniższe wartości `NOT_*` są prawdziwym stanem szablonu przed
wykonaniem R00 — Codex ma je zastąpić ustalonymi faktami, nie przewidywaniami.

### 0.1. Aktualny checkpoint

| Pole | Wartość |
|---|---|
| Repozytorium | `domlap94-star/ai-lab-core` |
| Gałąź wspólnej roadmapy — docelowa | `recovery/next-stabil-repair-completion` |
| Kanoniczna ścieżka w repo | `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md` |
| Stan rejestracji | `ROADMAP_SYNCED@9af4026eeffed2509af943bff1e37b2514bfd5e8`; R00 zaakceptowane przez właściciela; konsolidacja R01 gotowa do review |
| Checkpoint ID | `R01-20260907T214615Z-CONSOLIDATION-C1` |
| Ostatnia aktualizacja operacyjna UTC | `2026-09-07T21:46:15Z` |
| Aktualny wykonawca / sesja | Codex / jedna aktywna sesja R01 |
| Aktywny pakiet / podetap | `R01 / CONSOLIDATION` — exact-path retirement i reference closure zakończone lokalnie, oczekują na publikację/review |
| Potwierdzony lokalny worktree | `C:\ai-lab-core-recovery`, branch `recovery/next-stabil-repair-completion`; starting local/remote `9af4026eeffed2509af943bff1e37b2514bfd5e8` |
| Gałąź / SHA kodu objętego sprawdzeniem | source baseline `origin/main@483f9bf8b1a591ded8a42df5da87663c664ed5d4`; rescue `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` oceniane osobno, nieadoptowane |
| Baseline commit dokumentacji | `483f9bf8b1a591ded8a42df5da87663c664ed5d4` |
| Źródła runtime / release / DB | Bounded read-only: backend z clean main; Supervisor/gatewaye/workery mają mixed path/hash; DB head `followup_assistant_chat_history_20260829`; live Web `1.0.2+41`, source Flutter `1.0.2+29`, backend `1.0.0` |
| Ostatnia faktycznie zakończona czynność | Przeczytano i zmapowano RT-011/RT-052/RT-057, zamknięto aktywne referencje, zachowano provenance/hash/recovery i wycofano dokładnie trzy zatwierdzone pliki z aktywnego drzewa |
| Potwierdzone testy bieżącego wykonania | Reference scan i consolidation ledger PASS; registry 108/36/61/16/14/25 PASS; R02–R24 payload unchanged; testy aplikacji `NOT_RUN` — R01 jest wyłącznie dokumentacyjny |
| Niezacommitowana praca / zabezpieczenie | Oryginalny worktree: 6 modified + 197 untracked, staged 0, drift 0; 1 patch + 8 exact copies zachowane `LOCAL_ONLY` pod `C:\ai-lab-core-staging\recovery\R00_20260907T202413Z`; manifest SHA-256 `F3AD6C4CE025D969DDC46923CD3640FCCB370248D4D40677860BA9636770C56C` |
| Niezakończone procesy i skutki operacyjne | Ta sesja nie uruchomiła długich zadań; runtime nieprzejęty/nierestartowany; 15 preparation queued i 16 advanced_queued tylko zaobserwowane, bez zgody na wykonanie |
| Najnowsza notatka przekazania | `docs/recovery/checkpoints/20260907T214615Z-R01-CONSOLIDATION-C1.md` |
| Zakres aktualnej zgody | R01: konsolidacja dokumentacji, exact retirement RT-011/052/057 i commit/push wyłącznie na recovery; R02–R24 bez zgody |
| Blokada / wymagana decyzja | Brak nierozwiązanego wymagania R01; `READY_FOR_REVIEW` nie oznacza `ACCEPTED`. Runtime/source/rescue/LOCAL_ONLY pozostają nieprzejęte |
| Jeden następny bezpieczny krok | Właściciel ocenia wynik R01 i osobno zatwierdza albo odrzuca rozpoczęcie R02 |
| Warunek STOP | Po publikacji checkpointu R01 zatrzymać pracę; nie rozpoczynać R02–R24 samodzielnie |

**Jak identyfikować wersję tego checkpointu:** SHA commita zawierającego ten plik
odczytuje się z Git (`git log -1 --format=%H -- NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`).
Nie wpisujemy przyszłego SHA jego własnego commita do treści ani nie tworzymy
nieskończonej serii commitów „aktualizacja własnego SHA”. `Baseline commit`
i `code_under_test` są odrębnymi, już istniejącymi SHA.

**Synchronizacja:** push jest potwierdzony dopiero po porównaniu lokalnego HEAD
z zdalnym ref odczytanym po push i ponownym odczycie zawartości pliku dla tego SHA.
Dowód `ROADMAP_SYNCED@<SHA>` znajduje się w raporcie przekazania odpowiedzi Codexa
/ Git, nie jako obietnica wpisana przed push do checkpointu. W razie braku sieci
w odpowiedzi podać `LOCAL_ONLY` / `REMOTE_UNVERIFIED`, zachować lokalny commit
oraz bezpieczną kopię pracy. Następny start zawsze ponownie sprawdza zdalny ref.

### 0.2. Rejestr statusów pakietów — źródło bieżącego stanu

Statusy wszystkich pakietów w szablonie są PLANNED. `ACCEPTED` wymaga rzeczywistego
odbioru i wskazania decyzji właściciela; agent nie może sam sobie wystawić odbioru.
Git status/push nie oznacza statusu funkcjonalnego ani deploymentu.

| Pakiet | Status | Aktywny podetap / ostatni checkpoint | Dowód / review / pozostała bramka |
|---|---|---|---|
| R00 | ACCEPTED | `R00-20260907T204252Z-HANDOFF-B1` / OWNER REVIEW | Właściciel zaakceptował `ROADMAP_SYNCED@9af4026eeffed2509af943bff1e37b2514bfd5e8` |
| R01 | READY_FOR_REVIEW | `R01-20260907T214615Z-CONSOLIDATION-C1` / CONSOLIDATION | RT-011/052/057 wycofane z aktywnego drzewa po mapowaniu; odbiór właściciela pozostaje |
| R02 | PLANNED | — | — |
| R03 | PLANNED | — | Osobne zgody restore/escrow |
| R04 | PLANNED | — | — |
| R05 | PLANNED | — | — |
| R06 | PLANNED | — | — |
| R07 | PLANNED | — | — |
| R08 | PLANNED | — | — |
| R09 | PLANNED | — | — |
| R10 | PLANNED | — | — |
| R11 | PLANNED | — | — |
| R12 | PLANNED | — | — |
| R13 | PLANNED | — | — |
| R14 | PLANNED | — | — |
| R15 | PLANNED | — | — |
| R16 | PLANNED | — | — |
| R17 | PLANNED | — | — |
| R18 | PLANNED | — | — |
| R19 | PLANNED | — | — |
| R20 | PLANNED | — | — |
| R21 | PLANNED | — | — |
| R22 | PLANNED | — | — |
| R23 | PLANNED | — | — |
| R24 | PLANNED | — | Osobne zgody na exact-path cleanup |

`docs/recovery/PACKAGE_REGISTER.csv` i `docs/recovery/PACKAGE_DETAILS.json` są lustrzanym
indeksem tych samych pakietów. Przy zmianie statusu należy je zsynchronizować
w tym samym commicie. Pierwotne pola `implementation/runtime/evidence/business_acceptance`
w mapie wymagań pozostają historycznym audytem; nowe dowody i zmiany wpisywać
wyłącznie w polach wykonawczych z referencją do checkpointu.

### 0.3. Protokół przerwania, awarii i wznowienia

Przed pauzą: zapisz zakończone czynności, faktyczne wyniki testów (w tym FAIL lub
NOT_RUN), pliki changed/staged/untracked, stan zadań i ostatni bezpieczny krok.
Zachowaj odtwarzalną kopię niesekretnej pracy niezacommitowanej poza repo i podaj
lokalizację/manifest/hash oraz `LOCAL_ONLY`, gdy inna maszyna jej nie posiada.
Nie udawaj, że sam commit roadmapy zabezpiecza niezacommitowany kod lub dane.
Nie commituj sekretów ani wadliwego source tylko dla uzyskania „czystego Git”.

Po znaczącym podetapie oraz przed planowanym przerwaniem wykonaj mały checkpoint
commit/push w autoryzowanym zakresie. Przed potencjalnie długą/ryzykowną operacją
zapisz zamiar i stan startowy; po niej wynik. Nagła awaria może nastąpić pomiędzy
tymi zapisami: nowa sesja najpierw weryfikuje realne procesy, zadania, logi,
zmiany plików i ewentualne skutki, a nie ponawia nieidempotentną operację.
Nie ma gwarancji zapisu w chwili crasha ani automatycznej synchronizacji bez sesji.

Wznowienie:
1. Odczytaj faktyczny zdalny ref oraz lokalny stan bez reset/pull/rebase w ciemno;
   porównaj z checkpointem i czytaj plan ze wskazanej gałęzi, nie domyślnego main.
2. Odczytaj AGENTS, masterplan, followup, §0 i kartę aktywnego pakietu oraz
   powiązane ID; nie wykonuj historycznych poleceń ze starych roadmap.
3. Sprawdź aktywnego wykonawcę i zmiany od checkpointu. Nie uruchamiaj równoległego
   autora; nie nadpisuj zmian innej sesji. Zdalny konflikt wymaga jawnego rozstrzygnięcia.
4. Ustal, czy ostatnia operacja rzeczywiście się skończyła. Brak dowodu to
   NOT_VERIFIED, nie PASS i nie automatyczna zgoda na ponowienie.
5. Wznów wyłącznie pozostały krok w zakresie istniejącej zgody. Przy
   WAITING_APPROVAL/BLOCKED zgłoś konkretną bramkę; „kontynuuj” nie oznacza
   zgody na migrację, deployment, dane, sekrety, modele lub cleanup.
6. Zapisz nowe fakty, checkpoint i dowód synchronizacji; nie twórz nowej roadmapy.

Małe notatki przekazania w `docs/recovery/checkpoints/` przechowują tylko fakty,
SHA, testy, zakres zgody i następny krok. Nie są dodatkowymi planami. Bez raw
logów z danymi klientów, dumpów, cookies, sekretów, binariów i backupów w Git.

## 1. Cel i definicja zakończenia

Doprowadzić istniejący NEXT Stabil do spójnego wykonania masterplanu: CRM i archiwum dostarczają wiarygodny materiał, Qwen 9B łączy go z KB i narzędziami, Visual oraz trudne analizy korzystają z kontrolowanego Temporary Chat, a użytkownik wykonuje rzeczywisty proces od sprawy do zatwierdzonej oferty i umowy. Na końcu usuwamy tylko udowodnione pozostałości, nie działające fundamenty.

Nie powstaje nowy system ani kolejny równoległy pipeline. Każdy pakiet kończy się sprawdzalną zmianą zachowania lub dowodem działania, nie tylko nowym raportem. Wyniki audytu **nie są przepisane na status GOTOWE**.

**Zakończenie projektu wymaga odbioru właściciela zgodnego z §42 i §45.** Przy formalnym odroczeniu części zakresu wolno ogłosić wyłącznie odbiór zakresu uzgodnionego z jawnymi wyłączeniami — nie pełną realizację wszystkich zapisów masterplanu.

## 2. Źródła i ich rola

1. `AI_LAB_MASTER_PLAN.txt` — wymagania, architektura i cel.
2. `AI_LAB_FOLLOWUP_PLAN.md` — uzupełnienia, zatwierdzone decyzje, zabezpieczenia i historia; stare deklaracje kolejności nie unieważniają nowej decyzji właściciela.
3. `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md` — ten plik; po rejestracji R00 wspólna instrukcja kolejności wykonawczej i bieżący checkpoint. Każdy pakiet nadal wymaga swojego zlecenia.

Pozostałe raporty, registry i runbooki są dowodami/specyfikacją techniczną, nie dodatkowymi roadmapami. Nie wolno kasować zasad dostępu, uprawnień ani approval gates w ramach konsolidacji. Sprzeczność wymaga jawnego rozstrzygnięcia, nie milczącego wyboru wygodniejszego dokumentu.

Udostępnienie roadmapy i checkpointów zostało zlecone jako cel R00 v1.1. Nie jest to zbiorcza zgoda wykonawcza na wszystkie pakiety ani decyzje operacyjne. Historyczne blokowanie CHUNK23 oraz operacyjne gates pozostają obowiązujące aż do zatwierdzenia ich zmiany przez właściciela. Zatwierdzenie wcześniejszego miejsca escrow w planie nie jest jeszcze zgodą na odczyt/kopiowanie sekretów.

## 3. Stałe decyzje

- Lokalny reasoner: **`qwen3.5:9b`**. Nie pobieramy modeli „na próbę”, nie wracamy do konkursu 4B/7B/12B. Embedding pozostaje odrębną aktywną funkcją, nie modelem do zastąpienia reasonera.
- **Temporary Chat pozostaje** dla Visual oraz trudniejszej analizy po lokalnym gate. Brak fallback do zwykłego czatu, brak bezpośrednich biznesowych zapisów odpowiedzi zewnętrznej.
- **KB pozostaje i służy wnioskowaniu**: dane sprawy + reguła/źródło + zakres stosowalności + hipoteza/wniosek + brakujące dane. Streszczenie tematów nie zastępuje analizy.
- Wspierane targety Flutter to **Windows, Android i Web**. iOS/macOS nie są bieżącym zakresem; historyczny pomysł iOS nie jest aktywnym wymaganiem ani blockerem.
- Obliczenia kluczowe wykonuje deterministyczny engine, z wersją metody/jednostek/źródła; finalny wynik techniczny wymaga człowieka.
- Dane firmy i cudza praca są chronione. Brak destructive cleanup, backfill, model delete, deployment lub migracji „przy okazji”.
- Test mobilny korzysta z **istniejącego emulatora Pixel_8**. Nie wymagamy telefonu i nie kasujemy AVD ani jego danych. Candidate install wymaga osobnej zgody i zachowania zgodności podpisu.
- Nie migrujemy teraz na Linux i nie przebudowujemy całej infrastruktury, aby ominąć błędy aplikacji.

## 4. Punkt odniesienia i uczciwe granice dowodu

| Element | Snapshot wejściowy |
|---|---|
| ZIP audytu | `NEXT_STABIL_FULL_AUDIT_20260907.zip` |
| SHA-256 | `B38CF3DA7CB2699C97891DBC64FE03B4770D1E86F7C90A5280D9A72AC15CF2F9` |
| Main | `483f9bf8b1a591ded8a42df5da87663c664ed5d4` |
| Rescue | `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` |
| Pierwotny lokalny HEAD | `72950657ac79b50d0afe72753632ba4cde810b95` |
| Lokalna praca | 6 modified + 197 untracked, bez staged w audycie |
| DB head | `followup_assistant_chat_history_20260829` według audytu |
| Status audytu | `NEXT_STABIL_FULL_AUDIT_PARTIAL` |

Hash ZIP i CRC 15 wpisów sprawdzono niezależnie; odczyt GitHub potwierdził wskazane main/rescue. Liczby runtime są z audytu, nie z dzisiejszego testu instalacji. Brak manifestu historycznego, raw logów oraz rozbieżności ID/opisu są jawne w `docs/recovery/AUDIT_RECONCILIATION.md`.

**Pokrycie planistyczne:** 108/108 wymagań, 36/36 ustaleń i 61/61 kandydatów zostało przypisanych do pakietów. To 108 pozycji indeksu audytu, nie dowód zakończenia wszystkich podpunktów. `docs/recovery/SCOPE_DETAIL_CHECKLIST.csv` wskazuje 16 grup, których nie wolno zgubić w szerokich etykietach.

Najważniejsze korekty przed wykonaniem: powiązania ID z REPAIR_INPUT poprawione; ContactPerson B nie wymaga nowej decyzji; spór o utratę KB sprawdzany na rescue; globalne uruchomienie 15 produkcyjnych jobów zastąpione izolacją i allowlisted canary. Oryginalny audyt nie został nadpisany.

## 5. Organizacja pracy, statusy i bramki

**Jeden aktywny pakiet wykonawczy naraz.** Właściciel zleca Rxx; Codex wykonuje ten pakiet, a ChatGPT ocenia dowody. Zamknięcie kodu nie jest automatycznym release. Dopuszczalne jest wybranie niezależnej lokalnej poprawki podczas oczekiwania na osobną decyzję operacyjną — wyłącznie po jawnej zmianie wskazanego pakietu, nie z inicjatywy agenta.

Pakiet może składać się z małych Rxx.a/Rxx.b/Rxx.c (np. konkretne metody R17), ale wszystkie pozostają w tym planie. Nie narzucamy sztucznego limitu 2–3 plików, gdy poprawka wymaga kompletnego testu/API/UI; nie dopuszczamy też pakietu „napraw wszystko”. Zakres wynika z jednego zachowania i zależności.

| Status | Co oznacza |
|---|---|
| PLANNED | Zaplanowane, nic jeszcze nie dowiedzione. |
| IN_PROGRESS | Wykonywany dokładnie wskazany zakres. |
| PAUSED | Praca celowo przerwana, zachowana i opisana w checkpointcie; brak zgody na automatyczne następne operacje. |
| READY_FOR_REVIEW | Wykonanie/raport gotowe do oceny, lecz nieodebrane. Dotyczy również weryfikacji i dokumentacji. |
| SOURCE_PASS | Kod/testy kandydata przeszły; nie oznacza wdrożenia. |
| WAITING_APPROVAL | Dokładna operacja/ryzyko czeka na człowieka. |
| DEPLOYED_UNVERIFIED | Uruchomione, lecz bieżący odbiór nie jest skończony. |
| ACCEPTED | Uzgodniony pozytywny scenariusz, negatywne bramki i regresja działają na wskazanym zestawie. |
| DEFERRED_BY_OWNER | Jawne ograniczenie scope; nie zalicza się do pełnego Masterplan PASS. |
| BLOCKED | Konkretna zależność/przyczyna, nie ogólny niepokój. |

Każde zamknięcie wymaga: requirement/FND IDs, commit + dirty state, listy dokładnych zmian, dowodu fail-before/pass-after dla usterki (albo potwierdzenia już istniejącej naprawy), logu komend/wyników, wpływu na dane/schema/config, tożsamości artefaktów, ograniczeń, rollback i decyzji człowieka. Testy syntetyczne i mocki są opisane jako takie.

### Wspólny checkpoint i synchronizacja

Obowiązuje §0. Jeden aktywny pakiet i jeden autor zmian naraz. Przy rozpoczęciu,
znaczącym podetapie, wyniku testu, zmianie blokady, przed pauzą i na zakończenie
aktualizujemy checkpoint; nie po każdej komendzie i nie według fikcyjnego timera.
Mały bezpieczny checkpoint dokumentacji może zostać zatwierdzony/pchnięty mimo
niezakończonych lub negatywnych testów aplikacji: opisuje je zgodnie z prawdą,
a nie commituję wadliwego kodu jako PASS. Zgoda nie obejmuje samowolnego source
commit, nowego pakietu ani modyfikacji scope.

ChatGPT zaczyna kontrolę od odczytu faktycznej gałęzi/ref z GitHub. Codex
zaczyna od checkpointu i weryfikacji lokalnego/remote stanu. Żaden agent nie
może traktować pamięci rozmowy, kopii ZIP lub domyślnego main jako aktualniejszego
od przypiętego wspólnego checkpointu bez sprawdzenia. Przeniesienie kanonicznej
gałęzi do main lub innej gałęzi wymaga osobnej synchronizacji i decyzji.

### Bramki bez samoczynnego rozszerzenia zgody

- Zgoda na źródła/testy może obejmować jawny commit/push roboczej gałęzi. Nie obejmuje main/release/deploy.
- Zmiany schematu: design → izolowane upgrade/downgrade/re-upgrade → raport → human gate → apply. Nie obiecywać bezpiecznego destructive downgrade przy nowych danych biznesowych.
- Operacje runtime: osobna zgoda na restart/config/model/external smoke, emulator install i normalne production writes testowego canary. Przed pierwszym ryzykownym wdrożeniem lub zmianą danych wymagany R03.
- Backfill/rekonsyliacja historii/Qdrant rebuild: osobne IDs, limity, dry-run i zatwierdzenie. 15 jobów lub 5988 dokumentów z audytu nie jest zgodą.
- Retencja/cleanup/sekrety/gateway/firewall/Tailscale: istniejące dodatkowe bramki zachowane. Zatwierdzenie tej roadmapy nie konsumuje żadnej z nich.

Zakazy bazowe: `git add .`, `git clean`, `reset --hard`, force push, `flutter clean`, `docker system prune`, `docker volume prune`; brak kasowania AVD, source, danych, backupów, modeli i workerów na podstawie samej heurystyki.

### Bez zamkniętej pętli audytów

Nowy problem musi mieć wersję, konkretny wpływ i test rozstrzygający. Hipoteza nie jest naprawiana jak potwierdzony bug. Zamknięty pakiet otwieramy tylko dla odtworzonej regresji lub istotnego nowego dowodu dotyczącego jego warunku odbioru. Usprawnienie niewpływające na kryterium trafia do jawnego backlogu — nie resetuje projektu.

## 6. Kamienie odbioru i kolejność

- **K0 — baza kontrolowana:** R00–R04 w zakresie właściwych decyzji i operacji. Można bezpiecznie testować/odtwarzać oraz jednoznacznie identyfikować zestaw.
- **K1 — użyteczny CRM + Asystent:** R16 i jego zależności. 9B + KB + Visual + trudna analiza + historia działają w aplikacji. Nie czekamy z tym odbiorem na wszystkie oferty/umowy/CAD. Kontrolowane wydanie K1 jest osobnym zleceniem; nie jest pełnym Masterplan PASS.
- **K2 — pełny uzgodniony workflow:** R23, po domknięciu przyjętego zakresu technicznego/handlowego/operacyjnego i historycznych decyzji.
- **K3 — porządek końcowy:** R24 z ponownym krytycznym smoke po cleanup.

Numery wyznaczają domyślną kolejność. Zależności w rejestrze opisują **gotowość źródeł/testów**; dodatkowe zgody i R03 nadal obowiązują przed operacyjnym apply. Dlatego np. przygotowanie kandydata w R04 jest możliwe wcześniej niż produkcyjny rollout. R07/R08 można wykonać lokalnie podczas oczekiwania na privacy/restore approval — po jawnym wskazaniu tego pakietu.

| Pakiet | Cel | Zależności źródłowe/testowe |
|---|---|---|
| R00 | Wspólna roadmapa w Git i zabezpieczenie punktu startu | brak |
| R01 | Jedna roadmapa i wycofanie konkurencyjnych instrukcji | R00 |
| R02 | Odtwarzalne i izolowane testy | R00 |
| R03 | Odtwarzalność i chronione sekrety przed ryzykowną zmianą | R00, R02 |
| R04 | Jednoznaczny release i wersje wszystkich komponentów | R00, R02 |
| R05 | Działające Visual z kontrolą prywatności pikseli | R02, R04 |
| R06 | Trwały czat, publikacja i zakres Visual | R02, R04 |
| R07 | Naturalne polecenia i pytania mieszane | R02 |
| R08 | Retrieval i składanie kompletnego kontekstu | R02, R07 |
| R09 | Qwen 9B, starsze wejścia AI i zasoby | R02, R04, R07, R08 |
| R10 | Document Preparation/Intelligence i rzeczywiste formaty | R02, R06, R09 |
| R11 | Punktowa naprawa historycznego Unicode | R02, R03 |
| R12 | Gmail, załączniki i dowodliwe dopasowania | R02, R10 |
| R13 | Użyteczna, wersjonowana baza wiedzy | R08, R09, R10 |
| R14 | Archiwum i podobne realizacje | R08, R10, R11, R12, R13 |
| R15 | Realne Visual i trudna analiza przez Temporary Chat | R05, R06, R08, R09, R10, R13 |
| R16 | Odbiór aplikacji: emulator, Windows i Web | R04, R06, R07, R08, R09, R10, R12, R15 |
| R17 | Zweryfikowane metody techniczne i obliczenia | R09, R13, R15 |
| R18 | Oferty jako wersjonowany obieg | R13, R16 |
| R19 | Umowy z zaakceptowanej oferty | R18 |
| R20 | Domknięcie CRM, pracy terenowej i uprawnień | R16, R18, R19 |
| R21 | Zakres CAD i pozostałych możliwości docelowych | R10, R16 |
| R22 | Operacje, alerty i retencja | R03, R04, R09, R16 |
| R23 | Odbiór §42 i kontrolowane wydanie systemu | R03, R04, R11, R12, R13, R14, R16, R17, R18, R19, R20, R21, R22 |
| R24 | Końcowe sprzątanie bez utraty funkcji | R23 |


## 7. Karty pakietów

Kryteria poniżej są obowiązkowe wraz z odpowiednimi pozycjami `docs/recovery/REQUIREMENT_PACKAGE_MAP.csv` i podkryteriami masterplanu. Właściciel nie musi zatwierdzać całego zakresu przyszłych operacji z góry. Każdy pakiet ma własny wąski prompt; pierwszy dostarczony prompt obejmuje wyłącznie R00.

### R00 — Wspólna roadmapa w Git i zabezpieczenie punktu startu

**Typ:** DOC_BOOTSTRAP / VERIFY · **Status:** patrz §0.2 · **Zależności:** brak

**Cel:** Udostępnić jedną roadmapę lokalnie i na GitHub, z checkpointem wznowienia; zachować istniejącą pracę oraz odróżnić stan kodu od runtime.

**Odpowiedzialność za wymagania:** pakiet przygotowawczy/przekrojowy; powiązania poniżej.

**Pozostałe powiązania:** M-072, F-030, F-031. **Ustalenia:** FND-014, FND-028, FND-032.

**Zakres wykonania**

1. Zachować pierwotny preflight, brakujące dowody i ochronę pracy z R00 v1.0. Nie powtarzać zakończonego R00; wykorzystać dowody po sprawdzeniu aktualności. Nie uruchamiać drugiej równoległej sesji.
2. Po sprawdzeniu remote i skutków hooków/CI utworzyć lub bezpiecznie wznowić gałąź recovery/next-stabil-repair-completion w osobnym lokalnym worktree. Bazą nowej gałęzi dokumentacyjnej jest zweryfikowany origin/main; nie przełączać oryginalnego brudnego drzewa i nie adoptować automatycznie rescue.
3. Skopiować dostarczony plik NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md v1.1 do root repo oraz jawny allowlist załączników planistycznych do docs/recovery/. Nie generować na nowo wymagań i pakietów. W AGENTS wykonać wyłącznie zmianę wskaźnika na nową roadmapę i reguł checkpoint/wznowienia; reszta konsolidacji dopiero R01.
4. Zapisać prawdziwy checkpoint R00, sprawdzić diff/sekrety/referencje i opublikować dokumentacyjny bootstrap przed długą częścią baseline. Push tylko na wskazaną gałąź po wykluczeniu automatycznego deploymentu. Zgoda nie obejmuje main, PR/merge, tagu ani release.
5. Zweryfikować audit ZIP i dostępność brakującego historycznego manifestu; zachować odtwarzalną kopię niesekretnej lokalnej pracy poza repo/runtime oraz zapisać porównanie manifestów. Nie odtwarzać historycznych wyników przez zgadywanie.
6. Ustalić bounded read-only zestaw wykonawczy i propozycję przyszłego adoptowania rescue/lokalnych zmian. Fakty source i runtime zapisać osobno. Niczego nie restartować, nie opróżniać kolejek, nie kopiować sekretów do repo.
7. Po każdym znaczącym podetapie i przed pauzą zapisać checkpoint oraz bezpieczny commit/push dokumentacji. Na końcu opublikować mały zanonimizowany raport wznowienia, zgłosić wynik i czekać na odbiór; nie oznaczać samodzielnie ACCEPTED.

**Sprawdzenia i dowody**

- Oryginalny worktree, jego staged/unstaged/untracked i runtime zachowane; skutki utworzenia refs/worktree oraz commity dokumentacyjne są jawnie wykazane, nie raportowane jako Git changes=0.
- 108/108 wymagań, 36/36 ustaleń, 61/61 kandydatur i 25/25 pakietów zachowane. Statusy historycznego audytu nie zostały zmienione.
- Istnieje tylko jeden kanoniczny plik roadmapy i jedno źródło bieżących statusów (§0.2). Rejestry maszynowe są jego lustrzanym indeksem, nie osobną instrukcją.
- Lokalny commit jest odczytany na origin/recovery/next-stabil-repair-completion i roadmapa jest dostępna pod tym ref. Odpowiedź zawiera pełny SHA publikacji. Brak sieci oznacza LOCAL_ONLY, nie PUSH_PASS.
- Checkpoint wskazuje ostatnią zakończoną czynność, niewykonane kroki, zachowaną pracę niezacommitowaną, pending gates i jeden następny krok. Nowa sesja nie musi korzystać z historii rozmowy.

**Warunek zamknięcia:** Roadmapa i bezpieczny checkpoint są w lokalnym worktree i na wskazanej gałęzi GitHub. BASELINE_LOCK opisuje źródła, rescue, lokalną pracę, runtime i recovery. Codex kończy READY_FOR_REVIEW; ACCEPTED dopiero po rzeczywistym odbiorze właściciela.

**Dane/schema/config:** Tylko dokumentacja na allowliście, mała korekta AGENTS, nowe refs/worktree i kontrolowana kopia niesekretnej pracy poza repo. Brak zmian aplikacji/config/DB/modeli/deploymentu.

**Potrzebna zgoda:** Uruchomienie promptu R00 v1.1 autoryzuje dokumentacyjny bootstrap oraz checkpoint commit/push wyłącznie na recovery/next-stabil-repair-completion. Nie zatwierdza R01–R24, usuwania roadmap, zmian zakresu ani operacji produkcyjnych/escrow.

**Rollback:** Zachować oryginalne drzewo. Błędną opublikowaną dokumentację korygować nowym commitem; bez force push/reset. Usunięcie worktree dopiero po osobnej kontroli własności i lokalnej pracy, nie jako automatyczny rollback.

**Poza zakresem:** Naprawy aplikacji, pełny ponowny audyt, adopcja rescue/dirty changes, modyfikacja main/followup/masterplanu, usuwanie starych roadmap, R01–R24, migracje, restarty, modele, queue drain, runtime writes.

### R01 — Jedna roadmapa i wycofanie konkurencyjnych instrukcji

**Typ:** DOC_CONSOLIDATION · **Status:** patrz §0.2 · **Zależności:** R00

**Cel:** Usunąć konflikt dokumentów sterujących bez usuwania wymagań i zabezpieczeń.

**Odpowiedzialność za wymagania:** pakiet przygotowawczy/przekrojowy; powiązania poniżej.

**Pozostałe powiązania:** M-008, M-072, M-073, F-026, F-029. **Ustalenia:** FND-027.

**Zakres wykonania**

1. Wykorzystać roadmapę już opublikowaną w R00; nie tworzyć nowego pliku, drugiej gałęzi kanonicznej ani planu v2 od zera. Uzgodnić resztę kolejności i sprzeczności kanonicznych nagłówków bez zmiany wymagań.
2. Zweryfikować pokrycie podpunktów masterplanu przez 108 agregatów. Dopisać kryteria do istniejących rodziców, nie ogłaszać, że 108 wierszy dowodzi atomowego pokrycia każdego checkboxa.
3. Przenieść zgodne unikalne decyzje z dokładnie trzech starych roadmap; nadać historycznym dowodom datę/commit i zachować możliwość odtworzenia.
4. Sprawdzić małą zmianę AGENTS wykonaną w R00 i uzupełnić rzeczywiste odwołania w nagłówkach masterplanu/followup oraz README/runbookach. Nie usuwać treści projektowej ani globalnych approval gates; nie przepisywać całego AGENTS.
5. Wycofać CODEX_MASTER_EXECUTION.md, FOLLOWUP_PRECHUNK23_FULL_SYSTEM_ROADMAP.md oraz frontend/POST_BATCH_AUTH_REMOTE_PLAN.md w osobnym dokumentacyjnym commicie po akceptacji dokładnego diffu.

**Sprawdzenia i dowody**

- Każde aktywne odwołanie do starego planu zostało poprawione; wzmianki historyczne są oznaczone i nie są instrukcją.
- 108/108 wymagań, 36/36 ustaleń i 61/61 kandydatów mają mapowanie; nie ma usuniętej bramki zgody, zmienionego modelu ani instrukcji uruchomienia CHUNK23 bez zatwierdzenia nowej kolejności.

**Warunek zamknięcia:** W aktywnym sterowaniu są dwa kanoniczne plany i dokładnie jedna roadmapa; małe rejestry CSV są jej załącznikami, nie odrębnymi planami.

**Dane/schema/config:** Dokumentacja/Git wyłącznie. Brak zmian aplikacji, runtime i danych.

**Potrzebna zgoda:** Osobna zgoda na dokładne wycofywane ścieżki, aktualizację nagłówków/odwołań i dokumentacyjny commit/push R01. Zgoda na rejestrację roadmapy w R00 nie jest zgodą na delete ani przyszłe wdrożenia.

**Rollback:** Odtworzenie dokładnych wersji dokumentów i odwołań z zatwierdzonego commita; zachowanie audytu.

**Poza zakresem:** Usuwanie blueprinta, raportów, workerów, modeli, migracji lub buildów. Narzucanie nowych wymagań ze starych roadmap.

### R02 — Odtwarzalne i izolowane testy

**Typ:** FIX / VERIFY · **Status:** patrz §0.2 · **Zależności:** R00

**Cel:** Uzyskać wiarygodny wynik testów właściwego commita, nie wynik zależny od kolejności fixture lub brakujących bibliotek.

**Odpowiedzialność za wymagania:** M-033.

**Pozostałe powiązania:** M-031, M-073. **Ustalenia:** FND-019, FND-033, FND-034.

**Zakres wykonania**

1. Przygotować oddzielne, przypięte środowisko testowe z pytest i potrzebnymi bibliotekami; nie instalować narzędzi do niezmiennego obrazu produkcyjnego.
2. Naprawić izolację DOC-03: własna DB/schema albo testowy namespace i wybór własnych rekordów; nie osłabiać asercji produkcyjnej logiki leasingu.
3. Uruchomić main jako bazę i wybrane testy rescue jako kandydata z pełnym drzewem niezbędnych fixture. Sprawdzić schemat wymagany przez rescue, nie utożsamiać nazwy Visual V2 z potrzebą nowej migracji.
4. Zapisać uruchamialne reprodukcje REP-001–004 i spornego przypadku KB+supplemental Visual na rzeczywistych modułach. Utworzyć evidence log z dokładną komendą, commit, konfiguracją izolacji, stdout/stderr i exit code.

**Sprawdzenia i dowody**

- DOC-03 przechodzi sam oraz ze wspólnymi suite w co najmniej dwóch ustalonych kolejnościach, w tym permutacji z zapisanym seedem.
- Pytest-only suite uruchamiają się w test image; brak dostępu do produkcyjnych DB/storage/Gmail/workerów/modeli bez osobnej zgody.
- Błąd harnessu jest odróżniony od source failure; wynik main nie jest podstawiony za rescue.

**Warunek zamknięcia:** Zapisany powtarzalny baseline suite, brak niejawnych produkcyjnych zależności i uruchamialne testy naprawianych reguł.

**Dane/schema/config:** Test code/config i syntetyczne DB. Brak zmian produkcyjnego obrazu i danych.

**Potrzebna zgoda:** Zgoda na pakiet źródłowy/testowy i jego oddzielny commit. Brak zgody na deployment.

**Rollback:** Revert wyłącznie zmian testów; dokładnie nazwane zasoby syntetyczne usuwane według własności.

**Poza zakresem:** Sztuczne usuwanie testów, przepisywanie całego harnessu, pobieranie nowego modelu, podmienianie production data.

### R03 — Odtwarzalność i chronione sekrety przed ryzykowną zmianą

**Typ:** VERIFY / COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R00, R02

**Cel:** Przed migracją lub wdrożeniem wykazać możliwość odtworzenia, a nie wyłącznie istnienie pliku backupu.

**Odpowiedzialność za wymagania:** M-066, M-067, F-017, F-021, F-026.

**Pozostałe powiązania:** M-037, F-016. **Ustalenia:** FND-014, FND-025, FND-026.

**Zakres wykonania**

1. Uzgodnić z właścicielem wcześniejszy termin escrow względem historycznej sekwencji CHUNK23. Nie traktować tego dokumentu jako skonsumowania dawnego tokenu.
2. Sprawdzić istniejący backup DB/storage/konfiguracji oraz izolowany restore Qdrant ze zgodnością kolekcji, zakresów i generacji; nie odtwarzać niczego na aktywnym celu.
3. Wykorzystać istniejący Windows DR tool/runbook. Zmierzyć osiągnięte RTO/RPO i dopiero uzgodnić dopuszczalne wartości; nie wpisywać zmyślonego SLA.
4. Escrow: zaszyfrowane medium/vault, odrębny recovery key, ACL, wersja/inventory i próba odczytu. Żadnych wartości sekretów w Git, raporcie, ZIP lub promptach.

**Sprawdzenia i dowody**

- Restore do odizolowanego targetu odtwarza reprezentatywną sprawę, pliki i indeksy; hashe/counts/scope są zgodne.
- Można odzyskać niezbędną konfigurację według instrukcji bez pamięci operatora; brak przypadkowej wysyłki czy uruchomienia produkcyjnych kolejek po restore.

**Warunek zamknięcia:** Zatwierdzony dowód odzyskania oraz punkt odtworzenia dla najbliższej zmiany. W przypadku odmowy escrow odnotowany konkretny blocker odpowiednich wdrożeń, nie zakaz lokalnych poprawek.

**Dane/schema/config:** Nowe izolowane zasoby i chronione backupy. Brak production restore, purge lub rotacji credentials.

**Potrzebna zgoda:** Osobna zgoda operacyjna na restore/escrow i zmianę kolejności historycznego CHUNK23; rotacja nadal wymaga oddzielnej zgody.

**Rollback:** Usunąć wyłącznie nazwane izolowane cele po zatwierdzeniu; zachować zweryfikowane kopie. Nigdy nie nadpisywać czynnego systemu.

**Poza zakresem:** Sekrety w dokumentacji, automatyczne włączenie retencji, uznanie verified backup za restore PASS.

### R04 — Jednoznaczny release i wersje wszystkich komponentów

**Typ:** FIX / VERIFY · **Status:** patrz §0.2 · **Zależności:** R00, R02

**Cel:** Testować i uruchamiać ten sam zatwierdzony zestaw bez utraty pracy lokalnej.

**Odpowiedzialność za wymagania:** M-003, M-004, M-065, M-072, F-023, F-034.

**Pozostałe powiązania:** M-015, M-057, M-064, F-022, F-024, F-031. **Ustalenia:** FND-004, FND-006, FND-013, FND-014, FND-015, FND-016, FND-023, FND-028.

**Zakres wykonania**

1. Z clean base main zbudować kontrolowaną gałąź integracyjną. Ocenić pięć commitów rescue i lokalne różnice; przyjąć tylko potrzebne, przejrzane zmiany. Bez ślepego merge całego dirty repo.
2. Manifest łączy backend commit/image, API/schema, Web/Windows/Android build/hash/podpis, Supervisor, analysis/vision workers i efektywną niesekretną konfigurację.
3. Przypiąć procesy do odtwarzalnych deployment roots; wspólny fizyczny katalog nie jest obowiązkowy. Usunąć zależność runtime od zmiennego worktree dopiero w kontrolowanym rollout.
4. Naprawić kontrakt /version/stable/minimum/debug i zgodność starych klientów. Nie zrównywać sztucznie różnych numerów API/schema/app; muszą tworzyć poprawną macierz zgodności.
5. Przygotować odtwarzalny build Windows i aktualny build testowy Android z zatwierdzonym certyfikatem; nie publikować ani zużywać numeru release bez osobnej zgody.

**Sprawdzenia i dowody**

- Każdy runtime hash ma odpowiednik zatwierdzonego artefaktu; publiczny /control nadal niedostępny, rzeczywista konfiguracja debug bezpieczna.
- Aktualny stable klient zachowuje kompatybilność; candidate klient używa właściwego API; rollback komponentu udowodniony.

**Warunek zamknięcia:** RELEASE_ID + compatibility manifest gotowe. Stan source-ready/staged/deployed/accepted jest rozdzielony. Samo przygotowanie nie oznacza promocji rescue.

**Dane/schema/config:** Źródła wersjonowania/build/config. Operacyjne przepięcie i restart to oddzielne działania po R03, privacy gate i zgodzie.

**Potrzebna zgoda:** Commit źródłowy oddzielnie; przed operacyjnym przepięciem: R03 i osobny approval konfiguracji/deploy/gateway. Brak zmian firewall/Tailscale.

**Rollback:** Poprzedni podpisany lub hashowany zestaw wraz z konfiguracją i schema compatibility; zachowane stare ścieżki do czasu odbioru.

**Poza zakresem:** Usuwanie live Web lub zewnętrznego workera, podwyższanie minimum dla wymuszenia pozornego sukcesu, reset lokalnego repo.

### R05 — Działające Visual z kontrolą prywatności pikseli

**Typ:** FIX · **Status:** patrz §0.2 · **Zależności:** R02, R04

**Cel:** Zachować Temporary Chat dla Visual, nie wysyłając niedopuszczonej tożsamości lub danych ukrytych w rastrze.

**Odpowiedzialność za wymagania:** pakiet przygotowawczy/przekrojowy; powiązania poniżej.

**Pozostałe powiązania:** M-002, M-028, M-057, M-058, M-061, F-019, F-022. **Ustalenia:** FND-004, FND-005, FND-013, FND-036.

**Zakres wykonania**

1. W istniejącej bramce eksportu określić dopuszczalność rzeczywistych bajtów obrazu, jego treści i metadanych. Wybrać z właścicielem bezpieczną politykę: zatwierdzona lokalna redakcja albo jawnie dopuszczony materiał; niepewne i restricted pozostają zablokowane.
2. Nie traktować resize, EXIF strip, regex/OCR bez oceny jakości ani pola customer_sanitizable jako certyfikatu anonimowości. Żaden niedopuszczony raster nie może być wysłany do usługi po to, aby dopiero tam go zanonimizować.
3. Sprawdzić mapę oryginał → wersja eksportowa → hash manifestu → dokładne bytes uploadu. Zmiana obrazu po zatwierdzeniu unieważnia zgodę.
4. Minimalnie skorygować obecny service/spool/privacy contract. Bez nowego pipeline ani gwarancji bezbłędnego automatycznego rozpoznawania wszystkich PII.

**Sprawdzenia i dowody**

- Negatywne: syntetyczny adres/nazwisko w pikselach, niepewny skan i restricted dają 0 uploadów; błędny hash i podmieniony plik są blokowane.
- Pozytywne: dopuszczony public-safe/sanitized materiał jest pakowany i później przechodzi R15. Samo blokowanie wszystkich obrazów nie zamyka wymagania.

**Warunek zamknięcia:** Privacy gate ma dowód zgodności faktycznych bajtów i obustronne testy: blokuje niedopuszczone, przepuszcza dopuszczone. P0 blokuje eksport/promocję Visual, nie każdą lokalną poprawkę.

**Dane/schema/config:** Domyślnie bez migracji i zmian danych firmy; ewentualna zmiana kontraktu klasyfikacji wymaga projektu.

**Potrzebna zgoda:** Zgoda na politykę prywatności, source commit oraz osobno każdy live Temporary Chat smoke i deploy.

**Rollback:** Bezpieczne wyłączenie wyłącznie nowej gałęzi eksportu; nie wracać do niekontrolowanego V1. Wyniki i historia zachowane.

**Poza zakresem:** Permanentne wyłączenie Visual jako końcowa naprawa, API zamiast Temporary Chat, usuwanie oryginałów, zniesienie restricted.

### R06 — Trwały czat, publikacja i zakres Visual

**Typ:** FIX / VERIFY · **Status:** patrz §0.2 · **Zależności:** R02, R04

**Cel:** Włączyć już istniejące poprawki do właściwego kandydata i sprawdzić granice współbieżności.

**Odpowiedzialność za wymagania:** M-012, M-047, M-048, M-049, M-059.

**Pozostałe powiązania:** M-005, M-031, M-057, M-062, M-070, F-025. **Ustalenia:** FND-004, FND-006.

**Zakres wykonania**

1. Przyjąć z rescue świeży blokowany odczyt rozmowy i current-request coverage, zamiast pisać oba mechanizmy ponownie.
2. Przeprowadzić test dwóch sesji dla delete/publication ze starym obiektem ORM i idempotentną ponowną finalizacją.
3. Sprawdzić reuse broad → explicit oraz explicit → broad na tych samych źródłach; strona niepokryta i częściowy dokument nie mogą zostać nazwane kompletnym.
4. Zachować limit 4 źródeł pojedynczego zadania Visual, trwały wynik AssistantRun oraz rozróżnienie delete/cancel/background. Wieloetapowe pokrycie dokumentu należy do R10/R15.

**Sprawdzenia i dowody**

- Deletion wins = 0 późnych wiadomości i brak przesunięcia last_activity; publication wins = co najwyżej 1 wiadomość, bez duplikatu.
- Wynik runu zachowany po delete; zmiana ekranu lub tło nie anuluje; explicit cancel respektuje współdzielony/preparation-owned Visual.
- Bieżący zakres pytania determinuje gate, a wynik współdzielony pozostaje niemutowany.

**Warunek zamknięcia:** Poprawki działają na docelowym kandydacie z izolowaną integracją; po R16 także w aplikacji. Nie przenosić statusu rescue PASS do produkcji bez deploy evidence.

**Dane/schema/config:** Backend i testy; bez migracji według obecnego diffu. Potwierdzić faktycznie używane tabele.

**Potrzebna zgoda:** Source commit; operacyjne wdrożenie osobno, po zgodności R03/R04 i właściwych bramkach dla eksportu.

**Rollback:** Revert kandydata lub poprzedni kompatybilny release; brak usuwania rozmów i historycznych wyników.

**Poza zakresem:** Anulowanie runu przez delete/background, przenoszenie blokady DB na czas pracy modelu, nowe usługi czatu.

### R07 — Naturalne polecenia i pytania mieszane

**Typ:** FIX · **Status:** patrz §0.2 · **Zależności:** R02

**Cel:** Pytanie użytkownika wykonuje właściwe zadanie, a nie opisuje możliwości systemu.

**Odpowiedzialność za wymagania:** M-046.

**Pozostałe powiązania:** F-025. **Ustalenia:** FND-007, FND-008.

**Zakres wykonania**

1. Dodać parafrazy do testu rzeczywistego routera i endpointu: wybrany dokument, jawny tytuł, pytanie ogólne o funkcje i brak/niejednoznaczny cel.
2. Rozdzielić polecenie działania od pytania o możliwości. Brak zaznaczonego pliku nie oznacza automatycznie SYSTEM_META: zastosować istniejące bezpieczne rozwiązywanie celu albo poprosić o wskazanie.
3. Zapytanie techniczne + adres ma zachować techniczne retrieval KB oraz autoryzowany odczyt CRM. Nie doklejać adresu do zewnętrznego pakietu tylko dlatego, że był częścią pytania.
4. Nie tworzyć kolejnego planner LLM. Doprecyzować istniejące reguły oraz testy ich priorytetu.

**Sprawdzenia i dowody**

- „Czy możesz przeanalizować ten dokument?” przy wybranym materiale uruchamia analizę; prawdziwe pytanie o możliwości nadal otrzymuje opis.
- Technika + adres ma oba lokalne zakresy i poprawną izolację klienta; brak celu jest jawny, a nie domyślnie zgadywany.

**Warunek zamknięcia:** Reprezentatywny zestaw parafraz daje zgodny plan/intencję i prawidłowe zachowanie uprawnień.

**Dane/schema/config:** Kod routingu i testy, bez produkcyjnych zapisów i migracji.

**Potrzebna zgoda:** Zgoda source; deploy oddzielnie.

**Rollback:** Revert małego commita i zachowanie testu regresji do ponownej naprawy.

**Poza zakresem:** Zmiana modelu, wymaganie od użytkownika specjalnych komend, omijanie autoryzacji.

### R08 — Retrieval i składanie kompletnego kontekstu

**Typ:** FIX · **Status:** patrz §0.2 · **Zależności:** R02, R07

**Cel:** Właściwe źródła trafiają do modelu i walidatora, zamiast znikać po późniejszym przycięciu listy.

**Odpowiedzialność za wymagania:** M-039, M-040, M-042.

**Pozostałe powiązania:** M-041, M-047, M-060, F-018, F-020, F-025. **Ustalenia:** FND-008, FND-009, FND-010, FND-011.

**Zakres wykonania**

1. Przenieść ograniczenie po materiale/statusie/scope przed ranking i limit w KB; test z właściwym źródłem poza globalnym top-N. Zachować filtrowanie uprawnień w DB, nie tylko po pobraniu.
2. Oddzielić ERROR, NOT_READY, EMPTY_CORPUS, NO_MATCH i PARTIAL; fault injection nie może być interpretowane jako brak wiedzy. Ewentualny lexical fallback jest jawny.
3. Na rzeczywistym _collect() rescue rozstrzygnąć C-004: 5 źródeł sprawy + 3 KB + 4 supplemental Visual. Zastosować jeden końcowy dobór uwzględniający wymagane warstwy i deduplikację, nie zwykłe odcinanie końca.
4. Sprawdzić zgodność listy źródeł, tool payloads, mapy handle i final prompt. Source count nie jest jedyną miarą: fragment KB musi rzeczywiście zawierać potrzebną zasadę.
5. Zawęzić filtrowanie wewnętrznych uchwytów do rzeczywistego manifestu/kontraktu; S235/S355 mają przejść bez usuwania treści technicznej.

**Sprawdzenia i dowody**

- Test 5+3+4 nie traci całej wymaganej KB; kontekst mieści się w zatwierdzonym budżecie 9B. Gdy wymagania nie mieszczą się, system etapuje lub zgłasza zakres, nie twierdzi complete.
- Cel poza globalnym top-N jest znaleziony; fault injection odróżnia awarię; S235/S355 dozwolone, rzeczywiste niedopuszczone handle/obce źródła odrzucone.
- Dla explicit covered page wynik przechodzi; broad partial wymaga uzupełnienia; żadne evidence nie pochodzi od innego klienta.

**Warunek zamknięcia:** Spójny ślad retrieved → selected → actually provided → claimed. Sporna teza ma rozstrzygnięcie na właściwym commicie, nie etykietę z innej gałęzi.

**Dane/schema/config:** Istniejące retrieval/context/validator i testy. Brak masowej indeksacji, zmiany modelu i migracji bez potrzeby.

**Potrzebna zgoda:** Zgoda source; Qdrant/live test tylko osobno na wydzielonym namespace.

**Rollback:** Revert zmian retrieval; testowe kolekcje według własności; nie kasować produkcyjnego indeksu.

**Poza zakresem:** Nieograniczony kontekst, wyłączenie źródeł lub walidacji, ogólne „Visual zawsze usuwa KB” bez wskazania ścieżki.

### R09 — Qwen 9B, starsze wejścia AI i zasoby

**Typ:** FIX / VERIFY · **Status:** patrz §0.2 · **Zależności:** R02, R04, R07, R08

**Cel:** Zachować 9B jako wspólny reasoner i sprawdzić jego działanie, bez dalszego konkursu modeli.

**Odpowiedzialność za wymagania:** M-036, M-043, M-050, M-063.

**Pozostałe powiązania:** M-002, M-031, M-045, M-048, M-062, M-069, M-070, M-072, F-025, F-032. **Ustalenia:** FND-002, FND-023, FND-024, FND-029.

**Zakres wykonania**

1. Zmapować użytkowników aktywnych legacy RAG/Client Knowledge/Business/Technical/Agent. Przepiąć lub zaadaptować je do istniejącej ścieżki 9B i guardów z zachowaniem kontraktów klientów i zamkniętego katalogu narzędzi.
2. Usunąć problem process-local ownership po restarcie na podstawie dowodów własności; ta sama nazwa/digest nie dowodzi, że wolno rozładować model cudzej aktywnej sesji.
3. Wykonać kontrolowany local smoke 9B + embedding, timeout/unload/retry/restart recovery. Zapisać model digest, parametry, czas, Windows/WSL RAM/swap i zachowanie po błędzie.
4. FND-024 pozostaje hipotezą do testu 1–2 kontrolowanych overlap. Dopiero stwierdzony problem uzasadnia minimalną koordynację istniejących dispatcherów; nie budować nowego globalnego schedulera dla samego podejrzenia.

**Sprawdzenia i dowody**

- Każde zachowane aktywne wejście AI używa zatwierdzonego 9B lub jawnej deterministycznej odpowiedzi; brak ukrytego llama fallback.
- Brak permanent wait po restarcie, brak rozładowania obcej aktywnej pracy, zakończenie/timeout pozostają trwałe.
- Realna telemetria nie narusza dotychczasowych zatwierdzonych limitów; limity nie są obniżane, aby uzyskać PASS.

**Warunek zamknięcia:** Local-only użyteczny scenariusz i zasoby odebrane na właściwym zestawie; modele historyczne zachowane do końcowego consumer audit.

**Dane/schema/config:** Adaptery/model ownership/testy; live model calls po zgodzie. Bez pobierania/usuwania modeli i strojenia systemu operacyjnego.

**Potrzebna zgoda:** Source i oddzielne okno live 9B/restart test. Produkcyjny restart wymaga R03.

**Rollback:** Poprzednie kompatybilne adaptery i konfiguracja; brak model delete.

**Poza zakresem:** Nowy model, wielomodelowy pipeline, wyłączanie embedding, migracja Linux, zwiększanie RAM/context bez projektu.

### R10 — Document Preparation/Intelligence i rzeczywiste formaty

**Typ:** FIX / VERIFY / COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R02, R06, R09

**Cel:** Nowy wspierany dokument sam przechodzi trwały proces i staje się materiałem użytecznym dla Asystenta.

**Odpowiedzialność za wymagania:** M-011, M-019, M-020, M-024, M-025, M-027, M-028, M-029, M-030, M-031, M-032, M-070, F-001.

**Pozostałe powiązania:** M-018, M-023, M-026, M-033, M-034, M-069, F-025. **Ustalenia:** FND-002, FND-003, FND-004, FND-019, FND-020, FND-021, FND-022, FND-024, FND-034.

**Zakres wykonania**

1. Sprawdzić validate → metadata → native/OCR → pages/assets → current intelligence → index z checksum/generation, lease, heartbeat, retry i idempotencją.
2. Ujednolicić obsługę PDF/Office/obrazów/EML/ZIP; ODP/ODS i XLSX charts/shapes mają jawny kontrakt tekst/render/asset/limitation. Przy długich dokumentach dzielić pracę z checkpointami i kontrolą pełnego zakresu.
3. Rozróżnić READ, MATERIAL_READY, INTELLIGENCE_READY, INDEXED i SUFFICIENT_FOR_QUESTION. Sam processed/ready nie dowodzi gotowości odpowiedzi.
4. Najpierw syntetyczny end-to-end w izolacji. Następnie po odrębnej zgodzie mały zestaw allowlisted nowych dokumentów; sprawdzić, czy istniejący dispatcher potrafi wybrać tylko te ID. Jeżeli nie, nie włączać globalnej flagi „na próbę”.
5. 15 queued to snapshot audytu, nie autoryzacja ich drainu. Przed każdym krokiem odczytać aktualny stan; nie uruchamiać V1 auto-externalization.

**Sprawdzenia i dowody**

- Jeden dokument każdego zatwierdzonego typu i przypadki corrupt/no_text/unsupported/duplikat przechodzą realne moduły; żaden unsupported nie udaje sukcesu.
- Restart/fencing nie tworzą podwójnych artefaktów; superseded checksum nie jest podawany jako current; długi dokument ma jawne pokrycie.
- Kontrolowany nowy materiał uzyskuje accepted artifact bez ręcznego utworzenia AssistantRun i bez nieuprawnionych external calls.

**Warunek zamknięcia:** Proces istniejący działa dla zatwierdzonych formatów i ograniczeń. Aktywacja nowej pracy produkcyjnej dopiero po osobnym planie rollout/pause.

**Dane/schema/config:** Kod istniejącego pipeline; możliwe normalne zapisy jobów/artifacts w zatwierdzonym canary. Backfill i schema poza automatyczną zgodą.

**Potrzebna zgoda:** Source; oddzielnie production flag/canary IDs/Qdrant writes i zatrzymanie testu. Przed deploy R03.

**Rollback:** Pause dopuszczonego dispatchera/bezpieczna konfiguracja poprzednia; zachowanie oryginałów i audytu jobów, bez ręcznego kasowania rekordów.

**Poza zakresem:** Cała historia 5988 dokumentów, „enable i obserwuj wszystkie 15”, nowy równoległy pipeline i usuwanie ograniczeń safety.

### R11 — Punktowa naprawa historycznego Unicode

**Typ:** FIX_DATA / VERIFY · **Status:** patrz §0.2 · **Zależności:** R02, R03

**Cel:** Usunąć konkretną przeszkodę zapytań JSON bez przebudowy historycznych danych.

**Odpowiedzialność za wymagania:** M-023.

**Pozostałe powiązania:** F-001, F-033. **Ustalenia:** FND-019.

**Zakres wykonania**

1. Sprawdzić, czy Document 8903 nadal ma ten sam problem i preimage hash. Jeżeli został naprawiony poza roadmapą, zweryfikować efekt i nie wykonywać apply ponownie.
2. Użyć istniejącego deterministic projection/dry-run; pokazać zakres różnicy bez danych klienta. Brak zmian semantycznych poza usunięciem nieprawidłowej reprezentacji.
3. Po zgodzie na dokładnie wskazany rekord wykonać bounded apply, audyt oraz powtórzenie zapytań i recurrence tests. Oddzielić naprawę od globalnego cleanupu.

**Sprawdzenia i dowody**

- Pre/post hash, oczekiwany row count = 1 przy faktycznej naprawie; JSON operators i serializacja działają; ponowne uruchomienie idempotentne.
- Test tworzenia nowych metadanych nadal blokuje invalid surrogates i nie obcina prawidłowego Unicode.

**Warunek zamknięcia:** Błąd naprawiony lub potwierdzone wcześniejsze usunięcie; zachowany chroniony dowód i reversibility.

**Dane/schema/config:** Jedna jawna produkcyjna mutacja danych po zgodzie; bez schema migration i model reconstruction.

**Potrzebna zgoda:** Odrębna approval historycznej naprawy: dokładny ID, preimage, projection, limit i backup.

**Rollback:** Chroniony preimage oraz kontrolowana przywracająca procedura; nie przywracać uszkodzenia automatycznie do czynnego systemu.

**Poza zakresem:** Bulk SQL replace, cała tabela, usuwanie dokumentu lub naprawa przez model.

### R12 — Gmail, załączniki i dowodliwe dopasowania

**Typ:** FIX / VERIFY · **Status:** patrz §0.2 · **Zależności:** R02, R10

**Cel:** Przetworzony lokalnie załącznik trafia do właściwej sprawy lub review, a historia nie jest przepinana po cichu.

**Odpowiedzialność za wymagania:** M-018, M-021, F-009, F-010, F-011.

**Pozostałe powiązania:** F-005, F-033. **Ustalenia:** FND-003, FND-017, FND-018.

**Zakres wykonania**

1. Spiąć lokalny terminal z istniejącym bounded reconciliation oraz jego eligibility; nie wystarczy dopisać call-site, jeżeli wewnętrzna bramka nadal wymaga V1 Vision.
2. Sprawdzić exactly-once/idempotency, retry i konflikty certain/ambiguous/unresolved dla PDF/TXT oraz metadanych nadawcy.
3. Przygotować read-only mailbox ID/window comparison bez bodies, mark-read i zmian labels. Rozróżnić permission/window gap od braku wiadomości w DB.
4. Dla 4262 historycznych źródeł najpierw aktualny raport dry-run i conflict review. Nowe zachowanie matcher ≠ zgoda na masowy relink; apply tylko wskazanego batcha po osobnej zgodzie.

**Sprawdzenia i dowody**

- Local success przy vision_auto_eligible=false wywołuje drugi pass bez Vision; brak duplikatów i cross-client links.
- Niejednoznaczne pozostają do review; forced failure/retry nie nadpisuje ręcznej decyzji.
- Provider/DB comparison podaje wyraźne okno i kompletność; compose/send test używa stub/sandbox i potwierdzenia człowieka.

**Warunek zamknięcia:** Nowy przepływ przyjęcia i powiązania odebrany; historyczne rekordy mają rozstrzygniętą klasę lub jawny backlog zaakceptowany przez właściciela.

**Dane/schema/config:** Kod matcher/call-sites; normalne link writes i historyczny apply oddzielnie gated. Brak provider writes w audycie coverage.

**Potrzebna zgoda:** Source/deploy; provider read scope; osobne batch IDs i approval dla historycznych relacji.

**Rollback:** Revert call-site; odtworzenie konkretnych starych linków z provenance, nie masowy unlink.

**Poza zakresem:** Automatyczne uznanie confidence za zgodę na konflikt, full mailbox export, automatyczna wysyłka.

### R13 — Użyteczna, wersjonowana baza wiedzy

**Typ:** FIX / COMPLETE_REQUIREMENT / VERIFY · **Status:** patrz §0.2 · **Zależności:** R08, R09, R10

**Cel:** Asystent otrzymuje zasady, wzory i ograniczenia z zatwierdzonej KB, a nie sam spis tematów.

**Odpowiedzialność za wymagania:** M-041, M-056, F-018.

**Pozostałe powiązania:** M-002, M-026, M-036, M-037, M-054, M-060, F-020, F-025. **Ustalenia:** FND-009, FND-011, FND-012, FND-022, FND-030, FND-031.

**Zakres wykonania**

1. Rozstrzygnąć statusy current not_ready/failed/superseded; istniejące narzędzia admin process/review/index mają aktualne i jawne błędy.
2. Zdefiniować minimalny korpus dla fundamentów, gruntów, osiadań, posadzek i robót firmy na legalnych źródłach. Rejestr źródła zawiera wersję, datę dostępu, typ, URL/pochodzenie, licencję/uprawnienie i status review.
3. Dostarczyć kontrolowane pobieranie/odświeżanie zatwierdzonych źródeł internetowych z ograniczeniami i audytem; ręczny upload jest etapem przejściowym, nie pełną realizacją masterplanu §28.
4. Trzymać osobno fakty klienta, reguły KB i zewnętrzne publikacje. Nie nazywać tekstu aktualną normą bez jej identyfikacji; brak dostępu licencyjnego i nieaktualność są jawne.
5. Sprawdzić abstrakt vs treść: na pytanie analityczne deterministic topic inventory nie kończy się accepted analysis. Wymagana lokalna synteza i poprawne źródła.

**Sprawdzenia i dowody**

- Każdy zatwierdzony current item jest wyszukiwalny albo jawnie wyłączony z uzasadnieniem; zmiana wersji unieważnia stale artifact/index.
- Pytanie wymaga połączenia faktu sprawy z zasadą KB; ślad pokazuje fragment faktycznie podany 9B i twierdzenie oparte na nim.
- Brak normy/licencji/danych wywołuje właściwy MISSING/review, nie fikcyjny cytat; public-safe źródło internetowe przechodzi kontrolowany import z provenance.

**Warunek zamknięcia:** Zatwierdzony korpus i mechanizm świeżości działają; nie wystarcza liczba itemów ani sam indeks green.

**Dane/schema/config:** Istniejące KB/retrieval/źródła; Qdrant i corpus writes po zgodzie. Możliwa mała additive schema po projekcie, nie domyślne NO za wszelką cenę.

**Potrzebna zgoda:** Zatwierdzenie źródeł/licencji, zakresu kontrolowanego Internetu, danych i indeksacji; osobno migracja w razie potrzeby.

**Rollback:** Powrót do poprzedniej zatwierdzonej generacji; historyczne źródła zachowane, nie usuwać całej kolekcji.

**Poza zakresem:** General web agent bez ograniczeń, pozyskiwanie płatnych norm bez uprawnień, udawanie analizy przez opis zawartości.

### R14 — Archiwum i podobne realizacje

**Typ:** COMPLETE_REQUIREMENT / VERIFY · **Status:** patrz §0.2 · **Zależności:** R08, R10, R11, R12, R13

**Cel:** Znajdować porównywalne wykonane sprawy i wyjaśniać podobieństwa oraz różnice, a nie wyłącznie podobne słowa.

**Odpowiedzialność za wymagania:** M-034, M-035, M-037, M-038, M-044, F-020.

**Pozostałe powiązania:** M-011, M-036, M-060, M-071, F-001, F-004, F-011, F-018. **Ustalenia:** FND-002, FND-018, FND-022, FND-031.

**Zakres wykonania**

1. Opracować aktualny coverage report per format/status/generation: liczby document/page/asset/chunk/vector są różnymi jednostkami i nie wolno dzielić 57 wektorów przez 5988 dokumentów jako miary recall.
2. Po zatwierdzeniu reprezentatywnej próbki uruchamiać małe checkpointowane batch historycznych dokumentów z resume/pause, bez nadpisywania ręcznych powiązań.
3. Zbudować/dokończyć podobne realizacje na istniejącym retrieval: porównywane zjawisko, materiał, warunki, prace, wynik i ograniczenia; samo retrieval dokumentów nie zamyka biznesowego case similarity.
4. Dodać zaakceptowane scenariusze wyszukiwania opisów obrazów/uszkodzeń i porównania before/after. Image embeddings są osobnym punktem scope, nie pretekstem do lokalnego modelu Vision.

**Sprawdzenia i dowody**

- Gold set ma jawne relewantne i nierelewantne sprawy; wyniki wskazują prawidłowe klient/project/doc/page i różnice.
- Cross-client visibility odpowiada uprawnieniom; citation otwiera właściwą stronę/zdjęcie.
- Batch jest idempotentny i wznawialny; stare niewłączone materiały nie są przedstawiane jako przeszukane.

**Warunek zamknięcia:** Mierzalne, uzgodnione pokrycie i jakość podobnych realizacji, ze wskazaniem jakiej części archiwum faktycznie dotyczy odpowiedź.

**Dane/schema/config:** Nowe/odświeżone artefakty i indeksy w zatwierdzonych batchach. Brak relink bez osobnej zgody.

**Potrzebna zgoda:** Każdy historyczny batch/backfill ma osobny approval zakresu i limitu; mechanizm snapshot przed indeksem.

**Rollback:** Przywrócenie generacji i usunięcie wyłącznie własnych testowych/potwierdzonych punktów; nie rebuild wszystkiego w ciemno.

**Poza zakresem:** Full corpus drain na starcie, deklaracja pełnego archive search dla ograniczonego indeksu.

### R15 — Realne Visual i trudna analiza przez Temporary Chat

**Typ:** COMPLETE_REQUIREMENT / VERIFY · **Status:** patrz §0.2 · **Zależności:** R05, R06, R08, R09, R10, R13

**Cel:** Udowodnić pełną analizę z wiedzą i obrazem na obecnym zestawie, bez bezpośredniej publikacji zewnętrznej odpowiedzi.

**Odpowiedzialność za wymagania:** M-002, M-026, M-054, M-057, M-058, M-060, M-062, F-019.

**Pozostałe powiązania:** M-028, M-041, M-042, M-044, M-045, M-050, M-056, M-059, M-070, F-025. **Ustalenia:** FND-004, FND-005, FND-008, FND-011, FND-012, FND-013, FND-016, FND-035, FND-036.

**Zakres wykonania**

1. W kontrolowanej ścieżce syntetycznej wykonać material → visual need → approved raster → Temporary Chat → strict binding/validation → local Qwen synthesis.
2. Oddzielnie sprawdzić trudną analizę: najpierw 9B i deterministic gate, potem minimalny pakiet bez zbędnej tożsamości, wynik bound do job/target/evidence i lokalna kontrola merytoryczna.
3. Obserwować rzeczywisty temporary mode, AUTH_REQUIRED/UI_CHANGED, brak zwykłego-chat fallback, bounded retry/spool i izolację równoległych klientów. Nie obchodzić login/auth/protections.
4. Dla dokumentu >4 źródeł odebrać etapowanie ograniczonych porcji i końcową agregację zakresu. Gdy potrzebny następny etap, wykonać go lub jawnie zawęzić pytanie; nie oznaczać połowy dokumentu jako complete.
5. Zamrozić użyteczne zadania: analiza osiadania z materiału sprawy i KB, rysy na obrazie, różne hipotezy z brakującymi badaniami, odmowa wyliczenia przy brakach. Zachować przyjęte wcześniej progi i hard safety gates; rozszerzać zestaw, nie obniżać progów po wyniku.

**Sprawdzenia i dowody**

- Pozytywny public-safe Visual i realna trudna analiza kończą się poprawnym lokalnym wynikiem; privacy/wrong-source/target-binding negative dają zero fałszywej akceptacji.
- Sam summary/overview nie liczy się jako wykonanie zadania analitycznego; każda hipoteza ma status i podstawę, brak danych nie jest zastępowany fantazją.
- Eskalacja pozostaje wyjątkową, kontrolowaną ścieżką; wynik zewnętrzny nie wykonuje biznesowych zapisów ani indeksacji.

**Warunek zamknięcia:** Obie ścieżki Temporary Chat mają dzisiejszy evidence i wersję workerów; poprawność, użyteczność i bezpieczeństwo odebrane razem.

**Dane/schema/config:** Syntetyczne external/model jobs i lokalne wyniki w wyznaczonym środowisku; produkcyjne kolejki nadal bez drainu.

**Potrzebna zgoda:** Odrębna zgoda na exact synthetic external smoke i ewentualny testowy session setup; po privacy R05.

**Rollback:** Zatrzymanie własnych testów, bezpieczna blokada niedopuszczonej eskalacji; zachowanie audytu i brak zwykłego-chat fallback.

**Poza zakresem:** Test na realnych danych klientów bez klasyfikacji, ocena pipeline tylko po JSON, zastąpienie tempchat API.

### R16 — Odbiór aplikacji: emulator, Windows i Web

**Typ:** VERIFY / FIX · **Status:** patrz §0.2 · **Zależności:** R04, R06, R07, R08, R09, R10, R12, R15

**Cel:** Uzyskać pierwszą realnie używalną wersję CRM + AI bez czekania na wszystkie późniejsze moduły.

**Odpowiedzialność za wymagania:** M-015, M-045, M-064, F-024, F-025.

**Pozostałe powiązania:** M-001, M-010, M-012, M-022, M-043, M-048, M-049, M-057, M-073, F-035. **Ustalenia:** FND-006, FND-007, FND-014, FND-015, FND-016, FND-029, FND-036.

**Zakres wykonania**

1. Użyć istniejącego AVD Pixel_8: uruchomić po sprawdzeniu zasobów, nie żądać telefonu, nie wipe/reinstall dla wygody. Połączyć z bezpiecznym backendem syntetycznym.
2. Najpierw sprawdzić zainstalowaną wersję i kompatybilność. Nowy candidate APK tylko po osobnej zgodzie, zachowując certyfikat i dane. Test starego APK nie potwierdza nowego UI.
3. Przejść login/expiry, Client 360, upload/source viewer, chat, tło, powrót, przerwanie sieci, rename/delete/cancel, wielokrotne finalizacje i wiadomości błędu.
4. Odebrać analogiczny zakres na Windows/Web z tego samego RELEASE_ID; dotyk/układ/loading/back/deep links, role i brak rzeczywistych wysyłek.
5. W emulatorze udowodnić kontrakt aparatu/foreground GPS z symulowanym wejściem; nie nazywać tego pomiarem dokładności fizycznego GPS/aparatu.

**Sprawdzenia i dowody**

- Operator wykonuje syntetyczną sprawę od kliknięcia do zapisanej odpowiedzi z prawidłowym źródłem i wraca do niej po zamknięciu klienta.
- Background nie anuluje; cancel jest jawny; usunięta rozmowa nie pojawia się ponownie; utrata sieci nie dubluje runu.
- Każdy wspierany target ma zidentyfikowany build i zaakceptowany krytyczny przepływ.

**Warunek zamknięcia:** Kamień K1: działający CRM + analityczny Asystent, gotowy do osobnego kontrolowanego wydania, mimo nadal otwartych ofert/umów/metod. Nie oznaczać pełnego Masterplan PASS.

**Dane/schema/config:** Testy runtime i ewentualne małe UX fixes. Brak automatycznej publikacji lub kasowania AVD.

**Potrzebna zgoda:** Okno emulatora/modeli/tempchat oraz osobno candidate install/release; before production deploy R03.

**Rollback:** Zachowany build/aplikacja/dane i kompatybilny backend; nie downgrade niekompatybilnego schema w ciemno.

**Poza zakresem:** Wymóg fizycznego telefonu, mylenie 341 testów Flutter z E2E, końcowy globalny redesign UI.

### R17 — Zweryfikowane metody techniczne i obliczenia

**Typ:** COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R09, R13, R15

**Cel:** Dostarczyć realne narzędzia techniczne, nie jedynie dowolny kalkulator wzorów.

**Odpowiedzialność za wymagania:** M-055.

**Pozostałe powiązania:** M-005, M-026, M-054, M-056, M-061, M-071. **Ustalenia:** FND-010, FND-030.

**Zakres wykonania**

1. Uzgodnić rejestr metod masterplanu: parametry gruntów/CPT/sondowania, nośność, osiadania, obciążenia, fundamenty, posadzki i elementy konstrukcyjne. Każda rodzina ma osobny mały podpakiet R17.x.
2. Wykorzystać istniejący deterministic calculation engine. Dla metody zapisać wersję, wiarygodne źródło/wzór, zakres stosowalności, jednostki, wymagane dane, założenia, wyniki pośrednie i końcowe, autor/date/status weryfikacji.
3. Qwen dobiera metodę i wyjaśnia; nie generuje kluczowej wartości rachunku jako tekstowej odpowiedzi bez wykonania narzędzia.
4. Dodać trwały artefakt obliczenia związany ze sprawą i wejściami, jeżeli obecny model tego nie zapewnia. Migracja tylko po projekcie i approval.
5. Odbiór poprawności dziedzinowej wymaga uzgodnionych przykładów referencyjnych oraz kompetentnej weryfikacji; wynik AI nie staje się końcową ekspertyzą bez człowieka.

**Sprawdzenia i dowody**

- Każda metoda: co najmniej przypadek referencyjny z udokumentowaną tolerancją, konwersja jednostek, wartości graniczne, brak danych i wejście poza stosowalnością.
- Brak danych prowadzi do jasnej odmowy wyliczenia lub oznaczonej estymacji tylko wtedy, gdy kontrakt ją dopuszcza; brak wymyślonych parametrów gruntu.
- Re-run tej samej metody/wersji/inputs daje ten sam wynik i historię; zmiana danych tworzy nową wersję.

**Warunek zamknięcia:** Rejestr metod rozstrzygnięty: wymagane metody zwalidowane; pozostałe jawnie odroczone decyzją scope i nie liczone do pełnej realizacji. Funkcje nie są zamykane samym green engine test.

**Dane/schema/config:** Metody, API/UI artefaktu, możliwa additive migration i dane testowe. Finalne obliczenia wymagają human review.

**Potrzebna zgoda:** Lista metod/źródeł i odbioru technicznego, source, migration, rollout oddzielnie.

**Rollback:** Wyłączenie wadliwej wersji metody; stare artefakty zachowane z oznaczeniem, bez przepisywania historycznych wyników.

**Poza zakresem:** Nowy framework obliczeń bez potrzeby, arbitralne jednostki, uznanie sztucznego przykładu za zatwierdzoną normę.

### R18 — Oferty jako wersjonowany obieg

**Typ:** COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R13, R16

**Cel:** Przygotować ofertę ze sprawy i firmowych reguł, z pełną kontrolą wersji i akceptacji.

**Odpowiedzialność za wymagania:** M-013, M-051, M-052.

**Pozostałe powiązania:** M-001, M-005, M-017, M-055, M-061, M-063, M-071. **Ustalenia:** FND-001.

**Zakres wykonania**

1. Najpierw zatwierdzić minimalny model danych: oferta, wersja, status, pozycje/zakres, źródła, firma/klient, założenia, ceny/reguły, termin i approval. Nie dopisywać ERP.
2. Zaimplementować jeden pionowy slice istniejącego backend/Flutter: draft → AI prepared/review → approved → sent/rejected/superseded, z autoryzacją i audytem.
3. Powiązać draft z wybranymi dokumentami, analizą, historycznymi ofertami i szablonem. AI nie wymyśla stawek, ilości ani decyzji handlowych; brak jest jawny.
4. Eksport czytelnego dokumentu i porównanie wersji; wygenerowany przez AI draft jest oznaczony. Edycja zatwierdzonej wersji tworzy rewizję i wymaga ponownej akceptacji.
5. Integracja z istniejącym compose/send wymaga osobnej akceptacji dokładnej wersji i adresata. Approval dokumentu nie jest automatyczną zgodą na wysłanie.

**Sprawdzenia i dowody**

- Syntetyczna sprawa → draft → poprawka → approve/reject → nowa rewizja → eksport; źródła i historia nie giną.
- Stare approval nie obejmuje nowszej treści; konflikt równoczesnej edycji wykrywany; obcy user/klient nie otrzymuje dostępu.
- Wysłanie jest testowane na sandbox/stub z jawnym potwierdzeniem, bez realnej korespondencji.

**Warunek zamknięcia:** M-013/M-051/M-052 mają działające encje, API/UI i odbiór właściciela; sam wygenerowany tekst nie wystarcza.

**Dane/schema/config:** Oczekiwana migration danych domeny po design/isolated upgrade/downgrade/report/approval; brak auto wysyłki.

**Potrzebna zgoda:** Model domeny i reguły firmy; osobno schema, source, deploy i wysyłka.

**Rollback:** Feature disable lub zgodna poprawka forward; nie kasować zatwierdzonych ofert ani ich historii.

**Poza zakresem:** Podpis elektroniczny, ERP/księgowość bez wymagania, automatyczne ustalanie cen z wyobraźni modelu.

### R19 — Umowy z zaakceptowanej oferty

**Typ:** COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R18

**Cel:** Wersjonowana umowa dziedziczy właściwe, zatwierdzone warunki zamiast bazować na zmiennym szkicu.

**Odpowiedzialność za wymagania:** M-014, M-053.

**Pozostałe powiązania:** M-001, M-005, M-017, M-061, M-063, M-071. **Ustalenia:** FND-001.

**Zakres wykonania**

1. Zaprojektować minimalny trwały obiekt umowy/wersji powiązany z konkretną approved offer version i zatwierdzonym szablonem.
2. Mapować zakres, cenę, adres, terminy, firmę i uzgodnienia; brakujące dane wymagają uzupełnienia. AI nie dopisuje niezleconych zobowiązań.
3. Obsłużyć draft/review/approved/superseded, diff wersji, historię, eksport i kontrolę dostępu.
4. Zmiana oferty po utworzeniu umowy nie aktualizuje po cichu zaakceptowanego dokumentu; pokaż niezgodność i wymuś nową decyzję.
5. Finalne użycie/wysłanie wymaga odrębnego potwierdzenia człowieka i właściwej wersji.

**Sprawdzenia i dowody**

- Offer v1 approved → contract draft v1 → review → approve; offer v2 nie mutuje starej umowy.
- Brak akceptacji oferty lub danych blokuje finalizację; zmiana szablonu zachowuje historyczną wersję.
- Eksport zgadza się z zaakceptowanymi polami; brak nieuprawnionej wysyłki.

**Warunek zamknięcia:** M-014/M-053 i końcowa część §42 działają w UI ze źródłem warunków i pełnym audytem.

**Dane/schema/config:** Oczekiwana additive migration i szablony po zatwierdzeniu; bez automatycznych działań prawnych/finansowych.

**Potrzebna zgoda:** Zatwierdzenie szablonów/warunków przez właściciela; osobno migracja, source, deploy i użycie finalne.

**Rollback:** Zachowanie poprzedniej kompatybilnej wersji i wszystkich zaakceptowanych dokumentów; forward correction zamiast destructive downgrade.

**Poza zakresem:** Swobodne generowanie finalnych postanowień jako porady prawnej, podpis/wysłanie bez zgody.

### R20 — Domknięcie CRM, pracy terenowej i uprawnień

**Typ:** VERIFY / FIX / COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R16, R18, R19

**Cel:** Zachować działający CRM i domknąć jego rolę jako miejsca całej historii sprawy.

**Odpowiedzialność za wymagania:** M-005, M-006, M-007, M-008, M-009, M-010, M-016, M-017, M-022, M-069, F-002, F-003, F-004, F-005, F-006, F-007, F-008, F-012, F-013, F-014, F-015, F-029, F-035.

**Pozostałe powiązania:** M-001, M-015, M-018, M-038, M-043, M-047, M-061, M-063, M-064, M-071, F-009, F-022. **Ustalenia:** brak odrębnego FND; wymagania kanoniczne.

**Zakres wykonania**

1. Odebrać Client 360, statusy/daty, global search, Candidate preview/merge, activity/change history, mail, dashboard, calendar/tasks/notes, inspections i Trash.
2. Nie otwierać na nowo wyboru A/B ContactPerson: followup dokumentuje B i migrację z 22.08.2026. Zweryfikować rzeczywiste działanie preferred/multiple decision-makers/generic coordinates/cross-client guard/archive.
3. Sprawdzić upload folder/multi-file/drag-drop, przypinanie/odpinanie/przenoszenie dokumentów z kontrolą, mapę/foreground GPS/EXIF/orientation/device metadata w zakresie masterplanu.
4. Dostarczyć brakujące drafts notatki/zadania/e-maila/raportu oraz porównanie dokumentów, jeżeli obecne wejścia ich nie realizują. Zapis narzędziowy tylko allowlisted i z wymaganym approval; bez dowolnego shell/SQL.
5. Rozstrzygnąć powiązanie finansowych dokumentów potrzebnych sprawie w istniejącym archiwum; nie zakładać budowy pełnej księgowości.

**Sprawdzenia i dowody**

- Właściciel wykonuje kompletną syntetyczną sprawę z dokumentami, osobami, zadaniem, wizją, ofertą i umową; historia i deep links są spójne.
- Role mają negatywne testy działań; optimistic conflict, merge review, Trash restore/purge tylko w izolacji i zgodnie z polityką.
- UI zachowuje stany loading/error/empty/offline/back i brak N+1 w krytycznych listach.

**Warunek zamknięcia:** Istniejące DEMONSTRATED pozostają objęte regresją, braki mają małe zakończone slice, a nie nową implementację CRM.

**Dane/schema/config:** Najpierw verification, minimalne fixes; możliwe potrzebne uzupełnienia schema po projekcie. Production business actions nie wchodzą do automatycznych testów.

**Potrzebna zgoda:** Source; osobno nowe tool write authority, schema i deploy. Bez powtórnej decyzji o już przyjętym ContactPerson B.

**Rollback:** Poprzedni kompatybilny build/feature switch; nie odwracać historycznych powiązań klientów globalnie.

**Poza zakresem:** Przebudowa całego CRM, nowe nieograniczone Agent write tools, testy realnego purge/send.

### R21 — Zakres CAD i pozostałych możliwości docelowych

**Typ:** OWNER_DECISION / COMPLETE_REQUIREMENT · **Status:** patrz §0.2 · **Zależności:** R10, R16

**Cel:** Nie udawać wsparcia całej dokumentacji technicznej i nie rozszerzać projektu bez końca.

**Odpowiedzialność za wymagania:** pakiet przygotowawczy/przekrojowy; powiązania poniżej.

**Pozostałe powiązania:** M-019, M-028, M-044, M-063. **Ustalenia:** FND-020, FND-021.

**Zakres wykonania**

1. Właściciel na początku planu rozstrzyga docelową macierz: DWG i ewentualnie DXF/IFC/DGN, multimedia, porównania obrazów, image embeddings, opcjonalny iOS i przyszłe Agent actions.
2. Dla potrzebnego CAD preferować istniejący bezpieczny renderer/converter/preview zamiast własnego CAD engine. Uwzględnić licencję, brak zewnętrznego wysyłania oryginałów, jednostki/skale/warstwy/odwołania.
3. Wspierane funkcje wykonać jako oddzielne małe R21.x z representative fixture. Jawny unsupported jest bezpiecznym stanem pilota, ale nie dowodem realizacji przyjętego wymagania CAD.
4. Image embeddings nie są zmianą modelu rozumującego 9B, ale wymagają oddzielnego zatwierdzenia zakresu, zasobów i indeksu. Do tego czasu wyszukiwanie obrazów może używać zatwierdzonych opisów Visual z jawnym ograniczeniem.
5. Odraczane możliwości pozostają w rejestrze ze źródłem, uzasadnieniem i decyzją; nie znikają, by podnieść procent ukończenia.

**Sprawdzenia i dowody**

- Każdy wybrany format ma osobno status metadata/text/render/Visual/index i bounded safety tests; rysunek ma identyfikowalny widok/skalę.
- Nieobsługiwany plik zachowuje oryginał i informację użytkownika, nie tworzy fikcyjnego success.
- Wszystkie wymagania/aspiracje masterplanu są powiązane lub jawnie odroczone przez właściciela.

**Warunek zamknięcia:** Zatwierdzony zakres kompatybilności zrealizowany i odebrany. Nierozstrzygnięta decyzja nie blokuje K1, ale blokuje twierdzenie o pełnej zgodności z danym wymaganiem.

**Dane/schema/config:** Możliwy nowy kontrolowany dependency lub additive metadata/schema po projekcie; żadnych samowolnych instalacji.

**Potrzebna zgoda:** Wybór zakresu i licencji; osobno dependency/security review, schema oraz deploy.

**Rollback:** Wyłączenie adaptera i pozostawienie explicit unsupported; zachowanie oryginałów i provenance.

**Poza zakresem:** Własny silnik CAD, nieograniczone web/Agent, iOS jako narzucony blocker mimo opcjonalności.

### R22 — Operacje, alerty i retencja

**Typ:** COMPLETE_REQUIREMENT / VERIFY · **Status:** patrz §0.2 · **Zależności:** R03, R04, R09, R16

**Cel:** Wykrywać awarie i chronić odtwarzalność bez automatycznego kasowania danych dla samego „porządku”.

**Odpowiedzialność za wymagania:** M-068, F-016, F-022, F-027, F-028.

**Pozostałe powiązania:** M-003, M-004, M-062, M-066, M-069, F-015. **Ustalenia:** FND-015, FND-024, FND-025.

**Zakres wykonania**

1. Domknąć backup stale/failure, disk low, DB down, Vision AUTH/UI_CHANGED, orphan job, schema mismatch i n8n down. Wybrany zewnętrzny kanał alertów wymaga osobnej zgody.
2. Zweryfikować aktualne schedule/UI i dry-run polityki E/F: próg 10%, cel 12%, wiek 60/14 dni i priorytety kopii zgodnie z zatwierdzoną decyzją. Przypisanie wieku do celu potwierdzić z rzeczywistym planem, nie odgadywać z samych liczb.
3. Retencja usuwa wyłącznie zarządzane, kwalifikujące się kopie, zachowując punkt odzyskania; stan z audytu auto_delete=false nie jest błędem do samowolnego przełączenia.
4. Audytować i uzgodnić n8n execution retention, log/audit policy oraz security-header compatibility; brak cleanup przed właściwym approval.
5. Powtórzyć potrzebne granice auth/rate/CORS/debug/secrets i admission backup/OCR/model na aktualnym zestawie.

**Sprawdzenia i dowody**

- Fault injection w izolacji wywołuje właściwy alert bez ujawnienia sekretów; przejściowy błąd nie powoduje nieograniczonych powiadomień.
- Dry-run retention daje dokładny manifest plików/rozmiarów/przyczyn i zachowanych kopii; apply tylko po osobnej zgodzie.
- Operacje nie blokują hot-path UI i mają jawny status, historię oraz możliwość bezpiecznego pause.

**Warunek zamknięcia:** Operacje wymagane w followup odebrane; wyłączona retencja jest akceptowana wyłącznie jako jawna decyzja właściciela, a nie ukryte COMPLETE.

**Dane/schema/config:** Konfiguracja/alerty; destructive retention i n8n purge oddzielnie gated, niezależnie od source PASS.

**Potrzebna zgoda:** Zachować istniejące FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED i FOLLOWUP_N8N_RETENTION_APPROVAL_REQUIRED; kanał zewnętrzny osobno.

**Rollback:** Wycofanie konfiguracji; skasowany backup nie ma automatycznego rollbacku — przed deletion wymagany zachowany restore chain i świadoma zgoda.

**Poza zakresem:** Docker prune, kasowanie kopii niezarządzanych, retencja traktowana jako bezpiecznie odwracalna.

### R23 — Odbiór §42 i kontrolowane wydanie systemu

**Typ:** VERIFY / RELEASE · **Status:** patrz §0.2 · **Zależności:** R03, R04, R11, R12, R13, R14, R16, R17, R18, R19, R20, R21, R22

**Cel:** Udowodnić działanie całego uzgodnionego produktu jako narzędzia pracy właściciela.

**Odpowiedzialność za wymagania:** M-001, M-061, M-071, M-073.

**Pozostałe powiązania:** M-067, F-026, F-035. **Ustalenia:** FND-001, FND-026.

**Zakres wykonania**

1. Zrealizować workflow §42: klient → lokalizacja/wizja/zdjęcia → dokumenty → intelligence/index → analiza z KB/Visual → podobne realizacje → obliczenie → oferta approved → umowa approved → historia.
2. Zamrozić release manifest i wykonać właściwe pełne regresje oraz aktualny restore drill dla tego schema/artefaktów. Stary restore PASS nie pokrywa automatycznie nowych ofert/umów.
3. Rozstrzygnąć każdy z 108 wpisów oraz dodatkowe podkryteria: ACCEPTED albo jawna podpisana decyzja scope. NOT_VERIFIED/OWNER_DECISION nie są ukrytym PASS.
4. Promocja source, deploy, migracja, aktualizacja aplikacji i praca na prawdziwych danych mają oddzielne zgody i log. Nie promować całego rescue dlatego, że jeden podpakiet przeszedł.
5. Wykonać ograniczony canary prawdziwej pracy po zgodzie i monitoring; progi czasowe/zasobowe z pomiarów, nie fikcyjne terminy zakończenia.

**Sprawdzenia i dowody**

- Przepływ biznesowy daje poprawne artefakty, źródła i wersje; człowiek zatwierdza wyniki wysokiego ryzyka.
- Brak otwartego P0 i potwierdzonego krytycznego błędu poprawności w wydawanym zakresie; niepewne materiały fail-closed bez niszczenia użyteczności pozytywnych przypadków.
- Aktualny stable i wspierane klienty działają; release/rollback i restore są odtwarzalne.

**Warunek zamknięcia:** Kamień K2: odebrany zakres operacyjny. „Pełny Masterplan” wolno napisać tylko przy spełnieniu wszystkich wymaganych pozycji albo z jawnym opisem zatwierdzonej zmiany specyfikacji.

**Dane/schema/config:** Wydanie i normalne operacje po zgodzie; migracje wyłącznie przygotowane w wcześniejszych pakietach.

**Potrzebna zgoda:** Osobny release/migration/deploy/canary approval i odbiór właściciela. Nie konsumuje approval final cleanup.

**Rollback:** Poprzedni release tylko gdy schema compatible; inaczej bezpieczny forward fix/feature disable lub zatwierdzone odtworzenie. Nie utracić nowych danych.

**Poza zakresem:** Kolejny pełny redesign, masowe historyczne apply jako test, ogłoszenie sukcesu samym licznikiem testów.

### R24 — Końcowe sprzątanie bez utraty funkcji

**Typ:** FINAL_CLEANUP · **Status:** patrz §0.2 · **Zależności:** R23

**Cel:** Usunąć zbędne pozostałości dopiero po kontroli zależności i odbiorze ich zastępstw.

**Odpowiedzialność za wymagania:** F-030, F-031, F-032, F-033.

**Pozostałe powiązania:** M-003, M-061, M-072, M-073, F-015, F-019. **Ustalenia:** FND-018, FND-029, FND-032, FND-035.

**Zakres wykonania**

1. Przejść 61 kandydatów RETIREMENT_EXECUTION_MAP.csv po dokładnych ścieżkach. Trzy roadmapy rozstrzygnięte już w R01; nie usuwać ich drugi raz.
2. 51 ARCHIVE_EVIDENCE zachować w Git lub nieinstrukcyjnym archiwum z datą/commit/provenance; nie zmieniać historycznych wyników w aktualne polecenia. Sprawdzić czy nie są potrzebne runbookom/restore.
3. Cztery REMOVE_CANDIDATE: pusty blueprint, dwie kopie .before_rfc822 i wycofany runner. Warunek usunięcia osobny dla każdego: aktualny consumer audit, hash, bezpieczna kopia, exact-path approval.
4. Live Web oraz external worker pozostają KEEP_RUNTIME aż do odebranego zastąpienia R04/R15/R16; C:\Ollama-Vision-Pilot pozostaje HOLD do wyjaśnienia launcherów. PostgreSQL:10 nie należy do AI-Lab bez dowodu — nie stop/delete.
5. 16 advanced_queued: najpierw provenance i dowód inert, poprawna prezentacja stanu. Ewentualne terminalization/archive tylko existing service + zatwierdzone ID; nie DELETE dla upiększenia kolejki.
6. Modele stare usuwać wyłącznie po R09 consumer/rollback proof. qwen3.5:9b i aktywny embedding są chronione mimo historycznej listy cleanup. Resztę danych historycznych oraz storage orphans tylko dry-run → approval → bounded apply.

**Sprawdzenia i dowody**

- Pre/post exact manifests, link/import/build/runtime smoke oraz cały krytyczny §42 smoke po sprzątaniu; żadnej utraty danych lub niezaplanowanego restartu.
- Nie ma aktywnych instrukcji konkurencyjnych; każdy usunięty plik ma dowód braku konsumentów i realny recovery dla właściwego typu.
- Unknown nie zmienia się automatycznie w delete; potrzeby innych systemów są zachowane.

**Warunek zamknięcia:** Kamień K3: porządek i odbiór po cleanup. Rejestr ma finalny werdykt dla wszystkich kandydatów: usunięto/archiwum/zachowano/pozostaje jawny HOLD z właścicielem.

**Dane/schema/config:** Exact-path usuwanie/archiwizacja oraz ewentualne bounded data cleanup oddzielnie autoryzowane; brak ogólnego prune.

**Potrzebna zgoda:** Osobne zgody FOLLOWUP_STORAGE_CLEANUP_APPROVAL_REQUIRED, FOLLOWUP_OLD_MODEL_CLEANUP_APPROVAL_REQUIRED, FOLLOWUP_HISTORICAL_DATA_CLEANUP_APPROVAL_REQUIRED zgodnie z zakresem; nie dotyczą chronionego 9B.

**Rollback:** Tracked: commit+path; untracked/outside: niezależna zweryfikowana kopia; dane: chroniony preimage/backup. Irreversible retention jawnie oznaczona.

**Poza zakresem:** Wildcard delete, git clean/reset, modele 9B/embedding, migracje/lockfile/licencje/regresje, live builds/workers przed zastąpieniem, obcy PostgreSQL.

## 8. Dokładne zasady wycofania plików

### Wczesne wycofanie instrukcji — R01

R01 wycofało z aktywnego drzewa dokładnie:

```
CODEX_MASTER_EXECUTION.md
FOLLOWUP_PRECHUNK23_FULL_SYSTEM_ROADMAP.md
frontend/POST_BATCH_AUTH_REMOTE_PLAN.md
```

Aktywne odwołania w `AGENTS.md`, obu kanonicznych planach, recovery README i
dokumentacji domenowej zostały zaktualizowane. Nadal ważne wymagania, bramki i
provenance są zmapowane w `docs/recovery/AUDIT_RECONCILIATION.md`; dokładne
bajty pozostają odtwarzalne z zaakceptowanego punktu
`9af4026eeffed2509af943bff1e37b2514bfd5e8`. Wzmianki w karcie R01,
rejestrze retirement, roadmapie i historycznym promptcie/audycie są dowodem
zakresu, nie aktywną instrukcją wznowienia starego planu.

### Cztery kandydatury do późniejszego usunięcia — R24

```
docs/ai-lab-blueprint.md
backend/app/services/document_extraction_service.py.before_rfc822
backend/app/services/document_metadata_service.py.before_rfc822
C:\ai-lab-core-staging\document-pipeline-runner\run-after-codex-exit.ps1
```

To kandydaci, nie polecenie `rm`. Runner wymaga sprawdzenia harmonogramów/procesów. Kopie `.before_rfc822` są poza Git, więc muszą mieć osobny recovery przed usunięciem. Pusty blueprint nadal wymaga kontroli linków. Każda pozycja ma indywidualne warunki w `docs/recovery/RETIREMENT_EXECUTION_MAP.csv`.

### Co chronimy

Live `frontend/build/web` i `C:\ChatGPT-Vision-Worker\worker\vision-job.js` do czasu odebranego zastąpienia; nieznany `C:\Ollama-Vision-Pilot` do rozstrzygnięcia konsumentów; obcy PostgreSQL do ustalenia właściciela. Ponadto masterplan, followup, 9B, embedding, migracje, lockfile, licencje, potrzebne testy, sekrety, dane i kopie odtworzeniowe.

51 historycznych dowodów ma kwalifikację ARCHIVE_EVIDENCE, nie automatyczny delete. Git zachowa tylko treść śledzoną; nie odzyska untracked, zewnętrznych workerów, danych i sekretów.

## 9. Kryteria merytoryczne odpowiedzi

Odbiór Asystenta i modułu technicznego sprawdza konkretny wynik pracy:

- **Fakt:** pochodzi z dopuszczonego materiału sprawy; źródło istnieje i zostało rzeczywiście dostarczone modelowi.
- **Reguła:** wynika z identyfikowalnej wiedzy/metody, z zakresem stosowalności i wersją.
- **Wniosek lub hipoteza:** łączy właściwe fakty z regułą; nie ukrywa niepewności.
- **Brak:** wskazuje, czego konkretnie brakuje i jak to wpływa na odpowiedź; brak danych nie jest automatycznie „model za słaby”.
- **Rachunek:** wykonany przez narzędzie, zapisany i odtwarzalny; nie tekstowa fikcja.
- **Akcja:** draft/odczyt zgodny z uprawnieniami; istotny zapis lub użycie finalne ma właściwe approval.

Do minimum należą pozytywne analizy, przypadki wymagające KB, obrazu i eskalacji, pytania mieszane, brak danych, sprzeczne źródła, zły scope, niegotowy dokument i błędy transportu. Poprawny JSON, wysoka długość odpowiedzi i brak crasha nie są wystarczające. Zachować wcześniejsze zatwierdzone progi jakości; każda zmiana kryterium wymaga jawnego uzasadnienia przed kolejną oceną.

## 10. Załączniki i aktualizacja statusów

- `docs/recovery/PACKAGE_REGISTER.csv` / `docs/recovery/PACKAGE_DETAILS.json` — techniczny indeks kart z tego pliku.
- `docs/recovery/REQUIREMENT_PACKAGE_MAP.csv` — wszystkie 108 wierszy oryginalnej macierzy, oryginalne cztery statusy i dodatkowe mapowanie/korekty.
- `docs/recovery/FINDING_PACKAGE_MAP.csv` — wszystkie 36 FND, bez wymazywania pierwotnego stopnia dowodu.
- `docs/recovery/RETIREMENT_EXECUTION_MAP.csv` — wszystkie 61 kandydatur z indywidualnymi warunkami wejściowymi.
- `docs/recovery/SCOPE_DETAIL_CHECKLIST.csv` — 16 grup podkryteriów szerokich wymagań.
- `docs/recovery/OWNER_DECISIONS.csv` — scope/operacje, z rozróżnieniem już podjętej decyzji ContactPerson.
- `docs/recovery/AUDIT_RECONCILIATION.md` — korekty planistyczne i ograniczenia dowodów.
- `docs/recovery/VALIDATION.json` — kontrola kompletności mapowania i grafu zależności; nie testy aplikacji.
- `input_only/evidence/NEXT_STABIL_FULL_AUDIT_20260907.zip` — oryginalne wejście w paczce przekazania; pozostaje poza repo. Git przechowuje jego hash i bezpieczne mapowania, nie raw audit ZIP.

Oryginalne statusy audytu są historyczne i pozostają stałe. Bieżący status pakietu jest autorytatywny w §0.2; checkpoint §0.1 opisuje dokładny podetap. Po zmianie statusu synchronizujemy wyłącznie pochodne pola indeksów w tym samym commicie, nie pierwotne oceny audytu. Każdy zamknięty pakiet wskazuje commit/release/evidence, a nie jedynie słowo PASS. Poprawka mapowania nie zmienia oryginalnego audytu.

## 11. Pierwsze zlecenie i wznowienie

**R00 v1.1 — opublikować wspólną roadmapę/checkpoint i zabezpieczyć punkt startu.**
Obowiązuje dostarczony `docs/recovery/prompts/R00_BASELINE.md` v1.1. Zastępuje prompt v1.0,
który zabraniał commit/push. Nie wolno wykonywać obu równolegle. Wykonane wcześniej
kroki starego R00 należy wykorzystać po kontroli aktualności, nie powtarzać audytu.

Gałąź docelowa to `recovery/next-stabil-repair-completion`, nie `main` i nie całe
rescue. Dokumentacyjny bootstrap jest odrębny od późniejszej integracji kodu.
R00 może wykonać jawny allowlist commit/push dokumentacji oraz małą zmianę AGENTS;
nie może usunąć roadmap, zmienić kodu aplikacji, konsumować R01–R24 ani uruchomić
produkcji. Stare roadmapy wycofujemy dopiero w R01 po osobnej zgodzie.

Krótki prompt wznowienia jest dostarczony jako `docs/recovery/prompts/RESUME.md`. Jego
zadaniem jest odczytać ten sam plik i stan z Git, a następnie wznowić wyłącznie
pozostały, wcześniej autoryzowany krok. Nie tworzy nowej roadmapy.

## 12. Źródła

Wymagania pochodzą wyłącznie z masterplanu/followup i aktualnych decyzji właściciela. Konkretne observed findings/runtime oraz indywidualne warunki plików pochodzą z otrzymanego ZIP wskazanego w §4. Odnośniki do pinned źródeł i dokładne wyjaśnienie rozbieżności znajdują się w `docs/recovery/AUDIT_RECONCILIATION.md`. Ten plan jest rekomendacją wykonawczą, nie fałszywym pomiarem uruchomionej instalacji.
