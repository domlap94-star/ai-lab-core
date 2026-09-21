# R04 / D-21 / P4-A — pakiet aktywacji jednego startu

Status: `P4A SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / P4B_PARTIAL_SAFE_INACTIVE / EXACT_ROLLBACK_SAFE_RECIPE_ACCEPTED / REPLACEMENT_READ_ONLY_PREFLIGHT_PARTIAL / HOST_TASK_FORMATTER_CIMCLASS_FAILURE / NO_UAC / NOT_INSTALLED / GLOBAL_START_MANIFEST_NOT_APPROVED`

Pakiet: `R04-D21-P4A-STARTUP-ACTIVATION-20260917T210051Z`
Decyzja: `D-21`
Podstawa: P1 launcher source `2e69622bc6a0b4888427f8ae5be119377aed26d9`,
DATA_ONLY source `cb6e22506a0fecc440400566293524536847b9b0`, P3 backend
source `0ee0ea50943578e6e552aae23ce1688595ddc262`; kontynuacja P4/A source
`8756314f51a76091a483cfc9b677a05c7f67f315`.

## 1. Granica i przyjęty stan P3

Właściciel przyjął `P3 CORE_BACKEND_SOURCE_SWITCH_ACCEPTED /
LIMITED_RUNTIME_SCOPE` dla OP_ID
`R04-D21-P3-CORE-SWITCH-20260917T141404Z`. Odbiór obejmuje wykonane
przełączenie backendu, 592/592 bajtów payloadu, zachowaną DB/schema i pending
`18/16/1`, preservation `116 + 87 = 203/203` oraz późniejszy readback dwóch
warstw środowiska `11/11 MATCH`, w tym `9/9` przełączników `false`.

Odbiór nie oznacza pełnego P3/R04, odczytu obiektu `Settings` w pamięci,
historii wszystkich dispatcherów, globalnego braku zapisów ani zgody na
launcher, relokację, P4-B/P5 lub nowe funkcje. Globalny manifest pozostaje
`NOT_APPROVED_FOR_START`.

## 2. Wynik P4-A

P4-A przygotowuje wyłącznie nieaktywny zestaw do osobnego review:

- dokładny minimalny payload przyjętego launchera P1 i helpera istniejących
  kontenerów;
- draft manifestu oparty na bieżących tożsamościach sześciu kontenerów;
- rollbackowe kopie pięciu definicji tasków i dwóch obecnych wejść użytkownika;
- wyłączony draft taska `NEXT Stabil - Host`, 1 536 B, SHA-256
  `013ED40479F65861E92A329077F7E2ECCBF04FB40C6891C96CD0638BB4B7FD21`;
- changeset triggerów i kolejność instalacji uniemożliwiającą przypadkową
  aktywację.

Lokalny pakiet jest w chronionym stagingu:

`C:\ai-lab-core-staging\recovery\R04_D21_P2_20260915T212340Z\p4-startup-activation-20260917T210051Z`

Pierwotny indeks 16 plików ma SHA-256
`DC76525E49B77C7CA791B9724D38F9E26C2FC7FDA8513A2403B7D167481ACB72`.
Pozostaje historycznym dowodem preimage; kontynuacja ma oddzielny indeks po
zmianie źródeł. Efektywny indeks kontynuacji obejmuje 18 przypiętych plików,
ma 4 222 B i SHA-256
`78966E33376D4A6E118B79AFE2A844403AFEF1B0E56BB8A972B438FB55428482`.
Całość jest `LOCAL_ONLY / NOT_INSTALLED / NOT_APPROVED`.

Korekta tożsamości zachowuje oba starsze indeksy. Nowy indeks 18 plików ma
5 545 B i SHA-256
`3FCF1938111C9746FB9F4B5D57F1F98C5085099503B1385B862B0F68776303A9`;
zmienionym plikiem pakietu jest wyłącznie nieaktywny draft, 15 469 B,
SHA-256 `E17DDCA39D4D3BC7BBAD6F0688738DAA1B7C28B5810BB611C83A940234A28403`.

## 3. Minimalny payload

| Rola | Źródło | Docelowa ścieżka po osobnej zgodzie | Bajty | SHA-256 | Stan dziś |
| --- | --- | --- | ---: | --- | --- |
| Launcher | `operations/runtime/start-host-services.ps1` z kontynuacji P4/A | `C:\ai-lab-core\operations\runtime\start-host-services.ps1` | 63 377 | `7BB24450C0B0EFDD8321935B129A25CEDD788BA3B8951965EF8E4A09BBF33871` | Brak w instalacji |
| Runtime validator | `operations/runtime/startup-runtime.ps1` z kontynuacji P4/A | `C:\ai-lab-core\operations\runtime\startup-runtime.ps1` | 69 194 | `349404C3B8DE7B2502437E023BEC09464428856A6D8F120EAFBD68E1ABCF4FA7` | Brak w instalacji |
| Existing-only helper | `operations/windows/start-compose-after-docker.ps1` z P1 | `C:\ai-lab-core\operations\windows\start-compose-after-docker.ps1` | 880 | `91C763F5D0FF6CC7184E0B238EA6A6047CBB3FB13F88917777F4E0696E9667EC` | Do zastąpienia starego helpera `445AFFC0...EDECC5` |
| P3 override | już zainstalowany plik | `C:\ai-lab-core\operations\runtime\approved-compose\R04-D21-P3-core.override.yml` | 1 174 | `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86` | KEEP |

Nie kopiuje się całego `operations` z recovery. Zainstalowane gatewaye i
Supervisor pozostają w swoich obecnych bajtach; draft manifestu wiąże właśnie
te bajty, nie ich recoveryowe odpowiedniki.

## 4. Bieżący zestaw runtime użyty do draftu

Pierwotny `runtime-inventory.json` punktu `20260917T082022Z` (captured at
`2026-09-17T08:21:56.3539611Z`, 11 349 B, SHA-256
`D3DE5C85E73F9B6771A5480D9A7E90A923CE0079BB2850702D5081E884D0EBC0`)
zawierał pełne ID kontenerów, image ID, RepoDigests i mounty czterech usług.
Pierwotny draft P4/A z commita `daf0931c...` zachował tylko zgodne skróty
widoczne wcześniej w UI, lecz miał inne rozwinięcia pozostałych znaków. Brak
innego pierwotnego odczytu potwierdzającego wartości draftu. Klasyfikacja:
`DRAFT_TRANSCRIPTION_ERROR_PROVEN`; nie ma dowodu recreate, zmiany obrazu,
sprawcy ani utraty danych.

Jedna zatwierdzona lista projektu `ai-lab-core`, obejmująca zatrzymane zasoby,
dała 10 rekordów. Dla każdej z czterech ról istniał dokładnie jeden kandydat.
Bieżące pełne ID tych kontenerów i ich obrazów są identyczne z pierwotnym
runtime inventory. Pierwszy formatter odczytał Qdrant, a dla trzech bindów
zakończył się kontrolowanym błędem opcjonalnego `Mount.Name`; po poprawce i
17/17 asercjach offline dokończono tylko te trzy zapisane selektory, bez drugiej
listy projektu i bez ponowienia Qdrant.

| Usługa | Bieżący pełny ID / nazwa | Image ID / RepoDigest | Stan i daty | Dane / klasyfikacja |
| --- | --- | --- | --- | --- |
| qdrant | `daa3b0b86b748aa3a52052dac08bfde499cf19ad61600a1325e09061a5451fae` / `/qdrant` | `sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286`; `qdrant/qdrant@sha256:0bd98fa7...d5286` | running; created `2026-08-21T14:19:38Z`; started `2026-09-14T14:41:10Z`; restart 0 | `qdrant_storage:/qdrant/storage:rw`; `DRAFT_TRANSCRIPTION_ERROR_PROVEN` |
| n8n | `a44e719ecfecf72a199b4f8b3ec9d7503548d2098601e767d5e9e6503d37081c` / `/n8n` | `sha256:3c07c723326dd72e46a6969181c66a75260b7a204b9b77ba1ece6d594489c684`; `docker.n8n.io/n8nio/n8n@sha256:3c07c723...9c684` | running; created `2026-08-19T22:21:37Z`; started `2026-09-14T14:41:11Z`; restart 0 | `C:/ai-lab-core/data/n8n:/home/node/.n8n:rw`; `DRAFT_TRANSCRIPTION_ERROR_PROVEN` |
| open-webui | `9575ca068b8cc17d0b2ac72e0062867c5c74650c12619bf6ecc6b48d1ec54c39` / `/open-webui` | `sha256:a26effeb220e132482bf7e0560b3404843e7bc40d23051144e062960df8df6b0`; `ghcr.io/open-webui/open-webui@sha256:a26effeb...f6b0` | running; created `2026-08-19T06:14:31Z`; started `2026-09-14T14:41:11Z`; restart 0 | `C:/ai-lab-core/data/openwebui:/app/backend/data:rw`; `DRAFT_TRANSCRIPTION_ERROR_PROVEN` |
| ollama | `7ff1c45ea12cb9a26df1540cdeb5993c30fe12ac1d9c199ea7ce776847aac083` / `/ollama` | `sha256:ec24bcaa2a810eb74171ce7c517813ef4821ed678988845e8d76cf62467036d4`; `ollama/ollama@sha256:ec24bcaa...036d4` | running; created `2026-08-19T06:12:25Z`; started `2026-09-14T14:41:10Z`; restart 0 | `C:/ai-lab-core/data/ollama:/root/.ollama:rw`; `DRAFT_TRANSCRIPTION_ERROR_PROVEN` |

Qdrant, n8n, Open WebUI i Ollama mają project/service labels `ai-lab-core` /
odpowiednią rolę, policy `unless-stopped`, prawidłowe loopback porty i sieć
`ai-lab-network`. Historyczny readback backend/PostgreSQL z
`2026-09-18T00:02:24Z`–`00:02:25Z` pozostaje źródłem ich poprawnych ID i
RepoDigests. Lista pokazała również cztery zatrzymane kontenery drillu z label
`service=backend`; nie zastępują one działającego, dokładnie przypiętego
`ai-lab-backend`.

Safe projections mają odpowiednio 21 717 B / SHA-256
`7FB247C58E9B1675D35572356C485219C14332771B48DF636F6CDFF75CA0B184`
oraz 16 859 B / SHA-256
`9F4980132ACCF73F4790742849862963E5629386C12E4F225676899DB7EE3B66`.
Draft wiąże teraz 6/6 pełnych ID, image ID i RepoDigest, lecz nadal ma
`approval.status=NOT_APPROVED`. Fizyczny backing `qdrant_storage` i Docker/WSL
VHD pozostają `UNKNOWN`; nie wolno zamieniać tego w `ALL_DATA_ON_D_PASS`.

## 4.1. Wynik review tożsamości i zimnego startu

Na preimage `daf0931cff28944e5df528f63cd95b4d99dd041a` odtworzono:

- zmianę wyłącznie pełnego ID: `valid=true`, bez błędu i bez blokady;
- kolejność draftu `backend, postgres, ...`: fake start backendu następował
  przed PostgreSQL, bez obserwacji health;
- brak ról `startup_launcher`, `startup_runtime`, `backend_override` oraz sześć
  placeholderów digestów.

Poprawka `NEXT_STABIL_STARTUP_PACKAGE_V1` egzekwuje oddzielnie service label,
runtime name i pełny ID, wiąże trzy brakujące role plików, rozróżnia normalny
RepoDigest od backend-only `LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST` oraz
porządkuje sześć usług. PostgreSQL ma wymaganie `HEALTHY`; backend zależy od
jego potwierdzonego health i nie jest startowany przy `starting`, `UNKNOWN` lub
deadline. Tryb local-image wymaga pozytywnie odczytanej pustej listy digestów;
timeout i błąd odczytu nie uruchamiają fallbacku.

Kampania offline Windows PowerShell 5.1 przeszła: P1 plan `53`, real adapters
`51`, DATA_ONLY `44` i P4 package `14` asercji. Są to asercje syntetycznych
granic, nie testy live startu ani P4-B.

Aktualny odczyt HTTP z 2026-09-17T21:00:51Z dał backend health `200`, public
gateway health `200` i publiczne `/control` `404`. Projekcja pól `/version`
utraciła szczegóły; P3 readback pozostaje właściwym dowodem source/schema.

## 5. Zainstalowane skrypty i narzędzia

| Element | Bieżąca ścieżka | SHA-256 / wersja | Decyzja P4-A |
| --- | --- | --- | --- |
| Public Gateway | `C:\ai-lab-core\operations\gateway\public_web_server.cjs` | `59B21389A25EAD7F73384F3267AD0238F4563B85589D823161A5853ECE41B37A` | KEEP, task jako executor |
| Private Gateway | `C:\ai-lab-core\operations\gateway\web_server.cjs` | `AD9D05F35A86AEDAF2F1522EE330788AD9312040525E5B65AF389EC07DFC06ED` | KEEP, task jako executor |
| Supervisor | `C:\ai-lab-core\operations\supervisor\server.js` | `4CFB7F9E3D97521D8D0F6D588BB119AB34C9D52FAD498AA520368CD13B170701` | KEEP, `INTENTIONALLY_STOPPED` |
| Docker CLI | instalacja Docker Desktop | `46D8A5BD7523C575FB276A75296AB19ABB9BF277D334169C665E521E46DBC2A4`; 29.8.0 | external tool |
| Docker Desktop | instalacja użytkownika | `F508DE4FA1F4A9E2EB8A2DDDE64A10D0CD45414E88CC11E9CD4120247E217799`; 4.91.0.239619 | external tool |
| Node | `C:\Program Files\nodejs\node.exe` | `9A4EB5F1C29C6A2E93852EAD46B999E284A6A5CA8BAB4D4E241D587D025A52DE`; 24.18.0 | external tool |

## 6. Konsolidacja wejść

| Wejście | Stan obserwowany | Rola docelowa | Zmiana dopiero w P4-B |
| --- | --- | --- | --- |
| `NEXT Stabil - Docker Desktop` | enabled, logon trigger | `REPLACE_TRIGGER` | usunąć niezależny logon trigger po zainstalowaniu kompletnego host taska; nie zmieniać instalacji Dockera |
| `NEXT Stabil - Docker Compose` | enabled, logon trigger, stary helper | `DISABLE_DUPLICATE_TRIGGER` | wyłączyć stary automatyczny start; launcher nie wykonuje `compose up` |
| `NEXT Stabil - Public Gateway` | enabled/running, logon trigger | `REUSE_EXECUTOR` | zachować task enabled/on-demand, usunąć jego niezależny trigger |
| `NEXT Stabil - Private Gateway` | enabled/ready, logon trigger | `REUSE_EXECUTOR` | zachować task enabled/on-demand, usunąć jego niezależny trigger |
| `NEXT Stabil - Supervisor` | enabled/ready, logon trigger | `REUSE_EXECUTOR` + `INTENTIONALLY_STOPPED` | zachować executor, usunąć trigger; launcher nie startuje go |
| `NEXT-Stabil-Host.cmd` w Startup | aktywny wrapper wskazujący brakujący launcher | `DISABLE_DUPLICATE_TRIGGER` | wyłączyć/przenieść przed instalacją launchera |
| `NEXT Stabil.lnk` | bezpośrednio otwiera istniejący klient Windows | `HOLD_WITH_REASON` | zachować do implementacji i odbioru `OPEN_AFTER_BASE_READY` |
| Backup 1/2/3, legacy Daily Backup, Trash Purge | odrębne harmonogramy | `KEEP_SEPARATE_SCHEDULE` | bez zmian w P4-B |

Task nie jest tym samym co trigger. Gatewaye i Supervisor pozostają potrzebnymi
wykonawcami on-demand; plan nie usuwa ich całych tasków.

Staging zawiera też pięć nieaktywnych draftów `after`: taski Docker Desktop i
Docker Compose bez triggerów i z `Enabled=false`; taski Public/Private/Supervisor
bez triggerów, nadal `Enabled=true`. Żaden XML nie został zaimportowany.

## 7. Sekwencja P4-B — NOT_EXECUTED / REQUIRES_SEPARATE_APPROVAL

1. Zweryfikować brak driftu pełnych identyfikatorów i zachować rollback XML,
   wrappera i skrótu. Efekt: wyłącznie punkt cofnięcia. Rollback: nie dotyczy.
2. Wyłączyć lub bezpiecznie przenieść `NEXT-Stabil-Host.cmd` ze Startup.
   To musi nastąpić **przed** pojawieniem się launchera pod jego docelową
   ścieżką. Rollback: przywrócić dokładne bajty tylko po przywróceniu poprzedniej
   semantyki startu.
3. Zarejestrować `NEXT Stabil - Host` jako `Enabled=false`, principal `domai`,
   `InteractiveToken`, `LeastPrivilege`, `IgnoreNew`, limit `PT15M`. Limit jest
   skończony i obejmuje budżet Engine 180 s, sześć ograniczonych etapów
   kontenerów, dwa host-service oraz finalne readiness; nie oznacza gwarancji
   zakończenia w tym czasie. Nie uruchamiać.
   Rollback: usunąć tylko dokładnie nowy task po potwierdzeniu identity.
4. Usunąć wyłącznie automatyczne triggery z tasków Public/Private/Supervisor,
   pozostawiając executory enabled/on-demand. Wyłączyć legacy Docker Desktop i
   Docker Compose jako konkurujące wejścia dopiero po kontroli definicji.
   Rollback: import dokładnych zachowanych XML; nie startować tasków.
5. Zainstalować trzy pliki payloadu przez atomową kopię i zweryfikować hash.
   Nie kopiować recovery jako rootu. Rollback: przywrócić stary helper i usunąć
   wyłącznie dwa wcześniej nieistniejące pliki.
6. Zainstalować osobno zatwierdzony manifest z `APPROVED` dopiero po uzupełnieniu
   RepoDigest/identity i review właściciela. Obecny draft pozostaje
   `NOT_APPROVED`; jego instalacja nie uprawnia do startu.
7. Włączyć jeden trigger host taska dopiero po fail-closed walidacji całego
   zestawu. Bez `pull/build/create/recreate/up`, migracji i naprawy mountów.
8. W osobnym oknie odbiorowym wykonać kolejno: normalny start, drugi start bez
   duplikatów, Docker ready/not-ready, intentional stop Supervisora, port
   conflict, image/mount mismatch, `/control` boundary, logon/reboot i rollback.

Każdy krok jest `NOT_EXECUTED / REQUIRES_SEPARATE_APPROVAL`. Nieaktywne XML w
stagingu nie zostało zaimportowane.

## 8. Rollback i ryzyka

- Rollback triggerów przywraca definicje, ale nie może automatycznie uruchomić
  Supervisora ani starego compose-up. Każdy start po rollbacku wymaga osobnej
  kontroli skutków.
- Timeout po przekazaniu startu jest `UNKNOWN`, nie dowodem braku startu i nie
  pozwala na retry.
- Zmiana taska lub wrappera może pozbawić użytkownika startu albo go zdublować;
  dlatego host task pozostaje disabled aż do kompletnego zestawu.
- Manualny skrót UI nie może być przełączony na launcher bez funkcji
  `OPEN_AFTER_BASE_READY`; w P4-A pozostaje bez zmian.
- Supervisor jest `INTENTIONALLY_STOPPED`. Jego task pozostaje wykonawcą, ale
  bez automatycznego triggera i bez startu przez launcher.

## 9. Backupy i dane D:

Backup 1/2/3 używają `run-backup-schedule.ps1`, który korzysta z Docker/backend,
ale nie z Supervisora. Legacy backup również nie wymaga Supervisora. Ostatnie
wyniki tasków `267014/1/1` nie są dowodem udanej pracy harmonogramu, dlatego
stan pozostaje `SCHEDULED_BACKUP_OPERATION_NOT_YET_VERIFIED /
REPAIR_PENDING`. Manualny punkt z 17 września nie zmienia tej oceny.

Junction `C:\ai-lab-core\data -> D:\ai-lab-data` i pięć przyjętych bindingów
DATA_ONLY pozostają bez zmian. Qdrant volume, Docker/WSL VHD, profile i inne
ciężkie lokalizacje nie są rozliczone jako D:. P4-A nie wykonuje relokacji i nie
usuwa tej bramki D-21.

## 10. Bramy przed P4-B

- P4/A source/offline/identity package ma odbiór właściciela; identity 6/6 nie
  jest już blockerem, lecz repository/global manifest nadal nie ma zgody startowej;
- właściciel dopuścił przygotowanie ograniczonego startu przed relokacją
  Qdrant/VHD/profile, z jawnym zachowaniem tych braków jako ryzyka — nie jest to
  akceptacja fizycznego położenia danych;
- właściciel dopuścił zachowanie oddzielnego skrótu UI; `OPEN_AFTER_BASE_READY`
  pozostaje poza Phase B i nie jest pozornie domykane przez launcher;
- dokładne, bieżące definicje triggerów bez driftu;
- osobny plan odbioru harmonogramu backupu;
- dokładne potwierdzenie właściciela Phase B dla opublikowanego OP_ID/hashów;
  obecny repository draft nie jest zatwierdzonym manifestem startowym.

Następny krok: po publikacji Phase A właściciel wysyła jedno dokładne zdanie
potwierdzenia P4/B albo odmawia. Bez tej zgody nie wolno wykonać żadnego kroku
instalacji lub aktywacji.

## 11. P4/B Phase A — dokładne okno przygotowane, bez instalacji

OP_ID: `R04-D21-P4B-WINDOW-20260918T084652Z`. Właściciel zaakceptował P4/A
source `8756314f51a76091a483cfc9b677a05c7f67f315` i evidence
`8a156e0c738699b4bfee01fb98f0d10f01c803ba` jako
`SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / NOT_INSTALLED`. Phase A
przygotowała pakiet, a właściciel następnie zatwierdził jednorazową Phase B na
opublikowanym HEAD `bd9acc14f6f0d12bacdb5a9a8dd5a8f69a5b333b`. Zgoda została
skonsumowana przez rozpoczętą operację i nie jest stałym uprawnieniem.

Fresh read-only preflight potwierdził sześć exact kontenerów jako running bez
restartu w oknie, PostgreSQL healthy, backend P3 na oczekiwanym ID/mountach,
Public Gateway i backend health `200`, publiczne `/control*` `404`, brak
listenerów `8787/8788` oraz niezmieniony stan Supervisor
`INTENTIONALLY_STOPPED`. Zadania backupowe nie były uruchamiane; ich ostatnie
wyniki pozostają osobnym dowodem, a globalny brak aktywnej pracy nie został
ogłoszony. Dodatkowy wpis HKCU Run dla Docker Desktop istnieje i w tym oknie
pozostaje bez zmian, poza allowlistą mutacji P4/B.

Resource preflight: Windows physical available `7.026 GiB`, commit reserve
`36.421 GiB`, C: free `577.991 GiB`, D: free `854.714 GiB` — dotychczasowe
progi host/disk przechodzą. Bieżąca dostępność puli Docker/WSL i bieżące użycie
swap pozostają `UNKNOWN`, ponieważ Phase A nie wykonywała WSL ani kontenera
pomiarowego. Configured swap to `8 GiB`; nie wolno przepisać tego na pełny
resource-gate PASS.

Dokładne artefakty Phase A w chronionym stagingu:

- P4/A effective index: `3FCF1938111C9746FB9F4B5D57F1F98C5085099503B1385B862B0F68776303A9`;
- Phase-A window index: `F99FF54E06DD9508992D9D41D38CE5C8BF54D02748814EDEA619BD046B772FF8`;
- proposed manifest target `C:\ai-lab-core\operations\runtime\startup-set.json`,
  SHA-256 `E66F22A7EC433183940FC3014E1B9F8C1DBE535375EC2D6580B958B55586010C`;
- exact task/file changeset SHA-256
  `FC0E884F531F93E922FF0C84AC87D6B6DBF34EC825B6E86796DE702ABE328F0C`;
- launcher/runtime/helper SHA-256 odpowiednio `7BB24450C0B0EFDD8321935B129A25CEDD788BA3B8951965EF8E4A09BBF33871`,
  `349404C3B8DE7B2502437E023BEC09464428856A6D8F120EAFBD68E1ABCF4FA7`,
  `91C763F5D0FF6CC7184E0B238EA6A6047CBB3FB13F88917777F4E0696E9667EC`;
- P3 override pozostaje KEEP: `F99BABA92A72DFA366367470181AB1BF9DEC19D71ADBD2CBF1632F0B74DE4E86`.

Proponowane XML SHA-256: Docker Compose disabled/no-trigger
`235F272C9C9BE19C1B1E67C1E7817189943F56309CDD73E7C9949E33C002FD3D`,
Docker Desktop disabled/no-trigger
`ED350348A5AD475B9866BE6AA86AD41E3694A60B68B312CC2CA38A66712D1EE5`,
Host disabled `28204912151A622AD05625D0E32578C354BE7A3F800E3E3DD76F0C10D7429106`,
Host enabled/logon `9AFA131B95498EDFEF78FD6CD411C9E03FCBD2611E05C105B3EFC536FD4190F0`,
Host enabled/on-demand `7EAA8E6B24F2581C7F7791BF261DACB962F18A9FB8E8309E10977D4599EA546E`,
Private/Public/Supervisor on-demand no-trigger odpowiednio
`0CEBB54538D713EB283EF6F95D9ED7933C5E954147621B71906D0F68D27F05EE`,
`1F1265B7C0FE2309317BB26123255C2CA5C8A6E4FEF9B70553B6D1A18DC75169`,
`22AFAFCB41FF0B5958417452D6EEF90B5C559E2520DFC77B4A61EA0EE0D19B4F`.

Walidacja Phase A zakończyła się exit `0`; stdout SHA-256
`FA967B2592EF3609B4FA00AB2AFDF557BC24A7A6F25735EA184917DAA2BEF8E1`.
Parser Windows PowerShell 5.1 przyjął trzy pliki payloadu, wszystkie XML i JSON.
Pure validator uruchomiony bez adapterów na zamierzonym canonical target odmówił
wyłącznie przez oczekiwane przed instalacją `FILE_MISSING` dla launcher/runtime
i `FILE_HASH_MISMATCH` legacy helpera. Nie zwrócił approval mismatch; dowodzi to
fail-closed pre-install, nie wykonania P4/B.

Phase B przeniosła dokładny wrapper poza Startup i utworzyła Host jako
disabled/no-trigger. Aktualizacja pierwszego istniejącego taska została
odrzucona przez Windows (`Access denied`); formalny proces `RunAs`/UAC został
anulowany i nie był ponawiany. Pięć istniejących tasków zachowuje preimage i
stare triggery. Launcher/runtime/manifest nie zostały zainstalowane, helper nie
został zastąpiony, warm runs wynoszą `0/2`, a żadnego taska ani usługi nie
uruchomiono. Próba SAFE_INACTIVE normalizacji została wykonana raz i zatrzymała
się na tej samej ochronie istniejących tasków. Stan to `PARTIAL_SAFE_INACTIVE /
INSTALLATION_BLOCKED_UAC_CANCELLED`, nie P4/B PASS.

Reboot/logoff/cold-stop, backup/restore, relokacja, Supervisor, P5 i R06
pozostają poza zakresem. Następny krok wymaga nowej bieżącej decyzji, świeżego
bounded drift check oraz obecności właściciela przy jednym monicie UAC; dopiero
potem wolno wznowić dokładną kolejność przed instalacją payloadu.

## 12. P4/B resume — zatrzymanie przed mutacją

Właściciel zatwierdził jednorazowe wznowienie
`R04-D21-P4B-RESUME-20260918T112015Z` z recipe index
`9DD6A85B14B307DA698513849EC0DF9E81ED7EBDF278B1064329AA64234B6E7E`.
Recepta miała SHA-256
`D8E2868F51F04D179C3749CA6E0691C307BA8B7ABEB668CC9987E60D4A350F61`,
a input index SHA-256
`ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA`.
Dokładnie jeden `RunAs`/UAC został uruchomiony i zaakceptowany. Instalator
potwierdził elevated token, właściwy SID i input index, lecz zakończył się na
pierwszym guardzie kontenera o `2026-09-18T11:58:10.5820968Z`.

Nie był to mismatch kontenera. `Start-Process -ArgumentList` w Windows
PowerShell 5.1 rozdzielił zawierający spacje Go-template dla `docker inspect`;
Docker otrzymał fragment `-}}{{range` jako flagę. Stderr ma 171 B i SHA-256
`37965294C541CC98E4D13C3EBB63DE7C24BCC71EFC2ECAE89DB3BD02D9523CBD`.
Event log ma SHA-256
`618B31443F27C22E0C745AB54D407FE4FED4C0177A85B5B1B5331D851E0C6339`
i jawnie zapisuje `mutation_started=false`.

Nie wykonano drugiego UAC, poprawki recepty, task update, instalacji plików,
manifestu, warm runu ani rollbacku resume. SAFE_INACTIVE rollback nie był
potrzebny, ponieważ recepta nie przekroczyła granicy mutacji. Stan po pierwszym
oknie pozostaje: wrapper poza Startup w chronionym rollbacku, Host
disabled/no-trigger/never-run, pięć tasków na preimage, legacy helper bez zmiany,
payload/manifest nieobecne, warm runs `0/2`. Obie jednorazowe zgody są
skonsumowane. Następny krok wymaga osobno przejrzanej recepty z bezpiecznym
transportem argumentów natywnych, nowego indeksu i nowej decyzji właściciela.

## 13. P4/B native argument transport — recepta gotowa do review

W zakresie `R04-D21-P4B-RECIPE-TRANSPORT-FIX-20260918T152017Z` nie wykonano
nowego UAC ani instalacji. Zachowana funkcja preimage przekazała dokładny guard
do nieszkodliwego programu argv i odtworzyła rozpad 7 oczekiwanych argumentów na
56. Poprawiona recepta przejęła przypięte funkcje
`ConvertTo-WindowsNativeArgument`, `Join-WindowsNativeArguments` i
`Invoke-BoundedNativeCommand` z accepted source
`8756314f51a76091a483cfc9b677a05c7f67f315`. Jej main block i kolejność
guardów/mutacji pozostały bez zmian.

Końcowa recepta ma SHA-256
`5F310C64DFB21F55B4403E9A738B80344EB9CEC38536EE4FD2081F6422F1FD67`;
LOCAL_ONLY index ma SHA-256
`43F285C2E82032F6914F5C5F8BA0653C85EC44F2A4F24E13D835A7C02162A2A9`.
Windows PowerShell `5.1.26100.8894` zaliczył 17/17 przypadków i 120 asercji.
Po tym PASS wykonano dokładnie jeden niepodniesiony `docker container inspect`
backendu przez tę samą funkcję i template; exit 0 potwierdził właściwy ID,
obraz, mounty, port, sieć oraz `RestartCount=0`. Nie był to pełny preflight
sześciu usług.

Status narzędzia: `RECIPE_NATIVE_ARGUMENT_TRANSPORT_FIXED /
TESTED_ON_POWERSHELL_51 / READY_FOR_REVIEW`. Stan instalacji nie zmienił się:
wrapper pozostaje w rollbacku, Host disabled/no-trigger/never-run, pięć tasków
na preimage, launcher/runtime/global manifest nieobecne, helper legacy, warm
runs `0/2`, globalny manifest `NOT_APPROVED_FOR_START`.

Przed przyszłą operacją kolejność nadal brzmi: review dokładnej recepty i
indeksu -> nowa jednorazowa decyzja właściciela -> świeży bounded drift check ->
co najwyżej jeden osobno zatwierdzony UAC -> istniejąca zamknięta sekwencja
instalacji. Obecny wynik nie upoważnia do żadnego z tych skutków operacyjnych.

## 14. P4/B exact-recipe preflight — blokada wiązania baseline paths

Dla przygotowanego external resume ID
`R04-D21-P4B-RESUME-20260918T163031Z` wykonano wyłącznie statyczny,
read-only preflight przed pytaniem właściciela o UAC. Recepta 45,009 B ma
oczekiwany SHA-256
`5F310C64DFB21F55B4403E9A738B80344EB9CEC38536EE4FD2081F6422F1FD67`,
a indeks 7,454 B ma oczekiwany SHA-256
`43F285C2E82032F6914F5C5F8BA0653C85EC44F2A4F24E13D835A7C02162A2A9`.
Wszystkie `17/17` wpisów indeksu recepty i `29/29` wpisów wskazanego input
indexu istnieją oraz mają zgodny rozmiar i hash. Katalog
`installer-execution` nie istniał, więc nie wykryto kolizji historycznych
wyników.

Preflight wykazał jednak deterministyczny błąd kontraktu wejściowego.
`Assert-ContainersUnchanged` czyta każdy baseline jako
`Join-Path $resumeRoot "docker-container-<service>-pass2-command.json"`, gdzie
`$resumeRoot` wskazuje katalog `p4b-native-transport-20260918T152017Z`.
Żaden z sześciu plików nie istnieje pod tą ścieżką. Wszystkie sześć poprawnych,
indeksowanych i hash-matched records znajduje się w katalogu poprzedniego,
skonsumowanego `r04-d21-p4b-resume-20260918t112015z`.

Niezmieniona recepta zatrzymałaby się z błędem odczytu baseline przed pierwszym
wywołaniem Docker i przed mutacją. Kopiowanie rekordów do nowego katalogu albo
zmiana `$resumeRoot` zmieniłyby przejrzany kontrakt wykonania; nie wykonano
takiego obejścia. Nie uruchomiono Docker, Task Scheduler, HTTP, UAC, instalatora,
rollbacku ani warm runu. Status pozostaje `PARTIAL_SAFE_INACTIVE`, warm runs
`0/2`, globalny manifest `NOT_APPROVED_FOR_START`.

Transport natywnych argumentów zachowuje ograniczony odbiór dla dokładnie
przejrzanych bajtów i wcześniejszego dowodu, ale recepta nie otrzymuje statusu
`ACCEPTED_FOR_EXACT_RESUME`. Następny krok to osobno przygotowana i przetestowana
recepta/index z jawnym bindingiem sześciu baseline paths; dopiero jej review może
poprzedzić fresh live drift check i nowe jednorazowe potwierdzenie UAC.

## 15. P4/B input binding — dokładny pakiet LOCAL_ONLY do review

Zakres `R04-D21-P4B-INPUT-BINDINGS-20260918T192258Z` nie wykonał UAC,
Dockera, Task Schedulera, HTTP ani instalacji. Fail-before rzeczywistej funkcji
ze starej recepty `5F310C64...1FD67` potwierdził, że pierwszy odczyt baseline
szukał `docker-container-backend-pass2-command.json` pod rootem recepty i
kończył się przed fake Docker oraz przed granicą mutacji.

Nowa recepta rozdziela: `recipePackageRoot`, przypięty `inputIndexPath` i
jednorazowy `ExecutionOutputRoot`. `Resolve-InstallerInputs` odczytuje indeks
raz, wymaga 29 unikalnych ról, sprawdza dokładną ścieżkę, rozmiar i SHA-256,
przechowuje zweryfikowany bufor, a następnie parsuje z niego sześć records.
`Assert-ContainersUnchanged` otrzymuje te same rozstrzygnięte obiekty; nie buduje
ponownie basename ani nie wybiera pliku z CWD. Ścieżki względne są rozstrzygane
wyłącznie względem rootu indeksu. Root escape, reparse, duplikat, brak, zmiana
serwisu lub uszkodzony JSON kończą się odmową.

| Service | Role | Indexed file | Bytes | SHA-256 |
|---|---|---|---:|---|
| backend | `resume_container_backend` | `r04-d21-p4b-resume-20260918t112015z\docker-container-backend-pass2-command.json` | 1420 | `55C4250C34C89C8545C2DF3F29C9A9D5673BBB065BEF48CB26EC6FE904DEAF2F` |
| postgres | `resume_container_postgres` | `r04-d21-p4b-resume-20260918t112015z\docker-container-postgres-pass2-command.json` | 1358 | `2BFBBB37FD1FB5E02B4786CDC10E107766629FB578DE90958CFFE8F8498E3289` |
| qdrant | `resume_container_qdrant` | `r04-d21-p4b-resume-20260918t112015z\docker-container-qdrant-pass2-command.json` | 1494 | `3534EB5AA13CD7F40547AA24E66673B27713AFFAD305740F6AFE2B013E871C55` |
| n8n | `resume_container_n8n` | `r04-d21-p4b-resume-20260918t112015z\docker-container-n8n-pass2-command.json` | 1342 | `B25B289BB1EAECD67CCE57B187E0437794B5C938BD0D91DADE6F57E179797055` |
| open-webui | `resume_container_open-webui` | `r04-d21-p4b-resume-20260918t112015z\docker-container-open-webui-pass2-command.json` | 1377 | `EF5E3CF0F922FC9F7ABD244BF7F7D2C4927739E9BCD4D5BCBAAC139FD8971677` |
| ollama | `resume_container_ollama` | `r04-d21-p4b-resume-20260918t112015z\docker-container-ollama-pass2-command.json` | 1342 | `39551CA0F6DC8EC1F0642D818EBF6F569EA0E6BCED826CB69CD2240D1D5EF78E` |

Końcowa recepta ma 55,623 B i SHA-256
`733AA23F15EF9CC1E8A87F1A1B38EF523464F09160EDACF50300F00957D05B6A`.
Indeks pakietu ma 4,156 B i SHA-256
`ED05FE269F89BE881474CA9B2C00D62589720FD0AE1959547D55A4032B54875C`.
Windows PowerShell `5.1.26100.8894` zaliczył 14/14 przypadków, 119 asercji,
6/6 historycznych odpowiedzi fake boundary oraz dokładne argv 7/7. Zarezerwowany
`execution-output\exact-resume-attempt-1` pozostaje nieutworzony. Stare recipe,
index, baseline i wejścia instalacji zachowują swoje bajty.

Status: `RECIPE_INPUT_BINDINGS_AND_OFFLINE_PREFLIGHT_PASS /
EXACT_PACKAGE_READY_FOR_REVIEW / NOT_INSTALLED`. Wymagany następny krok to
review dokładnych LOCAL_ONLY bajtów; fresh live drift check, jeden UAC i okno
operacyjne wymagają późniejszej, osobnej zgody.

## 16. P4/B full error path — recepta LOCAL_ONLY do review

Kontynuacja `R04-D21-P4B-FULL-PATH-20260919T045804Z` zachowuje historyczną
receptę input-binding bez zmian. Na jej preimage odtworzono `RV-P4B-FULL-01–04`:
kolizję `$Host` i nieprawidłowe wyrażenie statusu, niebezpieczne traktowanie
nieznanego stanu taska w rollbacku, granicę hosta poza deadline oraz
niewystarczający tekstowy harness.

Wynikowa recepta, `invoke-p4b-resume-installer.full-path.ps1`, ma 77,031 B i
SHA-256 `16A35C328A091801A4713A7F282A72C7E143BE489BF847A1AEE15599F70C4DC8`.
Indeks `full-path-package-index.json` ma 3,775 B i SHA-256
`1355EF0878C31202145E4E324C40A5D07E343FB78B0C6C7D029E2E932C43E3BF`.
Review ZIP ma 37,305 B i SHA-256
`DE8483568A17E27E80F3EE1C222C9E4BAC8EC6D78BA4C4CDC6DC48E2A86CFAEC`.

Końcowe PowerShell 5.1 testy offline:

- input/index: 14 przypadków, 110 asercji;
- real orchestration with complete lower-boundary fakes: 10 przypadków,
  67 asercji;
- własne workery: 9 startów i 9 rozliczonych zakończeń;
- real Docker/Task/CIM/TCP/HTTP/UAC/host mutations: 0;
- parser recepty: PASS; reserved execution output: absent.

Rollback usuwa własne pliki wyłącznie po pozytywnym potwierdzeniu dokładnej
tożsamości Host, disabled/no-trigger, stanu Ready/Disabled i braku
running/queued instances. UNKNOWN, denial, timeout, foreign helper/file lub
niejednoznaczna tożsamość kończą się PARTIAL/UNKNOWN bez destrukcyjnej
czynności. Awaria zapisu stage/final result nie maskuje pierwotnego błędu.

Status pozostaje `NOT_INSTALLED`; historyczny host to nadal
`PARTIAL_SAFE_INACTIVE`, warm runs `0/2`, globalny manifest
`NOT_APPROVED_FOR_START`. Następny krok to review dokładnych bajtów recepty,
indeksu i ZIP. Live drift check, UAC, instalacja i warm runs wymagają osobnej
jednorazowej zgody.

## 17. P4/B — zależności SAFE_INACTIVE i nierozliczone mutacje

Kontynuacja `R04-D21-P4B-ROLLBACK-DEPENDENCIES-20260919T101500Z` nie wykonała
live preflightu ani żadnej operacji hostowej. Na przypiętym preimage pełnej
ścieżki odtworzono `RV-P4B-FULL-03B`, `RV-P4B-FULL-02B` i
`RV-P4B-FULL-02C`. Poprawiona recepta:

1. przechowuje tożsamość i stan każdego mutatora; niepewny handoff kończy próbę
   jako `PARTIAL_PENDING_OPERATION_UNKNOWN` bez automatycznego retry,
   konkurującego rollbacku i cleanupu zależnych plików;
2. przywraca legacy helper wyłącznie po potwierdzeniu bezpiecznego Host i
   wszystkich znanych konsumentów Compose oraz braku ich running/queued;
3. przed każdym zapisem rollbacku taska ponownie odczytuje i dopuszcza tylko
   przypięty preimage albo znany stan pośredni/docelowy tej operacji;
4. zachowuje pozytywny `SAFE_INACTIVE` przy kompletnym, zgodnym dowodzie, więc
   poprawka nie polega na globalnym zakazie rollbacku.

Przypięte wyniki LOCAL_ONLY:

- recipe `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E`;
- package index `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F`;
- review ZIP `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C`;
- preimage `4/4`, `16` asercji; input `14/14`, `110` asercji;
  orkiestracja `15/15`, `96` asercji; workery `437/437`;
- rzeczywiste Docker/Task/CIM/TCP/HTTP/UAC/mutacje produktu `0`.

Pakiet ma status `ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW /
OFFLINE_ONLY / NOT_INSTALLED`. Jeden następny krok to niezależny review tych
dokładnych bajtów. Dopiero późniejsza, nowa zgoda może objąć fresh bounded drift
check, jeden UAC i próbę instalacji; obecna zgoda tego nie obejmuje.

## 18. Exact recipe acceptance i zatrzymany preflight

Właściciel przyjął dokładną receptę wyłącznie jako
`EXACT_ROLLBACK_SAFE_RECIPE_ACCEPTED / SOURCE_AND_OFFLINE_SCOPE /
NOT_INSTALLED`. Lokalna kontrola wykazała:

- recipe `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E`;
- package index `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F`;
- review ZIP `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C`;
- external input index `ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA`;
- ZIP `7/7`, package entries `6/6`, external inputs `29/29` zgodne;
- `VerifyInputsOnly` exit `0` dla
  `R04-D21-P4B-EXACT-RESUME-20260919T094244Z`; reserved execution output
  pozostał nieutworzony.

Świeży read-only preflight nie osiągnął bramki zgody operacyjnej. Zachowany
collector odczytał i wyeksportował pierwszy dokładny task, lecz zapis XML do
nowego, głęboko zagnieżdżonego katalogu zakończył się
`DirectoryNotFoundException`: pełna ścieżka przekroczyła praktyczny limit
Windows. Nie powstała bezpieczna projekcja taska, a katalog preflight pozostał
pusty. Zgodnie z zakazem ponawiania udanej części odczytu po błędzie loggera nie
uruchomiono kolektora ponownie pod krótszą ścieżką. Nie rozpoczęto odczytów
Docker/HTTP, UAC, Install ani warm runs; host mutations `0`.

Status: `PRE_UAC_BLOCKED / PREFLIGHT_EVIDENCE_NOT_PERSISTED_PATH_LENGTH /
NO_MUTATION`. Następny krok wymaga nowej decyzji właściciela na jeden
replacement bounded read-only preflight z wcześniej ustalonym krótkim katalogiem
dowodowym. Ta decyzja nie może jednocześnie stanowić zgody na UAC lub Install.

## 19. Zastępczy preflight pod krótką ścieżką

Właściciel dopuścił jedną zastępczą kampanię read-only pod dokładnym rootem
`C:\ai-lab-core-staging\recovery\P4B-PF-01`. Root nie istniał przed kampanią,
nie był reparse pointem i nie uzyskał szerszej listy principalów `Allow` niż
rodzic. Dwa lokalne błędy wzorca parsera ścieżki recepty wystąpiły przed I/O
probe i przed odczytami hosta; pusty własny root został zachowany i użyty po
osobnym potwierdzeniu poprawnego wzorca. Następnie:

- UTF-8 XML/JSON oraz atomic temp-to-rename roundtrip: `PASS`;
- najdłuższa planowana ścieżka kolektora: `90 <= 220`;
- ścieżki recepty: package root `205`, reserved execution root `252`,
  `installer-events.jsonl` `275`;
- reserved output nie został utworzony ani przetestowany, dlatego pozostaje
  `INSTALLER_OUTPUT_PATH_COMPATIBILITY_NOT_VERIFIED`.

Bounded host collector zakończył się `exit 1`, bez timeoutu, po utrwaleniu
sześciu XML-i tasków. Pięć historycznych tasków ma dokładne hashe preimage.
Host XML po normalizacji `domai` do przypiętego SID oraz braku `RunLevel` do
domyślnego `LeastPrivilege` odpowiada statycznie disabled/no-trigger,
InteractiveToken, IgnoreNew i PT15M. Błąd
`HOST_TRIGGER_CIMCLASS_PROPERTY_NOT_FOUND` wystąpił podczas budowy projekcji;
dynamiczny stan Host i `LastRunTime` pozostały `NOT_PERSISTED_NO_REREAD`.

Nie wykonano dalszych gałęzi host/resources, Docker ani HTTP. Lokalnie
potwierdzono: wrapper Startup `ABSENT`, kopia rollback zgodna, launcher/runtime/
manifest `ABSENT`, legacy helper i P3 override zgodne, reserved output
`ABSENT`. UAC, Install, warm runs, rollback i mutacje instalacji/danych: `0`.

Status: `REPLACEMENT_READ_ONLY_PREFLIGHT_PARTIAL /
HOST_TASK_FORMATTER_CIMCLASS_FAILURE / CURRENT_TASK_XML_AND_LOCAL_FILE_EVIDENCE /
NO_UAC / NOT_INSTALLED`. Kampania nie otwiera bramki UAC. Następny live odczyt
wymaga nowej decyzji po review poprawki wyłącznie read-only projekcji triggera;
nie wolno użyć tego wyniku do Install lub warm runs.

## 20. Poprawka kolektora XML i dokończenie ograniczonego odczytu

Właściciel dopuścił wyłącznie poprawkę LOCAL_ONLY kolektora oraz jedno
ograniczone dokończenie kampanii odczytowej w podkatalogu `c2` istniejącego
rootu PF-01. Historyczny kolektor pozostał bez zmian. Poprawiona wersja:

- nie używa `CimClass` do projekcji triggerów; typ bierze z bezpiecznie
  sparsowanego elementu XML w prawidłowym namespace;
- rozdziela statyczną definicję taska, bieżący `State` oraz `TaskInfo`;
- ma zamknięty katalog operacji i w fixture nie przechodzi do granicy hosta;
- zachowuje każdy wynik granicy przed późniejszym formatowaniem i pozwala
  użyć już utrwalonego rekordu bez ponowienia odczytu;
- ogranicza każdy własny worker i rozlicza go po PID.

Windows PowerShell `5.1.26100.8894` zaliczył `13` przypadków i `61` asercji,
owned workers `3/3`. Finalny collector ma SHA-256
`B78AC996CC180D0137454447EFC4C64007E83BFFC712D8960341BCFFF98850A3`,
a test SHA-256
`1F31D56E207E0F1EDC4735065A3861C1685BE3D37E00593A9691EE5F6513A83B`.
Sześć zachowanych XML-i zostało ponownie przetworzone lokalnie: pięć tasków ma
jeden `LogonTrigger`, Host ma zero triggerów i jest statycznie disabled;
wszystkie zachowują `InteractiveToken`, `LeastPrivilege` i `IgnoreNew`.

W ograniczonym oknie odczytowym utrwalono sześć stanów tasków. Public Gateway
był `Running`, Host `Disabled`, a Docker Desktop, Docker Compose, Private
Gateway i Supervisor miały stan `Ready`. Wszystkie sześć `TaskInfo` zakończyło
się błędem mapowania kolektora
`CommandNotFoundException,Invoke-ClosedWorkerOperation`. Odczytów nie
powtórzono, dlatego `LastRunTime` i `LastTaskResult` pozostają
`NOT_VERIFIED`. Listenery: `8000` Docker port proxy i `8789` Public Gateway;
`8787/8788` nie występowały w tym ograniczonym snapshotcie. HTTP: backend
health/version `200`, public root/gateway-health `200`, public `/control` i
`/control/health` `404`.

Windows available wynosił `6.557 GiB`, commit reserve `35.493 GiB`, wolne C:
`575.323 GiB`, wolne D: `854.573 GiB`; istniejące bramki Windows/dysk
przeszły. Docker/WSL pool available i swap-used pozostają `UNKNOWN`. Docker
local metadata potwierdziły istniejący HKCU Run, VHDX na C: (`44.902 GiB`)
oraz konfigurację WSL `18GB`/swap `8GB`; nie są one odbiorem relokacji.

Kampania Docker zapisała kompletne, bezpieczne rekordy: sześć kontenerów,
sześć obrazów, wolumen Qdrant i `docker info`. Końcowy formatter zawiódł po
odczytach, więc projekcję odtworzono wyłącznie z zapisanych rekordów, bez
ponownego kontaktu z Engine. Wszystkie sześć przypiętych kontenerów działało,
miało `RestartCount=0`, dokładne ID/image/mounty/porty/sieć odpowiadały draftowi,
a PostgreSQL był `healthy`. Qdrant używa `qdrant_storage`; Docker root to
`/var/lib/docker`, co nie zamyka relokacji VHD/profile.

Finalna bezpieczna projekcja LOCAL_ONLY ma SHA-256
`6D18493AFACBF19BFDA5D0607910572101AC5D27A36665AAE596727F8B159B74`,
indeks `A3FB97D5F46713753CBEC8A509D518D2DBFAE96EFAB7ABE44B8624F266FF52F8`.
Exact recipe/index/ZIP pozostają bez zmiany. UAC, Install, warm runs, rollback,
task/service/container mutations i business-data mutations: `0`.

Status: `P4B PREFLIGHT_EVIDENCE_PARTIAL /
TASK_INFO_MAPPING_ERROR_NO_REREAD / NO_UAC / NOT_INSTALLED`. Globalny manifest
pozostaje `NOT_APPROVED_FOR_START`, a kompatybilność zapisu zarezerwowanych
ścieżek outputu `252/275` pozostaje `NOT_VERIFIED_NO_IO`. Wynik nie otwiera
bramki UAC ani instalacji.

## 21. TaskInfo, krótki output i bramka nowego wznowienia

Właściciel dopuścił LOCAL_ONLY poprawkę dokładnej granicy TaskInfo, exact
pochodną zaakceptowanej recepty z krótką bazą outputu, ich testy oraz jeden
bounded readback. Historyczna recepta F6D3 i jej odbiór pozostają bez zmian.

Poprawiony collector przeszedł PowerShell 5.1 `16/126`, z `14/14` workerów i
zerem rzeczywistych wywołań systemowych w testach. Jedna live kampania
utrwaliła `TaskInfo 6/6`, bez startu lub modyfikacji tasków. Pochodna
`invoke-p4b-resume-installer.short-output.ps1` ma 91,912 B i SHA-256
`F65DF7232ADC3DBFE6B35FC08D255D385748ED17CC3078CACB93501FB9BF8C9A`.
Jej jedyny dozwolony diff obejmuje metadane oraz output
`C:\ai-lab-core-staging\recovery\P4B-FIN-01\out\run01`; ciała funkcji,
wejścia produktu, 29 ról, sześć baseline'ów, kolejność i rollback są
niezmienione. `run01` pozostaje nieobecny.

Końcowe wyniki: input `14/110`, orchestration `15/96`, workers `437/437`,
path/I/O max `206<=220`, VerifyInputsOnly `29/29 + 6`, ZIP roundtrip `17/17`.
Package index:
`36623A0384F400D10D9FF0714FE7ED67B0090FC872C19751ED195D2E52C8D49E`;
review ZIP:
`407A872A9B0504F35F2141992E3F84132198175A0146B5B0D1925B0F878D7272`.

Bieżący drift potwierdził wymagane task/container/file/HTTP identity i progi
Windows/dysk. Docker/WSL pool dostępna i swap-used pozostają `UNKNOWN`.
Installer zachowuje własne pre-mutation guards, ale przed pierwszym UAC nadal
wymagana jest jedna nowa bieżąca decyzja właściciela przyjmująca exact recipe,
index, external resume ID, krótki output, dwa warm runs, warunkowy SAFE_INACTIVE
rollback i jawne ograniczenia. Bez tej decyzji `RunAs` i `Install` są
zabronione.

Status: `SHORT_OUTPUT_DERIVATIVE_READY_FOR_REVIEW / TASKINFO_6_OF_6 /
CURRENT_DRIFT_PASS_WITH_RESOURCE_LIMITATION / NO_UAC / NOT_INSTALLED`.

## 22. Run01 — częściowa instalacja i STOP

Właściciel odebrał ograniczoną zmianę short-output i zatwierdził dokładnie jedno
wznowienie `R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z`. Wykonano jeden
RunAs/UAC. Recepta zainstalowała i zweryfikowała trzy pliki oraz exact manifest,
zastosowała docelowe definicje tasków i uruchomiła Host raz. Host zakończył się
`LastTaskResult=22`; Private Gateway nie został uruchomiony. Stdout launchera
nie był częścią akcji taska, dlatego dokładny wewnętrzny wynik pozostaje
`LAUNCHER_RESULT_DETAIL_NOT_CAPTURED`.

Recepta wykonała jedyny dozwolony SAFE_INACTIVE. Public Gateway pozostawał
`Running`, więc zależny destrukcyjny rollback plików i helper restore zostały
zablokowane. Wynik recepty: `PARTIAL_AFTER_FAILURE`; rollback:
`PARTIAL_UNKNOWN`; workery `50/50`; pending mutator `false`; warm runs `0/2`;
Private starts `0`.

Stan po operacji:

- launcher `7BB24450...F33871`, runtime `349404C3...4FA7`, existing-only helper
  `91C763F5...667EC` i manifest `E66F22A7...010C` są zainstalowane;
- Docker Desktop/Compose są disabled/no-trigger;
- Public/Private/Supervisor są enabled/on-demand/no-trigger; Public działa,
  Private i Supervisor nie działają;
- Host jest disabled/no-trigger, PT15M/InteractiveToken/LeastPrivilege/
  IgnoreNew, a trigger logowania nie został zainstalowany;
- wrapper Startup pozostaje poza Startup, z exact kopią w rollbacku;
- sześć przypiętych kontenerów pozostało running i bez restartów; PostgreSQL
  pozostał healthy; backend/Public Gateway odpowiedziały `200`, a publiczne
  `/control*` `404`.

Repozytoryjny draft zachowuje `NOT_APPROVED`. Exact zainstalowany manifest był
przypiętym `APPROVED_FOR_START` wejściem tej operacji; nie daje to odbioru P4/B.
Jednorazowa zgoda, UAC i SAFE_INACTIVE są zużyte. Następny krok to owner review
wyniku `HOST_TASK_FAILED_22` i osobna decyzja o ograniczonej diagnostyce. Bez
retry Host/Install, drugiego UAC, niezależnego rollbacku, logon/reboot, P5 lub
R06.

## 23. Host 22 — diagnoza tylko do odczytu, bez ponowienia startu

Kampania `P4B-E22-01` zachowała wynik run01 bez jego przepisywania. Akcja taska
Host nie kierowała stdout/stderr launchera do trwałego artefaktu, dlatego
historyczny wewnętrzny kod pozostaje `LAUNCHER_RESULT_DETAIL_NOT_CAPTURED`.
Jednocześnie diagnoza wystarcza do wskazania dwóch kolejnych, niezależnych
blokad w dokładnie zainstalowanym źródle:

1. Czyste wczytanie i walidacja exact manifestu przechodzą. Pierwsza granica
   adaptera Docker odpada jednak na szablonie Go odczytującym
   `.State.Health`. Backend nie ma klucza `Health`, więc exact inspect kończy
   się `map has no entry for key "Health"`, a plan mapuje wyjątek na
   `ADAPTER_FAILURE` i końcowy exit `22`.
2. Jedyny zapisany selector
   `project=ai-lab-core/service=backend`, obejmujący także stopped, zwrócił
   pięć kontenerów: jeden zatwierdzony runtime i cztery zachowane kontenery
   drill. Bezpieczna projekcja `with (index .State "Health")` potwierdziła ich
   pełne ID i stan bez ponowienia selektora. Prawdziwa faza kontenerowa na tych
   obserwacjach zwróciła `CONTAINER_IDENTITY_AMBIGUOUS`, `match_count=5`,
   starty `0`.

Test granicy rzeczywistego adaptera przeszedł przypadki `0/1/5` rekordów
(`36` asercji, starty `0`). Test poprawionej wyłącznie projekcji przeszedł
`7` kontroli. Offline replay fazy planu i adapter-error zachował zero wywołań
Docker/Task oraz zero mutacji. Łączny live skutek diagnostyki to jeden selector,
jeden nieudany exact inspect z bezpiecznym stderr oraz pięć celowanych
read-only inspectów; nie wykonano task read/write, HTTP, UAC, Host startu,
Install ani rollbacku.

Status: `HOST22_DIAGNOSED_READ_ONLY / SOURCE_FIX_REQUIRED /
NO_RETRY_AUTHORIZED`. Następny zakres musi być SOURCE/OFFLINE i obejmować
wyłącznie bezpieczny odczyt opcjonalnego health oraz exact-ID-first wybór
zatwierdzonego kontenera z fail-closed obsługą prawdziwego konfliktu. Dopiero
niezależny review/test tych nowych bajtów może poprzedzać nową decyzję
operacyjną.

## 24. Host 22 — poprawka source i nieaktywny zestaw do review

Source commit `ed961d6980ebebe2e4d351319e2aa909437bc1ec` implementuje
bezpieczną projekcję Health oraz exact-ID-first wybór kontenera. Brak/null
Health staje się `NOT_CONFIGURED`; PostgreSQL nadal wymaga jawnego `healthy`.
Pełny pinned ID jest sprawdzany przed bounded conflict scan. Brak ID nie
powoduje adopcji po nazwie/labelach. Cztery historyczne stopped drill są
pomijane wyłącznie po dodatnim rozpoznaniu wąskiego wzorca, stanu `exited` i
pustych mountów/portów; inne stopped, active, paused, restarting albo unknown
blokują plan.

Preimage z `e1f8e83d...` wykonał realną starą fazę na pięciu niezależnych
obserwacjach: `CONTAINER_IDENTITY_AMBIGUOUS`, starty `0`. Końcowa kampania PS
5.1 przeszła `37/53/51/44/16` asercji, każde stderr `0`, granice produkcji `0`.
W topologii 6+4 plan osiąga `BASE_READY_LIMITED`; wariant bez Private wykonuje
dokładnie jeden syntetyczny start i drugi przebieg zero, a cold start czeka na
PostgreSQL `starting -> healthy` przed backendem.

Nieaktywny candidate zmienia wyłącznie hashe przyszłego launcher/runtime:

| Path | Installed before | Candidate after |
|---|---|---|
| `operations/runtime/start-host-services.ps1` | `7BB24450...F33871` | `CF98B7BE...78E55` |
| `operations/runtime/startup-runtime.ps1` | `349404C3...D68E1ABCF4FA7` | `85A95894...34D85FB` |

Review ZIP `76A8999E...E74DBC` ma roundtrip `10/10`. Candidate pozostaje
`NOT_APPROVED_FOR_START / NOT_DEPLOYED`. Lista future update jest opisowa,
nie wykonawcza. Przed ewentualną kolejną próbą właściciel musi osobno odebrać
te bajty i zatwierdzić wąski update; przyszły Host musi utrwalić JSON
`code/events/details`, stdout/stderr i exit, zamiast samego LastTaskResult.

Status: `HOST22_HEALTH_AND_EXACT_ID_SOURCE_READY_FOR_REVIEW /
OFFLINE_TESTS_PASS / NOT_DEPLOYED`. Stan instalacji run01 pozostaje:
`PAYLOAD_AND_MANIFEST_INSTALLED / HOST_DISABLED_NO_TRIGGER / WARM_RUNS_0_OF_2`.

## 25. Host22 OBS-01–03 — kompletność, deadline i stan pinned

Kontynuacja na preimage `ed961d6980ebebe2e4d351319e2aa909437bc1ec`
odtworzyła trzy dodatkowe braki i opublikowała source
`b4269ffa7bacc95b4d1441bb196e572a34a4ec43`:

- odczyt natywny musi mieć jawną, kompletną kopertę; ucięcie, brak wymaganej
  metadanej, timeout, nonzero lub pozostawiony proces blokują;
- initial observation i readiness dzielą jeden malejący monotoniczny deadline,
  a po jego wyczerpaniu nie ma kolejnego inspectu ani startu;
- przypięty kontener jest gotowy wyłącznie przy `running=true` i dokładnym
  `state_status=running`; paused/restarting/removing/dead/unknown nie są
  gotowe, a PostgreSQL dodatkowo wymaga świeżego `healthy`.

Końcowa kampania Windows PowerShell 5.1 przeszła `51/57/51/44/40` asercji
dla focused Host22, planu launchera, real adapters, DATA_ONLY i pełnego
pakietu P4. Produkcyjne granice miały `0` wywołań. Nieaktywny ZIP review ma
SHA-256 `4EB0706A365C2D46AD7F63047AE2DB253D1841C7E372A45F4F1947CA212ADBD9`,
a indeks SHA-256
`CE373406DA49B35B01B20F4E8039A5F6F0060C54237C1B2D91193867B83B5763`.
Pakiet pozostaje `NOT_APPROVED_FOR_START / NOT_DEPLOYED`; nie jest nową
zgodą na Host retry, update instalacji ani zmianę run01.

## 26. Host22 final OBS conditions and inactive manifest bindings

Końcowy review na preimage `b4269ffa7bacc95b4d1441bb196e572a34a4ec43`
odtworzył `RV-H22-OBS-01B/02B`. Source
`8195e5cf8dacd1976ccd9f71a1f78175c3513acc` wymaga rzeczywistych typów pól
kompletności koperty oraz sprawdza ten sam deadline bezpośrednio przed
pozytywnym `PRESERVE_RUNNING`. Wcześniejsze exact-ID-first, Health i
`state_status=running` pozostają bez osłabienia.

Nieaktywny candidate wiąże teraz przyszły payload wykonawczo:

| Role | Exact path | Bytes | Raw SHA-256 |
|---|---|---:|---|
| `startup_launcher` | `operations/runtime/start-host-services.ps1` | 72 755 | `1327FADC5BD21DBBE076E5CAD2DF587C6B9B5F274511A99E96E8DDC4FC0BA190` |
| `startup_runtime` | `operations/runtime/startup-runtime.ps1` | 83 294 | `D1DD69F310909B62432C37863FEA2E45B8E3B846E85FE095D58B57912639F803` |

Walidacja porównuje `files[]`, pliki payloadu i metadane review niezależnie;
nie uzyskuje danych observed przez przepisanie expected. Candidate nadal ma
`approval.status=NOT_APPROVED` i nie jest zgodą na instalację lub uruchomienie.
Końcowe PS 5.1 przeszły `70/57/51/44/41`, pełny candidate binding + P4 `59`,
a binding po roundtrip ZIP `18`. Review ZIP ma SHA-256
`D6F48B9ED1178C6362A5BF8A8C79E6B08B72D569D5C0F880FA29990939C27AEA`.

### P4/B Host22 narrow update package (prepared, not authorized)

Owner acceptance covers Host22 source `8195e5cf...` only in its source/offline
scope. Proposed operation
`R04-D21-P4B-HOST22-NARROW-UPDATE-20260920T173311Z` is a new, inactive package:

1. verify the exact run01 launcher/runtime/manifest, helper KEEP hash, inactive
   Host preimage and semantic identities of the five dependency tasks;
2. back up only the owned run01 files and Host XML;
3. install exact Host22 launcher/runtime, the bounded result recorder and the
   exact proposed manifest while Host stays disabled/no-trigger;
4. bind Host to the recorder, verify exact installed bytes, then enable only
   on-demand execution;
5. accept two distinct evidence attempts only when both record
   `BASE_READY_LIMITED`; the first may start Private once and the second must
   start it zero times; both must start Supervisor/containers zero times;
6. add the single Host logon trigger only after both successes.

The helper and five other tasks are KEEP and cannot be rewritten by this
recipe. An unsettled mutation or Host handoff disables retry and destructive
rollback; known pre-handoff failure may use one exact SAFE_INACTIVE rollback
only with proven inactive owned Host and no foreign drift. The package remains
`NOT_AUTHORIZED / NOT_INSTALLED`; independent review and a new exact one-time
owner operational approval are required.
Następna operacja pozostaje odrębnym, wąskim update z nową zgodą; nie wolno
wracać do recepty zakładającej brak zainstalowanych plików lub stare triggery.

## 27. NUP-01/02/03 — bounded mutations, owned rollback and complete attempts

Pierwszy zbiorczy review D-23 przypisał wyłącznie `NUP-01 K0`, `NUP-02 K0`
i `NUP-03 K1`. Fail-before na exact preimage wykazał trzy odpowiadające im
ścieżki: fałszywe settlement mutacji, rollback bez pozytywnej własności i
bezczynności oraz warm gate bez pełnego dowodu nowej próby.

Nieaktywna pochodna `R04-D21-P4B-HOST22-NUP-20260920T200422Z` zachowuje
zamrożony zakres update'u: cztery pliki run01 i własny Host; helper oraz pięć
tasków zależnych są KEEP. Mutacje przechodzą przez zamknięty bounded catalog i
flushed mutation journal. Nierozliczony handoff blokuje retry i zależny cleanup.
Rollback wymaga exact semantic hash własnego, bezczynnego Host oraz bieżącego
after hash i backup before hash każdego przywracanego pliku. Dwa warm results
muszą mieć różne attempt IDs, zgodne marker/result, rozliczone dziecko oraz
zweryfikowane długości i hashe utrwalonych stdout/stderr. Pierwszy dopuszcza
wyłącznie Private `START_ONCE=1`, drugi `0`; `START_EXISTING`, Supervisor,
Docker Desktop i inne starty odrzucają wynik.

Końcowa kampania PS 5.1 zaliczyła recorder `32` asercje / `8` child cases oraz
rzeczywistą receptę z recorderem `51` asercji / `16` scenariuszy. Produkcyjne
granice i pięć task writes: `0`; własne procesy unsettled: `0`. Exact recipe
SHA-256 `0B051C2F...B9EF`, package index `67B32FB8...8222`, review ZIP
`C34B9460...7A1F` (roundtrip `28/28`). Pakiet pozostaje `OFFLINE_ONLY /
NOT_INSTALLED`; repozytoryjny draft jest `NOT_APPROVED`. D-23 pozostaje `1/2`:
następny krok to niezależny review tylko tego diffu i regresji, bez UAC,
instalacji, Host retry albo rollbacku hosta.

Review D-23 `2/2` został następnie zakończony: NUP-01 i NUP-02 zachowują PASS
w ocenionym zakresie, a właściciel zatwierdził domknięcie jedynego pozostałego
K1 NUP-03. Celowany fail-before na exact recepcie `0B051C2F...B9EF` wykazał,
że pierwszy warm zwracał `SUCCESS`, gdy właściwy Host nadal był `Running` z
jedną instancją; kolejny krok dopiero wtedy odmawiał startu.

LOCAL_ONLY recepta `DC1295C3...C4A0A` po walidacji kompletnego nowego evidence
wykonuje świeży bounded odczyt exact Host. `Running/Queued` pozostaje w tej
samej pętli i deadline, a SUCCESS wymaga exact semantic hash oraz pozytywnie
zerowych running/queued instances. Unknown, foreign lub wyczerpany deadline
daje bezpieczny wynik niepełny: brak drugiego warm, logon, retry i
destrukcyjnego rollbacku. Recorder, launcher/runtime Host22, helper, manifest,
XML-e oraz logika NUP-01/02 są niezmienione.

Końcowa kampania PS 5.1 na finalnych bajtach: `70` asercji / `20` scenariuszy;
oba Host przechodzą kontrolowane `Running -> Queued -> Ready`, dopiero potem
odpowiednio drugi start i logon. Private `1 -> 0`, container/Supervisor i pięć
dependency-task writes `0`, produkcyjne granice `0`, własne procesy `1`,
unsettled `0`. Package index `B3B50FD3...07919`; review ZIP
`3ED49CB3...FA09D`, roundtrip `34/34`. Status:
`NUP03_HOST_COMPLETION_SOURCE_FIX_READY_FOR_VERIFICATION / OFFLINE_PASS /
NOT_DEPLOYED`. Następna weryfikacja ogranicza się do tego diffu i jego
bezpośrednich regresji; przy PASS należy rekomendować odbiór zamiast szukać
nowych K2/K3. Nie ma zgody na operacje hosta.
