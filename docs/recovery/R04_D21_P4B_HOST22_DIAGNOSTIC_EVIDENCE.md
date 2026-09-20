# R04 / D-21 / P4-B — dowód diagnostyczny Host 22

Stan: `HOST22_DIAGNOSED_READ_ONLY / SOURCE_FIX_REQUIRED /
NO_RETRY_AUTHORIZED`

Czas kampanii: `2026-09-19T23:13:46Z–2026-09-19T23:23:24Z`

Wejściowy HEAD: `959d4095eb7a3929230d9754fcc90952502413ba`

## Wynik

Run01 pozostaje historycznie `PARTIAL_AFTER_FAILURE / HOST_TASK_FAILED_22 /
SAFE_INACTIVE_PARTIAL_UNKNOWN`. Akcja taska nie utrwaliła stdout/stderr
launchera, więc `LAUNCHER_RESULT_DETAIL_NOT_CAPTURED` nie został przepisany na
fikcyjny log. Ograniczona kampania bez ponowienia Host pozwoliła jednak
odtworzyć dwie źródłowe przeszkody:

- exact installed manifest przechodzi `Read-StartupSetManifest` i
  `Test-StartupSetManifest`;
- exact adapter Docker używa szablonu `.State.Health`; dla backendu bez tego
  opcjonalnego klucza inspect kończy się `map has no entry for key "Health"`,
  a plan mapuje wyjątek na `ADAPTER_FAILURE` i exit `22`;
- jedyny zapisany selector Compose zwrócił pięć kontenerów backendu: jeden
  zatwierdzony running i cztery retained drill/exited;
- po użyciu poprawnej, wyłącznie odczytowej projekcji tych pięciu obserwacji
  rzeczywista faza planu kończy `CONTAINER_IDENTITY_AMBIGUOUS`,
  `match_count=5`, przy `Start*=0`.

Pierwszy punkt jest najbardziej bezpośrednią, deterministyczną ścieżką do
historycznego kodu `22`. Drugi jest niezależnym blockerem, który wystąpiłby po
naprawie samej projekcji. Historycznego JSON launchera nie da się odzyskać z
Task Scheduler i nie jest on deklarowany jako odzyskany.

## Tożsamość i walidacja

| Element | SHA-256 / wynik |
|---|---|
| installed launcher | `7BB24450C0B0EFDD8321935B129A25CEDD788BA3B8951965EF8E4A09BBF33871` |
| installed runtime | `349404C3B8DE7B2502437E023BEC09464428856A6D8F120EAFBD68E1ABCF4FA7` |
| installed existing-only helper | `91C763F5D0FF6CC7184E0B238EA6A6047CBB3FB13F88917777F4E0696E9667EC` |
| installed manifest | `E66F22A7EC433183940FC3014E1B9F8C1DBE535375EC2D6580B958B55586010C` |
| pure manifest validation | `PASS`, errors `0`, adapters `0`, plan calls `0` |
| selector boundary test | `0/1/5`, `36` asercji, start calls `0` |
| safe inspect projection test | `7` kontroli, system calls `0` |
| actual plan replay | `CONTAINER_IDENTITY_AMBIGUOUS`, count `5`, starts `0` |

Zapisany selector wykonał się dokładnie raz z labelami
`com.docker.compose.project=ai-lab-core` i
`com.docker.compose.service=backend`, przez `ps -aq`, więc obejmował stopped.
Nie został ponowiony dla formattera. Jego stdout ma SHA-256
`0D7BB36B5FEB654095D6295A5659943296F23C4EA76941105B1B67989F5AA17F`.
Bezpieczny stderr exact inspectu ma SHA-256
`4ACD49B53353E4A70D0CDFE4F8945A047F10AFFBFFD4D432631998FED1A2A13C`.
Zbiorcza bieżąca projekcja pięciu kontenerów ma SHA-256
`878B8140A776B038EC42A93E8FBA5BEF305BA78E565672C2800C5CF518AA6E55`.

## Skutki i ograniczenia

Live skutki: jeden selector, jeden nieudany bezpieczny inspect i pięć
celowanych read-only inspectów. Task/EventLog/HTTP/UAC/RunAs/Host start/
Install/rollback/container start-stop-restart: `0`. Nie zmieniono plików
instalacji, tasków, usług ani danych. Supervisor nie został uruchomiony.

Dowody LOCAL_ONLY znajdują się w
`C:\ai-lab-core-staging\recovery\P4B-E22-01`. Indeks: `13 998 B`, SHA-256
`B228161D75DE431A6C367A2C7E6242127099821677F359B74AB63173DEEC1C23`.
Raw logi i bezpieczne projekcje nie trafiają do Git.

## Następna bramka

Jedyny następny krok to osobny SOURCE/OFFLINE zakres: bezpieczny odczyt
opcjonalnego health oraz exact-ID-first wybór zatwierdzonego kontenera, z
fail-closed wynikiem dla rzeczywistego duplikatu, zmiany ID albo konfliktu.
Nie ma zgody na retry Host, Install, UAC lub operacyjny rollback.

## Kontynuacja source/offline — 2026-09-20

Wąski zakres został wykonany w source commit
`ed961d6980ebebe2e4d351319e2aa909437bc1ec`. Zachowany preimage rzeczywistej
fazy kontenerowej nadal odtwarza `CONTAINER_IDENTITY_AMBIGUOUS`, pięć
obserwacji i zero startów. Nowa implementacja:

- bezpiecznie rozróżnia brak/null Health jako `NOT_CONFIGURED`, bez uznawania
  go za `healthy`;
- wiąże wybór, readiness i syntetyczny cold start z pełnym `container_id`;
- rozlicza cztery dokładnie rozpoznane stopped drill, lecz blokuje każdy inny
  konflikt lub niepełną obserwację;
- nie adoptuje obiektu o podobnej nazwie/labelach przy braku pinned ID.

Końcowa kampania Windows PowerShell 5.1 przeszła zestawy `37/53/51/44/16`
asercji, wszystkie exit `0`, stderr `0`, realne granice produkcji `0`.
Szczegóły i hashe znajdują się w
`docs/recovery/R04_D21_P4B_HOST22_SOURCE_TEST_EVIDENCE.md`.

Status kontynuacji: `HOST22_HEALTH_AND_EXACT_ID_SOURCE_READY_FOR_REVIEW /
OFFLINE_TESTS_PASS / NOT_DEPLOYED`. Historyczny run01 i jego brak
`LAUNCHER_RESULT_DETAIL` pozostają niezmienione; nadal nie ma zgody na retry.
