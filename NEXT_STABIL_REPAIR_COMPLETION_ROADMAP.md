# NEXT Stabil — naprawa, dokończenie, odbiór i porządek

**Jedna roadmapa wykonawcza · wersja 1.1 · 2026-09-07**

**Status rejestracji: R00–R02 ACCEPTED; R03 pozostaje WAITING_APPROVAL / WAITING_ESCROW_DECISION; R04 i R05 pozostają IN_PROGRESS. D-21 P1/P2/DATA_ONLY/guard, ograniczony P3, P4/A, Host22 i NUP-01/02/03 zachowują dotychczasowe odbiory. Run01 pozostaje historycznie PARTIAL_AFTER_FAILURE, Host disabled/no-trigger, warm 0/2 i Supervisor INTENTIONALLY_STOPPED. Historyczny `PACKAGE_STATUS_INVALID` pozostaje zachowany. Pochodny LOCAL_ONLY index zmienił wyłącznie top-level status wymagany przez niezmieniony package guard; manifest nadal jest `NOT_APPROVED`, a wszystkie zgody mutujące są false. Jeden exact VerifyOnly zakończył się `VERIFIED_NO_MUTATION`. Skonsolidowany read-only preflight potwierdził 6/6 pinned containers, healthy PostgreSQL, Public Gateway PRESENT, Private/Supervisor ABSENT, HTTP `200/200/200/404/404` oraz bramki Windows/dysków; Docker/WSL pool i swap usage pozostają jawnie `UNKNOWN_NOT_MEASURED`. Starty i mutacje `0`. Finalna kontrola exact bytes wykazała materialny K1: niezmieniony runtime zwraca `START_NOT_APPROVED` dla przypiętego manifestu, a recepta nie wykonuje approval transition. Stage B jest `BLOCKED_EXACT_APPROVED_MANIFEST_BINDING_NOT_PREPARED / NOT_AUTHORIZED`; brak zdania zgody/UAC. D-22 nadal ustala kolejność po właścicielskim odbiorze R04: ARKUSZE -> KOREKTA I WALIDACJA KLIENTÓW -> TYLKO NIEPRZYPISANE MAILE; wykonanie NOT_RUN. Bieżący stan znajduje się wyłącznie w §0.**

**Aktualizacja 2026-09-20:** właściciel przyjął dokładny source Host22
`8195e5cf8dacd1976ccd9f71a1f78175c3513acc` i jego ZIP jako
`HOST22_SOURCE_AND_OFFLINE_PACKAGE_ACCEPTED / NOT_DEPLOYED`. Pierwszy zbiorczy
review D-23 wykazał NUP-01/02/03. Skonsolidowana poprawka source
`d3435afcfb89d02d91f2db3d1eb55be17fd790bd` oraz LOCAL_ONLY package index
`67B32FB8981F765A251DDC081D4FD9473B224A2BFFEE7E96CA01C1C57A288222` są
`ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW / OFFLINE_ONLY /
NOT_INSTALLED`. Nie ma bieżącej zgody na UAC, update, Host retry ani rollback
hosta.

**Aktualizacja 2026-09-21:** review `2/2` jest zakończony. NUP-01/NUP-02
pozostają PASS w ocenionym zakresie; jedyny pozostały K1 NUP-03 został
odtworzony na recepcie preimage i domknięty wyłącznie SOURCE/OFFLINE. Nowa
recepta `DC1295C3...C4A0A`, index `B3B50FD3...07919` i ZIP
`3ED49CB3...FA09D` są gotowe do weryfikacji tego diffu, nie do instalacji.
D-23 odtąd wymaga wykazanego materialnego wpływu dla K0/K1; K2/K3 nie są
naprawiane, nie blokują odbioru i nie tworzą automatycznego backlogu.

**Aktualizacja Stage A 2026-09-21:** właściciel przyjął dokładny pakiet NUP-03
wyłącznie SOURCE/OFFLINE. Integralność `33/33`, ZIP `34/34` i bindings `8/8`
przeszły. Jedyny `VerifyOnly` odmówił przed mutacją na
`TASK_DEPENDENCY_DRIFT: NEXT Stabil - Docker Desktop`. Zachowane odczyty
projekcji potwierdziły 5/6 tożsamości kontenerów i healthy PostgreSQL, lecz
ujawniły dalsze mismatch backend/host services/Host; HTTP pozostał NOT_RUN po
lokalnym błędzie formattera, bez retry. Stage B nie ma zgody.

**Rozliczenie dowodów Stage A 2026-09-21:** omyłkowy untracked checkpoint z
oryginalnego rootu został usunięty po exact-path zgodzie; jego `5484` bajty,
SHA-256 `8ABFDCA9...56A5`, zachowano LOCAL_ONLY przed usunięciem. Backend mount
mismatch i Host hash/trigger mismatch są udowodnionymi różnicami reprezentacji,
nie zmianą zasobu. Docker Desktop drift nie zawiera zapisanego bieżącego hasha,
a trzy host-service mismatch nie zawierają bieżących pól taska; te dwie grupy
pozostają nierozstrzygnięte bez nowego odczytu. Formatter pomylił `status` z
`read_status`; HTTP pozostaje `NOT_RUN`. Rekomendowany jest jeden skonsolidowany
follow-up źródłowo-diagnostyczny, nie Stage B.

**Domknięcie P4B-STAGEA-GATE SOURCE/OFFLINE 2026-09-21:** source
`e8ad5e27bc8515e6536b5fc8696608b3d9c6e7de` na base
`17b81b5f46850ebf585c40724ab457a52cfce5c4` ogranicza normalizację bind
source do absolutnych ścieżek Windows typu `bind`, a tożsamość task action
wiąże dokładny executable, CWD, pojedynczy skrypt pod zatwierdzonym rootem i
pozostałe argumenty. Jedyny świeży, niepodniesiony capture czterech exact
tasków utrwalił `4/4` definicji i `4/4` zgodności po ograniczonej normalizacji;
bez task write/start. Focused i wymagane regresje PS 5.1 są PASS. To nie jest
ponowienie VerifyOnly ani Stage B: `HTTP / fresh six-container preflight /
live VerifyOnly = NOT_RUN`, a `Stage B = BLOCKED / NOT_AUTHORIZED`.
Nieaktywny package index `F74BD628...A5BD2`, review index
`F21EE086...CEB04` i ZIP `F9850E9B...19A3B` przeszły roundtrip `40/40`.

**VerifyOnly po przywróceniu exact ZIP 2026-09-22:** oryginalny plik właściciela
`223585` B / `0DE0E072...14F8` został skopiowany bez overwrite i ma identyczne
bajty w przypiętym rootcie. Bramka osiągnęła `4/4` top-level oraz `8/8`
bindings. Jedyny nowy ordinary-token VerifyOnly zakończył się exit `0` po
`55349.381 ms`: `VERIFIED_NO_MUTATION`, bez pending, changed roles, warm runs,
journalu lub rollbacku. Recepta wykonała tylko ograniczone odczyty pięciu
dependency tasks i Host. HTTP/fresh six-container preflight są `NOT_RUN`, a
Stage B nadal `BLOCKED / NOT_AUTHORIZED`.

**Formalna blokada PS5.1 host-services-only 2026-09-22:** dokładny LOCAL_ONLY
wrapper `observe-host-services.ps1` ma `17386` B i SHA-256
`02ACD6700BD6551491F41907C1A9F5FB7C125ECB7C49577F8B58A96E2AB57F56`; parser
Windows PowerShell 5.1 przeszedł. Jedyna próba uruchomienia exact
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` została
zatrzymana przed startem procesu komunikatem `This script contains malicious
content and has been blocked by your antivirus software.`. Nie powstały
engine/campaign/runner outputy, Task/CIM/TCP reads i workers wynoszą `0`, a
Public/Private/Supervisor pozostają `NOT_OBSERVED`. Nie wykonano retry ani
zmiany kanału. Status: `P4B_HOST_SERVICES_PS51_READBACK_NOT_RUN /
FORMAL_ANTIVIRUS_BLOCK_BEFORE_PROCESS / STAGE_B_BLOCKED_NOT_AUTHORIZED`.

**Statyczny materiał bezpieczeństwa 2026-09-22:** późniejszy exact-path odczyt
historycznego wrappera potwierdził `ERROR_FILE_NOT_FOUND`; nie szukano go szerzej
i nie odtwarzano jego bajtów. Powstał nowy, jawny i nieaktywny kandydat
`build/P4B-HS-REVIEW-01/observe-host-services.candidate.ps1`: `7940` B /
`4DCFE146ED51A8F68FECEB8DCB10FD1A873F4D88CC0892EDC372574B8B7890F9`.
Wiąże zaakceptowane launcher/runtime `B414...7892` / `9597...0732`, wystawia
wyłącznie trzy operacje `OBSERVE`, a wszystkie pozostałe dolne granice jawnie
odmawiają. Kandydat nie został uruchomiony ani sparsowany przez PowerShell.
Właściciel oświadczył, że wyjątek NEXT Stabil istniał wcześniej w Bitdefender
ATD; nie jest to nowy odczyt konfiguracji ani dowód źródła odmowy. Właściciel
przyjął wynik statyczny exact kandydata jako `STATIC_SOURCE_REVIEW_ACCEPTED /
NOT_EXECUTED / NOT_AV_CLEARANCE`. Dostępne narzędzia tej sesji nie udostępniają
formalnej ścieżki Bitdefender/ATD/AV, więc kandydat nie został przedłożony
warstwie ochronnej ani uruchomiony; nie wpisano `FALSE_POSITIVE_CONFIRMED`.
Stage B nadal bez zgody.

**Exact host-services OBSERVE 2026-09-22:** właściciel zmienił wyłącznie
proceduralny warunek wykonania: statyczny review `4DCFE146...90F9` pozostaje
odebrany, ale nie jest wymagany osobny, nieustalony certyfikat AV i nie nadano
statusu AV-cleared. Po ponownym .NET SHA-256 czterech przypięć, kontroli braku
kolizji i sentinel I/O wykonano dokładnie jedną próbę pod Windows PowerShell
5.1 zwykłym tokenem. Bounded runner: exit `0`, PID `65440`, `7411 ms`, bez
timeoutu, pozostawionego procesu, stderr i ucięcia strumieni. Wynik LOCAL_ONLY
`o1/host.json`: `2561` B / `DA2274B770CBD5351BAB0B4A51B884739DD4CA49CA3D28FC32BA60533FE23CB8`.
Public Gateway = `CONFLICT / PORT_OWNERSHIP_CONFLICT`; Private Gateway i
Supervisor = `UNKNOWN / OBSERVATION_UNKNOWN`. `starts/task_writes/docker_reads/
http_reads = 0`. Bez retry, dodatkowej diagnostyki, UAC i Stage B.

**Diagnoza przyczyny host-services 2026-09-23:** zachowany `host.json` ponownie
potwierdził hash `DA2274B7...23CB8`. Jedna owner-authorized kampania pod exact
Windows PowerShell `5.1.26100.8894` trwała `12364 ms`, wykonała osiem
ograniczonych liści i rozliczyła wszystkie dzieci; starts/task writes/Docker/
HTTP reads `0`. Listener `8789` był dokładnie `127.0.0.1`, PID `41784`.
Listenery `8788` i `8787` zwróciły `ObjectNotFound` z FQID
`CmdletizationQuery_NotFound,Get-NetTCPConnection`, ale ich niepusty
`TargetObject` nie równał się oczekiwanemu portowi. To odtwarza gałąź
`Test-ExpectedEmptyResultError=false -> OBSERVATION_UNKNOWN` i nie jest dowodem
braku procesu. Bezpieczna projekcja task/process po odczycie nie została
utrwalona z powodu lokalnego błędu zakresu funkcji collectora; zgodnie z zasadą
bez retry nie ponowiono żadnego liścia. Dla Public pierwszy odrzucający predykat
pozostaje potwierdzonym `foreignListener`, lecz rozstrzygnięcie obcy proces vs
różnica reprezentacji wymaga dokładnie bieżącej projekcji PID `41784` z czasem
utworzenia i tokenami. Status:
`P4B_HOST_SERVICE_CAUSE_DIAG_PARTIAL / PRIVATE_SUPERVISOR_LISTENER_EMPTY_NORMALIZATION_REPRODUCED / PUBLIC_PROCESS_TOKEN_EVIDENCE_UNRESOLVED / NO_RETRY / STAGE_B_BLOCKED_NOT_AUTHORIZED`.

**Process-only PID 41784 2026-09-23:** przed jedynym zapytaniem produkcyjne
granice wynosiły `0`; projekcja i harness przeszły Windows PowerShell 5.1
offline `10/10` przypadków i `113` asercji. Dokładnie jedno
`Get-CimInstance Win32_Process -Filter 'ProcessId = 41784'` zakończyło się exit
`0` w oknie `2026-09-23T11:55:13.0319978Z`–`11:55:14.3740950Z`; query count
`1`, retry/task/listener/other-process reads/starts/writes `0`. Bezpieczna
projekcja potwierdziła `node.exe`, exact executable, `argv_count=2`, brak
dodatkowych argumentów i ten sam kanoniczny skrypt pod absolutnym tokenem
`C:\ai-lab-core\operations\gateway\public_web_server.cjs` zamiast względnego
tokenu manifestu. CreationDate `2026-09-14T17:09:01.3918090Z` oraz ten sam PID
w historycznym listenerze z `2026-09-23T09:44:45.3839234Z` dają czasową
ciągłość instancji, ale nie świeże potwierdzenie ownership portu. Offline replay
niezmienionego adaptera na zachowanych danych zwrócił nadal `CONFLICT /
PORT_OWNERSHIP_CONFLICT`. Status:
`PUBLIC_GATEWAY_REPRESENTATION_DIFFERENCE_PROVEN /
PRIVATE_SUPERVISOR_LISTENER_EMPTY_NORMALIZATION_REPRODUCED /
SOURCE_FIX_NOT_AUTHORIZED / STAGE_B_BLOCKED_NOT_AUTHORIZED`.

**D-23 DELIVERY FIRST 2026-09-23:** właściciel zastąpił regułę małych chunków
i blanketowych testów polityką `COMPLETE_SCOPE_BEFORE_REVIEW`. Jednostką
wykonania i odbioru jest kompletny rezultat funkcjonalny lub jawnie uzgodniony
samodzielnie użyteczny segment; checkpointy i etapy techniczne nie wymuszają
mikro-pauz. Materialne K0/K1 i zgody operacyjne pozostają. Jeden szczegółowy
audyt implementacji/coverage/edge/hardening/K2/K3 wykonuje R23 po ukończeniu
prac funkcjonalnych. Zmiana jest wyłącznie dokumentacyjna: nie autoryzuje
source, testów wykonywalnych, CI, Stage B ani operacji produkcyjnych.

**R04-P4B-USABLE-WARM 2026-09-23 — paczka nieaktywna, preflight formalnie
zablokowany:** właściciel odebrał source
`49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc` wyłącznie jako
`SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED`. LOCAL_ONLY window
`R04-D21-P4B-USABLE-WARM-20260923T170936Z` ma receptę
`74E5664F...B7D6D`, indeks `6F379DC5...64698` i `8/8` zgodnych bindingów;
manifest `E139CEC5...357F0` pozostaje `NOT_APPROVED`. Formalna ścieżka
zatwierdzenia odrzuciła nowy ordinary-token `VerifyOnly` przed startem procesu.
Nie wykonano Task/Docker/CIM/TCP/HTTP reads, UAC, mutacji ani warm runu; nie
zastosowano obejścia. `Stage B = NOT_ELIGIBLE / NOT_AUTHORIZED`.

**R04-P4B-USABLE-WARM 2026-09-24 — kontrakt indeksu i kompletny read-only
preflight:** historyczny index `6F379DC5...64698` pozostał bez zmian. Pochodny
`package-index.verifyonly.json` `4A58DF7D...84DC` zmienia wyłącznie top-level
`status` na wartość wymaganą przez niezmieniony `Test-P4BPackageIndex`; manifest
pozostaje `NOT_APPROVED`, a authorization false. Full package gate PASS. Jeden
PS5.1 VerifyOnly zwrócił `VERIFIED_NO_MUTATION`. Bieżący readback potwierdził
6/6 exact pinned containers, PostgreSQL healthy, Public Gateway PRESENT,
Private/Supervisor ABSENT, HTTP `200/200/200/404/404` i bramki Windows/dysków.
Docker/WSL pool i swap usage pozostają `UNKNOWN_NOT_MEASURED`; nie są PASS.
Starty, task writes, mutacje, UAC, InstallAndWarm i Stage B `0`. Finalny guard
exact bytes wykazał `START_NOT_APPROVED`: recepta kopiuje manifest
`NOT_APPROVED` i nie wykonuje approval transition. Status:
`PREFLIGHT_PASS_WITH_DECLARED_UNKNOWNS /
STAGE_B_BLOCKED_EXACT_APPROVED_MANIFEST_BINDING_NOT_PREPARED_NOT_AUTHORIZED`.
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
| Stan rejestracji | P3 `CORE_BACKEND_SOURCE_SWITCH_ACCEPTED / LIMITED_RUNTIME_SCOPE`. P4-A `SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / NOT_INSTALLED`. P4/B pozostaje historycznie `PARTIAL_AFTER_FAILURE / HOST_TASK_FAILED_22 / SAFE_INACTIVE_PARTIAL_UNKNOWN`; Host22 i NUP-01/02/03 zachowują odbiory, a D-23 review `2/2` jest zakończony. Source `49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc` jest `SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED`. USABLE-WARM derived index `4A58DF7D...84DC` przeszedł full package gate; VerifyOnly = `VERIFIED_NO_MUTATION`; readback 6/6 containers, host services, HTTP i Windows/dyski PASS. Docker/WSL pool i swap usage pozostają `UNKNOWN_NOT_MEASURED`. Manifest pozostaje `NOT_APPROVED`; runtime zwraca `START_NOT_APPROVED`, recepta nie wykonuje approval transition, installed run01 bez zmian, a Stage B `BLOCKED / NOT_AUTHORIZED`. Cały R04/R05 `IN_PROGRESS`; R03 `WAITING_APPROVAL / WAITING_ESCROW_DECISION` |
| Checkpoint ID | `R04-D21-P4B-USABLE-WARM-20260923T170936Z` |
| Ostatnia aktualizacja operacyjna UTC | `2026-09-24T06:27:48.8457380Z`: po zmianie wyłącznie top-level statusu pochodnego indeksu full package gate PASS; exact PS5.1 VerifyOnly = `VERIFIED_NO_MUTATION`; jedna kampania read-only potwierdziła 6/6 containers, host services, HTTP i Windows/dyski. UAC, mutacje, starts i warm runs `0` |
| Aktualny wykonawca / sesja | Codex / OWNER-AUTHORIZED CONSOLIDATED READ-ONLY PREFLIGHT COMPLETE; exact approved-manifest binding blocker recorded |
| Aktywny pakiet / podetap | R04/D-21/P4-B — `P4B_USABLE_WARM_CONSOLIDATED_READ_ONLY_PREFLIGHT_PASS_WITH_DECLARED_UNKNOWNS / STAGE_B_BLOCKED_EXACT_APPROVED_MANIFEST_BINDING_NOT_PREPARED_NOT_AUTHORIZED` |
| Potwierdzony lokalny worktree | `C:\ai-lab-core-recovery`, branch `recovery/next-stabil-repair-completion`; start P4-A local/tracking/remote `c936643b0360cd5a78e72c9d1cc51467edbd83c1`. Oryginalny HEAD `72950657...` pozostaje chroniony; historyczne preservation `116 + 87 = 203/203`. Omyłkowy untracked checkpoint został po exact zgodzie zachowany bajtowo w LOCAL_ONLY i usunięty; oryginalny index i pozostałe pliki nie zostały zmienione |
| Gałąź / SHA kodu objętego sprawdzeniem | Host-service observation source `49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc`, launcher raw SHA-256 `686F4EC877AADC93D46D2B67858864BF9C728B00093037A266B257099BA14B66`; guard source `0ee0ea50943578e6e552aae23ce1688595ddc262`; accepted DATA_ONLY source `cb6e22506a0fecc440400566293524536847b9b0`; accepted P2 source `2e69622bc6a0b4888427f8ae5be119377aed26d9`; baseline `origin/main@483f9bf8b1a591ded8a42df5da87663c664ed5d4`; rescue `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` |
| Baseline commit dokumentacji | `483f9bf8b1a591ded8a42df5da87663c664ed5d4` |
| Źródła runtime / release / DB | Backend `686ac376...c854`, image `sha256:6342b36f...d63702`, source `0ee0ea5...`, `/app=C:/ai-lab-core/backend:ro`, `/data=C:/ai-lab-core/data:rw`; pozostałe pięć kontenerów zachowane. P4-A draft wiąże 6/6 bieżących pełnych ID, image ID, RepoDigests i mountów; Qdrant physical backing pozostaje `UNKNOWN`. Public Gateway działał; Supervisor `INTENTIONALLY_STOPPED` |
| Ostatnia faktycznie zakończona czynność | Zakończono jeden pełny USABLE-WARM read-only preflight. VerifyOnly = `VERIFIED_NO_MUTATION`; 6/6 pinned containers running i zgodne, PostgreSQL healthy; Public PRESENT, Private/Supervisor ABSENT; HTTP `200/200/200/404/404`; Windows/dyski PASS. Summary `1486F084...D75B5` |
| Potwierdzone testy bieżącego wykonania | Existing full `Test-P4BPackageIndex` PASS na rzeczywistych plikach; exact PS5.1 VerifyOnly PASS; accepted real adapters potwierdziły 6/6 identities; exact PS5.1 host observer 3/3; HTTP 5/5; Windows resource gate PASS. Wcześniejsze `53/57` source tests nie były powtarzane |
| Niezacommitowana praca / zabezpieczenie | LOCAL_ONLY `C:\Users\domai\AppData\Local\Temp\P4B-UW-01\preflight\status01`; summary `11302` B / `1486F0840D2DC604329385363B374A2BE3752F1761D8C1C1A7454BFD250D75B5`. Oryginalny indeks i historyczne `campaign01` pozostają bez zmian; zarezerwowany `apply` nie istnieje |
| Niezakończone procesy i skutki operacyjne | Wszystkie własne procesy odczytowe zakończone. Task writes/starts, service/container starts, UAC, InstallAndWarm, Host start/rollback i warm runs `0`; installed run01 bez zmian |
| Najnowsza notatka przekazania | `docs/recovery/checkpoints/20260924T062935Z-R04-D21-P4B-USABLE-WARM-READONLY-PREFLIGHT.md` |
| Zakres aktualnej zgody | Zgoda read-only została wykorzystana i zakończona. Nie obejmowała UAC, Stage B, InstallAndWarm, Host/task write/start ani warm runs; kolejna operacja wymaga nowej bieżącej odpowiedzi właściciela |
| Blokada / wymagana decyzja | Techniczne bramki read-only przeszły; jawne `UNKNOWN_NOT_MEASURED` pozostają dla Docker/WSL pool i swap usage. Przypięty manifest ma `NOT_APPROVED`, runtime zwraca `START_NOT_APPROVED`, a recepta nie wykonuje approval transition; niezmienione Stage B nie może osiągnąć warm runs |
| Jeden następny bezpieczny krok | Jedna decyzja właściciela o minimalnym LOCAL_ONLY przygotowaniu exact `APPROVED_FOR_START` manifest bytes, pochodnym index binding i przejściu niezmienionych guardów; nadal bez UAC, instalacji, Host startu i warm runs |
| Warunek STOP | Brak kolejnego UAC, retry Host/launchera/instalatora, niezależnego rollbacku, logon/reboot, Supervisora, backup/restore, relokacji, P5/R06 |

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

<a id="ANTI_EXCESSIVE_WORK"></a>
### ZASADA ANTY-PĘTLA / ANTI_EXCESSIVE_WORK — obowiązkowa dla Codexa i ChatGPT

Ta zasada jest decyzją właściciela D-23 i obowiązuje od jej publikacji. Nie
zmienia statusów wykonania ani odbiorów produktu. Jej celem jest domykanie
uzgodnionego zakresu bez dokładania kolejnych kryteriów tylko dlatego, że można
znaleźć dalsze ulepszenia.

<a id="COMPLETE_SCOPE_BEFORE_REVIEW"></a>
#### DELIVERY FIRST / COMPLETE_SCOPE_BEFORE_REVIEW

Jednostką planowania, wykonania i formalnego odbioru jest kompletny uzgodniony
rezultat funkcjonalny albo jawnie uzgodniony, samodzielnie użyteczny segment.
Nie są nią pojedyncze helpery, hashe, testy, odczyty, ZIP-y, commity ani
checkpointy. Plan przed pracą obejmuje cały rezultat, zależności, kryteria,
testy, operacyjne bramki i rollback. W granicach bieżącej zgody Codex wykonuje
kolejne potrzebne etapy techniczne bez mikro-pauz i mikro-promptów aż do
kompletnego wyniku lub rzeczywistego blokera.

Rozróżniamy dwa poziomy kontroli:

1. **Weryfikacja dostarczenia zakresu** — podczas Rxx sprawdzamy pełny dotknięty
   workflow, materialną poprawność danych i bezpieczeństwa, kluczowe integracje
   oraz bezpośrednie regresje. Testy dobiera się do zmiany i dowodu ryzyka; nie
   uruchamia się blanketowych pełnych kampanii backendu/Fluttera po każdym
   technicznym podkroku.
2. **Szczegółowy audyt końcowy** — jeden szeroki audyt implementacji, pokrycia,
   przypadków brzegowych, hardeningu, martwego kodu oraz nieblokujących K2/K3
   wykonuje R23 po ukończeniu prac funkcjonalnych. Tego audytu nie duplikuje się
   w każdym wcześniejszym pakiecie.

Materialne K0/K1 i faktyczne bramki zgody pozostają obowiązujące. Blokują tylko
zależną ryzykowną operację; bezpieczna, niezależna część już autoryzowanego
kompletnego zakresu trwa dalej. K2/K3 nie są poprawiane „przy okazji”, nie
blokują odbioru i nie tworzą automatycznych zadań. Checkpoint dokumentuje stan,
dowody i możliwość wznowienia, ale sam nie jest obowiązkową pauzą, odbiorem ani
nową zgodą.

Raport opisuje wynik użytkowy, materialne K0/K1, przeprowadzone adekwatne testy,
pozostałe realne bramki i jedną drogę do kompletnego wyniku — nie przedstawia
liczby plików, asercji lub artefaktów jako samodzielnego sukcesu funkcjonalnego.
W razie sprzeczności z dawną regułą małych chunków lub testów po każdym
podkroku obowiązuje niniejsze D-23. Historia wcześniejszych odbiorów i dowodów
pozostaje nienaruszona.

#### Klasy uwag review

Każda nowa uwaga, dodatkowy test lub propozycja pracy otrzymuje jedną klasę.
Klasa nie zastępuje `PLANNED`, `NOT_RUN`, `WAITING_APPROVAL` ani `ACCEPTED`.
Zaplanowany, niewykonany test nie jest automatycznie wadą produktu.

| Klasa | Znaczenie | Wpływ |
|---|---|---|
| `K0 — ISTOTNE BEZPIECZEŃSTWO` | Wykazane ryzyko utraty/uszkodzenia danych, nieuprawnionego dostępu/eksportu/startu lub nierozliczonej mutacji. Szkoda nie musi już wystąpić, ale potrzebny jest konkretny dowód i związek z daną operacją, nie ogólne „dla bezpieczeństwa” | Zatrzymać tylko zależną operację; ustalić minimalny bezpieczny dowód i rozwiązanie bez ryzykownej reprodukcji na produkcji |
| `K1 — ISTOTNY BLOKER FUNKCJONALNY/OPERACYJNY` | Problem uniemożliwia lub znacząco pogarsza uzgodnioną funkcję, poprawność danych, uruchomienie, niezawodność operacji albo wykonanie koniecznego kroku | Naprawić w bieżącym zakresie po wskazaniu konkretnego skutku, dowodu/wersji i minimalnej zmiany/testu |
| `K2 — WPŁYW NIEZNACZNY` | Brak istotnego wpływu na działanie, dane i bezpieczeństwo | Nie naprawiać, nie blokować odbioru, nie uruchamiać dodatkowych testów/kampanii. Dopuszczalna jest jedna informacyjna linia bez obowiązku zadania lub backlogu |
| `K3 — BRAK WYKAZANEGO WPŁYWU / ULEPSZENIE` | Kosmetyka, refaktoryzacja, styl, nieużywany kod lub dodatkowy hardening bez konkretnego uzasadnienia | Nie ruszać, nie szukać dalszych takich uwag i nie tworzyć automatycznej przyszłej pracy |

Nie wolno zmienić uzgodnionego kryterium odbioru na `K2/K3` bez decyzji
właściciela. Każde `K0/K1` zawiera: `ID | klasa | blokowany krok/kryterium |
dowód i wersja | skutek | minimalna naprawa/test`. Oddzielać
`ODTWORZONE`, `POTWIERDZONE_W_KODZIE` i `HIPOTEZA`; wyobrażalny scenariusz bez
dowodu nie wystarcza do `K0/K1`.

Przed zaproponowaniem naprawy ChatGPT lub Codex obowiązkowo odpowiada:
**„Co konkretnie nie zadziała lub jakie istotne zagrożenie powstanie, jeśli
tego nie zmienimy — i jaki mamy na to dowód?”** Bez odpowiedzi popartej dowodem
uwagi nie podnosić do K0/K1 i nie naprawiać „na zapas”. Błąd testu,
formattera albo pakowania jest problemem narzędzia; poprawiać go minimalnie
tylko wtedy, gdy rzeczywiście blokuje konieczne wykonanie lub niezbędny dowód.
Błąd formatowania nie uzasadnia nowego odczytu hosta, a timeoutu/asercji nie
zmienia się wyłącznie dla uzyskania PASS.

#### Zamrożony kontrakt i punkt zakończenia

Przed zamkniętym zakresem zapisać w istniejącej karcie: cel użytkowy, dozwolone
zmiany, skończoną listę kryteriów, wymagane dowody i jeden następny krok. Po jej
zamrożeniu nowe `K2/K3` nie rozszerzają odbioru. Nowe `K0/K1` wymagają nowego
dowodu i związku z bieżącym celem; poszerzenie zmian wymaga decyzji właściciela.
Po spełnieniu kryteriów i zamknięciu `K0/K1` rekomendować odbiór kompletnego
rezultatu lub wcześniej jawnie uzgodnionego, samodzielnie użytecznego segmentu
albo wykonać już autoryzowany krok, zamiast otwierać kolejną rundę ulepszeń.
Techniczny podetap pozostaje dowodem i historią, a nie automatyczną formalną
jednostką odbioru. Wcześniejsze jawne odbiory zachowują ważność.

Pierwszy review obejmuje zbiorczo całą zmienioną ścieżkę: wejścia, wykonanie,
wynik, błędy i zależny rollback. Drugi review sprawdza poprawki i regresje
wynikające z diffu, nie ponawia ogólnego audytu. Po dwóch cyklach
`naprawa -> review` bez domknięcia tego samego zakresu zatrzymać automatyczny
trzeci mikrofiks i przekazać właścicielowi jedną diagnozę procesu, wszystkie
pozostałe `K0/K1` oraz jeden skonsolidowany zakres. Zmiana nazwy uwagi, pliku,
commita lub fixture nie zeruje licznika. Licznik stosuje się od D-23; nie
rekonstruować retrospektywnie dawnych cykli, lecz długą serię R04 domknąć na
aktualnym kontrakcie.

Zachowywać odbiory i dowody niezmienionych bajtów. Ponowienie wymaga zmiany
kodu/kontraktu lub istotnych warunków, dowodu regresji albo wymaganej świeżości
runtime. Błąd formatowania rozliczać z zachowanych danych, bez ponawiania
operacji hosta. Nie zwiększać timeoutu, nie usuwać asercji ani nie zmieniać
oczekiwania wyłącznie dla PASS. Nie ponawiać niepewnej mutacji ani nie odnawiać
zużytej zgody. Brak zgody operacyjnej, niewykonana praca, faktyczna wada i
ulepszenie są odrębnymi stanami.

#### Obowiązek ChatGPT przed review lub kolejnym promptem

Przed każdą merytoryczną oceną NEXT Stabil ChatGPT ponownie odczytuje przez
dostępny konektor: §0, ten rozdział `ANTI_EXCESSIVE_WORK`, aktywną kartę i
najnowszy właściwy checkpoint na raportowanym SHA. Jeden niezmieniony snapshot
w obrębie jednego review wystarcza. Brak dostępu trzeba ujawnić; pamięć rozmowy
nie zastępuje odczytu. Odpowiedź wskazuje zwięźle: rzeczywiste `K0/K1`, nowy
dowód uzasadniający kolejny fix, zachowane odbiory i jedną czynność prowadzącą
do zakończenia. Gdy nie ma nowego `K0/K1`, nie proponować kolejnego mikrofiksu
zamiast odbioru właściwego zakresu.

Każdy wynikowy raport, handoff, checkpoint, częściowy wynik i blocker Codexa
kończy się krótkim blokiem:

> **ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT**
>
> Przed oceną tej zwrotki i kolejnym promptem przeczytaj
> `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`: §0, `ANTI_EXCESSIVE_WORK` oraz
> aktywną kartę/checkpoint na pełnym SHA raportu.
>
> Nie wracaj do odebranych etapów i nie dodawaj `K2/K3` do warunków odbioru.
> `K0/K1` blokujące ten krok: `<ID + dowód / BRAK>`.
> Efekt użytkowy i pozostałe kryterium: `<jedno zdanie>`.
> Cykl `naprawa -> review`: `<n/2>`; następny krok: `<jedna czynność>`.

Raport podaje link do roadmapy przypięty do opublikowanego SHA. `ROADMAP_SYNCED`
wolno podać dopiero po push/readback; bez publikacji użyć `LOCAL_ONLY`.
Dokument nie tworzy kolejnego commita tylko po to, by wpisać własny przyszły
SHA — SHA publikacji znajduje się w odpowiedzi końcowej.

#### Zastosowanie do bieżącego R04 / D-21 / P4-B

| Poziom | Zamrożony stan i kryterium |
|---|---|
| Bieżący krok P4/B | Host22/NUP i D-23 `2/2` zachowują odbiory. Source `49c3f64c...` pozostaje `SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED`. USABLE-WARM status-only index przeszedł pełny package gate, VerifyOnly `VERIFIED_NO_MUTATION`, a skonsolidowany read-only preflight potwierdził 6/6 kontenerów, usługi hosta, HTTP i Windows/dyski. Docker/WSL pool i swap pozostają jawnie `UNKNOWN_NOT_MEASURED`. Stage B blokuje exact manifest `NOT_APPROVED` / runtime `START_NOT_APPROVED`; brak approved-manifest binding i autoryzacji |
| Kompletny pozostały wynik R04 | Jeden wspólny start i repeat bez duplikatów; odebrany logon/cold-start; kanoniczne ścieżki, manifest i tożsamości; rozliczone pozostałe ciężkie dane na D: z jawnym Qdrant/VHD/profile; zachowane i zweryfikowane w swoim zakresie harmonogramy backupu; zgodność wspieranych artefaktów/release. Techniczne P1–P4/Host22/NUP są dowodami wewnątrz tego wyniku |
| Późniejsze `K2/K3` | Kosmetyka, refaktoryzacja, dodatkowy hardening i cleanup starych miejsc po wykazaniu braku konsumentów nie rozszerzają bieżącego pakietu. Żadnego obowiązkowego kryterium właściciela — w tym danych D:, junctionu, backupów i jednego startu — nie wolno odroczyć samą zmianą etykiety |

Pełny plan R04 znajduje się w `R04_SINGLE_ROOT_STARTUP_PLAN.md` §8 i obejmuje
używalny warm CRM/Web, jedno wejście/logon/cold-start, dane D:/backup proof oraz
compatibility acceptance w czterech spójnych oknach. Nie otwiera to review
NUP-01/02/03, nie dowodzi świeżego stanu usług i nie upoważnia do Stage B ani
operacji hosta. D-22 pozostaje
nienaruszone i `NOT_RUN`;
po zakończeniu i właścicielskim odbiorze R04 nadal obowiązuje kolejność
`ARKUSZE -> KOREKTA I WALIDACJA KLIENTÓW -> TYLKO NIEPRZYPISANE MAILE`, wraz
z zapisanymi zasadami automatycznych klientów, historii zmian, dopasowania po
e-mailu lub telefonie i istniejącego cyklu n8n 15 minut.

### 0.2. Rejestr statusów pakietów — źródło bieżącego stanu

Statusy wszystkich pakietów w szablonie są PLANNED. `ACCEPTED` wymaga rzeczywistego
odbioru i wskazania decyzji właściciela; agent nie może sam sobie wystawić odbioru.
Git status/push nie oznacza statusu funkcjonalnego ani deploymentu.

| Pakiet | Status | Aktywny podetap / ostatni checkpoint | Dowód / review / pozostała bramka |
|---|---|---|---|
| R00 | ACCEPTED | `R00-20260907T204252Z-HANDOFF-B1` / OWNER REVIEW | Właściciel zaakceptował `ROADMAP_SYNCED@9af4026eeffed2509af943bff1e37b2514bfd5e8` |
| R01 | ACCEPTED | `R01-20260907T224502Z-HISTORY-C2` / OWNER REVIEW | Właściciel zaakceptował wynik na `535ab0b80d12d3f18b9f734dfb9e769c91e11e74` |
| R02 | ACCEPTED | `R02-20260908T065945Z-HANDOFF-C3` / OWNER REVIEW | Właściciel zaakceptował R02 na `883987f8ba422986db6893aa993da730fa9405a2`; FND-019 i REP-001–004 pozostają otwarte we właściwych późniejszych pakietach |
| R03 | WAITING_APPROVAL | `R03-20260909T064442Z-A4-ACCEPTANCE` / A4 ACCEPTED | Właściciel zaakceptował A4 na `92cc3aa38f0a81ff40e3798981970bd2e45b6206`: `DATA_RESTORE_VERIFIED_FOR_MANIFEST_8F20A784`. Cały R03 nadal `WAITING_ESCROW_DECISION`; credentials, recovery key, aplikacja, pełne RTO, cleanup i rollout pozostają niezatwierdzone/niewykonane |
| R04 | IN_PROGRESS | `R04-D21-P4B-USABLE-WARM-20260923T170936Z` / CONSOLIDATED READ-ONLY PREFLIGHT PASS; STAGE B MANIFEST BLOCKED | P3/P4-A, Host22 i NUP-01/02/03 odbiory zachowane; D-23 review `2/2`. Source `49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc` pozostaje `SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED`. Derived index `4A58DF7D...84DC` zmienia tylko top-level status; manifest jest `NOT_APPROVED`, authorization false. VerifyOnly = `VERIFIED_NO_MUTATION`; 6/6 pinned containers, PostgreSQL healthy, Public PRESENT, Private/Supervisor ABSENT, HTTP `200/200/200/404/404`, Windows/dyski PASS; Docker/WSL pool i swap `UNKNOWN_NOT_MEASURED`. Installed run01 pozostaje na starszych bajtach, Host historycznie disabled/no-trigger, warm `0/2`, Supervisor `INTENTIONALLY_STOPPED`. Runtime zwraca `START_NOT_APPROVED`, recepta nie wykonuje approval transition; Stage B jest `BLOCKED / NOT_AUTHORIZED`; P5/D-22 nie są uruchomione |
| R05 | IN_PROGRESS | `R05-20260914T184044Z-A4-BACKEND-TESTS` / A4 OWNER ACCEPTED SOURCE ONLY | Właściciel zaakceptował A4 source `04ab5e58cf86896ffd946cabffde13367d343f53` i evidence `8620871711321a42e62291e52865b5a668a4955d` jako `SOURCE_AND_API_WIDGET_TESTS_ACCEPTED / NOT_DEPLOYED`. A1/A2/A3 zachowują wąskie odbiory. Supervisor jest `INTENTIONALLY_STOPPED`; operator Web runtime, Temporary Chat, remote upload, locally_redacted generation i external end-to-end pozostają `NOT_VERIFIED` |
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

**Jeden aktywny kompletny zakres wykonawczy naraz.** Właściciel zleca Rxx lub
jawnie uzgodniony samodzielnie użyteczny segment; Codex wykonuje go do wyniku
albo rzeczywistego blokera, a ChatGPT ocenia cały rezultat. Zamknięcie kodu nie
jest automatycznym release. Dopuszczalne jest kontynuowanie bezpiecznej,
niezależnej części tego samego uprawnionego zakresu podczas oczekiwania na
osobną decyzję operacyjną; przejście do innego pakietu wymaga decyzji.

Pakiet może mieć techniczne etapy Rxx.a/Rxx.b/Rxx.c, ale nie są one
automatycznie osobnymi jednostkami odbioru ani obowiązkowymi pauzami. Nie
narzucamy limitu 2–3 plików, gdy kompletne zachowanie wymaga testu/API/UI; nie
dopuszczamy też nieograniczonego „napraw wszystko”. Zakres wynika z jednego
pełnego celu użytkowego i jego materialnych zależności.

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

Obowiązuje §0. Jeden aktywny zakres i jeden autor zmian naraz. Checkpoint
aktualizujemy przy materialnej zmianie stanu, realnym blokerze, przed faktyczną
pauzą i na końcu rezultatu; nie po każdej komendzie lub technicznym podkroku.
Checkpoint nie wymusza pauzy ani nowej zgody.
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

Nowy problem musi mieć wersję, konkretny wpływ i test rozstrzygający. Hipoteza
nie jest naprawiana jak potwierdzony bug. Zamknięty rezultat otwieramy tylko
dla odtworzonej regresji lub istotnego nowego dowodu dotyczącego jego warunku
odbioru. Usprawnienie niewpływające na kryterium nie jest automatycznie
naprawiane ani zamieniane w backlog. Jeżeli jest istotne dla końcowej jakości,
rozlicza je jeden szczegółowy audyt R23 — nie resetuje ono bieżącego projektu.

## 6. Kamienie odbioru i kolejność

### Pilny priorytet po właścicielskim odbiorze R04 — D-22

Ta kolejność zaczyna obowiązywać dopiero po zakończeniu i właścicielskim odbiorze
R04. Nie przerywa bieżącego R04/P4-B, nie uruchamia R12/R16/R20/R22 i nie
stanowi zgody na odczyt lub zapis danych:

1. **ARKUSZE:** audyt rzeczywistej ścieżki importu zatwierdzonych Excel/Google
   Sheets, usunięcie przyczyny nowych błędów i kontrolowana korekta historycznych
   pól klientów wyłącznie na podstawie arkuszy.
2. **KOREKTA I WALIDACJA KLIENTÓW:** dry-run per rekord/pole, ochrona poprawnych,
   ręcznych, potwierdzonych i świadomie pustych wartości, osobna zgoda na
   odwracalną partię, optimistic concurrency i post-check. Brak wystarczającego
   materiału arkuszowego pozostaje jawnym wyjątkiem; Gmail nie jest źródłem
   zastępczym. Każda propozycja wskazuje arkusz, zakładkę, stabilną tożsamość
   rekordu/komórki i wersję lub hash materiału; sam numer wiersza po sortowaniu
   nie wystarcza.
3. **TYLKO NIEPRZYPISANE MAILE:** dopiero po walidacji poprawionego zakresu
   klientów zamknąć stabilny zbiór wiadomości bez skutecznego powiązania,
   analizować wyłącznie ten zbiór i zmieniać wyłącznie dozwolone powiązanie oraz
   metadane decyzji. Już przypisanych wiadomości nie analizować ponownie ani nie
   przepinać; mail nie może poprawiać pól klienta.
4. Następnie pozostałe pilne poprawki CRM: ręczny wybór klienta poza sugestiami;
   zaznaczanie/licznik/bulk delete kandydatów z koszem; odporne scalanie grupowe;
   diagnoza credentials n8n/Google bez próbnej rotacji/restartu; opisowe błędy
   z zachowanymi kodami maszynowymi; oraz odrębne, pochodzeniowo bezpieczne
   uporządkowanie importowych bloków mailowych w notatkach, jeśli zostanie
   osobno objęte wykonaniem.

Wcześniejszy plan użycia arkuszy **oraz maili** do historycznej korekty klientów
jest zastąpiony. Historyczne dowody operacji pozostają niezmienione. Źródła
korekty historycznych pól: wyłącznie arkusze; liczba maili użytych do tej
korekty ma wynosić `0`. CRM i historia zmian służą jedynie identyfikacji,
porównaniu, wykrywaniu konfliktów i ochronie wpisów użytkownika. Audyt,
implementacja, modele i naprawa danych mają status `NOT_RUN`.
Model lokalny może później proponować ustrukturyzowaną interpretację tylko z
dowodami arkuszowymi, po wykazaniu jakości i odrębnym dopuszczeniu; nie jest
wymagany dla przypadków deterministycznych i nie otrzymuje dowolnego SQL.

Po przyszłym zatwierdzonym wdrożeniu arkusze są traktowane jako całość
dostępnych właścicielowi informacji dla tego zakresu. Jednoznaczny nowy wpis
tworzy bezpośrednio jednego klienta albo wiąże się z istniejącym; nie powstaje
obowiązkowy kandydat arkuszowy ani osobny monit dla każdego poprawnego wiersza.
Brak opcjonalnych danych pozostaje pusty. Stabilna tożsamość źródła, wersja i
identyfikator operacji chronią przed duplikatem po sortowaniu, przesunięciu,
retry albo timeoutcie. Nieczytelny, pusty, sprzeczny lub niejednoznaczny wpis
ma osobny wynik do rozliczenia, a historyczne kandydaty arkuszowe wymagają
kontrolowanego audytu zamiast masowej akceptacji/usunięcia.

Kandydat powstaje wyłącznie z kwalifikującego się maila, którego nie można
jednoznacznie dopasować do istniejącego klienta; awaria techniczna nie jest
`no-match`, a odpowiedzi jednego zgłoszenia nie tworzą kandydata per wiadomość.
Po zapisaniu klienta ręcznie/z arkusza albo właściwego kontaktu jednoznaczny
nierozstrzygnięty kandydat może zostać automatycznie połączony po e-mailu **LUB**
telefonie, z zachowaniem maili, dokumentów, relacji, provenance i audytu. Spór
e-mail kontra telefon, kontakt współdzielony lub kilka osób pozostaje wyjątkiem;
nie scala dwóch klientów i nie zmienia pól klienta na podstawie maila.

Zmiana wcześniej powiązanego wiersza Sheets dopisuje wersję źródła, nowe
rozpoznane informacje i widoczną historię `poprzednia -> nowa` przy tym samym
kliencie. Poprzednie dane nie są kasowane, automatyczny log nie trafia do
ręcznych notatek, a czasu/autora edycji nie wolno zgadywać. Wyczyszczenie
komórki, usunięcie wiersza, niedostępność źródła albo niepełny odczyt nie usuwa
klienta, kontaktów, dokumentów, relacji ani wcześniejszych wartości. Ponowne
pojawienie się rekordu korzysta z zachowanego powiązania. Nowa wartość bieżąca
może zostać wybrana automatycznie tylko według odebranej polityki pola i bez
konfliktu z wartością ręczną/główną/potwierdzoną/świadomie pustą.

Istniejący mechanizm n8n pozostaje jedynym harmonogramem przyrostowym co 15
minut dla nowych kwalifikujących się maili, nowych wierszy Sheets oraz zmian
powiązanych wierszy. Nie wolno co cykl czytać/analizować całej poczty ani tworzyć
drugiego schedulera. Brak zmian daje zero nowych klientów/kandydatów/wersji;
retry, nakładanie cykli i timeout po zapisie zachowują pojedynczy efekt, a błąd
pozycji nie może zniknąć przy przesunięciu kursora. Błąd credentials lub
niepełny odczyt ma jawny status oraz czas ostatniego udanego sprawdzenia i
przetworzenia. Deklaracja `15 minut` i ręczne `Execute` nie są dowodem działania;
późniejszy audyt musi sprawdzić realną konfigurację i wykonania.

Minimalna macierz odbioru D-22, rozdzielona między R12/R16/R20/R22:

- poprawny nowy wiersz, także bez danych opcjonalnych, daje jednego klienta i
  zero kandydatów arkuszowych; powtórzenie, sortowanie i przesunięcie nie
  dublują, a informacja w mylącej kolumnie ma właściwą semantykę albo wyjątek;
- jednoznaczny mail trafia do klienta bez kandydata, niedopasowany tworzy jednego
  kandydata dla zgłoszenia, a kolejności `kandydat -> klient` i `klient -> mail`
  kończą się pojedynczym powiązaniem po e-mailu **lub** telefonie;
- konflikt e-mail/telefon, kontakt współdzielony lub kilka osób nie scala
  klientów; ręczna zmiana/przypisanie wykonane w trakcie cyklu jest chronione,
  a retry, restart i równoległe zdarzenia nie dublują efektu;
- połączenie zachowuje wiadomości, dozwolone dokumenty/załączniki i audyt, nie
  dokleja całego wątku do notatek i nie poprawia pól klienta z maila;
- zmiana powiązanego wiersza zachowuje poprzednią i nową wersję, dodaje właściwy
  kontakt/pole/sprawę/obiekt albo jawny konflikt; historyczny błędny adres jest
  audytowalny, ale nie wraca jako bieżący cel mapy;
- wyczyszczenie komórki i usunięcie wiersza nie kasują danych CRM, ponowne
  pojawienie się wpisu nie dubluje, a identyfikator tylko błędny/sporny/
  historyczny nie uruchamia automatycznego scalenia kandydata;
- rzeczywisty później autoryzowany harmonogram potwierdza interwał 15 minut dla
  nowych maili, nowych wierszy i edycji starego wiersza; cykl bez zmian tworzy
  zero danych merytorycznych, a timeout/równoległość mają pojedynczy efekt;
- awaria źródła, niepełny odczyt lub wygasłe credentials jest błędem bez
  usuwania danych i pozornego `0 zmian`; wznowienie nie gubi ani nie dubluje
  pozycji, Gmail nie skanuje całej historii, a niezmienione Sheets nie trafiają
  ponownie do modelu bez potrzeby;
- szczegóły klienta pokazują poprzednią/nową wartość, źródło, czas wykrycia i
  rzeczywisty skutek; ręczne notatki pozostają odrębne, a brak autora/czasu
  edycji źródła nie jest uzupełniany domysłem.

Dokumentacyjny checkpoint tej polityki:
`docs/recovery/checkpoints/20260919T220056Z-D22-CRM-AUTOMATION-POLICY.md`.
Nie zastępuje aktywnego checkpointu operacyjnego R04/P4-B i nie zmienia jego
warunków STOP.

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

**Cel:** Dostarczyć i odebrać jeden zgodny zestaw: wspólny start/repeat/logon,
kanoniczne komponenty, dane D:/backup schedules i release compatibility, bez
utraty pracy lokalnej.

**Odpowiedzialność za wymagania:** M-003, M-004, M-065, M-072, F-023, F-034.

**Pozostałe powiązania:** M-015, M-057, M-064, F-022, F-024, F-031. **Ustalenia:** FND-004, FND-006, FND-013, FND-014, FND-015, FND-016, FND-023, FND-028.

**Zakres wykonania**

Pozostały R04 jest jednym kompletnym wynikiem zgodnie z D-23. Host22/NUP,
obserwacja usług, manifest, aktywacja, cold/logon, dane i zgodność wydania są
etapami i dowodami tego rezultatu; nie wymagają mikro-odbioru każdego helpera.
Jawne zgody na source, instalację, task writes, live start i dane pozostają
niezmienione.

1. Z clean base main zbudować kontrolowaną gałąź integracyjną. Ocenić pięć commitów rescue i lokalne różnice; przyjąć tylko potrzebne, przejrzane zmiany. Bez ślepego merge całego dirty repo.
2. Manifest łączy backend commit/image, API/schema, Web/Windows/Android build/hash/podpis, Supervisor, analysis/vision workers i efektywną niesekretną konfigurację.
3. Historyczna reguła przed D-21 dopuszczała odrębne odtwarzalne deployment roots. D-21 zastępuje ją dla stanu docelowego: `SINGLE_INSTALL_ROOT=C:\ai-lab-core`, jawne wersjonowane podkatalogi komponentów i jeden zwykły, idempotentny punkt startu. Dokładny junction `C:\ai-lab-core\data -> D:\ai-lab-data` jest świadomym wyjątkiem `ACTIVE_DATA_ONLY`; kod/skrypty/executable/CWD nie mogą z niego korzystać. P1 source/offline tests i P2 preservation/candidate są zaakceptowane jako NOT_DEPLOYED. Destination guard source `cb6e225...` z evidence `e9c17933...` jest zaakceptowany jako `OFFLINE_TEST_ONLY / NOT_DEPLOYED`; wiąże dokładny, case-sensitive kontrakt service/role/destination. Guard seed/reconcilera `0ee0ea5...` jest `BASE_START_GUARD_SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED`. Właściciel przyjął dowód danych P3 fresh pointu `E:\ai-lab-backup\20260917T082022Z`, manifest `2759D684...95597`, jako `ROLLBACK_POINT_DATA_EVIDENCE_ACCEPTED_WITH_RECORDED_LIMITATIONS`; tool provenance i odstępstwa pozostają zapisane, a spójność nadal jest `COMPONENT_WINDOWS_RECORDED_NON_TRANSACTIONAL / VERIFIED_LINKS_IN_TESTED_SCOPE`. Dla OP_ID `R04-D21-P3-CORE-SWITCH-20260917T141404Z` wykonano jedno backend-only przełączenie na source `0ee0ea5...`; dokładny runtime payload `592/592`, DB/schema/pending `18/16/1`, junction i pozostałe kontenery zachowano. Właściciel przyjął wynik jako `CORE_BACKEND_SOURCE_SWITCH_ACCEPTED / LIMITED_RUNTIME_SCOPE`. Późniejszy readback tej samej instancji potwierdził dwie warstwy środowiska `11/11 MATCH` i `9/9` przełączników `false`; pozostaje `CURRENT_READ_ONLY_EVIDENCE` bez bezpośredniego odczytu obiektu Settings. Kontynuacja P4-A odtworzyła brak pełnego ID binding i PostgreSQL health-gate, wdrożyła fail-closed source, zaliczyła testy offline i rozliczyła tożsamości 6/6; właściciel przyjął ją jako `SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / NOT_INSTALLED`. Pierwsza Phase B zatrzymała się po przeniesieniu wrappera i utworzeniu Host disabled/no-trigger. Późniejsze jednorazowe resume `R04-D21-P4B-RESUME-20260918T112015Z` zaakceptowało jeden UAC, lecz zatrzymało się przed mutacją na błędzie transportu argumentu `docker inspect` w PowerShell 5.1; `mutation_started=false`. Istniejące taski nie zostały zmienione, payload/manifest nie są zainstalowane, a warm runs pozostają `0/2`. Następna source/offline-only praca odtworzyła rozpad argv i przygotowała LOCAL_ONLY receptę `5F310C64...1FD67`; Windows PowerShell 5.1 zaliczył 17/17 przypadków, a jeden exact read-only Docker inspect przeszedł bez UAC i mutacji. Późniejszy static preflight ujawnił błędne wiązanie sześciu baseline paths. Następny LOCAL_ONLY pakiet `733AA23F...D05B6A` / `ED05FE26...875C` odtworzył fail-before i przeszedł Windows PowerShell 5.1 offline 14/14 oraz 119 asercji, wiążąc wszystkie 29 ról i sześć baseline bez live Docker/Task/HTTP/UAC/mutacji. Narzędzie ma `EXACT_PACKAGE_READY_FOR_REVIEW`, lecz stan instalacji pozostaje `PARTIAL_SAFE_INACTIVE / NOT_INSTALLED`. Produkcyjny globalny manifest pozostaje `NOT_APPROVED_FOR_START`; wcześniejsze zgody operacyjne są skonsumowane, a nowa operacja, relokacja, live startup/rollback acceptance, cleanup i P4-B/P5 wymagają dalszej zgody. Kolejny owner-authorized review odtworzył na preimage `RV-P4B-FULL-01–04` i przygotował LOCAL_ONLY receptę `16A35C32...0C4DC8` z indeksem `1355EF08...3E3BF`; finalne testy wejściowe 14/110 i orkiestracyjne 10/67 wykonały rzeczywiste funkcje z kompletnymi atrapami. Najnowsza kontynuacja odtworzyła `RV-P4B-FULL-03B/02B/02C` i przygotowała LOCAL_ONLY receptę `F6D3A8CC...C883F0E`, indeks `FDF9FE7A...A977F` oraz ZIP `D2B3263B...65DA1C`; końcowe testy wejściowe 14/110 i orkiestracyjne 15/96 rozliczyły 437/437 workerów bez live Docker/Task/CIM/TCP/HTTP/UAC/mutacji. Wynik ma `ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW / OFFLINE_ONLY / NOT_INSTALLED`. Produkcja nie może wykonywać recovery/staging/test WIP.
3a. Właściciel przyjął dokładne bajty `F6D3A8CC...C883F0E` jako `EXACT_ROLLBACK_SAFE_RECIPE_ACCEPTED / SOURCE_AND_OFFLINE_SCOPE / NOT_INSTALLED`. `VerifyInputsOnly` przeszedł, ale świeży preflight nie utrwalił pierwszej projekcji taska z powodu zbyt długiej ścieżki dowodowej. Odczytu nie ponowiono, UAC/Install nie uruchomiono, a status operacyjny pozostaje `PRE_UAC_BLOCKED` do nowej decyzji na replacement read-only preflight.
3b. Jedna owner-authorized zastępcza kampania read-only użyła krótkiego rootu i zaliczyła local I/O/path budget, lecz zakończyła się `PARTIAL`: sześć task XML utrwalono, pięć preimage jest exact-match, Host statycznie odpowiada disabled/no-trigger, ale projekcja dynamiczna przerwała się na braku `CimClass`. Bez ponowienia odczytu, Docker/HTTP/UAC/Install/warm runs. Installer output 252/275 pozostaje `NOT_VERIFIED`.
3c. Właścicielsko zatwierdzona poprawka LOCAL_ONLY kolektora usunęła zależność od `CimClass` i zaliczyła Windows PowerShell 5.1 `13/61`. Kontynuacja utrwaliła Task State `6/6`, host/resources/HTTP oraz bieżące safe records Docker dla `6/6` exact kontenerów. Wszystkie sześć TaskInfo zakończyło się błędem mapowania kolektora i nie zostało ponowione; `LastRunTime/LastTaskResult` pozostają `NOT_VERIFIED`. Docker formatter zawiódł po zapisaniu wszystkich exit-zero rekordów, dlatego projekcję zbudowano lokalnie bez kolejnego Engine read. Wynik `PREFLIGHT_EVIDENCE_PARTIAL / TASK_INFO_MAPPING_ERROR_NO_REREAD / NO_UAC / NOT_INSTALLED`; installer output `252/275` nadal `NOT_VERIFIED_NO_IO`.
3d. Następna owner-authorized kontynuacja naprawiła dokładną granicę TaskInfo i zaliczyła offline `16/126`; jedna kampania zapisała `TaskInfo 6/6`. Dokładna pochodna recepty `F65DF723...BF8C9A` zmienia wyłącznie metadane i output na `C:\ai-lab-core-staging\recovery\P4B-FIN-01\out\run01`; funkcje i wejścia pozostały byte-equal. Input `14/110`, orchestration `15/96` z `437/437` workerów, I/O/path budget `206<=220` i VerifyInputsOnly `29/29 + 6` przeszły. Bieżący drift potwierdził taski/kontenery/health i Windows/disk gates; Docker/WSL pool oraz swap-used pozostają `UNKNOWN`. Pakiet `36623A03...D49E`, ZIP `407A872A...D7272`; status `SHORT_OUTPUT_DERIVATIVE_READY_FOR_REVIEW / TASKINFO_6_OF_6 / NO_UAC / NOT_INSTALLED`. Operacja wymaga nowej bieżącej decyzji właściciela.
3e. Właściciel odebrał ograniczoną zmianę short-output i jednorazowo zatwierdził resume `R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z`. Jeden RunAs/UAC doprowadził do instalacji dokładnych trzech plików i manifestu oraz docelowych definicji tasków. Pierwsze uruchomienie Host zakończyło się `LastTaskResult=22` przed startem Private Gateway. Recepta wykonała jedyny SAFE_INACTIVE, ale Public Gateway pozostawał `Running`, dlatego zależny rollback plików/helpera został prawidłowo pominięty, a wynik to `PARTIAL_AFTER_FAILURE / SAFE_INACTIVE_PARTIAL_UNKNOWN`. Host jest `Disabled/no-trigger`, warm `0/2`, logon trigger nie został zainstalowany. Pooperacyjny odczyt potwierdził sześć niezmienionych działających kontenerów, PostgreSQL healthy, backend/Public Gateway `200` i publiczne `/control*=404`. Szczegół wyniku launchera nie został przechwycony; `HOST_TASK_FAILED_22 / LAUNCHER_RESULT_DETAIL_NOT_CAPTURED` wymaga owner-reviewed zakresu diagnostycznego, bez retry w ramach zużytej zgody.
3f. Ograniczona read-only diagnoza bez ponowienia Host wykazała opcjonalny Health template failure i broad selector pięciu backend-labelled kontenerów. Następna właścicielsko zatwierdzona praca SOURCE/OFFLINE przygotowała commit `ed961d6980ebebe2e4d351319e2aa909437bc1ec`: mała projekcja rozróżnia `NOT_CONFIGURED` od `healthy`, a wybór/readiness/cold start wiążą się z pełnym manifest ID i bounded conflict scan. Preimage reprodukuje count `5`/starty `0`; końcowe PS 5.1 `37/53/51/44/16` przeszły bez produkcyjnych granic. Nieaktywny candidate pozostaje `NOT_APPROVED_FOR_START`, ZIP review `76A8999E...E74DBC` ma roundtrip `10/10`. Status `HOST22_HEALTH_AND_EXACT_ID_SOURCE_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED`; installed run01 nie został zmieniony i retry nadal wymaga osobnej decyzji.
3g. Kolejna owner-authorized kontynuacja SOURCE/OFFLINE na preimage `ed961d6980...` odtworzyła `RV-H22-OBS-01/02/03`. Source `b4269ffa7bacc95b4d1441bb196e572a34a4ec43` wymaga jawnie kompletnej koperty natywnej, przekazuje jeden malejący monotoniczny deadline przez observation/readiness i uznaje przypięty kontener za gotowy wyłącznie przy `running=true` oraz `state_status=running`. Paused/restarting/removing/dead/unknown i stale healthy PostgreSQL nie przechodzą; istniejący cold start created/exited pozostał. Końcowe PS 5.1 `51/57/51/44/40` przeszły przy granicach produkcji `0`. ZIP `4EB0706A...12ADBD9` i indeks `CE373406...3B5763` są LOCAL_ONLY w TEMP, ponieważ istniejący staging odmówił zapisu bez elewacji, której nie użyto. Status `HOST22_OBSERVATION_COMPLETENESS_DEADLINE_AND_STATE_SOURCE_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED`; run01 i D-22 są nietknięte, Host retry/update nadal nieautoryzowane.
3h. Końcowy review na preimage `b4269ffa...` odtworzył `RV-H22-OBS-01B/02B`: wartości null/pusty lub błędny typ pól kompletności przechodziły jako false, a gotowy RUNNING/HEALTHY mógł zostać zatwierdzony po deadline. Source `8195e5cf8dacd1976ccd9f71a1f78175c3513acc` wymaga rzeczywistych Boolean/string/int w kopercie i sprawdza ten sam stage deadline bezpośrednio przed `PRESERVE_RUNNING`. `PKG-HASH-01` został domknięty przez niezależny binding `files[] -> payload path -> size/SHA -> current review metadata`; candidate pozostaje `NOT_APPROVED`. Końcowe PS 5.1 `70/57/51/44/41`, candidate+P4 `59`, binding po ZIP `18` przeszły przy granicach produkcji `0`. LOCAL_ONLY ZIP `D6F48B9E...39C27AEA` ma roundtrip `21/21`. Status `HOST22_FINAL_OBSERVATION_CONDITIONS_AND_MANIFEST_BINDINGS_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED`; installed run01 i D-22 pozostają nietknięte.
3i. Po właścicielskim odbiorze Host22 pierwszy zbiorczy review D-23 potwierdził w kodzie `NUP-01/02/03` (`K0/K0/K1`). Fail-before na exact preimage wykazał błędne `FAILED/settled`, nieograniczony read, brak kontroli obcego disabled Host/file backup oraz niepełny warm result. Source `d3435afcfb89d02d91f2db3d1eb55be17fd790bd` nie uznaje własnego childa recordera za settled bez dowodu. LOCAL_ONLY recepta `0B051C2F...B9EF` używa zamkniętej bounded granicy i trwałego mutation journal, wymaga ownership+idle oraz before/after hash przy rollbacku i akceptuje dopiero dwie odrębne kompletne próby z utrwalonymi streamami i zdarzeniami `Private 1 -> 0`; `START_EXISTING` jest niedopuszczony. Końcowe PS 5.1: recorder `32` asercje / `8` child cases, orkiestracja `51` asercji / `16` scenariuszy, produkcyjne granice `0`; indeks `67B32FB8...8222`, ZIP `C34B9460...7A1F`, roundtrip `28/28`. Status `ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW / OFFLINE_ONLY / NOT_INSTALLED`. To nadal cykl D-23 `1/2`; następny krok to niezależny review tego diffu, bez automatycznego trzeciego mikrofiksu.
3j. Review D-23 `2/2` zakończył ocenę poprzednika: NUP-01 i NUP-02 zachowują PASS, a jeden pozostały K1 NUP-03 dotyczył wyłącznie zakończenia właściwego Host po zapisaniu kompletnego wyniku. Na exact recepcie `0B051C2F...B9EF` fail-before wykazał pierwszy warm `SUCCESS` przy Host nadal `Running`/1 instance, po czym drugi krok został odrzucony. Właścicielsko zatwierdzona pochodna zmienia tylko `Invoke-P4BWarmAttempt`: po pełnej walidacji nowego evidence wykonuje świeży bounded read expected Host; `Running/Queued` czeka w tym samym deadline, a SUCCESS wymaga exact semantic hash i pozytywnie zerowych running/queued instances. Unknown/foreign/deadline nie uruchamia drugiego warm ani logon i zachowuje pliki. Recepta `DC1295C3...C4A0A`, index `B3B50FD3...07919`, ZIP `3ED49CB3...FA09D`; PS 5.1 `70` asercji / `20` scenariuszy, Host `2`, Private `1 -> 0`, container/Supervisor/5 dependency-task writes `0`, produkcyjne granice `0`, unsettled `0`. Status `NUP03_HOST_COMPLETION_SOURCE_FIX_READY_FOR_VERIFICATION / OFFLINE_PASS / NOT_DEPLOYED`; następny krok to weryfikacja wyłącznie tego diffu i odbiór przy PASS, bez dalszego poszukiwania K2/K3.
3k. Właściciel przyjął exact NUP-03 package jako `SOURCE_AND_OFFLINE_PACKAGE_ACCEPTED / NOT_DEPLOYED` i dopuścił jeden Stage A. Integralność package `33/33`, ZIP `34/34` i payload bindings `8/8` przeszła. Jedyny niepodniesiony VerifyOnly zakończył się exit `22` / `TASK_DEPENDENCY_DRIFT` dla `NEXT Stabil - Docker Desktop`, bez journalu, mutacji, warm runu lub rollbacku. Jedna niezależna projekcja read-only zachowała odpowiedzi: pięć kontenerów zgodnych, PostgreSQL healthy i resource gates PASS; backend odrzucony na mount representation, trzy host services zwróciły `IDENTITY_MISMATCH`, a Host był Disabled i bez instancji, lecz miał jeden trigger i obcy semantic hash. Lokalny formatter zakończył projekcję przed HTTP; odczytów nie ponowiono. Wynik `P4B_STAGE_A_BLOCKED / NO_STAGE_B_AUTHORIZATION_REQUESTED`; brak UAC, update, Host start/retry, task write lub rollbacku.
3l. Skonsolidowany owner-authorized P4B-STAGEA-GATE nie ponowił VerifyOnly. Source `e8ad5e27bc8515e6536b5fc8696608b3d9c6e7de` dopuszcza wyłącznie separator absolutnego Windows bind source oraz tę samą akcję taska po bezpiecznym parsowaniu argv i rozstrzygnięciu jednego skryptu względem exact CWD/rootu. Host/dependency XML porównuje osobny comparable hash po normalizacji EOL/końcowego separatora, a trigger count pochodzi z elementów potomnych XML. Jedyny świeży read-only capture czterech exact tasków zakończył się `4/4 OBSERVED / 4/4 NORMALIZED_MATCH`, task writes/starts `0`; safe result SHA-256 `5D990650...10028`. Finalne offline testy focused/P1/adapters/DATA_ONLY/P4/NUP są PASS. Status `P4B_STAGEA_GATE_NORMALIZATION_SOURCE_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED`; HTTP, fresh six-container preflight i live VerifyOnly są `NOT_RUN`, a Stage B `BLOCKED / NOT_AUTHORIZED`.
3m. Review Stage-A wykazał jeden materialny K1 ciągłości Host: preflight akceptował zachowany raw XML `85C4...` przez pinned comparable `7BBC...`, lecz późniejszy Register/Start/Rollback wymagał wyłącznie raw hash docelowego XML. Fail-before na pełnej orkiestracji zatrzymał się po czterech własnych zmianach fixture, przed leaf Register, z warm `0`; dowód `C7D0D1...0587F`. Pochodna LOCAL_ONLY rozszerza wspólną kontrolę własności tylko o przypięte pary raw/comparable dla preimage/disabled/on-demand/logon, zachowując osobno akcję, principal, trigger, enabled, bezczynność, dziennik i pending-operation. Obcy raw+comparable, obca akcja/trigger/principal, UNKNOWN i aktywny Host nadal blokują; rollback zgodnych własnych plików pozostaje dodatnim przypadkiem. Końcowy PS 5.1: `91` asercji / `26` scenariuszy, Host starts `2`, Private `1 -> 0`, container/Supervisor/unapproved/dependency-task writes `0`, własne procesy `1/1`, unsettled `0`, produkcyjne granice `0`. Recepta `FD8DB2C5...BBCFE`, package index `0BC434D9...6CDD`, ZIP `F0BE2DB3...8298`. Status `P4B_STAGEA_HOST_IDENTITY_CONTINUITY_SOURCE_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED`; review D-23 `2/2` nie jest resetowany, następny krok obejmuje wyłącznie ten diff i bezpośrednie regresje.
3n. Właściciel przyjął dokładny diff Host identity continuity jako `P4B_STAGEA_HOST_IDENTITY_CONTINUITY_SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED` i dopuścił jedno niepodniesione VerifyOnly. Top hashe `4/4`, payload bindings `8/8`, local I/O i brak kolizji `out` przeszły. Jedyna próba `R04-D21-P4B-HOST-IDENTITY-VERIFYONLY-20260921T171832Z` użyła PS 5.1 `-NoProfile`, exact recipe/index i zakończyła się exit `1` po `958` ms: `Get-P4BSha256` wywołał nierozpoznany `Get-FileHash` podczas lokalnej walidacji paczki. `stdout` `0` B, `stderr` `653` B / `9C578DD4...F205`; `result.json` i `out` absent. Kod nie dotarł do `New-RealP4BNarrowUpdateBoundary/ObserveTask`, więc Task Scheduler reads/writes/starts, journal, mutation, warm, rollback, Docker/HTTP/CIM/TCP/SQL/UAC/install wynoszą `0`. Retry nie wykonano, zgoda jest zużyta. Status `P4B_VERIFYONLY_BLOCKED_LOCAL_PREREQUISITE_GET_FILE_HASH_UNAVAILABLE / NO_TASK_READS / NO_MUTATION`; następnym krokiem jest wyłącznie minimalna SOURCE/OFFLINE zgodność hash pliku z PS 5.1 i review przed ewentualną nową zgodą VerifyOnly.
3o. Właścicielsko zatwierdzona minimalna praca SOURCE/OFFLINE zmieniła wyłącznie `Get-P4BSha256` w LOCAL_ONLY recepcie: literalny read-only stream, `System.Security.Cryptography.SHA256.ComputeHash` oraz zwolnienie stream/hashera w `finally`; `Get-P4BTextSha256`, operacje, deadline'y, osiem payload bindings, XML-e, manifest i operation ID pozostały bez zmian. Preimage `FD8DB2C5...BBCFE` wywołał dokładny poison-pill raz, a finalna recepta `CA6A5DCC...87157` nie wywołała `Get-FileHash`. PS 5.1 `5.1.26100.8894` zaliczył focused `35` asercji / `15` scenariuszy w `4/4` rozliczonych procesach: znane bajty/CRLF-LF/BOM/lock/handle, rzeczywisty package gate z podmianą/brakiem oraz rzeczywisty `Invoke-P4BNarrowUpdate -Mode VerifyOnly` z kompletną syntetyczną granicą. Produkcyjne granice `0`; finalny package gate po aktualizacji indeksu `8/3` PASS. Package index `C2F6A77C...2B8AA`, review index `A4D2A5DB...732DE`, ZIP `0DE0E072...14F8` (`223585` B, roundtrip `87/87`). Status `P4B_PS51_SELF_CONTAINED_FILE_SHA256_SOURCE_READY_FOR_REVIEW / FOCUSED_OFFLINE_PASS / NOT_DEPLOYED`; następny krok to wyłącznie review tego diffu. Live VerifyOnly, UAC, Stage B, Host retry i operacje hosta nie są autoryzowane; D-23 pozostaje `2/2`, bez K2/K3.
3p. Właściciel przyjął exact helper jako `P4B_PS51_SELF_CONTAINED_FILE_SHA256_SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED` i zezwolił na jedno nowe VerifyOnly pod warunkiem zgodności czterech top-level artefaktów. Lokalny .NET SHA-256 potwierdził receptę `CA6A5DCC...87157`, package index `C2F6A77C...2B8AA`, review index `A4D2A5DB...732DE` i `8/8` payload bindings. Exact ZIP `223585` B / `0DE0E072...14F8` nie istniał w przypiętym rootcie ani pod dokładną nazwą w sprawdzonych rootach dowodowych. Roundtrip nie został przepakowany. `vfy1/out` pozostały absent, proces recepty i Task Scheduler reads `0`, bez retry i bez mutacji. Status `P4B_VERIFYONLY_NOT_RUN / BLOCKED_LOCAL_PREREQUISITE_REVIEW_ZIP_MISSING / NO_TASK_READS / NO_MUTATION`; Stage B pozostaje zablokowany. D-23 `2/2` nie jest resetowany i nie otwarto K2/K3.
3q. Właściciel dostarczył oryginalny ZIP `223585` B / `0DE0E072...14F8`; został skopiowany bez overwrite, przepakowania lub zmiany pakietu i ponownie zweryfikowany jako byte-identical. Końcowa bramka potwierdziła `4/4` top-level, `8/8` bindings i unchanged operation ID. Dokładnie jeden ordinary-token Windows PowerShell 5.1 VerifyOnly (`2026-09-22T07:46:18.3640556Z`–`07:47:13.7134368Z`) zakończył się exit `0`, bez timeoutu, z rozliczonym procesem/strumieniami. `result.json` ma `VERIFIED_NO_MUTATION`, mutation/pending false, changed roles i warm runs puste, journal `NOT_OPENED`, rollback `NOT_NEEDED`, pięć dependency tasks bez zmian i helper bez zmiany. Recepta wykonała bounded read-only pięciu dependency tasks i Host; writes/starts/UAC/Stage B/install/rollback i inne granice wyniosły `0`, HTTP/fresh six-container preflight `NOT_RUN`. Status `EXACT_REVIEW_ZIP_RESTORED_FROM_OWNER_SUPPLIED_IDENTICAL_BYTES / P4B_VERIFYONLY_PASS / CURRENT_READ_ONLY_TASK_AND_FILE_EVIDENCE`; nie jest to odbiór Stage A/P4-B/R04 ani zgoda na mutację. D-23 pozostaje `2/2`, bez K2/K3.
3r. W jednym owner-authorized zakresie SOURCE/OFFLINE source
`49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc` domknął dwie wykazane przyczyny
host-service gate: tylko code token procesu jest porównywany kanonicznie pod
approved root, a listener collection wykonuje pełny bounded snapshot bez
`-LocalPort` i lokalny exact-port filter. PS5.1 real-adapter/plan `53` i direct
plan `57` są PASS; produkcyjne granice `0`. Launcher ma raw SHA-256
`686F4EC8...14B66`; nieaktywny draft `967E9C2C...00457` pozostaje
`NOT_APPROVED / NOT_DEPLOYED`. Installed run01, Host, kontenery, Supervisor,
dane i backupy nie zostały zmienione. Pełna droga do zamknięcia R04 jest
zamrożona w `R04_SINGLE_ROOT_STARTUP_PLAN.md` §8; pierwszym przyszłym
samodzielnie użytecznym segmentem jest `R04-P4B-USABLE-WARM`, wymagający nowej
zgody i osobnego bieżącego potwierdzenia przed UAC/Stage B.
3s. Właściciel następnie jawnie zatwierdził dokładnie jeden skonsolidowany
read-only preflight istniejącego okna
`R04-D21-P4B-USABLE-WARM-20260923T170936Z`. Lokalna kontrola PS5.1 ponownie
potwierdziła receptę `74E5664F...B7D6D`, indeks `6F379DC5...64698`, `8/8`
bindingów, parsery i brak kolizji `verifyonly`/`apply`. Przewidziana formalna
ścieżka odrzuciła jednak exact `VerifyOnly` przed `CreateProcess`, twierdząc, że
brak rozpoznanej bieżącej zgody na live Task/system read. Nie użyto retry ani
alternatywnego runnera i zgodnie z warunkiem STOP nie wykonano Docker/CIM/TCP/
HTTP/resource reads. Bezpieczny rekord odmowy ma `1998` B / SHA-256
`D9A547A45147DD60249EDBFA2FC295F181386F56D8E1F08D2AE148D385E64AFE`.
Manifest nadal ma `NOT_APPROVED`, indeks authorization pozostaje false,
`apply` nie istnieje, installed run01 i wszystkie usługi są nietknięte. Status
`P4B_USABLE_WARM_READ_ONLY_PREFLIGHT_FORMALLY_REFUSED_NOT_RUN /
STAGE_B_NOT_ELIGIBLE_NOT_AUTHORIZED`; brak podstaw do zdania zgody na UAC.
4. Naprawić kontrakt /version/stable/minimum/debug i zgodność starych klientów. Nie zrównywać sztucznie różnych numerów API/schema/app; muszą tworzyć poprawną macierz zgodności.
5. Przygotować odtwarzalny build Windows i aktualny build testowy Android z zatwierdzonym certyfikatem; nie publikować ani zużywać numeru release bez osobnej zgody.
6. D-17 kieruje bieżący odbiór wspólnego API i logiki najpierw przez Web. Android pozostaje wspieranym, nieodebranym targetem; wąski viewport Web nie zastępuje natywnego lifecycle, uprawnień, aparatu/GPS, transportu ani podpisu Androida.

**Sprawdzenia i dowody**

- Każdy runtime hash ma odpowiednik zatwierdzonego artefaktu; publiczny /control nadal niedostępny, rzeczywista konfiguracja debug bezpieczna.
- Aktualny stable klient zachowuje kompatybilność; candidate klient używa właściwego API; rollback komponentu udowodniony.
- Web-first nie zezwala na łamanie wspólnego API ani maskowanie błędu backendu w kliencie; nowy Android build jest potrzebny dopiero po późniejszej zmianie lub osobno zatwierdzonym odbiorze platformy.

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

**Bieżący dowód wykonawczy A1/A2/A3/A4:** właściciel zaakceptował A1 source
`d31e105427acd40733e91c4d4b46f0412b0f95ad` i evidence
`05995ab2c87438c5786a9f874793e95d2bf5b296` jako
`SOURCE_AND_SYNTHETIC_TESTS_ACCEPTED / NOT_DEPLOYED`. Dowód A1 obejmuje
świeżą kontrolę na granicy claim → submit, trwałość candidate między requestami,
wersjonowany server-derived scope, rzeczywiste współbieżne wejścia V1/V2 oraz
trwałe rozróżnienie pewnej odmowy przed kontaktem od możliwego rozpoczęcia
kontaktu. Historyczne claimy bez nowego markera pozostają fail-closed. A2 source
`dc075426c233ac204cec144be04cb66e74349702` zachowuje dowód exact-byte do fake
`setInputFiles`. Kontynuacja na source
`d1b0518ad9aefb5bc05cd89308de923ca54d2809` została zaakceptowana wraz z
evidence `60b1736db9eb18ef5445a2d8407988106ff96407` jako
`SOURCE_AND_OFFLINE_BOUNDARY_ACCEPTED / NOT_DEPLOYED`: rzeczywiste moduły
odtworzyły fail-before dwóch fake uploadów, a po zmianie wyłączne utworzenie
markera V2 i recheck kolejki dały co najwyżej jeden fake upload dla tego samego
job/source binding. Marker przerwany, historyczny albo potwierdzony nie jest
nadpisywany; potwierdzenie wymaga właściwej próby. A3 następnie przekazało
zaakceptowane syntetyczne bufory przez rzeczywisty lokalny Playwright/Edge
`setInputFiles` i niezależnie odczytało zgodne nazwy, MIME, rozmiary i SHA-256 z
DOM `FileList`. Wynik to `REAL_BROWSER_FILELIST_EXACT_BYTES_PASS` oraz
`LOCAL_BROWSER_FILE_INPUT_READY_FOR_REVIEW / TEST_ONLY`. Temporary Chat mode,
zdalny uploader, UI operatora, eksport sieciowy i external end-to-end pozostają
`NOT_VERIFIED`. Właściciel zaakceptował A3 evidence
`1ae3f99edd5cb39b9cb795ba573878e9ded6b30e` jako
`LOCAL_BROWSER_FILE_INPUT_ACCEPTED / TEST_ONLY / NOT_DEPLOYED`. A4 source
`f3cbe58bed0de34cfd39a57d481abb2c61c2f4ac` dodaje admin-only endpoint, który
zwraca jeden sprawdzony bufor finalnego rastra związany z aktualnym
document/job/source/scope/package, oraz dialog Flutter wymagający jawnego
rodzaju i czasu zgody. Testy backend/API/widget obejmują public-safe,
istniejący locally-redacted, role, scope/hash conflict, cancel, double-click,
unused revoke i stan niepewnego kontaktu. To
`OPERATOR_APPROVAL_SOURCE_READY_FOR_REVIEW / NOT_DEPLOYED`; operator Web
runtime, Temporary Chat mode, remote upload i external end-to-end nadal są
`NOT_VERIFIED`. Nie zmienia to warunku zamknięcia całego R05 ani zakresu R06.
Kontynuacja RV05-A4-01/02 potwierdziła statycznie brak ekspozycji trzech
nagłówków preview oraz odtworzyła na prawdziwym dialogu mylne komunikaty po
timeout i stary stan przedstawiany jako bieżący. Lokalny WIP dodaje wyłącznie
endpointowe `Access-Control-Expose-Headers` dla `X-Source-Ref`,
`X-Content-SHA256`, `X-Package-SHA256` oraz rozróżnienie potwierdzonego wyniku,
potwierdzonej odmowy 4xx i nieznanego dostarczenia odpowiedzi. Flutter focused
`11/11`, Documents/Auth `28/28` i analyze przeszły. Wymagany test prawdziwego
routera/CORS oraz compileall w przypiętym obrazie są `NOT_RUN` z powodu
`RESOURCE_OBSERVABILITY_BLOCKED`; patch SHA-256 `81E311E7C129FC7ACC8829BC8B2E3FB31CDFEA6F800D56EE46E16E9E58A17914`
pozostaje `LOCAL_ONLY / SOURCE_PARTIAL / NOT_DEPLOYED`, bez samodzielnego READY.
Wznowienie na `215432831278c0c417bc950ccc8406718be604a1` potwierdziło ten sam
patch, wynikowe hashe czterech plików i niezmienione dowody Fluttera. Context
`desktop-linux`, endpoint i bieżąca pula WSL były czytelne, ale żądanie
`docker version` do właściwego Engine zakończyło się bounded timeoutem po
`20.235 s` bez stdout/stderr. Dlatego dokładny stary kontener pozostaje
`UNKNOWN`, obrazu nie zweryfikowano, nie utworzono nowego kontenera i nie
uruchomiono backend ASGI/CORS/API/compileall. Stan pozostaje
`SOURCE_PARTIAL / LOCAL_ONLY / RESOURCE_OBSERVABILITY_BLOCKED`.

Po jednym zatwierdzonym Restarcie Docker Desktop GUI zgłosiło
`Wsl/Service/CreateInstance/0x800705b4`. Właściciel następnie zgłosił aktualizację
Docker wykonaną poza Codexem. Po tej zmianie Engine `29.8.0` odpowiada, a
faktyczne `Mounts` kontenera backendu potwierdzają
`/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend` i brak recovery/WIP;
stary kontener A4 nie istnieje. Backend, n8n i Open WebUI zwracają `200`, lecz
Supervisor i public gateway pozostają nieosiągalne. Zgodnie z bramką operacyjną
test backend ASGI/CORS/API i compileall nadal są
`NOT_RUN / PRODUCTION_PARTIAL_UNHEALTHY`. Bieżący stan A4 to
`SOURCE_PARTIAL / LOCAL_ONLY / NOT_DEPLOYED`, bez samodzielnego READY.

Kontynuacja host-services `2026-09-14T17:16:01Z` przywróciła istniejący Public Gateway jednym startem (`127.0.0.1:8789`; Web/API health `200`; `/control*` = `404`). Supervisor nie został uruchomiony: read-only gate ujawnił aktywne źródła pracy i oczekujące statusy (`advanced_queued=16`, `document_preparation queued=18`, `assistant waiting=1`, `vision not_evaluated=5956`) oraz niepusty spool. Nie zmieniono producerów, kolejek ani danych. Backend A4 ASGI/CORS/API/compileall pozostaje `NOT_RUN`; potrzebna jest jawna decyzja o `INTENTIONALLY_STOPPED` i dopuszczeniu izolowanej kampanii mimo tej świadomej bramki.

Właściciel następnie świadomie zatwierdził pozostawienie Supervisora jako
`INTENTIONALLY_STOPPED` i jedną izolowaną kampanię backendu A4. Preimage routera
`f3cbe58bed0de34cfd39a57d481abb2c61c2f4ac` odtworzyło właściwy fail-before:
nowy test rzeczywistego routera i middleware CORS zakończył się `1 failed`,
exit `1`, z brakiem `Access-Control-Expose-Headers`. Na zachowanym WIP cały
`test_r05_visual_export_api.py` przeszedł `3 passed`, exit `0`, a compileall
routera i testu zakończył się exit `0`. Source commit
`04ab5e58cf86896ffd946cabffde13367d343f53` zawiera dokładnie cztery wcześniej
zabezpieczone pliki backend/Flutter. Testowy kontener miał `network=none`,
read-only root/source, tmpfs, brak portów i produkcyjnych mountów; po teście
został zatrzymany i usunięty. Public Gateway/API/n8n/Open WebUI nadal zwracały
`200`, `/control*` = `404`, a Supervisor pozostał nieosiągalny. A4 ma status
`PREVIEW_TRANSPORT_AND_DECISION_FIX_READY_FOR_REVIEW / NOT_DEPLOYED`;
operator Web runtime, Temporary Chat, remote upload i external end-to-end są
nadal `NOT_VERIFIED`.

Właściciel następnie zaakceptował A4 dla funkcji z
`f3cbe58bed0de34cfd39a57d481abb2c61c2f4ac`, końcowego czteroplikowego source
`04ab5e58cf86896ffd946cabffde13367d343f53` i evidence
`8620871711321a42e62291e52865b5a668a4955d` jako
`SOURCE_AND_API_WIDGET_TESTS_ACCEPTED / NOT_DEPLOYED`. Odbiór nie rozszerza
testu ASGI/CORS do Web E2E ani wcześniejszych wyników Fluttera do nowych
wykonań; operator Web runtime, locally_redacted generation, Temporary Chat,
remote upload i external end-to-end pozostają `NOT_VERIFIED`.

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
5. Zachować decyzje D-15/D-16: nie klasyfikować braku kompletu dokumentów jako automatycznej odmowy, gdy można uzasadnić warianty/estymację, i nie dopytywać o fakt już dostępny w uprawnionych źródłach sprawy. Nieprzeczytany materiał ani błąd retrieval nie są rzeczywistym brakiem.

**Sprawdzenia i dowody**

- „Czy możesz przeanalizować ten dokument?” przy wybranym materiale uruchamia analizę; prawdziwe pytanie o możliwości nadal otrzymuje opis.
- Technika + adres ma oba lokalne zakresy i poprawną izolację klienta; brak celu jest jawny, a nie domyślnie zgadywany.
- Osobno odebrać: uzasadnioną estymację przy niepełnych danych, odmowę samej bezpodstawnej liczby bez odmowy całej pomocy oraz dopytanie dopiero po wyczerpaniu uprawnionych źródeł i rozsądnych wariantów.

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
6. Po wybraniu klienta/sprawy etapowo zebrać pełny potrzebny, uprawniony obraz z karty klienta, poczty i załączników, dokumentów, wizji, notatek, pomiarów, zdjęć i realizacji. Zachować wersje, konflikty, aktualność, tenant scope i provenance; nie mylić błędu odczytu z brakiem danych.

**Sprawdzenia i dowody**

- Test 5+3+4 nie traci całej wymaganej KB; kontekst mieści się w zatwierdzonym budżecie 9B. Gdy wymagania nie mieszczą się, system etapuje lub zgłasza zakres, nie twierdzi complete.
- Cel poza globalnym top-N jest znaleziony; fault injection odróżnia awarię; S235/S355 dozwolone, rzeczywiste niedopuszczone handle/obce źródła odrzucone.
- Dla explicit covered page wynik przechodzi; broad partial wymaga uzupełnienia; żadne evidence nie pochodzi od innego klienta.
- Rozproszone, lecz wystarczające dane sprawy są rzeczywiście przekazane do kolejnych etapów bez zbędnego dopytania; błędny scope, nieaktualny pomiar i sprzeczne źródła są jawnie rozstrzygnięte. Kryterium nie oznacza nieograniczonego jednorazowego kontekstu.

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
5. D-22 ogranicza pilną kampanię historycznej poczty po R04 do stabilnego snapshotu **wyłącznie wiadomości nieprzypisanych**, wyznaczonego z metadanych i rzeczywistych relacji po walidacji klientów. Już przypisanych wiadomości nie analizować ani nie przepinać; nie pobierać hurtowo wątków/załączników i nie używać maili do zmiany pól klientów.
6. W przyrostowym przepływie najpierw dopasować kwalifikujący się mail do istniejącego klienta po prawidłowym e-mailu, telefonie i dozwolonym kontekście. Kandydat mailowy powstaje tylko przy braku jednoznacznego klienta; błąd odczytu/credentials/parsera/zapisu pozostaje błędem, a nie `no-match`. Odpowiedzi tego samego zgłoszenia wykorzystują jednego właściwego kandydata.
7. Po utworzeniu klienta ręcznie/z arkusza lub dodaniu dozwolonego kontaktu automatycznie rozwiązać jednoznacznego kandydata po e-mailu **LUB** telefonie, zachowując źródła, wiadomości, dokumenty i audyt. Konflikt identyfikatorów/współdzielony kontakt blokuje tylko tę pozycję; mail nie zmienia pól klienta i nie przepina istniejącego powiązania z innym klientem.

**Sprawdzenia i dowody**

- Local success przy vision_auto_eligible=false wywołuje drugi pass bez Vision; brak duplikatów i cross-client links.
- Niejednoznaczne pozostają do review; forced failure/retry nie nadpisuje ręcznej decyzji.
- Provider/DB comparison podaje wyraźne okno i kompletność; compose/send test używa stub/sandbox i potwierdzenia człowieka.
- Tuż przed zapisem wiadomość nadal jest nieprzypisana; ręczne przypisanie wygrywa, batch wznawia tylko niezakończone pozycje, a `matched / ambiguous / no-match / error` pozostają rozróżnione bez dopasowania na siłę.
- Kolejności `mail -> kandydat -> klient` oraz `klient -> mail` dają pojedyncze powiązanie; zgodny sam e-mail lub sam telefon wystarcza dla jednoznacznego przypadku, lecz rozbieżność e-mail/telefon i wspólny kontakt nie powodują błędnego scalenia.
- Retry, równoległy cykl i timeout po zapisie nie dublują kandydata, maila ani relacji; już przypisany mail pozostaje nietknięty.

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
6. Zgodnie z D-15 KB może uzasadniać przedział lub wariant estymacji tylko razem z jawnymi faktami sprawy, założeniami, niepewnością, analizą wpływu i granicą stosowalności. Brak podstaw do liczby nie kończy pomocy jakościowej.

**Sprawdzenia i dowody**

- Każdy zatwierdzony current item jest wyszukiwalny albo jawnie wyłączony z uzasadnieniem; zmiana wersji unieważnia stale artifact/index.
- Pytanie wymaga połączenia faktu sprawy z zasadą KB; ślad pokazuje fragment faktycznie podany 9B i twierdzenie oparte na nim.
- Brak normy/licencji/danych wywołuje właściwy MISSING/review, nie fikcyjny cytat; public-safe źródło internetowe przechodzi kontrolowany import z provenance.
- Brak dokumentu przy wystarczających, zgodnych przesłankach daje oznaczoną estymację; nieznany istotny parametr daje warianty bez pozornej dokładności; brak podstaw daje odmowę liczby, nie całej analizy.

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
6. Pełny lokalny odczyt sprawy z D-16 nie jest zgodą na wysłanie całej teczki do Temporary Chat. Eksport nadal wymaga minimalizacji, dozwolonego zakresu, ścisłego bindingu i lokalnej re-syntezy; estymacja z D-15 nie może stać się fikcyjną zewnętrzną liczbą.

**Sprawdzenia i dowody**

- Pozytywny public-safe Visual i realna trudna analiza kończą się poprawnym lokalnym wynikiem; privacy/wrong-source/target-binding negative dają zero fałszywej akceptacji.
- Sam summary/overview nie liczy się jako wykonanie zadania analitycznego; każda hipoteza ma status i podstawę, brak danych nie jest zastępowany fantazją.
- Eskalacja pozostaje wyjątkową, kontrolowaną ścieżką; wynik zewnętrzny nie wykonuje biznesowych zapisów ani indeksacji.
- Osobno odebrać lokalne wykorzystanie pełnego potrzebnego obrazu sprawy i minimalny pakiet eksportowy; materiał dostępny lokalnie nie zostaje pominięty, ale również nie jest automatycznie eksportowany.

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
6. W odbiorze Asystenta przejść oddzielne scenariusze D-15/D-16: rozproszone wystarczające dane bez zbędnego dopytania; brak dokumentu z uzasadnioną estymacją; nieznany parametr z wariantami; odmowa nieuzasadnionej liczby przy zachowanej pomocy; oraz jawne rozstrzygnięcie złego scope, nieaktualnego pomiaru i konfliktu źródeł.
7. Dla priorytetu D-22 odebrać API/UI poprawionych pól i rozdzielenie semantyczne informacji: opis zdarzenia nie jest adresem mapy, rodzaj budynku nie jest typem prawnym klienta, a data zgłoszenia/propozycja/potwierdzony termin pozostają odrębne. Błędy mają opis dla użytkownika oraz stabilny kod diagnostyczny; niepewny zapis nie może być fałszywie opisany jako brak zapisu.
8. W szczegółach klienta odebrać historię D-22 jako odrębne od notatek wersje źródła i wartości: poprzednia/nowa treść, komórki, czas wykrycia, dostępny czas/autor źródła bez domysłów oraz faktyczny skutek systemu. Wyczyszczenie/usunięcie w Sheets nie może zniknąć jako pozorny sukces ani usunąć danych klienta.

**Sprawdzenia i dowody**

- Operator wykonuje syntetyczną sprawę od kliknięcia do zapisanej odpowiedzi z prawidłowym źródłem i wraca do niej po zamknięciu klienta.
- Background nie anuluje; cancel jest jawny; usunięta rozmowa nie pojawia się ponownie; utrata sieci nie dubluje runu.
- `R04-A2-UI06`: `SOURCE_ACCEPTED / WEB_AB_FUNCTIONAL_ACCEPTED / NOT_DEPLOYED` dla `DocumentsController`. Właściciel zaakceptował source/test `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`, route-first A (`PASS / OWNER_OPERATED_RUSTDESK`, dowód `0d0ac4d48624035682b4b7dda06f83dd80d6abe8`) oraz historyczny B (`FUNCTIONAL_PASS / OWNER_OPERATED_RUSTDESK`, dowód przy `25c30e7dd9e3d451772eee812bdef190665e1b8d`). B zachowuje przekroczenie 25 minut i przerwy monitoringu ponad 30 sekund, więc nie otrzymuje wstecz pełnego proceduralnego PASS. Dwa wcześniejsze A pozostają `NOT_VERIFIED`; Dashboard preview `limit=6` jest dozwolony. Konkretny defekt `DocumentsController` jest naprawiony źródłowo i odebrany funkcjonalnie w Web na wskazanych wersjach. Nie dowodzi to braku wszystkich innych przyczyn historycznego incydentu ani nie obejmuje `ClientsController`, Androida, W-02, całego A2/R04/R16, docelowego zestawu wydania lub deploymentu.
- D-17: Web jest pierwszą ścieżką kolejnych testów wspólnego API/logiki, a Android runtime jest `DEFERRED_BY_OWNER / NOT_TESTED`. Nie zamyka to wieloplatformowego K1 ani natywnych kryteriów lifecycle, uprawnień, aparatu/GPS, transportu i podpisu; wąski viewport Web nie jest Android PASS.
- Każdy wspierany target ma zidentyfikowany build i zaakceptowany krytyczny przepływ.
- API/UI pokazuje nowe i wcześniejsze informacje bez sklejenia ich w Notatki; ręczna/główna wartość jest chroniona, konflikt czytelny, a nieznany autor/czas edycji nie jest zmyślony.
- Odbiór samego dokumentu nie zastępuje odbioru całej uprawnionej sprawy, a poprawna odmowa liczby bez podstaw nie zastępuje pozytywnego testu estymacji tam, gdzie podstawy istnieją. R04-A2 bez modelu nie nadaje tym kryteriom PASS.

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
6. Decyzja D-15 dopuszcza robocze warianty i przedziały bez osobnego approval dla każdego założenia, lecz wymaga jawnych założeń, niepewności, analizy wpływu i granic stosowalności. Właściwy deterministic tool pozostaje obowiązkowy dla istotnego rachunku.

**Sprawdzenia i dowody**

- Każda metoda: co najmniej przypadek referencyjny z udokumentowaną tolerancją, konwersja jednostek, wartości graniczne, brak danych i wejście poza stosowalnością.
- Brak danych prowadzi do wariantów lub oznaczonej estymacji, gdy fakty/KB/porównania dają podstawę; brak podstaw prowadzi do odmowy samej liczby i pomocy jakościowej ze wskazaniem najmniejszego braku. Brak wymyślonych parametrów gruntu i procentów pewności.
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

0. Bezpośrednio po właścicielskim odbiorze R04 wykonać priorytet D-22 bez czekania na niepowiązane oferty/umowy/AI ani pełne zakończenie pozostałego R20: prześledzić `arkusz/komórka -> importer -> kandydat -> klient/sprawa -> API -> UI`, naprawić przyczynę i istniejące błędne pola **wyłącznie z zatwierdzonych arkuszy**. Nagłówki są wskazówką, a znaczenie wynika z całego logicznego rekordu (np. e-mail w kolumnie telefonu pozostaje e-mailem; opis oględzin nie staje się adresem; dom/posadzka nie zmieniają typu prawnego/branży; daty zgłoszenia, propozycji i wizyty są odrębne; sąsiedni wiersz nie jest źródłem). Każda propozycja wiąże arkusz, zakładkę, stabilny rekord/komórkę oraz wersję/hash. Dry-run pokazuje current/proposed/source/provenance/reason/decision per pole; correct/manual/confirmed/explicitly-cleared są chronione, konflikty pozostają propozycjami, a zapis sprawdza bieżącą wersję. Ponowienie nie tworzy duplikatów ani nie cofa napraw.
1. Odebrać Client 360, statusy/daty, global search, Candidate preview/merge, activity/change history, mail, dashboard, calendar/tasks/notes, inspections i Trash.
2. Nie otwierać na nowo wyboru A/B ContactPerson: followup dokumentuje B i migrację z 22.08.2026. Zweryfikować rzeczywiste działanie preferred/multiple decision-makers/generic coordinates/cross-client guard/archive.
3. Sprawdzić upload folder/multi-file/drag-drop, przypinanie/odpinanie/przenoszenie dokumentów z kontrolą, mapę/foreground GPS/EXIF/orientation/device metadata w zakresie masterplanu.
4. Dostarczyć brakujące drafts notatki/zadania/e-maila/raportu oraz porównanie dokumentów, jeżeli obecne wejścia ich nie realizują. Zapis narzędziowy tylko allowlisted i z wymaganym approval; bez dowolnego shell/SQL.
5. Rozstrzygnąć powiązanie finansowych dokumentów potrzebnych sprawie w istniejącym archiwum; nie zakładać budowy pełnej księgowości.
6. Zachować pilne poprawki użyteczności: ręczne wyszukiwanie docelowego klienta poza sugestiami; `Zaznacz wszystko` z rozróżnieniem strony i całego filtra, licznikiem oraz batch delete przez kosz; scalanie grupowe z wynikiem per element, kontrolą konfliktu/wersji i retry tylko pozycji niezakończonych.
7. Po przyszłym wdrożeniu jednoznaczny nowy wiersz zatwierdzonego arkusza tworzy bezpośrednio jednego klienta lub wiąże źródło z istniejącym — bez kandydata arkuszowego i bez obowiązkowej akceptacji per wiersz. Brak pól opcjonalnych nie blokuje; stabilna tożsamość źródła i operacji chroni przed duplikatem po sortowaniu, przesunięciu, retry lub timeoutcie. Błędny/sprzeczny wpis pozostaje jawnym wyjątkiem.
8. Dla zmiany powiązanego wiersza zachować poprzednią i nową wersję oraz dopisać jednoznaczną nową informację do właściwego pola/kontaktu/sprawy/obiektu/historii bez destrukcyjnego lustrzanego nadpisania. Wyczyszczenie komórki i usunięcie/nieobecność wiersza są zdarzeniami źródłowymi, nigdy automatycznym usunięciem danych CRM.
9. Zachować historię błędnej wartości przy naprawie bieżącego pola, oddzielić aktywne identyfikatory dopasowania od identyfikatorów tylko historycznych/spornych oraz uruchomić regułę rozwiązywania kandydatów dopiero dla nowego prawidłowego kontaktu.

**Sprawdzenia i dowody**

- Właściciel wykonuje kompletną syntetyczną sprawę z dokumentami, osobami, zadaniem, wizją, ofertą i umową; historia i deep links są spójne.
- Role mają negatywne testy działań; optimistic conflict, merge review, Trash restore/purge tylko w izolacji i zgodnie z polityką.
- UI zachowuje stany loading/error/empty/offline/back i brak N+1 w krytycznych listach.
- Testy D-22 obejmują mylące kolumny, wiele adresów/spraw, ręczne poprawki i świadomie puste pola, równoległą edycję, przerwany batch oraz ponowienie po utracie odpowiedzi. Liczba maili użytych do korekty historycznych pól klientów wynosi `0`; raport rozróżnia naprawione, poprawne bez zmian, konflikty, brak źródła i pominięcia.
- Nowy poprawny wiersz daje jednego klienta i zero kandydatów arkuszowych; brak danych opcjonalnych pozostaje pusty, a powtórzenie/sortowanie/zmiana pozycji nie tworzą duplikatu. Już istniejący klient zachowuje chronione pola.
- Zmiana wiersza daje tę samą kartę, nową wersję/zdarzenie i zachowaną poprzednią wartość; wyczyszczenie komórki lub usunięcie wiersza nie usuwa klienta/relacji, a ponowne pojawienie się wpisu nie dubluje danych.
- Ręczna zmiana w trakcie cyklu wygrywa z wcześniejszym odczytem; update źródłowy pozostaje propozycją/konfliktem. Historyczny błędny adres pozostaje w audycie, ale nie wraca jako bieżący cel mapy.
- Nowy prawidłowy e-mail/telefon może rozwiązać jednoznacznego kandydata; identyfikator tylko błędny, sporny lub historyczny nie scala automatycznie.

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
6. Po etapach arkuszowej korekty i ograniczonego dopasowania poczty z D-22 zdiagnozować okresowe błędy credentials n8n/Google na podstawie konkretnego etapu, kodu błędu i minimalnych metadanych/logów. Opublikowany projekt nie jest automatycznie `Testing`; bez próbnej rotacji/kasowania credentials, restartu usług ani analizy treści całej skrzynki.
7. Zachować istniejący mechanizm n8n co 15 minut dla nowych kwalifikujących się maili, nowych wierszy Sheets i rzeczywistych zmian wcześniej powiązanych wierszy. Użyć trwałych checkpointów, stabilnych ID, kontroli nakładających się cykli i jawnego backlogu pozycji błędnych; bez drugiego schedulera, pełnego reimportu skrzynki i modelowania niezmienionych rekordów. Pokazywać ostatnie udane sprawdzenie i przetworzenie per źródło; awaria/niepełny odczyt nie jest `0 zmian`.

**Sprawdzenia i dowody**

- Fault injection w izolacji wywołuje właściwy alert bez ujawnienia sekretów; przejściowy błąd nie powoduje nieograniczonych powiadomień.
- Dry-run retention daje dokładny manifest plików/rozmiarów/przyczyn i zachowanych kopii; apply tylko po osobnej zgodzie.
- Operacje nie blokują hot-path UI i mają jawny status, historię oraz możliwość bezpiecznego pause.
- Późniejszy autoryzowany test realnego harmonogramu potwierdza około 15-minutowy trigger dla nowych maili, nowych wierszy i edycji istniejącego wiersza; ręczne `Execute` lub deklaracja konfiguracji nie wystarcza.
- Cykl bez zmian daje zero nowych klientów/kandydatów/wersji, a retry, równoległość i timeout po zapisie dają pojedynczy efekt. Awaria źródła pozostaje widoczna i po wznowieniu nie gubi ani nie dubluje pozycji.

**Warunek zamknięcia:** Operacje wymagane w followup odebrane; wyłączona retencja jest akceptowana wyłącznie jako jawna decyzja właściciela, a nie ukryte COMPLETE.

**Dane/schema/config:** Konfiguracja/alerty; destructive retention i n8n purge oddzielnie gated, niezależnie od source PASS.

**Potrzebna zgoda:** Zachować istniejące FOLLOWUP_BACKUP_RETENTION_DELETE_APPROVAL_REQUIRED i FOLLOWUP_N8N_RETENTION_APPROVAL_REQUIRED; kanał zewnętrzny osobno.

**Rollback:** Wycofanie konfiguracji; skasowany backup nie ma automatycznego rollbacku — przed deletion wymagany zachowany restore chain i świadoma zgoda.

**Poza zakresem:** Docker prune, kasowanie kopii niezarządzanych, retencja traktowana jako bezpiecznie odwracalna.

### R23 — Odbiór §42 i kontrolowane wydanie systemu

**Typ:** VERIFY / RELEASE · **Status:** patrz §0.2 · **Zależności:** R03, R04, R11, R12, R13, R14, R16, R17, R18, R19, R20, R21, R22

**Cel:** Wykonać jeden szczegółowy audyt końcowy i udowodnić działanie całego
uzgodnionego produktu jako narzędzia pracy właściciela.

**Odpowiedzialność za wymagania:** M-001, M-061, M-071, M-073.

**Pozostałe powiązania:** M-067, F-026, F-035. **Ustalenia:** FND-001, FND-026.

**Zakres wykonania**

1. Po zakończeniu prac funkcjonalnych wykonać jedyny szeroki audyt końcowy:
   implementacja całej aplikacji, pokrycie, przypadki brzegowe, hardening,
   martwy kod i zgromadzone nieblokujące K2/K3. Nie duplikować tego audytu w
   każdym wcześniejszym Rxx.
2. Zrealizować workflow §42: klient → lokalizacja/wizja/zdjęcia → dokumenty → intelligence/index → analiza z KB/Visual → podobne realizacje → obliczenie → oferta approved → umowa approved → historia.
3. Zamrozić release manifest i wykonać właściwe pełne regresje oraz aktualny restore drill dla tego schema/artefaktów. Stary restore PASS nie pokrywa automatycznie nowych ofert/umów.
4. Rozstrzygnąć każdy z 108 wpisów oraz dodatkowe podkryteria: ACCEPTED albo jawna podpisana decyzja scope. NOT_VERIFIED/OWNER_DECISION nie są ukrytym PASS.
5. Promocja source, deploy, migracja, aktualizacja aplikacji i praca na prawdziwych danych mają oddzielne zgody i log. Nie promować całego rescue dlatego, że jeden podpakiet przeszedł.
6. Wykonać ograniczony canary prawdziwej pracy po zgodzie i monitoring; progi czasowe/zasobowe z pomiarów, nie fikcyjne terminy zakończenia.

**Sprawdzenia i dowody**

- Przepływ biznesowy daje poprawne artefakty, źródła i wersje; człowiek zatwierdza wyniki wysokiego ryzyka.
- Brak otwartego P0 i potwierdzonego krytycznego błędu poprawności w wydawanym zakresie; niepewne materiały fail-closed bez niszczenia użyteczności pozytywnych przypadków.
- Aktualny stable i wspierane klienty działają; release/rollback i restore są odtwarzalne.
- Jeden końcowy raport rozlicza szeroki audit code/coverage/edge/hardening/K2/K3;
  brak wcześniejszego duplikowania tej kampanii w pakietach funkcjonalnych.

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
