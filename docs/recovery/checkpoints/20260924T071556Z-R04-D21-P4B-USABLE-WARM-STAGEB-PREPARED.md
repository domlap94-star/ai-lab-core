# R04 / D-21 / P4-B — USABLE-WARM Stage B configuration prepared

- UTC: `2026-09-24T07:15:56.7002666Z`
- Window decision ID: `R04-D21-P4B-USABLE-WARM-STAGEB-20260924T071556Z`
- Package OperationId: `R04-D21-P4B-USABLE-WARM-20260923T170936Z` (unchanged)
- Initial preparation scope: `LOCAL_ONLY / OFFLINE VALIDATION`; no host
  operation in that initial phase. Later authorized phases are recorded below.

## Prepared exact bytes

| Artifact | Size | SHA-256 | State |
|---|---:|---|---|
| `payload/startup-set.approved-for-start.json` | 31588 B | `38D7C529FD7CE37E25E32A58CC9CF46075FF5E97D7E60F3618D088653C492BDE` | `APPROVED_FOR_START` bytes prepared; not installed |
| `package-index.install-preapproval.json` | 10908 B | `E298F50753BECB023A5A159F010D746046A111DFCEC2B51E89F3E8C2027C93AD` | proposed; all operational authorization false |
| recipe | unchanged | `74E5664F50CCAE9E641BC076390CE17A769C2E6F1D6F109FB6990C80220B7D6D` | no code change |

Original manifest `E139CEC5...357F0` and VerifyOnly index
`4A58DF7D...84DC` remain unchanged. Manifest semantic diff is exactly
`approval.status`, `approval.installation_authorized` and
`approval.startup_authorized`; `set_id` remains the package OperationId and
`decision_id=D-21`. Index semantic diff is exactly manifest package path,
size/hash and `prepared_window.manifest_state`. Its top status remains
`PROPOSED_AWAITING_SEPARATE_OWNER_OPERATIONAL_APPROVAL`.

The future owner-authorized six-field index transition was computed but not
written: `10904` B / SHA-256
`CF1CCA92DFE3E9A0791615F0EA22454E45D600FDA634FC9DF03D507441A7CCE7`.

## Validation

- Windows PowerShell `5.1.26100.8894`;
- unchanged `Test-P4BPackageIndex`: PASS on the complete derivative index and
  real package files;
- unchanged `Test-StartupSetManifest`: PASS on an isolated projection of the
  exact approved manifest;
- negative projection with `NOT_APPROVED`: FAIL with `START_NOT_APPROVED`;
- validation fixture used one owned junction and was removed without traversing
  its target;
- validation summary: `1031` B /
  `CE75DE1DA2A3FB3236F69FC4136C3FF2F7C8380E3CA00892273201C3440D1559`;
- preparation summary: `4279` B /
  `6CE0F8A06BC5FE1E98E52BE84B5829519FA177E55F2507C788283CE2AF16CB18`;
- production Docker/Task/CIM/TCP/HTTP/UAC/start/write boundaries: `0`.

## Exact next gate

No UAC or InstallAndWarm is authorized by this checkpoint. One current owner
confirmation must bind the six authorization-field transitions, one UAC, four
files plus existing `NEXT Stabil - Host`, two recorder-backed warm runs with
Private `START_ONCE 1 -> 0`, logon only after both complete results and Host
idle, one bounded SAFE_INACTIVE, and a short CRM/Web open check through the
unchanged `C:\Users\domai\Desktop\NEXT Stabil.lnk`.

The previous read-only preflight is not repeated. Six containers, five
dependency tasks, helper, backend flags and data junction remain KEEP;
Supervisor remains `INTENTIONALLY_STOPPED`. Docker/WSL available pool and swap
usage remain `UNKNOWN_NOT_MEASURED`. Installed run01 remains unchanged, Host is
historically disabled/no-trigger and warm runs remain `0/2`.

Status: `P4B_USABLE_WARM_STAGE_B_CONFIGURATION_PREPARED /
OFFLINE_GUARDS_PASS / OPERATION_NOT_AUTHORIZED_NOT_RUN`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną i kolejnym promptem przeczytaj roadmapę na SHA publikacji: §0,
`ANTI_EXCESSIVE_WORK`, aktywną kartę R04 i ten checkpoint. Zachowaj odbiory;
nie dodawaj K2/K3. K0/K1 blokujące konfigurację: `BRAK`; operację blokuje tylko
bieżąca zgoda właściciela. Efekt: dokładny zestaw jest przygotowany i
zwalidowany offline, ale nie uruchomiony. Cykl review pozostaje `2/2`;
następny krok to jedna decyzja Stage B, nie nowy preflight.

## Aktualizacja po jedynej autoryzowanej próbie Stage B

- owner confirmation: otrzymane dla exact window i SHA tej fazy;
- authorized index: `package-index.install-authorized.json`, `10904` B,
  SHA-256 `CF1CCA92DFE3E9A0791615F0EA22454E45D600FDA634FC9DF03D507441A7CCE7`;
- one UAC / one InstallAndWarm: wykorzystane;
- elevated PID `79776`: `2026-09-24T07:38:21.0096157Z`–
  `2026-09-24T07:39:42.3941321Z`, exit `22`;
- result: `PARTIAL_PENDING_OPERATION_UNKNOWN`, error
  `PENDING_HOST_DISABLED_REGISTER`;
- four exact files: installed and hash-matched;
- task mutation: `TASK_POSTCHECK_NOT_CONFIRMED`, possible effect true,
  settled false, worker cleanup `WORKER_SETTLED`;
- warm runs `0/2`, Host/Private starts `0`, logon `NOT_ENABLED`, shortcut test
  `NOT_RUN`;
- rollback: `FILES_PRESERVED_NO_DESTRUCTIVE_ROLLBACK`;
- result: `3412` B /
  `9598F6CBE756625636D1AF406DD1FAC6A2E8CA55A735FCF3D57E250682506655`;
- journal: `6222` B /
  `A0A3171F4C9D290E3ABA02873CA294F4CE2ED4D604BB56FBBF773A1473D575F2`,
  `CLOSED`;
- zewnętrzny Task/Docker/HTTP post-check: `NOT_RUN`.

Zgoda operacyjna i UAC są zużyte. Stan Host po możliwej mutacji pozostaje
niepotwierdzony; nie wolno retry, competing write, startu ani zewnętrznego
rollbacku. Status checkpointu po aktualizacji:
`P4B_USABLE_WARM_STAGE_B_PARTIAL_PENDING_OPERATION_UNKNOWN /
FOUR_FILES_INSTALLED / WARM_RUNS_0_OF_2 / READY_FOR_OWNER_REVIEW`.

## Późniejsze rozliczenie READ-ONLY dokładnie jednego taska Host

Jedna nowa zgoda odczytowa objęła wyłącznie `\NEXT Stabil - Host`. Kampania
Windows PowerShell `5.1.26100.8894`, zwykły token, trwała od
`2026-09-24T08:10:30.0437471Z` do `2026-09-24T08:10:39.2325694Z` i wykonała
dokładnie jeden bounded `OBSERVE_TASK`. Koperta zakończyła się
`SUCCESS / HOST_OPERATION_CONFIRMED / WORKER_SETTLED`, `possible_effect=false`;
task writes, task starts, UAC, warm runs i wszystkie inne granice produkcyjne
wyniosły `0`.

Dwa wcześniejsze wywołania wrappera zakończyły się lokalnie przed utworzeniem
procesu kampanii i przed kontaktem z Task Scheduler: pierwsze na wymaganiu
`UseShellExecute=false`, drugie na kolizji nazwy lokalnej zmiennej
`OutputRoot`. Katalog wynikowy nie istniał po żadnym z nich. Nie są liczone
jako odczyty; faktyczny bounded task read wykonano dokładnie raz.

### A. Dowód historyczny

`result.json` i `mutation-journal.jsonl` zachowują wyłącznie
`PENDING_UNKNOWN / TASK_POSTCHECK_NOT_CONFIRMED / possible_effect=true /
settled=false / WORKER_SETTLED`. Nie zawierają pierwotnej odpowiedzi
post-checku ani jego obserwacji XML. Historyczny szczegół jest zatem
`NOT_CAPTURED`; późniejszy odczyt nie zmienia historycznego wyniku
`PARTIAL_PENDING_OPERATION_UNKNOWN`.

### B. Świeża obserwacja

- `State=Disabled`, `Enabled=false`, `Triggers=0`;
- observer wyprowadził `running_instances=0` i `queued_instances=0` z tego
  samego `State`; nie są to niezależne pomiary instancji;
- action: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` z
  argumentem `-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass
  -File "C:\ai-lab-core\operations\runtime\invoke-host-with-evidence.ps1"`;
- `WorkingDirectory=C:\ai-lab-core`, principal
  `S-1-5-21-712169069-4165966233-3173903118-1001`,
  `LogonType=InteractiveToken`; element `RunLevel` jest nieobecny w odczytanym
  XML i pozostaje `NOT_AVAILABLE`, zamiast domniemanego odczytu
  `LeastPrivilege`;
- `MultipleInstancesPolicy=IgnoreNew`, `ExecutionTimeLimit=PT15M`;
- `LastRunTime=2026-09-19T21:07:53Z`, `LastTaskResult=22`.

Odczytany XML ma semantic SHA-256
`AA989DF63F264770C85C7FC63753FE21D708677CE0BD47A0CBEE592F45EFAA08` i
comparable SHA-256
`E3147E8F756802E7EEE4F2EBE872452439D51AC0AECE25F5A8AC0474366D0BA7`.
Nie odpowiada więc przypiętym hashom disabled
`B1CE9C862E575E59EAA00EBAB0F85D262C573DADE6BB7B4130038626A0197E06` /
`E8F1A517654C10CE59B28860FE65B1FE8A7518229DE504B4FD662620D6333EA0`
ani preimage. Dokładne porównanie decoded text po istniejącej normalizacji
wyłącznie EOL wykazało tę samą długość `1452` i tylko trzy różne znaki na
pozycjach `30..32`: deklaracja `encoding="utf-16"` w przypiętym disabled XML
versus `encoding="UTF-16"` w eksporcie taska. Wszystkie projekcje pól taska są
identyczne z disabled XML. Preimage nie jest obecny: poza innym opisem używał
bezpośrednio `start-host-services.ps1 -ManifestPath ...`, podczas gdy bieżący
task wskazuje recorder.

Dowody LOCAL_ONLY znajdują się w
`C:\Users\domai\AppData\Local\Temp\P4B-UW-01\host-reconcile01`:
`campaign-result.json` `7461` B /
`A09D9574A80AD8FF5F4B76EA9C926DF0B45DCAF1C7170A18B23FBC567F8D78D1`,
raw observation `3190` B /
`7710BDDAD600A7CC2694A70129EFD5392FBF8306CD878F70A6D44653E36E3135`
oraz artifact index `1027` B /
`5D4FD66E09E187BF70F430B702276EBBD5DDE77C268B9BF29619D42E926D15FC`.

### C. Granica wiedzy i jedna propozycja dokończenia

Nowa obserwacja dowodzi bieżącej semantyki disabled/no-trigger/idle oraz
representation-only mismatch deklaracji XML. Nie dowodzi, jaki dokładnie XML
zwrócił historyczny post-check o `07:39:41Z`; przyczyna tamtej odmowy pozostaje
`NOT_CAPTURED`. Ponieważ istniejący raw/comparable guard nie akceptuje
bieżących hashów, nie wolno wznowić całego `InstallAndWarm` ani samoczynnie
przyjąć nowego hasha.

Jedyny proponowany następny zakres wymaga nowej zgody i wąskiej metody
kontynuacji od dokładnie zaobserwowanego stanu: uznać bieżącą parę hashów tylko
jako przypięty pre-state tej jednej operacji, ponownie potwierdzić exact
disabled/no-trigger/idle oraz cztery już zainstalowane hashe, zarejestrować
wyłącznie przypięty wariant on-demand Host, wykonać dwa odrębne
recorder-backed warm runs (`Private 1 -> 0`), po każdym potwierdzić zakończenie
właściwego Host, dopiero potem zastosować przypięty logon XML i wykonać krótki
test CRM/Web zachowanym skrótem. Bez ponownej rejestracji disabled, kopiowania
czterech plików, pełnego `InstallAndWarm`, zmian dependency tasks, kontenerów
lub Supervisora.

Status rozliczenia: `P4B_HOST_RECONCILIATION_READ_ONLY_COMPLETE /
DISABLED_NO_TRIGGER_IDLE_SEMANTICS_CONFIRMED /
EXACT_HASH_REPRESENTATION_MISMATCH / HISTORICAL_POSTCHECK_NOT_CAPTURED /
NO_MUTATION`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną i kolejnym promptem przeczytaj roadmapę na SHA publikacji: §0,
`ANTI_EXCESSIVE_WORK`, aktywną kartę R04 i ten checkpoint. Zachowaj odbiory;
nie dodawaj K2/K3. K0: `BRAK`. K1: istniejący exact hash guard odrzuca
zaobserwowaną disabled reprezentację wyłącznie z powodu `utf-16`/`UTF-16`, co
blokuje bezpieczne przejście do on-demand; dowód to bieżący raw XML i hash pair,
bez domniemania historycznej odpowiedzi. Efekt: nie powtarzać disabled register
ani czterech kopii; przyszła zgoda może objąć tylko zamkniętą kontynuację
exact-current -> on-demand -> dwa warm runs -> logon -> CRM/Web. Cykl review
pozostaje `2/2`; brak zgody na task write/start, UAC lub dalszy live read.

## Jednorazowa wąska kontynuacja — UAC zużyty, brak trwałego wyniku

- Continuation ID: `R04-D21-P4B-USABLE-WARM-CONTINUE-20260924T104156Z`.
- Właściciel oświadczył, że Bitdefender wcześniej zablokował połączenie i że
  dodał je w swoim interfejsie do wyjątków. Nie jest to potwierdzona przyczyna
  historycznego błędu ani ogólne AV clearance; konfiguracji ochrony nie
  zmieniano w tej pracy.
- LOCAL_ONLY root: `C:\Users\domai\AppData\Local\Temp\P4B-UWC-01`.
- Continuation script: `25749` B /
  `D2F6D8490C39A3FF61A8D8D0DC5DDF260FC46DCF7EFF67E4F02A25A8482CF63B`.
- Continuation index: `5456` B /
  `D6432185D409ABC26639EAF3DC53C2B57CAD4EF1DF092BFCDF6DB6AAA3BBCA1B`.
- Offline: `PASS`, `4` scenariusze / `24` asercje, production boundaries `0`.

Po bieżącym potwierdzeniu właściciela wywołano dokładnie jeden RunAs/UAC.
Monitor `541` B /
`CDBA2FE433E43CFD56A04DA2911EB99EA95CE9E64CC9893748B5757B2C229011`
zapisał `UAC_REQUESTED` `2026-09-24T11:35:00.5990291Z`, elevated PID `82116`
oraz exit `0` `2026-09-24T11:35:08.1965722Z` po `7598.112` ms.

Zarezerwowany output `...\P4B-UWC-01\apply` nie istnieje. Nie powstały
`preflight.json`, `mutation-journal.jsonl` ani `result.json`. Ponieważ
kontynuacja tworzy ten output przed preflightem i przed granicą mutacji, nie ma
dowodu wejścia w przepisaną operację, odczytu hosta ani rozpoczęcia mutacji.
Brak utrwalonego stderr oznacza `EXACT_FAILURE_MESSAGE=NOT_AVAILABLE`; kod `0`
procesu nie zastępuje obowiązkowego wyniku recepty.

Wynik: `P4B_USABLE_WARM_CONTINUATION_NO_DURABLE_RESULT /
SCRIPT_ENTRY_NOT_EVIDENCED / UAC_CONSUMED / NO_RETRY /
WARM_RUNS_0_OF_2 / LOGON_AND_CRM_WEB_NOT_RUN`. SAFE_INACTIVE nie był
uruchamiany. Nie wykonano skrótu CRM/Web, ponieważ poprzedzające dwa warm runs
nie uzyskały PASS. Stan Host disabled/no-trigger/idle i Supervisor
`INTENTIONALLY_STOPPED` pozostają wyłącznie ostatnim wcześniejszym dowodem,
bez świeżego readbacku tej próby.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną przeczytaj roadmapę na SHA publikacji: §0,
`ANTI_EXCESSIVE_WORK`, aktywną kartę R04 i ten checkpoint. Zachowaj D-23 `2/2`
i wcześniejsze odbiory. K0: `BRAK NOWEGO DOWODU`. K1: dokładne wywołanie nie
pozostawiło outputu powstającego przed preflightem, więc nie można udowodnić
wejścia w receptę ani uzyskać dwóch warm runs; dowód to monitor i brak
obowiązkowych artefaktów. Nie dodawać K2/K3. Następny krok wymaga jawnej decyzji
o jednym obserwowalnym wywołaniu z trwałym stderr/result; obecna zgoda i UAC są
zużyte, bez automatycznego retry.

## Obserwowalne zastępstwo — wynik przed UAC

Nowe zadanie miało zachować exact continuation script/index i poprawić tylko
transport oraz capture. Przygotowany LOCAL_ONLY wrapper miał zapisać marker
wejścia, rzeczywisty child PID, safe argv, stdout, stderr, exit i monitor
result przed oceną `result.json` produktu. Test miał użyć rzeczywistego PS5.1
i nieszkodliwych targetów, bez UAC i bez granic hosta.

Wrapper został zapisany pod
`C:\Users\domai\AppData\Local\Temp\P4B-UWC-01\invoke02\invoke-observable-continuation.ps1`.
Pierwszy parser PS5.1 zwrócił dokładnie błąd odczytu `file in use by another
process`; następnie exact ścieżka była nieobecna. `selftest01`, `run01` i
produktowy `apply` nie powstały. Pozostałe trzy nieszkodliwe fixture pozostały.
Brak formalnej odpowiedzi mechanizmu ochrony oznacza, że sprawca i dokładna
przyczyna są `NOT_AVAILABLE`; nie przypisano zdarzenia AV i nie próbowano
zmiany kanału, ochrony lub ACL.

Bezpieczny zapis LOCAL_ONLY ma `1083` B / SHA-256
`EF82E5577AA080B927C3CAF93EA2BA1B95F02F479B6EBD20330D6255D24016B1`.
Nowy UAC, wrapper execution, selftest, product preflight, Host/Docker/Task/
CIM/TCP/HTTP reads/writes/starts i SAFE_INACTIVE wynoszą `0`.

Wynik: `OBSERVABLE_INVOCATION_LOCAL_WRAPPER_REMOVED_BEFORE_OFFLINE_TEST /
NO_UAC / PRODUCT_BOUNDARIES_0 / WARM_RUNS_0_OF_2 / LOGON_AND_CRM_WEB_NOT_RUN`.
Nie ma bieżącego zdania do potwierdzenia UAC, ponieważ wymagana lokalna bramka
nie przeszła.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed kolejnym krokiem przeczytaj roadmapę na SHA publikacji: §0,
`ANTI_EXCESSIVE_WORK`, kartę R04 i ten checkpoint. D-23 pozostaje `2/2`.
K0: `BRAK NOWEGO DOWODU`. K1: obserwowalny wrapper nie przetrwał do parsera i
selftestu, więc warunek bezpiecznego jednego UAC nie został osiągnięty; dowód
to dokładny błąd file-in-use, następna nieobecność ścieżki i brak wszystkich
katalogów wykonawczych. Bez K2/K3, automatycznego retry lub zmiany kanału.
