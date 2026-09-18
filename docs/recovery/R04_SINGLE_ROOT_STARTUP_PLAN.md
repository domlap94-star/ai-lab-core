# R04 / D-21 — plan jednego katalogu instalacji i jednego startu

Status dokumentu: `P1_SOURCE_AND_OFFLINE_TESTS_ACCEPTED /
P2_PRESERVATION_AND_CANDIDATE_ACCEPTED /
ACTIVE_DATA_TOPOLOGY_AND_DESTINATION_SOURCE_ACCEPTED /
P3_CORE_BACKEND_SOURCE_SWITCH_ACCEPTED_LIMITED_RUNTIME_SCOPE /
P4A_SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED_NOT_INSTALLED /
P4B_PHASE_A_WINDOW_READY_WAITING_OWNER_CONFIRMATION_NOT_INSTALLED`
Źródło statusu wykonawczego: §0 i §0.2
`NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`. Ten dokument jest załącznikiem
wykonawczym D-21, a nie drugą roadmapą.

## 1. Wynik inventory

Ograniczony odczyt wykonano 2026-09-15, bez uruchamiania launcherów, usług,
kontenerów, modeli, kolejek, backupu ani restore. Mapa 33 elementów znajduje
się w `docs/recovery/R04_SINGLE_ROOT_STARTUP_MAP.csv`.

Najważniejsze ustalenia:

1. **Historyczny odczyt 2026-09-15:** aktywny wtedy backend nie korzystał z
   `C:\ai-lab-core\backend`. Kontener
   `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`
   ma rzeczywisty mount
   `C:/ai-lab-core/build/deploy-main-483f9bf8/backend -> /app`, obraz
   `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`
   i clean source `483f9bf8b1a591ded8a42df5da87663c664ed5d4`.
2. `C:\ai-lab-core\backend` jest częścią chronionego dirty worktree. W
   porównaniu bajtów z aktywnym deploymentem, po pominięciu generowanych
   cache, ma 90 równych plików, 479 różnych plików o tej samej ścieżce, 259
   plików tylko po swojej stronie i 9 tylko w aktywnym deploymencie. Sama
   nazwa katalogu nie dowodzi tożsamości runtime.
3. Wszystkie 203 wpisy preservation manifestu oryginalnego worktree istnieją i
   mają zgodne SHA-256 (`203/203`, brak mismatch, staged `0`). Recovery jest
   clean na `8620871711321a42e62291e52865b5a668a4955d` i ma 64 commity ponad
   `origin/main`; nie jest konsumentem produkcyjnym.
4. Pięć clean promotion worktrees nie ma unikalnych commitów względem
   `origin/main`. Właścicielska ścieżka `doc04-main-promotion` jest nieobecna;
   osobno istnieje `doc04a-main-promotion`. Worktree Visual V2 ma 13 unikalnych
   commitów i 5 lokalnych zmian, więc nie jest kandydatem do usunięcia.
5. Aktualny start jest rozproszony. Task Scheduler ma osobne zadania logowania
   dla Docker Desktop, Compose, Public Gateway, Private Gateway i Supervisora.
   Public Gateway działa jako PID `41784` z
   `C:\ai-lab-core\operations\gateway\public_web_server.cjs`; ograniczony
   odczyt zwrócił `/gateway-health=200` i `/control=404`. Supervisor pozostaje
   `INTENTIONALLY_STOPPED` i nie został uruchomiony.
6. Użytkownik ma dodatkowy autostart
   `...\Startup\NEXT-Stabil-Host.cmd`, SHA-256
   `C843C05CB023CE187D7C6829DB904E2FDB58B893C8072CBC33E476D7307C06D4`.
   Wrapper wskazuje nieistniejący
   `C:\ai-lab-core\operations\runtime\start-host-services.ps1`; jest więc
   zerwany, a nie kanoniczny. Desktop shortcut uruchamia tylko zainstalowany
   klient `1.0.2+29`, nie cały stos.
7. `start-compose-after-docker.ps1` jest rzeczywiście konsumowany przez zadanie
   `NEXT Stabil - Docker Compose`. Ogranicza liczbę iteracji, lecz pojedyncze
   zawieszone wywołanie `docker.exe info` nie ma własnego deadline. To ustalenie
   do przyszłej poprawki source, nie wykonana zmiana.
8. Web jest serwowany z `C:\ai-lab-core\frontend\build\web`: 40 plików,
   47,848,874 B, file-manifest SHA-256
   `3951EBEB2053F60AC9FD2295B2EBCFA73126777A098102FF4F3B62DE4787F5D9`,
   deklarowana wersja `1.0.2+41`. Aktualny Windows client ma 22 pliki,
   file-manifest SHA-256
   `B8FA2AC194BD4B002FE7654ABC8F109E20956D111735F22A210BBD8E536BFEBB`;
   `frontend.exe` ma SHA-256
   `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`
   i nie ma podpisu Authenticode.
9. `C:\ChatGPT-Vision-Worker` zawiera chroniony profil/stany i zewnętrzne
   worker files. Jego `vision-job.js` różni się zarówno od original/main, jak i
   recovery. Supervisor jest zadeklarowanym konsumentem tej ścieżki, lecz jest
   zatrzymany; żadnego workera nie zaobserwowano. Profile/cookies nie były
   odczytywane.
10. `C:\Ollama-Vision-Pilot` istnieje, ale w ograniczonych task/process/repo
    references nie znaleziono bieżącego konsumenta. Pozostaje `HOLD / UNKNOWN`,
    nie `UNUSED`. `C:\ai-lab-repair` jest niegitowym obszarem naprawczym SDK;
    także nie uzyskał zgody na cleanup.

## 2. Preferowany układ docelowy

Docelowym rodzicem instalacji jest wyłącznie `C:\ai-lab-core`. Poniższy układ
jest propozycją do odbioru; nie został utworzony ani zasilony w tej sesji.

| Rola | Preferowana ścieżka | Zasada |
|---|---|---|
| Backend runtime source | `C:\ai-lab-core\backend` | Tylko bajty z osobno zaakceptowanego, hashowanego source/build set; nie dzisiejszy dirty katalog. |
| Web | `C:\ai-lab-core\frontend\build\web` | Jeden manifest bajtów na build; zmiana dopiero z kompatybilnym backendem. |
| Dane usług | logicznie `C:\ai-lab-core\data`, fizycznie `D:\ai-lab-data` | Zachowany directory junction `ACTIVE_DATA_ONLY`; ciężkie, trwałe dane rosną na aktywnym dysku D:, a kod nigdy nie wykonuje się z tego targetu. |
| Gateway/Supervisor | `C:\ai-lab-core\operations\gateway` i `...\supervisor` | Wersja z tego samego zaakceptowanego source set. |
| Workery repozytoryjne | `C:\ai-lab-core\operations\vision-worker` | Kod z Git; bez zewnętrznej kopii jako nieweryfikowanego źródła. |
| Stan/profile workerów | `C:\ai-lab-core\data\vision-worker` | Chroniony state oddzielony od kodu; migracja sesji dopiero po osobnym teście i zgodzie. |
| Release channel | `C:\ai-lab-core\release-channel` | Normalny start nie publikuje ani nie zmienia stable/minimum. |
| Windows client | `C:\ai-lab-core\client\windows` | Dopiero po build/signature/runtime acceptance; obecny klient pozostaje bez zmian. |
| Staging nieprodukcyjny | `C:\ai-lab-core\staging` | Tylko przyszłe, jawnie oznaczone build/test payloads; nigdy aktywny fallback runtime. |
| Jeden launcher | `C:\ai-lab-core\operations\runtime\start-host-services.ps1` | Naprawia istniejący, obecnie zerwany łańcuch; jeden kod dla startu ręcznego i logon. |

Jawne wyjątki pozostają poza rootem: aktywny dysk danych
`D:\ai-lab-data` dostępny przez dokładny junction
`C:\ai-lab-core\data`, backupy E:/F: i decyzje R03, recovery key/escrow,
zainstalowany Docker/WSL/SDK/Node/Flutter oraz standardowe Docker volumes/VHD.
Bieżące `C:\ai-lab-core-backups` pozostaje chronione do osobnej decyzji o
docelowym zewnętrznym backup root. Inne junctiony/symlinki nie uzyskują zgody;
wyjątek `ACTIVE_DATA_ONLY` nie obejmuje kodu, skryptów, executable ani CWD.

## 3. Specyfikacja jednego startu

Jedynym kodem startowym ma być przyszły, śledzony w Git
`operations/runtime/start-host-services.ps1`, naprawiający cel już istniejącego
wrappera Startup. Zarówno pojedyncze zadanie logowania `NEXT Stabil - Host`, jak
i ręczny shortcut mają wywoływać ten sam plik. `start-compose-after-docker.ps1`
może pozostać jego wewnętrznym etapem tylko po dodaniu ograniczonych deadline
dla każdej natywnej komendy. Osobne taski startowe mają być wycofywane dopiero
po odbiorze wspólnego wejścia.

Kolejność przyszłego launchera:

1. Rozwiąż własną ścieżkę niezależnie od bieżącego CWD i wczytaj wyłącznie
   zatwierdzony manifest zestawu.
2. Potwierdź, że Docker Engine odpowiada, nie tylko że działa GUI. Jeżeli
   Engine nie działa, uruchom dokładnie jedną istniejącą, zatwierdzoną instancję
   Docker Desktop (bez restartu, aktualizacji lub zmiany contextu), a następnie
   czekaj w ograniczonym oknie na odpowiedź serwera. Każde wywołanie CLI ma
   własny deadline, PID i kontrolowany błąd.
3. Odczytaj istniejące kontenery, pełne ID, obrazy, mounty i Compose project.
   Przy innym source/image/mouncie: `STOP / CONTROLLED_DEPLOY_REQUIRED` bez
   `pull`, `build`, `recreate` i bez fallbacku do recovery/staging.
4. Uruchom albo zachowaj wyłącznie bazowy zestaw CRM/API/Web według jednego
   przypiętego Compose/config set. Drugi start rozpoznaje te same zasoby i nie
   dubluje instancji.
5. Uruchom/zweryfikuj publiczny i prywatny gateway z niezmienną granicą:
   publiczny `8789` nie udostępnia `/control`, prywatny `8788` może kierować do
   `8787` wyłącznie lokalnie.
6. Supervisor/export jest osobną polityką. Przy obecnym stanie launcher pokazuje
   `INTENTIONALLY_STOPPED` i nie wznawia kolejek. Dopiero osobna decyzja i
   bramki R05 pozwalają zmienić ten etap.
7. Potwierdź gotowość komponentowo: Engine, DB, API, Web, gateways, a następnie
   jawnie oznacz wyłączone/niezweryfikowane AI/export. Exit `0` launchera nie
   oznacza automatycznie gotowości wszystkich usług.
8. Opcjonalne otwarcie zaakceptowanego klienta następuje dopiero po gotowości
   bazowej; konflikt portu, mountu lub wersji kończy się czytelną odmową.

Przyszła macierz odbioru obejmuje: zwykły start, drugi start bez duplikatów,
Engine już gotowy, Engine niegotowy, usługę celowo wyłączoną, konflikt portu,
błędny mount/wersję, zachowanie `/control*`, reboot hosta w osobnym oknie oraz
rollback. Wszystkie te scenariusze są obecnie `NOT_RUN`.

## 4. Pakiety przyszłego wykonania

Każde polecenie operacyjne w tej sekcji ma status
`NOT_EXECUTED / REQUIRES_SEPARATE_APPROVAL`.

### D21-P1 — źródło launchera i testy offline (pierwszy minimalny pakiet)

Stan 2026-09-15: właściciel zaakceptował P1 wyłącznie jako
`SOURCE_AND_OFFLINE_TESTS_ACCEPTED / NOT_DEPLOYED` na source
`2e69622bc6a0b4888427f8ae5be119377aed26d9` i evidence
`7687cc15bb31175d19485b10a6e13dfc5945bfc2`. Parser PowerShell 5.1 i przykład
JSON przeszły; focused test wykonał 53 asercje, a test rzeczywistych adapterów
z dolnymi atrapami 48 asercji, oba exit 0.
Szczegóły: `docs/recovery/R04_D21_P1_STARTUP_SOURCE_EVIDENCE.md`.

Ścieżki:

- `operations/runtime/start-host-services.ps1` — nowy, brakujący cel istniejącego wrappera;
- `operations/windows/start-compose-after-docker.ps1` — bezpieczny interfejs
  istniejących zasobów; bezpośrednie wykonanie odmawia i nie zawiera już
  fallbacku `docker compose up`;
- jeden mały test kontraktowy pod `operations/runtime/`;
- aktualizacja recepty/manifestu tożsamości startu.

Precondition: owner review tej mapy i jawna zgoda source/test.
Efekt: kod nie wykonuje się na produkcji; testy atrapiają Docker/tasks/processy i
sprawdzają idempotencję, brak pull/build/recreate, błędny mount, konflikt portu,
Supervisor `INTENTIONALLY_STOPPED` oraz timeout.
Verification: parser PowerShell 5.1, testy focused, negatywne identity/mount,
`git diff --check`, brak zmiany Task Scheduler.
Rollback: revert jednego source commita.
Uprawnienie: zgoda D21-P1 SOURCE/OFFLINE TEST została wykorzystana wyłącznie do
source i atrapionych testów; odbiór nie jest zgodą operacyjną.

### D21-P2 — zabezpieczenie unikalnej pracy i candidate manifest

Stan po decyzji właściciela: `PRESERVATION_AND_CANDIDATE_ACCEPTED /
NOT_DEPLOYED`. Wyjątek `ACTIVE_DATA_ONLY` jest
`SOURCE_ACCEPTED / OFFLINE_TEST_ONLY / NOT_DEPLOYED` na commicie
`cb6e22506a0fecc440400566293524536847b9b0` i evidence
`e9c17933b9f6a7f9ee6c825d371661a3769da0c9`; nie jest wdrożony.
Wybrany jest jeden pełny source set
`2e69622bc6a0b4888427f8ae5be119377aed26d9`, który zawiera niezmienione bajty
aplikacyjne zaakceptowanego A4 oraz odebrany launcher P1. Snapshot, manifest
1,198 plików i roundtrip hashy są zapisane w jednym nieaktywnym rootcie P2.

Precondition spełnione w zakresie nieoperacyjnym: original 203/203 bez driftu;
audit HEAD i 5 lokalnych zmian zachowane przez zweryfikowany bundle, exact bytes
i binary patch; siedem jawnie dozwolonych plików zewnętrznego workera
zabezpieczono bez profilu/sesji. Recovery remote wymaga końcowego readbacku tego
handoffu. Aktualny rollback kodu to nadal aktywny deploy `483f9bf8...`; recovery
dzisiejszych danych pozostaje oddzielną otwartą decyzją R03.

Efekt: jeden inertny snapshot źródła sprzed poprawki DATA_ONLY, jeden Web build `TEST_ONLY`, jawna macierz
source→artifact→target i draft `NOT_APPROVED_FOR_START` dla backend/API/schema/
Web/gateway/Supervisor/workers. Nie jest to deployment ani `CUTOVER_READY`.
Snapshot `318A41...CC6C3` pozostaje przypięty do `2e69622...`; aktualne źródło
walidatora jest identyfikowane przez Git commit/tree, bez przepisywania starego
archiwum na nowe pochodzenie.
Verification: pełne hashe, provenance, 1,198/1,198 roundtrip, Web build exit 0,
oraz oczekiwana odmowa draftu przez walidator P1 w PowerShell 5.1 z
`START_NOT_APPROVED` i bez adapterów.
Rollback: zachowane oryginalne drzewo, audit, aktywny deploy `483f9bf8...`,
override D21-016 i zewnętrzne state roots.
Uprawnienie: osobna zgoda P2 obejmuje preservation/candidate wyłącznie lokalnie;
sekretne lub biznesowe payloads pozostają poza Git. Szczegóły:
`R04_D21_P2_CANDIDATE_EVIDENCE.md`.

### D21-P3 — wykonany backend-only switch, ograniczony odbiór

OP_ID `R04-D21-P3-CORE-SWITCH-20260917T141404Z` wykonał dokładnie jedno
przełączenie backendu na source
`0ee0ea50943578e6e552aae23ce1688595ddc262`. Bieżący backend
`686ac37663ad369f253eb91da4364aa2bd6c16c77b1205cc41d61c68d4d9c854`
ma `/app=C:/ai-lab-core/backend:ro` i `/data=C:/ai-lab-core/data:rw`; payload
592/592, schema i pending `18/16/1` zostały zachowane. Rollback nie był użyty.
Późniejszy readback tej samej instancji potwierdził dwie warstwy `11/11 MATCH`
i `9/9` przełączników `false`.

Właściciel przyjął ten wynik jako `CORE_BACKEND_SOURCE_SWITCH_ACCEPTED /
LIMITED_RUNTIME_SCOPE`. Odbiór nie jest odczytem obiektu `Settings` w pamięci,
historią wszystkich dispatcherów, globalnym dowodem braku zapisów ani odbiorem
całego P3/R04. `DELTA_NOT_FULLY_OBSERVED`, VHD/Qdrant/profile, harmonogramy
backupu oraz globalny start pozostają odrębnymi bramkami. Zużyta zgoda na switch
nie uprawnia do recreate lub rollbacku.

### D21-P4 — jeden start i rollback acceptance

P4-A przygotował `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z` jako
`STARTUP_ACTIVATION_PACKAGE_READY_FOR_REVIEW / NOT_INSTALLED`. Pakiet zawiera
minimalny trzyplikowy payload przyjętego launchera, draft manifestu sześciu
istniejących kontenerów, dokładny changeset triggerów, rollback XML pięciu
tasków, kopie wrappera/skrótu i wyłączony draft `NEXT Stabil - Host`.

Docelowo jeden task `NEXT Stabil - Host` uruchamia zaakceptowany launcher.
Taski Public/Private/Supervisor pozostają enabled/on-demand jako executory, lecz
ich niezależne triggery logon mają zostać usunięte. Startup wrapper musi zostać
wyłączony **przed** instalacją launchera. Taski backupu i Trash Purge pozostają
oddzielnymi harmonogramami.

Manualny `NEXT Stabil.lnk` pozostaje obecnym wejściem UI, ponieważ P1 nie ma
`OPEN_AFTER_BASE_READY`; nie wolno go przepiąć na launcher, który nie otworzy
klienta. To jawna luka do osobnego source/review, nie powód do drugiego
launchera.

Verification P4-B: normalny start, drugi start bez duplikatów, Docker
ready/not-ready, celowo zatrzymany Supervisor, konflikt portu, błędny
mount/wersja, publiczne `/control`, logon/reboot i rollback. Supervisor pozostaje
`INTENTIONALLY_STOPPED`. Globalny manifest jest `NOT_APPROVED`; P4-B wymaga
osobnej exact zgody na instalację, aktywację i okno operacyjne.

### D21-P5 — archiwizacja i wycofanie

Precondition: P3/P4 accepted, co najmniej jeden stabilny okres pracy, brak
konsumentów i pełna ochrona unikalnej pracy.
Efekt: tylko exact-path retirement clean promotion worktrees i później
udowodnionych kopii. Recovery, Visual audit, staging, external worker/profile,
backupy i modele nie kwalifikują się obecnie do automatycznego cleanupu.
Verification: aktualny consumer audit, hashes, Git common-dir/ref i post-check.
Rollback: zachowany ref/archive; dla danych bez odwracalności cleanup nie jest
wykonywany bez jawnej decyzji.
Uprawnienie: osobna exact-name cleanup approval.

## 5. Otwarte bramki i niewiadome

- `R03 WAITING_APPROVAL / WAITING_ESCROW_DECISION`: nie blokuje mapy ani P4-A,
  ale blokuje deklarację pełnej recovery readiness.
- `R05 IN_PROGRESS`: operator Web runtime, real Temporary Chat, upload i external
  end-to-end pozostają niezweryfikowane. Dlatego P3/P4 nie może automatycznie
  uruchomić Supervisora/exportu.
- `R04 IN_PROGRESS`: source/test acceptance nie jest runtime acceptance;
  Windows/Android i pełna compatibility matrix pozostają otwarte.
- Aktualny backup destination trzech schedule runners nie został odczytany z
  biznesowej DB; same taski i ich wrappery zostały zidentyfikowane.
- `C:\Ollama-Vision-Pilot` nie ma potwierdzonego konsumenta ani potwierdzenia
  zbędności.
- Siedem nazwanych plików zewnętrznego workera zachowano w P2, lecz 0 jest
  identycznych z kandydatem, 3 są różne, a 4 nieobecne; ich adopcja oraz profil
  nadal wymagają osobnego review/migracji bez odczytu cookies i utraty sesji.
- `C:\ai-lab-core-staging` jest mieszanką evidence/cache/deployment declarations;
  tylko aktywny override został zidentyfikowany jako bieżący konsument.
- Kandydat wywołuje bezwarunkowo `init_database()` i uruchamia backup plan
  reconciler w lifespan; P3 musi osobno kontrolować ich skutki i efektywną
  konfigurację wszystkich bramek AI.
- `C:\ai-lab-core\data -> D:\ai-lab-data` jest zatwierdzonym wyjątkiem
  `ACTIVE_DATA_ONLY` i pozostaje. P3 nie wybiera ponownie C: kontra D:; ma
  potwierdzić każdą usługę/mount/volume, brak ukrytych zapisów ciężkich danych na
  C: oraz rollback. Syntetyczny test junctionu nie jest dowodem wszystkich
  bieżących zapisów runtime.
- Qdrant managed volume, Docker/WSL VHD i warstwy zapisu, zewnętrzne
  tablespaces/WAL, container logs/cache oraz profil/state zewnętrznego workera
  nadal nie mają pełnego dowodu fizycznej lokalizacji.
- Draft P4-A jest celowo `NOT_APPROVED_FOR_START`. Bieżące container ID,
  image ID i mounty są zarejestrowane, ale RepoDigests, Qdrant/VHD backing,
  `OPEN_AFTER_BASE_READY`, task install i pełna macierz start/rollback pozostają
  otwarte.

Te braki blokują odpowiednie relokacje lub cleanup, lecz nie unieważniają
gotowości mapy i planu do właścicielskiego review.

## 6. Skutki tej sesji

P1 jest odebrane wyłącznie jako source/offline tests i pozostaje NOT_DEPLOYED.
P2 preservation/candidate jest odebrane jako NOT_DEPLOYED. P2 utworzyło jeden chroniony root z lokalnymi archiwami preservation, inertnym
snapshotem, katalogami walidacyjnymi, logami oraz jednym buildem Web TEST_ONLY.
Do Git trafiają tylko zanonimizowane indeksy, draft i dokumentacja. Nie wykonano
cutoveru, relokacji, cleanupu, task/shortcut/mount/config/flag change, restartu,
startu aplikacji/launchera/Supervisora/workera, UI, modeli, backupu ani restore.

Launcher P1 nadal nie jest zainstalowany. Draft P4-A ma `NOT_APPROVED`, a
nieaktywny pakiet, XML i rollback copies pozostają LOCAL_ONLY. P4-A nie zmienił
tasków, skrótów, plików instalacji, manifestu produkcyjnego ani runtime.

Phase A okna `R04-D21-P4B-WINDOW-20260918T084652Z` przygotowała exact pakiet,
preimage i walidację offline, bez instalacji lub mutacji runtime. Następny krok
to jedno dokładne potwierdzenie właściciela dla opublikowanych hashów, kolejności
wyłączenia Startup wrappera, instalacji disabled host taska i payloadu,
zatwierdzenia manifestu oraz dwóch warm runs. Ten plan nie udziela tej zgody.
