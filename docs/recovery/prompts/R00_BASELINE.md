# NEXT_STABIL_R00 v1.1 — wspólna roadmapa w Git + bezpieczny baseline

Wykonaj WYŁĄCZNIE R00 v1.1. Ten prompt ZASTĘPUJE wcześniejszy R00 v1.0,
który zabraniał commit/push. Nie wykonuj obu jednocześnie. Jeżeli stary R00
właśnie pracuje, nie uruchamiaj drugiego autora; doprowadź bieżący podetap do
bezpiecznej pauzy. Jeżeli zakończył baseline, wykorzystaj jego dowody po
sprawdzeniu aktualności i wykonaj brakującą publikację, bez nowego pełnego audytu.

## 1. Decyzja właściciela i granice

Właściciel chce mieć JEDNĄ roadmapę w lokalnym repo i na GitHub, dostępną
ChatGPT i Codexowi, stale aktualizowaną w toku pracy z punktem wznowienia.

Uruchomienie tego promptu autoryzuje:
- przygotowanie osobnego lokalnego worktree oraz wskazanej gałęzi;
- instalację dostarczonej roadmapy v1.1 i jawnego allowlist załączników;
- minimalną aktualizację wskazań AGENTS i reguł checkpointów;
- małe dokumentacyjne commit/push wyłącznie na
  `recovery/next-stabil-repair-completion`;
- odczyty i bezpieczne raporty R00 oraz zachowanie niesekretnej lokalnej pracy.

NIE autoryzuje zmian kodu aplikacji/config/DB, adopcji rescue, zmian main,
merge/rebase/cherry-pick, PR/release/tag, deploy, migracji, restartu,
uruchomienia modeli/Temporary Chat, drain kolejek, backfill, secrets/escrow,
instalacji APK, usuwania plików/roadmap ani wykonania R01–R24.

Ochrona danych i istniejące approval gates pozostają obowiązujące. Wskazanie
nowej roadmapy zastępuje starą kolejność wykonawczą, nie reguły bezpieczeństwa.
Qwen 9B, osobny embedding, KB i Temporary Chat dla Visual/analiz pozostają.

## 2. Wejście — nie generuj nowego planu

Repo: `domlap94-star/ai-lab-core`.
Oryginalny worktree historycznie: `C:\ai-lab-core` — sprawdź.
Nowy docelowy worktree: `C:\ai-lab-core-recovery` — tylko gdy bezpieczny/wolny.
Gałąź wspólna: `recovery/next-stabil-repair-completion`.

Z pakietu `NEXT_STABIL_ROADMAP_R00_V1_1_20260907.zip` przeczytaj:
- `README.md` — instrukcja paczki, NIE README do nadpisania w repo;
- `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md` v1.1, §0–§6 oraz karty R00/R01;
- `docs/recovery/AUDIT_RECONCILIATION.md` i `GOVERNANCE_CHANGE_V1_1.md`;
- rejestry z `docs/recovery/` oraz `PACKAGE_SHA256.csv`;
- `AGENTS_RECOVERY_BLOCK.md` — treść do kontrolowanej integracji, nie replacement AGENTS.

Sprawdź pliki paczki przed użyciem, hash i bezpieczne ścieżki ZIP, bez wykonywania
kodu z archiwów. Nie rozpakowuj całej paczki w ciemno do roboczego repo.
Roadmapę KOPIUJ z załącznika; nie odtwarzaj jej z pamięci ani streszczenia.
Jeśli brak wejścia, nie wymyślaj roadmapy: podaj konkretną brakującą ścieżkę.

Oryginalny audit ZIP jest w `input_only/evidence/` i ma SHA-256:
`B38CF3DA7CB2699C97891DBC64FE03B4770D1E86F7C90A5280D9A72AC15CF2F9`.
Katalog źródłowy audytu na komputerze:
`C:\ai-lab-core-staging\audits\NEXT_STABIL_FULL_AUDIT_20260907_20260907T161000Z`.

Snapshoty HISTORYCZNE — nie traktuj ich jako aktualnego odczytu:
- main: `483f9bf8b1a591ded8a42df5da87663c664ed5d4`;
- rescue `rescue/prechunk23-assistant-visual-v2-final-20260907`:
  `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`;
- oryginalny HEAD: `72950657ac79b50d0afe72753632ba4cde810b95`;
- dirty: 6 modified + 197 untracked, staged 0;
- mixed runtime i DB head: zgodnie z audytem, wymagają odczytu.

## 3. Krótki preflight — przed pierwszym zapisem

1. Odczytaj istniejące AGENTS, masterplan i followup oraz aktywne instrukcje
   objętych ścieżek. Ujawnij konflikty; ten prompt jawnie zmienia tylko wskaźnik
   planu oraz dopuszcza wymienione dokumentacyjne checkpointy w R00.
2. Zapisz status oryginalnego drzewa, staged diff, HEAD, branches/worktrees,
   remotes i istotnych aktywnych runnerów. Nie drukuj URL z credentialami ani
   pełnych command lines z tokenami. Nie kasuj i nie zatrzymuj procesów.
3. Ustal, czy inna sesja już publikuje lub pracuje na recovery. Jeden autor;
   nie wymyślaj drugiej gałęzi `...-final-v2`. Konflikt opisz i zatrzymaj zapis.
4. Sprawdź lokalne Git hooks oraz znane workflow CI/launchery reagujące na push.
   Nowy push dokumentów nie może wykonać deploymentu/produkcji. Nie obchodź
   hooków przez --no-verify, zmiany ustawień, wyłączanie CI lub tokeny skip.
   Niejasny/potwierdzony autodeploy: zachowaj pliki lokalnie i zgłoś konkretną
   blokadę publikacji, bez rozszerzania pracy do audytu wszystkich workflow.
5. Ustal actual origin/main i recovery przez bezpieczny odczyt remotes.
   Fetch jest dozwolony jako odświeżenie refs, bez pull, prune, rebase lub
   modyfikacji oryginalnego worktree. Zapisz bazowy pełny SHA.

## 4. Bezpieczny lokalny worktree i gałąź

Jeśli recovery jeszcze nie istnieje: utwórz gałąź od zweryfikowanego origin/main
oraz osobny worktree. `git worktree add -b ... <path> <verified_base_sha>` jest
w tym R00 dozwolonym, kontrolowanym wyjątkiem od zakazu checkout: NIE przełącza
ani nie czyści oryginalnego brudnego worktree. Nie twórz worktree nad istniejącym
katalogiem, backupem, rootem produkcyjnym albo niesprawdzoną ścieżką.

Jeśli istnieje: ustal jego własność, cleanliness, upstream, historię i brak
równoległego autora. Wznów zgodny stan bez reset/stash/force checkout. Jeśli
remote jest ahead lub rozbieżny, nie nadpisuj go; porównaj zmiany i zgłoś
konkretną bezpieczną synchronizację do decyzji. Przy całkowicie nowym lokalnym
worktree istniejącej gałęzi rozpocznij od jej potwierdzonego remote HEAD.

To lokalny worktree TEGO SAMEGO repo, nie druga implementacja ani niezależna
kopia roadmapy. Wszystkie dalsze zapisy R00 wykonuj jawnie w tym katalogu
(np. git -C <worktree>). Runtime nadal używa dotychczasowych ścieżek.

Baza main służy tylko rejestracji dokumentów. Nie oznacza odrzucenia rescue
ani dirty source: ich przyszłe adoptowanie pozostaje propozycją baseline.
Jeżeli zmienił się HEAD od audytu, zapisz drift; nie resetuj do starego SHA.

## 5. Bootstrap dokumentacji — opublikuj zanim wykonasz długi baseline

### Dokładny allowlist kopii do repo

1. Root: `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`.
2. `docs/recovery/README.md`.
3. `docs/recovery/AUDIT_RECONCILIATION.md`.
4. `docs/recovery/GOVERNANCE_CHANGE_V1_1.md`.
5. `docs/recovery/REQUIREMENT_PACKAGE_MAP.csv`.
6. `docs/recovery/FINDING_PACKAGE_MAP.csv`.
7. `docs/recovery/RETIREMENT_EXECUTION_MAP.csv`.
8. `docs/recovery/SCOPE_DETAIL_CHECKLIST.csv`.
9. `docs/recovery/OWNER_DECISIONS.csv`.
10. `docs/recovery/PACKAGE_REGISTER.csv`.
11. `docs/recovery/PACKAGE_DETAILS.json`.
12. `docs/recovery/SOURCE_ARCHIVE_MEMBER_HASHES.csv`.
13. `docs/recovery/VALIDATION.json` — oznaczone testy materiału wejściowego,
    nie testy aplikacji ani bieżący status odbioru.
14. Bieżący prompt do `docs/recovery/prompts/R00_BASELINE.md`.
15. Prompt `PROMPT_CODEX_RESUME.md` do `docs/recovery/prompts/RESUME.md`.
16. AGENTS: tylko ograniczona zmiana wskazania na nową roadmapę oraz treść
    bloku checkpointów opisanego w `AGENTS_RECOVERY_BLOCK.md`.
17. Nowe, małe zanonimizowane notatki tego wykonania pod dokładnie wskazanymi
    ścieżkami `docs/recovery/checkpoints/<UTC>-R00-<unique>.md`.

Nie kopiuj do Git: root README paczki, PACKAGE_SHA256.csv/hash paczki traktowanego
jako aktualny hash żyjących plików, input_only, oryginalnego audit ZIP, raw
logów/runtime manifestów, backupów, .env, cookies, keys, danych firmy,
kopii dirty code, binariów, model blobs i generowanych buildów. Nie nadpisuj
istniejących plików bez sprawdzenia ich pochodzenia i różnic.

Przed stagingiem przejrzyj planistyczne mapowania i notatki pod kątem danych
wrażliwych. Oryginalne bajty zostają w wejściu zewnętrznym; ewentualną konieczną
redakcję w kopii Git oznacz z zachowaniem ID. Nie traktuj samego regex scan
jako gwarancji braku sekretów. GitHub prywatny także nie jest vaultem.

### Minimalna korekta AGENTS

Zastąp starą wskazówkę `CODEX_MASTER_EXECUTION.md` nową roadmapą i followup.
Dodaj regułę odczytu §0 przed pracą, aktualizacji checkpointów i wznowienia.
Zachowaj pozostałe zabezpieczenia, w tym kompatybilność API i granicę gatewayów.
Wyjątek od zakazu generated reports obejmuje tylko bezpieczne mapowania planu
oraz krótkie checkpointy tego allowlistu. Wyjątek od „no failing commit” oznacza
commit dokumentacji opisującej FAIL/PAUSED, NIE commit niezaliczonej funkcji
jako gotowej. Nie zastępuj całego AGENTS plikiem z paczki.

Nie zmieniaj w R00 masterplanu/followup/README repo i nie usuwaj trzech starych
roadmap. Ich pełna konsolidacja ma zostać R01. Nowy wskaźnik AGENTS i bieżące
zlecenie identyfikują jedyne aktywne sterowanie mimo historycznych pozostałości.

### Pierwszy checkpoint i commit

Uzupełnij §0 z faktów: branch/worktree, checkpoint ID i UTC, lokalny baseline
SHA, executor, R00/BOOTSTRAP, następny krok, stan źródeł i brak przejęcia runtime.
Nie wpisuj zmyślonych PASS/ACCEPTED ani SHA własnego przyszłego commita.
R00 = IN_PROGRESS, wszystkie pozostałe PLANNED. Synchronizuj indeksy statusów
PACKAGE_REGISTER/DETAILS w tym samym commicie; historyczne statusy audytu stałe.

Sprawdź: staged allowlist, pełny diff, git diff --check, poprawność CSV/JSON,
108/36/61 mapowań, 25 pakietów, ID/zależności/linki i brak utraty tekstu R02–R24.
Nie uruchamiaj pełnych testów backendu/Flutter tylko dla bootstrapu dokumentów.

Wykonaj jawny dokumentacyjny commit i zwykły push wyłącznie na recovery.
Nie git add ., nie --force, nie --all/--mirror, nie main/tag/PR/release.
Sprawdź remote HEAD po push i odczytaj plik dla tego SHA. W raporcie roboczym
zanotuj ROADMAP_SYNCED@<pełny_SHA> albo uczciwie LOCAL_ONLY/REMOTE_UNVERIFIED.
Brak sieci nie pozwala ogłosić sukcesu; nie tworzy jednak potrzeby kasowania
lokalnych dokumentów. Można kontynuować bezpieczne odczyty baseline.

## 6. Baseline R00 — zachowaj pracę, bez powtarzania całego audytu

A. Integralność: sprawdź SHA/CRC 15 wpisów oryginalnego audit ZIP. Poszukaj
brakującego ARTIFACT_MANIFEST_SHA256.csv TYLKO w oryginalnym katalogu audytu;
porównaj bez nadpisywania. Nowy pomiar oznacz jako nowy. Brak logu oznacz
NOT_AVAILABLE; nie uruchamiaj pełnych suite/modeli dla odzyskania dawnego PASS.
Uwzględnij korekty C-001…C-008; ContactPerson B nie jest nową decyzją.
Spór KB+Visual to późniejszy test R02/R08 na rzeczywistym rescue.

B. Praca lokalna: manifest modified/untracked z bezpiecznymi hashami oraz
porównanie do audytu. Chroniona kopia niesekretnego kodu/testów/dokumentacji
poza repo i runtime, z odczytem/hashami i instrukcją recovery. Nie pakuj całego
brudnego katalogu, profili, spool, .env ani firmowych plików. Dane wrażliwe
pozostają w dotychczasowej chronionej procedurze z osobną zgodą.

C. Runtime: bounded read-only ustalenie actual backend/Web/app/gateway/
Supervisor/workers, hashy, źródła konfiguracji, DB head i istotnych flag.
Użyj znanych rootów i metadanych, nie skanuj dysku. Nie drukuj sekretów lub
danych klientów. DB wyłącznie krótkie READ ONLY z timeoutem. Endpoints przed
użyciem sprawdź pod kątem skutków. Nie restartuj, nie unloaduj modeli, nie
uruchamiaj ingestion/Temporary Chat/Gmail send/Qdrant writes/backup/restore.

D. Integracja: przedstaw odrębnie propozycję main + ocenione rescue + zachowana
lokalna praca. Nie merge/cherry-pick/promocja. 15 preparation queued ani 16
advanced_queued z audytu nie stanowi zgody na przetwarzanie/terminalizację.

Zewnętrzny katalog raportów R00 zawiera R00_BASELINE_REPORT,
R00_RUNTIME_MANIFEST, R00_WORKTREE_MANIFEST, R00_EVIDENCE_GAPS,
R00_SOURCE_PRESERVATION_MANIFEST, R00_INTEGRATION_BASE_PROPOSAL oraz hashe.
Nie jest dodatkową roadmapą. Do Git trafia tylko zwięzły bezpieczny checkpoint
z metadanymi/dowodami/hashami i następnym krokiem. Surowe materiały i kopia
niezatwierdzonego source pozostają lokalne; ich dostępność zaznacz LOCAL_ONLY.

## 7. Aktualizowanie w toku pracy, pauza i awaria

Po znaczącym podetapie, wyniku testu/odczytu, zmianie blokady, przed pauzą oraz
na koniec zapisz checkpoint. Nie po każdej komendzie, nie obiecuj timera ani
pracy w tle. W tym R00 wykonaj co najmniej bootstrap i końcowy/handoff checkpoint.
Przed długą operacją zachowaj stan i zamiar; po niej rezultat. Jednoznacznie
rozróżniaj „uruchomiono”, „zakończono”, „sprawdzono” i „zaakceptowano”.

Dokumentacyjny checkpoint musi zawierać:
- ID sesji, UTC, pakiet/podetap, branch/worktree, code-under-test/base SHA;
- co faktycznie zakończono i jaka jest pozostała praca;
- PASS/FAIL/NOT_RUN/NOT_VERIFIED z komendą i dowodem, nie wynikami historycznymi;
- stan staged/unstaged/untracked, odtwarzalność własnych niezacommitowanych zmian;
- stan długich zadań/procesów i możliwe niezweryfikowane skutki;
- zakres zgody, pending gates, jedną następną bezpieczną czynność i STOP;
- link do poprzedniego małego checkpointu i wersję ocenianego kodu.

Sama aktualizacja roadmapy nie zapisuje WIP kodu. Dozwolone source commity
przyszłych pakietów wymagają ich własnej zgody i odpowiednich testów.
Nieprzechodzący kod można zachować jako zweryfikowaną bezpieczną kopię/patch
poza repo, bez reset/stash/delete. Nie zgłaszaj REMOTE_RECOVERABLE dla lokalnego
patcha, którego nie ma na GitHub. Nie uruchamiaj publikacji sekretów jako backupu.

Checkpoint dokumentacji opisujący PAUSED lub FAIL może być poprawnie commitowany
na recovery — nie oznacza SOURCE_PASS. Zachowaj atomowość edycji i sprawdź diff.
Jeżeli ktoś zmienił remote, nie force push/rebase w ciemno; zapisz lokalny stan
oraz konflikt. Równoległa sesja musi zostać rozstrzygnięta, nie nadpisana.

Nagła awaria może uniemożliwić ostatni zapis. Przy powrocie przeczytaj §0,
porównaj Git/worktree oraz faktyczne skutki ostatniej operacji i odtwarzaj tylko
brakujący fragment. Nie zakładaj, że każdy nagły crash uruchomi graceful shutdown.

## 8. Zakończenie R00

Gdy bootstrap i baseline wykonane: ustaw R00 READY_FOR_REVIEW; jeśli brakuje
istotnego warunku — PAUSED/BLOCKED z dokładnym powodem. Nie ACCEPTED samodzielnie.
R01 pozostaje PLANNED. Następny krok: ocena raportu R00 i osobna zgoda R01,
nie automatyczne usuwanie roadmap ani realizacja R01–R24.

Wykonaj końcowy checkpoint commit/push na recovery po walidacji allowlist.
Porównaj post-push local HEAD/remote HEAD i odczyt roadmapy. Commit własnego
checkpointu identyfikuj z Git, bez pętli dopisywania jego SHA do niego samego.

Końcowa odpowiedź obowiązkowo:
- `NEXT_STABIL_R00_READY_FOR_REVIEW` albo `NEXT_STABIL_R00_PARTIAL`;
- `ROADMAP_SYNCED@<pełny_SHA>` albo `LOCAL_ONLY/REMOTE_UNVERIFIED`;
- repo, dokładna gałąź, lokalny worktree, ścieżka i link GitHub do roadmapy;
- poprzedni/nowy doc HEAD, właściwy source baseline, main/rescue unchanged
  przez Ciebie oraz jawny zaobserwowany cudzy drift;
- stan baseline/recovery, zakres zmienionych dokumentów i checkpoint ID;
- R00 wykonane/pozostałe, wszystkie wymagane zgody i jedna następna czynność;
- wszystkie faktyczne skutki (w tym refs/worktree/doc writes/commit/push).
Nie pisz „Git changes=0”, gdy opublikowałeś dokumenty. Kod aplikacji/config/
produkcja/migracje/model calls pozostają 0, o ile faktycznie 0.

STOP. Bez R01 i bez dalszych pakietów. Nie usuwaj oryginalnego worktree ani
nowego worktree po publikacji — ma służyć wspólnej kontynuacji.
