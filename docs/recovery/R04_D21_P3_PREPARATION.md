# R04 / D-21 / P3 — przygotowanie dokładnego changesetu

Status: `PREPARATION_PARTIAL / BASE_START_GUARD_ACCEPTED / CURRENT_DB_METADATA_OBSERVED / ROLLBACK_EVIDENCE_REVIEW_READY / NO_CUTOVER`
Punkt wejścia: evidence `e9c17933b9f6a7f9ee6c825d371661a3769da0c9`
Zaakceptowany source DATA_ONLY: `cb6e22506a0fecc440400566293524536847b9b0`
Tree source: `c349a1d6ebfeb6077bc62181667f7f3c8f9d42cc`
Zaakceptowany guard source: `0ee0ea50943578e6e552aae23ce1688595ddc262`
Guard tree: `4ccbc8922051401da1422be0d08f271476c3bab6`
Okna obserwacji: `2026-09-16T13:38:16Z–13:43:51Z`,
`2026-09-16T18:29:26Z–18:34:45Z` oraz
`2026-09-16T19:59:54Z–20:05:34Z`

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

Właściciel odebrał też guard source
`0ee0ea50943578e6e552aae23ce1688595ddc262` z evidence
`c52f453513dc96bd750dd9e6c0a0a836f134d7e6` jako
`BASE_START_GUARD_SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED` i
zezwolił na jedną bieżącą kampanię odczytową PostgreSQL/rollback. Odbiór nie
jest PostgreSQL integration, zatwierdzeniem manifestu ani zgodą na cutover.

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
| Engine | dokładny odczyt jednego backendu zakończył się `exit 0` po 281 ms; lokalny helper diagnostyczny nie został uruchomiony, bo odczyt wystarczył | `CURRENT_OBSERVED` o `2026-09-16T18:29:26Z`; przyczyna wcześniejszych timeoutów pozostaje `UNKNOWN` |
| Backend runtime | full ID `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`, running, image `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`, restart `unless-stopped`; `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`, `/data=C:/ai-lab-core/data`, oba RW | `CURRENT_OBSERVED`; Compose labels są zgodne, lecz mounty pochodzą z faktycznego inspectu. Brak mountu recovery/WIP |
| Obraz testowy | pinned R02 image `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`, Linux/amd64, 1,314,265,170 B | `CURRENT_LOCAL_IMAGE_OBSERVED`; bez pull/build |
| Docker/WSL data disk | istnieje `C:\Users\domai\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, 46,937,407,488 B, last write `2026-09-16T13:40:12Z` | `CURRENT_C_RELOCATION_REQUIRED`; `docker-desktop` był `Running`, ale `df -T /var/lib/docker` zwrócił brak mount point, więc relacja Linux path→VHD nie jest pełnym runtime proof |
| PostgreSQL | exact ID `240343ebff4fb299b239db2817efea1910ab59c29ed3ec9df3a8abde04e81226`, image `sha256:a426e44b...d8508d`, running, project/service `ai-lab-core/postgres`, restart `unless-stopped`, host port tylko `127.0.0.1:5432`; bind `C:\ai-lab-core\data\postgres -> /var/lib/postgresql/data`; backend host/DB/user zgodne z nazwą lub aliasem tego kontenera na jednej wspólnej sieci | `CURRENT_OBSERVED` `2026-09-16T19:59:54Z–20:05:34Z`; bez utrwalenia wartości config/sekretów |
| Public Gateway | listener `127.0.0.1:8789`, PID `41784`, Node, skrypt `C:\ai-lab-core\operations\gateway\public_web_server.cjs`; `/gateway-health=200`, publiczne `/control=404` | `CURRENT_OBSERVED` o `2026-09-16T13:40:09Z`; tylko bezpieczne GET |
| Private Gateway / Supervisor | zapytanie TCP zwróciło strukturalne `CmdletizationQuery_NotFound`; brak listenera nie został przepisany na fałszywe PRESENT | `CURRENT_ABSENCE_INDICATION`; Supervisor nadal politycznie `INTENTIONALLY_STOPPED` |
| Task Scheduler | odczytano wyłącznie taski `NEXT Stabil`; Public Gateway `Running`, pozostałe startowe `Ready` | `CURRENT_OBSERVED`; niczego nie uruchomiono |
| Backup task 1 | last `2026-09-13T01:00:00Z`, result `267014` | `CURRENT_TASK_METADATA / SCHED_S_TASK_TERMINATED`; nie RUNNING/sukces, aktor i przyczyna unknown |
| Backup task 2 / 3 | last odpowiednio `2026-09-15T23:00:01Z` i `23:30:01Z`, result `1` | `CURRENT_TASK_METADATA / NONZERO`; brak zachowanego końcowego logu i brak zgody na ponowienie |
| Manifesty backupu | accepted full `E:\ai-lab-backup\20260908T210559Z` `8F20A784...`, 9/9 artefaktów obecnych i zgodnych rozmiarem; latest DB `F:\ai-lab-system-backup\20260911T230006Z` `769583D1...`, 1/1; latest n8n `F:\ai-lab-system-backup\20260911T233006Z` `F8005856...`, 3/3 | `CURRENT_FILE_METADATA_PLUS_HISTORICAL_RESTORE_EVIDENCE`; nie haszowano dużych artefaktów, a taski `267014/1/1` nie potwierdzają świeżej kopii po tych punktach |
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

### 2.2. Aktywna diagnoza i odzyskany odczyt zasobu

Jedna dozwolona sesja diagnostyczna potwierdziła właściwy context
`desktop-linux`, endpoint `npipe:////./pipe/dockerDesktopLinuxEngine` oraz brak
override `DOCKER_HOST`/`DOCKER_CONTEXT`. Exact inspect wskazanego backendu
zakończył się bez timeoutu. Hostowy i VM proxy log mają skorelowane żądanie i
odpowiedź `GET /v1.56/containers/<full-id>/json` o tym samym czasie. Nie ma
dowodu, co usunęło poprzedni timeout; przyczyna pozostaje `UNKNOWN`.

Przed testem Windows miał 7.484 GiB dostępnego fizycznego RAM oraz 37.608 GiB
zapasu commit; pula `docker-desktop` raportowała 15.011 GiB available i 0 z
8 GiB użytego swapu. Backend i Public Gateway health zwróciły `200`, publiczne
`/control` zwróciło `404`, a port Supervisora `8787` nie miał listenera.

Jedyny efemeryczny kontener testowy miał full ID
`e9a43bf24c8e3c2979537c6813d1a806b2dfebda8e85a6cd50c551432b52c62c`,
obraz R02, `network=none`, read-only root/source, tmpfs, bez portów, Docker
socketa, privileged i host PID. Po kampanii został usunięty; exact inspect
zwrócił `No such container`. Nie uruchomiono serwera produktu, dispatchera,
Supervisora, modelu, SQL produkcji ani restartu Engine. Lokalny indeks dowodów:
`docs/recovery/R04_D21_P3_DIAGNOSTIC_INDEX.csv`.

### 2.3. Bieżąca baza i rollback — odczyt ograniczony

W oknie `2026-09-16T19:59:54Z–20:05:34Z` wykonano jeden odczyt metadanych
bieżącego backendu i PostgreSQL. Sesja `psql` użyła `-X`,
`ON_ERROR_STOP=1`, połączenia z `default_transaction_read_only=on`, następnie
`BEGIN READ ONLY`, `statement_timeout=5s`, `lock_timeout=1s`, ograniczonego
`idle_in_transaction_session_timeout` i jawnego `ROLLBACK`. Całość trwała
1424 ms i zakończyła się kodem `0`; nie wykonano retry ani drugiej sesji SQL.

Odczyt potwierdził PostgreSQL `17.10`, bazę/użytkownika `ai_lab`, revision
`followup_assistant_chat_history_20260829`, dokładnie jedną rolę
`Administrator` i dokładnie jedno skonfigurowane aktywne, nieusunięte konto
administratora. `transaction_read_only=on`. `PGDATA` to
`/var/lib/postgresql/data`, host bind to `C:\ai-lab-core\data\postgres`,
`pg_wal` i `pg_tblspc` są zwykłymi katalogami pod PGDATA, brak zewnętrznych
tablespaces, `log_directory=log`, a baza zajmuje 743 765 683 B. Junction
`C:\ai-lab-core\data -> D:\ai-lab-data` pozostał bez zmian.

Odczytano wyłącznie małe agregaty stanu: zero aktywnych backupów, zero rekordów
restore/import, 18 document-preparation `queued/queued`, 16 analysis
`advanced_queued`, jeden Assistant `waiting/analyzing_local`, zero aktywnych KB
i zero pending backup sync. Nie odczytywano treści dokumentów, poczty, zapytań
innych sesji, haseł, adresów e-mail ani danych użytkowników. Żądane zapisy
danych biznesowych: brak. To nie jest deklaracja braku technicznego I/O hosta.

Rollback pozostaje `REVIEW_READY / DATA_FRESHNESS_OWNER_DECISION_REQUIRED`:

- odebrany full point `E:\ai-lab-backup\20260908T210559Z`, manifest
  `8F20A7845473097EE74019966583EC3F121139C4B562265F9A7391FAFAF6BE4B`,
  ma 9/9 artefaktów obecnych i zgodnych rozmiarem oraz historyczny odbiór R03-A4
  dla dokładnego manifestu;
- najnowszy znaleziony DB point `F:\ai-lab-system-backup\20260911T230006Z`,
  manifest `769583D1CD2CCDDA3C83786AC05B4C9E53015870C5AA23C0A0B84DEEECEB2382`,
  ma 1/1 artefakt obecny i zgodny rozmiarem, bez bieżącego restore proof;
- najnowszy n8n point `F:\ai-lab-system-backup\20260911T233006Z`, manifest
  `F8005856EF68F1AF88B5CD70DC19452B4DA8FDCE689371E397131081F71539AA`,
  ma 3/3 artefakty obecne i zgodne rozmiarem;
- bieżące wyniki tasków `267014/1/1` nie dowodzą świeżej kopii po tych punktach.

Nie haszowano ponownie dużych artefaktów. Zanonimizowany stdout SQL jest
`LOCAL_ONLY`, 10 219 B, SHA-256
`EA575FADD1537B2BFDAC813F23766E838536CA366DB361869A5DA818FA9B704E`;
sanitowane podsumowanie ma 2 936 B i SHA-256
`F9E9F3B5D1F5CDC71683328D46AB72E88B32356AAF29ADB401E8B65669BADE07`.

## 3. Miejsca fizycznego zapisu

| Kategoria | Łańcuch | Ocena | Decyzja P3 |
|---|---|---|---|
| PostgreSQL PGDATA | `/var/lib/postgresql/data` → `C:\ai-lab-core\data\postgres` → junction `D:\ai-lab-data`; `pg_wal` i `pg_tblspc` pod PGDATA | `CURRENT_OBSERVED_ON_D`; exact inspect + READ ONLY SQL, brak zewnętrznych tablespaces/WAL | `KEEP`; nie migrować tych samych plików, zachować dokładny bind i junction |
| Backend application data | current `/data` → `C:\ai-lab-core\data` → junction D: | `CURRENT_BIND_OBSERVED`; junction current | `KEEP`; nadal zinwentaryzować dodatkowe cache/tmp/log paths |
| n8n | deklarowane `/home/node/.n8n` → `D:\ai-lab-data\n8n` | `HISTORICAL_ON_D`; target current | `KEEP` po exact mount readback |
| Open WebUI | deklarowane `/app/backend/data` → `D:\ai-lab-data\openwebui` | `HISTORICAL_ON_D`; target current | `KEEP` po exact mount readback |
| Ollama | deklarowane `/root/.ollama` → `D:\ai-lab-data\ollama` | `HISTORICAL_ON_D`; target current | `KEEP`; bez pobierania/przenoszenia modeli |
| Qdrant | deklarowane `/qdrant/storage` → external volume `qdrant_storage` | bieżący wolumen `UNKNOWN`; Docker VHD jest aktualnie na C: | `UNKNOWN_BLOCKING`; jeżeli relacja volume→VHD zostanie potwierdzona, przeniesienie Docker data disk na D: jest osobną operacją, nie nowym pustym volume |
| Docker layers/write layers/json logs | current VHD na C: | `CURRENT_C_RELOCATION_REQUIRED` | osobny, wspierany przez Docker Desktop move do `D:\ai-lab-data\docker-desktop`; nie łączyć z backend switch |
| Vision Worker profile/state | `C:\ChatGPT-Vision-Worker` | `CURRENT_C_RELOCATION_REQUIRED` | osobna session-safe relokacja do logicznego `C:\ai-lab-core\data\vision-worker`; bez odczytu/utraty profilu |
| Backupy | taski i `C:\ai-lab-core-backups`; R03 E: pozostaje odrębny | `NOT_APPLICABLE` dla zwykłego startu | `KEEP`; harmonogram, retencja i cele bez zmian |

Nie nadano `ALL_LIVE_WRITES_ON_D_PASS`.

## 4. Wybrany source i skutki startupu

Między main `483f9bf8...` i guard source `0ee0ea5...` nie ma zmian w
`backend/Dockerfile`, requirements ani migracjach Alembic. Source head Alembic
pozostaje `followup_assistant_chat_history_20260829`. To uzasadnia możliwość
użycia zgodnego istniejącego obrazu zależności, ale nie zastępuje bieżącego
image ID/digest ani SQL na docelowej bazie.

Preimage guarda `ddec6ea...` nie był skutkiem neutralnym:

1. `init_database()` jest bezwarunkowe i wykonuje `seed_admin()`. Przy obecnej
   roli/użytkowniku tylko odczytuje, ale przy braku może zapisać role/admina.
2. `start_backup_plan_reconciler()` jest bezwarunkowe. Reconciler tworzy lub
   aktualizuje durable sync events, wykonuje commity i może wywołać Supervisor.
   Przy zatrzymanym Supervisorze może zapisać status `failed/error`.
3. Pozostałe dispatchery mają flagi, lecz deklarowany live Compose ma
   `VISION_AUTOMATION_ENABLED=true`, `KNOWLEDGE_BASE_PROCESSING_ENABLED=true`,
   `KNOWLEDGE_BASE_VECTOR_WRITES_ENABLED=true`,
   `ADVANCED_ANALYSIS_ENABLED=true`, `DOCUMENT_PREPARATION_ENABLED=true` i
    `ASSISTANT_PIPELINE_V2_ENABLED=true`; aktywny historyczny override ustawia
    tylko `DOCUMENT_PREPARATION_ENABLED=false`. Bieżących effective env z
    kontenera nie odczytano i deklaracja nie jest dowodem procesu.
4. `VISUAL_V2_ENABLED` nie jest zadeklarowane w pliku `.env` i source default
   to `false`; nie jest to jednak obserwacja uruchomionego procesu.

Zaakceptowany źródłowo guard `0ee0ea5...` rozwiązuje pierwsze dwa skutki:
wyłączony seed wykonuje wyłącznie fail-closed readiness w transakcji READ ONLY,
a wyłączony reconciler nie tworzy tasku, sesji ani wywołania zewnętrznego.
Bieżący SQL potwierdził wymagany revision, rolę i konto administratora. Minimalny
kandydat P3 musi jednak przed cutoverem:

- wymusić w zatwierdzonym override wszystkie dispatch/producer flags na
  `false` i potwierdzić effective env projekcją bez sekretów;
- zachować zastany pending work: 18 document-preparation, 16 analysis i jeden
  Assistant; nie wykonywać ich ani nie zgubić podczas okna;
- rozstrzygnąć świeżość punktu rollbacku;
- zachować Supervisor `INTENTIONALLY_STOPPED`.

Guard jest odebrany jako source/test i nie jest wdrożony. Bez jawnych flag w
zatwierdzonym manifeście, decyzji o świeżości rollbacku i odbioru operacyjnego
nie istnieje zatwierdzony `BASE_READY_ONLY` manifest produkcji.

### 4.1. Guard pierwszego startu — source zaakceptowany, niewdrożony

W source `0ee0ea50943578e6e552aae23ce1688595ddc262` zapisano pięć
przetestowanych ścieżek:

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

Kampania w przypiętym obrazie R02 użyła wyłącznie syntetycznych ustawień i DB
contract fake; nie jest to PostgreSQL integration. Wyniki:

- preimage `ddec6ea...`: `2 passed / 9 failed`, oczekiwany exit `1`, przyczyna
  dotyczyła brakujących flag/readiness/reconciler controls;
- focused guard: `11 passed`, exit `0`;
- auth: osiem odpowiedzi `401`, zero uruchomień product lifespan, exit `0`;
- `/version` i R05-A4 API: `26 passed`, exit `0`;
- compileall czterech modułów i testu: exit `0`.

Python miał wersję `3.12.13`, pytest `8.3.5`. Testy nie uruchomiły produkcyjnego
PostgreSQL, migracji, modelu, dispatchera ani zewnętrznej sieci. Właściciel
odebrał guard jako `BASE_START_GUARD_SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED /
NOT_DEPLOYED`; nie jest to akceptacja PostgreSQL integration ani manifestu.
Historyczne zabezpieczenie WIP pozostaje dowodem pre-commit:

- `startup-guard-tracked-wip.patch`, SHA-256
  `E043325F662D7A443534CC884C23B95EEA340348EA0823E348DEAB27F64EC0E3`;
- `startup-guard-test-wip.patch`, SHA-256
  `78A8394E1B5E4B80AAEED3E3B7FAFFC773112DAD33BECD62E3C2ED6EB013A4DA`.

Draft P3 wiąże backend source z `0ee0ea5...`; zaakceptowany source DATA_ONLY
`cb6e225...`, stary ZIP i Web zachowują własne pochodzenie. Produkcyjny manifest
pozostaje `NOT_APPROVED_FOR_START`.

## 5. Wybrany najmniejszy pakiet operacyjny

Preferowany pierwszy pakiet po usunięciu blockerów to
`P3 CORE BACKEND SOURCE SWITCH`, bez relokacji danych, VHD/profile, Web build,
task install, Supervisora i cleanupu.

Zakres planowany:

1. `KEEP` wszystkich potwierdzonych bindów danych D: oraz live Web
   `1.0.2+41`; obecny Web TEST_ONLY z API `18004` nie jest wdrażany.
2. Z Git utworzyć inertny payload dokładnie z `0ee0ea5...:backend` w istniejącym
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

`PREPARATION_PARTIAL` pozostaje z powodu dwóch operacyjnych bramek i potrzeby
ochrony zastanego pending work:

1. `ROLLBACK_DATA_FRESHNESS_OWNER_DECISION_REQUIRED`: task 1 ma
   `SCHED_S_TASK_TERMINATED`, taski 2/3 wynik `1`, brak zachowanych końcowych
   logów; odebrany punkt full z 2026-09-08 i punkty DB/n8n z 2026-09-11 nie
   obejmują jawnie zmian do bieżącej obserwacji 2026-09-16.
2. `PRODUCTION_START_MANIFEST_NOT_APPROVED`: draft ma wymagane flagi `false`,
   lecz nie został zainstalowany, odczytany jako effective ani zatwierdzony.
3. `PENDING_WORK_MUST_BE_PRESERVED`: 18 document-preparation, 16 analysis i
   jeden Assistant pozostają zastanym stanem, którego P3 nie może uruchomić,
   zdublować ani zgubić.

Dokładne akcje komponentowe znajdują się w
`docs/recovery/R04_D21_P3_CHANGESET.csv`. W tej kontynuacji testy aplikacji,
Flutter, Web build, migracje i runtime smoke kandydata były `NOT_RUN`. Wykonano
wyłącznie bieżący metadata read i jedną transakcję PostgreSQL READ ONLY.

Jedyna następna decyzja właściciela: czy przyszły P3 może użyć odebranego full
pointu z 2026-09-08 razem z DB/n8n z 2026-09-11 mimo nieobjętych zmian do
2026-09-16 i niezerowych wyników ostatnich tasków, czy przed cutoverem wymagany
jest nowy, zweryfikowany punkt rollbacku. Bez tej decyzji nie ma zgody na
cutover, P4/P5 ani R06.
