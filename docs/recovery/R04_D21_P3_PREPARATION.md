# R04 / D-21 / P3 — przygotowanie dokładnego changesetu

Status: `PREPARATION_PARTIAL / READ_ONLY_INVENTORY / NO_CUTOVER`
Punkt wejścia: evidence `e9c17933b9f6a7f9ee6c825d371661a3769da0c9`
Zaakceptowany source DATA_ONLY: `cb6e22506a0fecc440400566293524536847b9b0`
Tree source: `c349a1d6ebfeb6077bc62181667f7f3c8f9d42cc`
Okno obserwacji: `2026-09-16T13:38:16Z–2026-09-16T13:43:51Z`

Ten dokument jest załącznikiem wykonawczym D-21. Nie jest nową roadmapą,
zatwierdzonym manifestem startowym ani zgodą na wykonanie opisanych operacji.
Każda czynność mutująca poniżej ma status
`NOT_EXECUTED / REQUIRES_OWNER_APPROVAL`.

## 1. Odbiór wejścia i granice

Właściciel odebrał source `cb6e225...` i evidence `e9c17933...` jako
`ACTIVE_DATA_TOPOLOGY_AND_DESTINATION_SOURCE_ACCEPTED / OFFLINE_TEST_ONLY /
NOT_DEPLOYED`. P1 oraz preservation/candidate P2 zachowują swoje wcześniejsze
odbiory. Kandydat pozostaje `DRAFT_NOT_APPROVED_FOR_START`, a jego
`approval.status` pozostaje `NOT_APPROVED`.

Utrzymana topologia:

- `INSTALL_ROOT=C:\ai-lab-core`;
- `ACTIVE_DATA_PATH=C:\ai-lab-core\data`;
- `ACTIVE_DATA_TARGET=D:\ai-lab-data`;
- istniejący directory junction pozostaje;
- Supervisor pozostaje `INTENTIONALLY_STOPPED`;
- backup schedules pozostają oddzielne i niezmienione.

Nie wykonano instalacji, startu/restartu, zmiany kontenera, mountu, obrazu,
wolumenu, taska, flagi, kolejki, danych, backupu, restore ani escrow.

## 2. Bieżące obserwacje i jakość dowodu

| Element | Bieżąca obserwacja | Klasa dowodu / ograniczenie |
|---|---|---|
| Git | local/tracking/remote `e9c17933b9f6a7f9ee6c825d371661a3769da0c9`; recovery clean | `CURRENT_OBSERVED`; bez pull/rebase/reset |
| Junction | `C:\ai-lab-core\data`, `Directory, ReparsePoint`, `LinkType=Junction`, target `D:\ai-lab-data` | `CURRENT_OBSERVED_ON_D` o `2026-09-16T13:40:09Z`; nie jest testem zapisu aplikacji |
| D: | NTFS, `Healthy`, 1,000,187,359,232 B, wolne 917,945,978,880 B | `CURRENT_OBSERVED`; nie jest oceną wszystkich plików |
| Engine | odczyt wersji/informacji serwera przeszedł, ale `docker ps -a` i następnie pojedynczy celowany `docker inspect` sześciu nazw przekroczyły po 20 s | `CURRENT_OBSERVABILITY_BLOCKED`; CLI PID `72400` i `66564` były własne i zostały zakończone; żadnego zasobu Docker nie zmieniono |
| Kontenery/images/mounty | bieżące pełne ID, obrazy, repo digests, Mounts, LogPath i restart policy nie zostały odczytane | `CURRENT_UNKNOWN`; wartości z 2026-09-15 pozostają `HISTORICAL`, nie current |
| Docker/WSL data disk | istnieje `C:\Users\domai\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, 46,937,407,488 B, last write `2026-09-16T13:40:12Z` | `CURRENT_C_RELOCATION_REQUIRED`; `docker-desktop` był `Running`, ale `df -T /var/lib/docker` zwrócił brak mount point, więc relacja Linux path→VHD nie jest pełnym runtime proof |
| PostgreSQL | host `psql.exe` nie istnieje; `docker exec` nie został wykonany po utracie obserwowalności Engine | `CURRENT_UNKNOWN`: schema, `data_directory`, WAL, tablespaces, log paths, kolejki i backup metadata w DB nieodczytane |
| Public Gateway | listener `127.0.0.1:8789`, PID `41784`, Node, skrypt `C:\ai-lab-core\operations\gateway\public_web_server.cjs`; `/gateway-health=200`, publiczne `/control=404` | `CURRENT_OBSERVED` o `2026-09-16T13:40:09Z`; tylko bezpieczne GET |
| Private Gateway / Supervisor | zapytanie TCP zwróciło strukturalne `CmdletizationQuery_NotFound`; brak listenera nie został przepisany na fałszywe PRESENT | `CURRENT_ABSENCE_INDICATION`; Supervisor nadal politycznie `INTENTIONALLY_STOPPED` |
| Task Scheduler | odczytano wyłącznie taski `NEXT Stabil`; Public Gateway `Running`, pozostałe startowe `Ready` | `CURRENT_OBSERVED`; niczego nie uruchomiono |
| Backup task 1 | last `2026-09-13T01:00:00Z`, result `267014` | `CURRENT_TASK_METADATA / SCHED_S_TASK_TERMINATED`; nie RUNNING/sukces, aktor i przyczyna unknown |
| Backup task 2 / 3 | last odpowiednio `2026-09-15T23:00:01Z` i `23:30:01Z`, result `1` | `CURRENT_TASK_METADATA / NONZERO`; brak zachowanego końcowego logu i brak zgody na ponowienie |
| Manifesty backupu | lokalny root: ostatnio widziany `20260829T191529Z`; odebrany R03 point `E:\ai-lab-backup\20260908T210559Z`, manifest `8F20A784...` | `HISTORICAL_BACKUP_METADATA`; R03 point jest nowszy i ma osobny accepted restore drill, ale nie dowodzi dzisiejszej świeżości |
| Vision Worker state | `C:\ChatGPT-Vision-Worker`: 7,328 plików, 890,094,670 B; tylko metadane, bez cookies/tokenów | `CURRENT_C_RELOCATION_REQUIRED`; odczyt rozmiaru ukończony w limicie 15 s |

Surowe wyjście nie zawierało `Config.Env`, pełnego inspectu, pełnych command
lines ani treści danych firmy. Dwa timeouty Engine kończą tę serię odczytów;
nie wykonano retry-do-skutku.

Zanonimizowane lokalne podsumowanie obserwacji pozostaje `LOCAL_ONLY` pod
istniejącym chronionym rootem P2 jako `p3-preparation-20260916T133633Z/
observations-summary.md`, SHA-256
`7B70A85AC45E7470A80C13EBE33C7E24855584FB7F9BB2397E2044F865865674`.

### 2.1. Kontynuacja diagnozy Engine i backupów

Ograniczona diagnoza odczytała zachowany log
`%LOCALAPPDATA%\Docker\log\host\com.docker.backend.exe.log.20260916-162308.200`
dla okna `2026-09-16T13:38:16Z–13:43:51Z`. Log pokazuje działające
odpowiedzi IPC `/time` oraz powtarzające się anulowanie strumieni zdarzeń przez
klienta z `EOF`, ale nie zawiera pasującego `containers/json` ani exact backend
`inspect`. Nie rozstrzyga więc, czy timeout powstał w runnerze, proxy czy Engine
i nie potwierdza odzyskania resource reads. Log VM `init.log` dla tego okna
został już zrotowany; ograniczone odczyty `Application`/`System` nie miały
pasujących zdarzeń Docker/WSL. Warunkowego inspectu, SQL oraz testowego
kontenera nie uruchomiono.

Zadania backupu wskazują istniejący
`operations/hardening/run-backup-schedule.ps1` dla schedule ID 1/2/3. Runner
nie przekierowuje stdout/stderr do trwałego pliku, a Task Scheduler Operational
nie zachował pasujących zdarzeń z ostatniego okna tasków 2/3. Dlatego:

- `267014 = 0x41306 / SCHED_S_TASK_TERMINATED`; nie jest to `RUNNING` ani
  potwierdzony sukces i nie przypisano aktora lub przyczyny zakończenia;
- wyniki tasków 2/3 `1` pozostają bez zachowanego końcowego logu i bez ustalonego
  etapu awarii;
- manifest `C:\ai-lab-core-backups\20260829T191529Z` jest tylko ostatnim
  widzianym manifestem w tym lokalnym rootcie, nie najnowszą kopią systemu;
- odebrany punkt R03 `E:\ai-lab-backup\20260908T210559Z`, manifest SHA-256
  `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B`,
  ma historyczny `capture_status=COMPLETE`, `scope_status=COMPLETE` i
  `restore_status=NOT_RUN_WAITING_APPROVAL`; odbiór R03-A4 jest odrębnym
  dowodem restore drill dla dokładnie tego manifestu;
- ostatni udany harmonogram, kompletność dzisiejszych danych i faktyczna
  świeżość rollbacku pozostają `UNKNOWN / UNRESOLVED`.

Sanitowane podsumowanie kontynuacji jest `LOCAL_ONLY` w podkatalogu
`startup-guard-20260916T161200Z/diagnosis-summary.md`, SHA-256
`275D637CCD09F1CE4D59E24E2E8714AC1E1C49EC60EE690EE3032EB35DC3399B`.

## 3. Miejsca fizycznego zapisu

| Kategoria | Łańcuch | Ocena | Decyzja P3 |
|---|---|---|---|
| PostgreSQL PGDATA | deklarowane `/var/lib/postgresql/data` → `C:\ai-lab-core\data\postgres` → junction D:; katalog D: istnieje | `HISTORICAL_ON_D`, bieżący mount i SQL `UNKNOWN` | `KEEP` dopiero po bieżącym inspect i SQL; osobno wykluczyć zewnętrzne WAL/tablespaces |
| Backend application data | deklarowane `/data` → logical data root → D: | `HISTORICAL_ON_D`; junction current | `KEEP`; potwierdzić exact mount i dodatkowe cache/tmp/log paths |
| n8n | deklarowane `/home/node/.n8n` → `D:\ai-lab-data\n8n` | `HISTORICAL_ON_D`; target current | `KEEP` po exact mount readback |
| Open WebUI | deklarowane `/app/backend/data` → `D:\ai-lab-data\openwebui` | `HISTORICAL_ON_D`; target current | `KEEP` po exact mount readback |
| Ollama | deklarowane `/root/.ollama` → `D:\ai-lab-data\ollama` | `HISTORICAL_ON_D`; target current | `KEEP`; bez pobierania/przenoszenia modeli |
| Qdrant | deklarowane `/qdrant/storage` → external volume `qdrant_storage` | bieżący wolumen `UNKNOWN`; Docker VHD jest aktualnie na C: | `UNKNOWN_BLOCKING`; jeżeli relacja volume→VHD zostanie potwierdzona, przeniesienie Docker data disk na D: jest osobną operacją, nie nowym pustym volume |
| Docker layers/write layers/json logs | current VHD na C: | `CURRENT_C_RELOCATION_REQUIRED` | osobny, wspierany przez Docker Desktop move do `D:\ai-lab-data\docker-desktop`; nie łączyć z backend switch |
| Vision Worker profile/state | `C:\ChatGPT-Vision-Worker` | `CURRENT_C_RELOCATION_REQUIRED` | osobna session-safe relokacja do logicznego `C:\ai-lab-core\data\vision-worker`; bez odczytu/utraty profilu |
| Backupy | taski i `C:\ai-lab-core-backups`; R03 E: pozostaje odrębny | `NOT_APPLICABLE` dla zwykłego startu | `KEEP`; harmonogram, retencja i cele bez zmian |

Nie nadano `ALL_LIVE_WRITES_ON_D_PASS`.

## 4. Wybrany source i skutki startupu

Między main `483f9bf8...` i source `cb6e225...` nie ma zmian w
`backend/Dockerfile`, requirements ani migracjach Alembic. Source head Alembic
pozostaje `followup_assistant_chat_history_20260829`. To uzasadnia możliwość
użycia zgodnego istniejącego obrazu zależności, ale nie zastępuje bieżącego
image ID/digest ani testu kandydata.

Start source `cb6e225...` nie jest skutkiem neutralnym:

1. `init_database()` jest bezwarunkowe i wykonuje `seed_admin()`. Przy obecnej
   roli/użytkowniku tylko odczytuje, ale przy braku może zapisać role/admina.
2. `start_backup_plan_reconciler()` jest bezwarunkowe. Reconciler tworzy lub
   aktualizuje durable sync events, wykonuje commity i może wywołać Supervisor.
   Przy zatrzymanym Supervisorze może zapisać status `failed/error`.
3. Pozostałe dispatchery mają flagi, lecz live Compose deklaruje obecnie
   `VISION_AUTOMATION_ENABLED=true`, `KNOWLEDGE_BASE_PROCESSING_ENABLED=true`,
   `KNOWLEDGE_BASE_VECTOR_WRITES_ENABLED=true`,
   `ADVANCED_ANALYSIS_ENABLED=true`, `DOCUMENT_PREPARATION_ENABLED=true` i
   `ASSISTANT_PIPELINE_V2_ENABLED=true`; aktywny historyczny override ustawia
   tylko `DOCUMENT_PREPARATION_ENABLED=false`. Bieżących effective env z
   kontenera nie odczytano.
4. `VISUAL_V2_ENABLED` nie jest zadeklarowane w pliku `.env` i source default
   to `false`; nie jest to jednak obserwacja uruchomionego procesu.

Minimalny kandydat P3 musi więc przed cutoverem:

- mieć jawny, odebrany guard wyłączający backup reconciler dla pierwszego
  base-only startu albo osobno autoryzować jego skutki;
- wymusić w zatwierdzonym override wszystkie dispatch/producer flags na
  `false` i potwierdzić effective env projekcją bez sekretów;
- potwierdzić w READ ONLY SQL istniejącą rolę/admina, current schema, brak
  aktywnego backup/import/restore/export i stan eventów/kolejek;
- zachować Supervisor `INTENTIONALLY_STOPPED`.

Bez pierwszego punktu source `cb6e225...` nie jest jeszcze bezpiecznym
`BASE_READY_ONLY` produkcyjnym manifestem.

### 4.1. Lokalny guard pierwszego startu — nieprzetestowany WIP

W recovery przygotowano pięć ścieżek WIP:

- `backend/app/core/config.py`: kompatybilne domyślne `true` dla
  `database_startup_seed_enabled` i `backup_plan_reconciler_enabled`;
- `backend/app/database/init_db.py`: przy wyłączonym seed jawna transakcja
  PostgreSQL `READ ONLY`, statement timeout, sprawdzenie expected Alembic
  revision, roli `Administrator` i aktywnego administratora, zawsze rollback;
- `backend/app/services/backup_plan_reconciler.py`: `enabled=false` zwraca
  `None` przed utworzeniem tasku i sesji;
- `backend/app/main.py`: wybór seed/readiness oraz bezpieczny shutdown `None`;
- `backend/test/test_d21_p3_startup_guard.py`: focused macierz default/invalid,
  read-only/no-write, fail-closed, reconciler off/on i lifespan all-off.

WIP jest `SOURCE_PARTIAL / LOCAL_ONLY / TESTS_NOT_RUN`, ponieważ zgodnie z
bramką §5 brak dowodu odzyskania odczytów zasobów Engine. Nie użyto hostowego
Pythona ani testu na produkcji. `git diff --check` przeszedł, lecz nie zastępuje
pytest/compileall/auth/API. Zabezpieczenie WIP:

- `startup-guard-tracked-wip.patch`, SHA-256
  `E043325F662D7A443534CC884C23B95EEA340348EA0823E348DEAB27F64EC0E3`;
- `startup-guard-test-wip.patch`, SHA-256
  `78A8394E1B5E4B80AAEED3E3B7FAFFC773112DAD33BECD62E3C2ED6EB013A4DA`.

Źródłem kandydata nadal jest odebrany `cb6e225...`; niesprawdzony WIP nie jest
przypisany do starego ZIP-a/Web ani do produkcyjnego manifestu.

## 5. Wybrany najmniejszy pakiet operacyjny

Preferowany pierwszy pakiet po usunięciu blockerów to
`P3 CORE BACKEND SOURCE SWITCH`, bez relokacji danych, VHD/profile, Web build,
task install, Supervisora i cleanupu.

Zakres planowany:

1. `KEEP` wszystkich potwierdzonych bindów danych D: oraz live Web
   `1.0.2+41`; obecny Web TEST_ONLY z API `18004` nie jest wdrażany.
2. Z Git utworzyć inertny payload dokładnie z `cb6e225...:backend` w istniejącym
   chronionym stagingu P2 i zweryfikować file manifest. Produkcja nie wykonuje
   recovery.
3. Ponownie potwierdzić P2 preservation wszystkich kolidujących plików
   `C:\ai-lab-core\backend`; bez checkout/reset/clean/stash w głównym
   worktree i bez zmiany `.git`/common-dir.
4. W kontrolowanym oknie zachować dzisiejszy backend directory przez exact
   move do podkatalogu istniejącego rootu P2, a zweryfikowany payload umieścić
   w `C:\ai-lab-core\backend`. Jest to przyszła, osobno zatwierdzana mutacja.
5. Użyć jednego in-root override
   `C:\ai-lab-core\operations\runtime\approved-compose\R04-D21-P3-core.override.yml`
   z `/app=C:\ai-lab-core\backend` read-only, zachowanym `/data`, exact image
   identity i jawnie wyłączonymi producentami. Nie używać recovery/staging jako
   runtime mountu.
6. Kontrolowanie odtworzyć wyłącznie backend (`--no-build`, bez pull i bez
   innych usług), odczytać nowy pełny ID/mounty/image i zweryfikować schema,
   `/version`, legacy API, public gateway/Web oraz brak nowych zadań/kolejek.

Przykładowe mutujące polecenia są wyłącznie specyfikacją i mają status
`NOT_EXECUTED / REQUIRES_OWNER_APPROVAL`:

```powershell
# NOT_EXECUTED / REQUIRES_OWNER_APPROVAL
Move-Item -LiteralPath 'C:\ai-lab-core\backend' `
  -Destination 'C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p3-cutover-R04-D21-P2-20260916T083044Z-cb6e225\rollback-backend'

# NOT_EXECUTED / REQUIRES_OWNER_APPROVAL
Move-Item -LiteralPath 'C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p3-cutover-R04-D21-P2-20260916T083044Z-cb6e225\candidate-backend' `
  -Destination 'C:\ai-lab-core\backend'

# NOT_EXECUTED / REQUIRES_OWNER_APPROVAL; exact image must first be resolved
docker --context desktop-linux compose -p ai-lab-core `
  -f 'C:\ai-lab-core\compose.yaml' `
  -f 'C:\ai-lab-core\operations\runtime\approved-compose\R04-D21-P3-core.override.yml' `
  up -d --no-deps --no-build --force-recreate backend
```

Nie wolno wykonać tych poleceń z nierozstrzygniętym image identity, SQL,
backup/event state, rollback point lub bez nowej zgody właściciela.

Rollback kodu/config dla tego pakietu używa istniejącego deploymentu
`483f9bf8b1a591ded8a42df5da87663c664ed5d4`, historycznego image ID
`sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`
po jego bieżącym potwierdzeniu oraz override D21-016 o SHA-256
`36355C9392BA1A9A060B036D7B64B42E0CBD4EF65579335BB7C95DDA807436E8`.
Powrót danych nie jest zawarty w tym rollbacku i pozostaje zależnością R03.

## 6. Blockery i wynik

`PREPARATION_PARTIAL` wynika z czterech konkretnych blockerów:

1. `DOCKER_ENGINE_RESOURCE_OBSERVABILITY_BLOCKED`: zachowane logi nie ustaliły
   przyczyny timeoutu ani nie potwierdziły odzyskania resource reads; brak
   bieżących ID/image/mount/log/restart facts.
2. `DATABASE_METADATA_NOT_OBSERVED`: brak bezpiecznej ścieżki SQL po utracie
   Engine; schema/WAL/tablespaces/queue/backup state są unknown.
3. `BASE_START_GUARD_SOURCE_PARTIAL_TESTS_NOT_RUN`: guard seed/reconcilera jest
   lokalnym WIP, bez wymaganej kampanii R02 i bez source commit/review.
4. `ROLLBACK_DATA_FRESHNESS_UNRESOLVED`: task 1 ma
   `SCHED_S_TASK_TERMINATED`, taski 2/3 wynik `1`, brak zachowanych końcowych
   logów; odebrany punkt R03 z 2026-09-08 jest historyczny, nie current.

Dokładne akcje komponentowe znajdują się w
`docs/recovery/R04_D21_P3_CHANGESET.csv`. Nie wykonano testów aplikacji, P1,
Fluttera, Web builda, migracji ani runtime smoke. Odebrany source pozostaje
niezmieniony; lokalny WIP guarda nie został przetestowany, ponieważ bramka
odczytu zasobów Engine nie przeszła.

Następny krok: po niezależnie potwierdzonej zmianie stanu resource reads
wykonać dozwolony exact backend inspect z limitem 20 s, a dopiero po
potwierdzeniu obrazu i bramek jedną izolowaną kampanię guarda. Następnie guard
może otrzymać własny source/evidence review; bez automatycznego SQL/cutoveru,
P4/P5 lub R06.
