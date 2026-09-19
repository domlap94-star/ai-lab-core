# R04 / D-21 / P4-B — TaskInfo i krótki output instalatora

Data wykonania: `2026-09-19`

Zakres: `SOURCE / LOCAL FILE / OFFLINE TEST / BOUNDED READ ONLY`

Stan instalacji: `PARTIAL_SAFE_INACTIVE / NOT_INSTALLED`

## Wynik

Przyczyna wcześniejszego `TaskInfo 0/6` została ustalona w warstwie
kolektora: proces dziecka polegał na niejawnie dostępnej nazwie operacji, a
test nie wykonywał rzeczywistej ścieżki dispatcher → worker → getter →
projekcja → zapis. Poprawiony, nadal LOCAL_ONLY collector jawnie ładuje moduł
`ScheduledTasks`, sprawdza obecność `Get-ScheduledTask` i
`Get-ScheduledTaskInfo`, a w trybie fixture dopuszcza wyłącznie zamknięte
gettery testowe. Brak kompletnej atrapy odmawia testu; nie ma fallbacku do
hosta. `null` i brak pola nie są zamieniane na zero.

Windows PowerShell `5.1.26100.8894` przeszedł `16` przypadków, `126` asercji
i rozliczył `14/14` własnych workerów. Test obejmował sześć dokładnych nazw,
TaskPath `\`, wybór operacji, czas lokalny i UTC, wynik zero/niezero,
brak/null, never-run, access denied, timeout i nieznaną operację. Rzeczywiste
Task Scheduler/Docker/HTTP/CIM/TCP/UAC oraz mutacje hosta w testach: `0`.

Jedna dozwolona kampania TaskInfo wykonała się od
`2026-09-19T20:23:54.0045496Z` do
`2026-09-19T20:23:59.1708711Z`. Wszystkie `6/6` odczytów zostały zapisane,
wszyscy workerzy `6/6` rozliczeni, bez uruchamiania lub zmiany tasków:

| Task | LastRunTime local | LastRunTime UTC | LastTaskResult | Interpretacja |
|---|---|---|---:|---|
| NEXT Stabil - Docker Desktop | `2026-08-23T20:50:19+02:00` | `2026-08-23T18:50:19Z` | 0 | obserwacja historycznego wykonania |
| NEXT Stabil - Docker Compose | `2026-08-23T20:50:19+02:00` | `2026-08-23T18:50:19Z` | 0 | obserwacja historycznego wykonania |
| NEXT Stabil - Public Gateway | `2026-09-14T19:09:01+02:00` | `2026-09-14T17:09:01Z` | 267009 | niezerowy wynik zachowany bez uruchomienia taska |
| NEXT Stabil - Private Gateway | `2026-08-23T20:50:19+02:00` | `2026-08-23T18:50:19Z` | 1073807364 | niezerowy wynik zachowany bez uruchomienia taska |
| NEXT Stabil - Supervisor | `2026-08-29T13:46:14+02:00` | `2026-08-29T11:46:14Z` | 3221225786 | niezerowy wynik; Supervisor nie został uruchomiony |
| NEXT Stabil - Host | `1999-11-30T00:00:00+01:00` | `1999-11-29T23:00:00Z` | 267011 | kontekst `never-run`; nie jest to sukces taska |

`NextRunTime` był nieobecny dla wszystkich sześciu, a
`NumberOfMissedRuns=0`. Te pola nie zastępują definicji triggerów zapisanych w
XML i nie dowodzą wykonania startu po logowaniu.

## Pochodna short-output

Historyczna odebrana recepta
`invoke-p4b-resume-installer.rollback-safe.ps1` pozostała niezmieniona:
91,889 B, SHA-256
`F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E`.
Obok niej przygotowano dokładną pochodną
`invoke-p4b-resume-installer.short-output.ps1`: 91,912 B, SHA-256
`F65DF7232ADC3DBFE6B35FC08D255D385748ED17CC3078CACB93501FB9BF8C9A`.

Allowlisted diff obejmuje wyłącznie identyfikację pochodnej, `entryHead`,
kanoniczną nazwę oraz bazę wyników
`C:\ai-lab-core-staging\recovery\P4B-FIN-01\out\run01`. Ciała funkcji,
29 wejść, sześć baseline'ów, kolejność mutacji i rollback są byte-equal z
preimage. External input index pozostał niezmieniony:
`ED8826F7CFAB1A33B84C5FCF3BDA1E57FB48E9598100B3826C0CDDDCC3131CDA`.

Test ścieżek i I/O przeszedł: root/event/result mają odpowiednio
`52/75/79` znaków, najdłuższa generowana ścieżka ma `206 <= 220`, a te same
API zapisu/append/rename/hash zaliczyły syntetyczny roundtrip. Dokładne własne
fixture usunięto, log próby zachowano. `out\run01` nie został utworzony.

Końcowe testy pochodnej:

- input/index: `14/14`, `110` asercji, 29 ról i sześć baseline'ów;
- orkiestracja/rollback: `15/15`, `96` asercji, `437/437` workerów;
- zależności pending mutator, foreign task, timeout i brak destrukcyjnego
  rollbacku przy UNKNOWN: zachowane;
- parser PowerShell 5.1 oraz exact diff/function-body comparison: `PASS`;
- `VerifyInputsOnly`: `29/29`, sześć baseline'ów, exit `0`, bez host calls,
  `run01` nadal nieobecny.

External resume ID przygotowania:
`R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z`.

## Bieżący bounded drift

Bezpieczna projekcja z okna
`2026-09-19T20:34:58.3707182Z`–`2026-09-19T20:35:19.8495097Z` ma
55,768 B i SHA-256
`72788969A6AEB0B15EB4F25E1A98158274A5F925E5A555B83A605DA126E7C012`.
Wynik: `PASS_WITH_DOCKER_WSL_POOL_AND_SWAP_UNKNOWN`.

- pięć legacy tasków zachowało dokładne preimage; Host pozostaje
  disabled/no-trigger i odpowiada bieżącej znormalizowanej definicji;
- wrapper Startup jest nieobecny, kopia rollback zgodna, launcher/runtime/
  manifest nie są zainstalowane, legacy helper i P3 override są zgodne;
- sześć przypiętych kontenerów działa z tymi samymi pełnymi ID, image,
  mountami, portami i siecią; `RestartCount=0`, PostgreSQL `healthy`;
- backend health/version i Public Gateway health zwróciły `200`, publiczne
  `/control` i `/control/health` zwróciły `404`;
- porty `8787` i `8788` były wolne; Supervisor i Private Gateway nie zostały
  uruchomione;
- Windows available `5.468 GiB`, commit reserve `34.272 GiB`, wolne C:
  `579.172 GiB`, wolne D: `854.570 GiB` — dotychczasowe progi przeszły;
- Docker/WSL pool available i swap-used pozostają `UNKNOWN`.

Pierwsza próba snapshotu nie dotarła do granicy hosta, bo jej tymczasowy skrypt
nie był dostępny. Druga wykonała wszystkie dozwolone odczyty i zapisała rekordy;
lokalny agregator miał błąd składni właściwości. Projekcję zbudowano z tych
samych zachowanych rekordów bez powtarzania host/Engine reads.

UAC, RunAs, Install, zmiany tasków/plików instalacji, start usług, warm runs,
rollback oraz mutacje danych: `0`. Globalny manifest pozostaje
`NOT_APPROVED_FOR_START`.

## Pakiet review i następna bramka

Pakiet review:

`C:\ai-lab-core-staging\recovery\P4B-FIN-01\check\R04-D21-P4B-SHORT-OUTPUT-REVIEW-20260919T204200Z.zip`

- ZIP: 75,385 B, SHA-256
  `407A872A9B0504F35F2141992E3F84132198175A0146B5B0D1925B0F878D7272`;
- package index: SHA-256
  `36623A0384F400D10D9FF0714FE7ED67B0090FC872C19751ED195D2E52C8D49E`;
- exact diff: 4,763 B, SHA-256
  `C7D6ACB9719E11E36E5F30F31E7494FA5D8CCE5A4BB31A8AAD38C6701496FB9A`;
- ZIP roundtrip: `17/17`, mismatch `0`.

Oczyszczony exact diff jest opublikowany jako
`docs/recovery/R04_D21_P4B_SHORT_OUTPUT_EXACT.diff` (1,247 B, SHA-256
`3C6802211AB63FF710D0C14852CB92F78DBC003BC3ED57CBE952ECDB16C82F3E`),
a mały publiczny indeks referencyjny jako
`docs/recovery/R04_D21_P4B_SHORT_OUTPUT_INDEX.json` (3,222 B, SHA-256
`B64C7BAD7B380115C43D161F3AE9F3D15192CF8D0D47D60BEA7CAF02A1935C9B`).
Recepta, collector, harnessy i surowe logi pozostają wyłącznie LOCAL_ONLY.

Wynik przygotowania:
`SHORT_OUTPUT_DERIVATIVE_READY_FOR_REVIEW / TASKINFO_6_OF_6 /
CURRENT_DRIFT_PASS_WITH_RESOURCE_LIMITATION / NO_UAC / NOT_INSTALLED`.
Pochodna nie dziedziczy automatycznie odbioru F6D3 i nie jest zgodą na
operację. Następny krok to jedna bieżąca decyzja właściciela dotycząca
dokładnych hashy i jednego UAC. Bez niej obowiązuje STOP.

## Pozostałe elementy R04 / D-21

| Element | Istniejąca zgoda/dowód | Stan | Następna decyzja |
|---|---|---|---|
| Instalacja P4/B i dwa warm runs | pakiet powyżej gotowy do review | `NOT_RUN` | exact single-use approval + jeden UAC |
| Logon/reboot i dodatkowy HKCU Run | trigger docelowy zaplanowany; HKCU Run zachowany | `NOT_TESTED` | osobne okno logon/reboot i decyzja o HKCU Run |
| OPEN_AFTER_BASE_READY / skrót UI | oddzielny działający skrót UI zachowany | `OPEN_AFTER_BASE_READY_NOT_IMPLEMENTED` | osobny mały zakres source/odbiór |
| Qdrant/VHD/profile i ciężkie dane na D: | junction danych zachowany; backing częściowo znany | `RELOCATION_OPEN` | osobna mapa/cutover/rollback approval |
| Automatyczne backupy | harmonogramy zachowane; ręczny punkt nie dowodzi schedulera | `SCHEDULED_BACKUP_OPERATION_NOT_YET_VERIFIED` | ograniczony dowód wykonania/repair package |
| P5 archiwizacja/cleanup | mapa 33 i preservation 203/203 zachowane | `NOT_RUN` | osobny exact-path owner approval po odbiorze startu |
| Całe R04 | P1/P2/P3/P4-A ograniczenie odebrane | `IN_PROGRESS` | owner review P4/B i pozostałych kryteriów |

D-22 pozostaje niezmieniona i `NOT_RUN`: po odbiorze R04 obowiązuje
`ARKUSZE -> KOREKTA I WALIDACJA KLIENTÓW -> TYLKO NIEPRZYPISANE MAILE`.
