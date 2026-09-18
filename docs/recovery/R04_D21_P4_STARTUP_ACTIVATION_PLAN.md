# R04 / D-21 / P4-A — pakiet aktywacji jednego startu

Status: `P4A SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / P4B_PARTIAL_SAFE_INACTIVE_RESUME_PRE_MUTATION_NATIVE_ARGUMENT_TRANSPORT_FAILED / GLOBAL_START_MANIFEST_NOT_APPROVED`

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
