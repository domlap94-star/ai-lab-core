# R04 DATA/BACKUP + COMPATIBILITY — wykonane okno i rozliczony K1

Status: `PARTIAL_EXECUTED / BACKUP_SCHEDULE_PROOF_FAILED_K1 / NO_PENDING_MUTATION`.

Zachowane bez ponawiania: `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` oraz
`ONE_ENTRY_COLD_COMPLETE / OWNER_CONFIRMED`.

## Bramka i instalacja

- Operację rozpoczęto wyłącznie na clean
  `recovery/next-stabil-repair-completion@18f142dca043d996a0f614bdb5f0946b5429db0a`.
- Exact preimages ośmiu przygotowanych celów były zgodne.
- Jeden zatwierdzony UAC zainstalował wyłącznie cztery pliki:
  `admin_backup.py`, `backup_restore_service.py`, `backup-production.ps1` oraz
  `backup_storage.js`. Końcowe SHA-256 są identyczne z blobami commita.
- `server.js`, startup manifest i pliki Vision/Analysis Workera nie zostały
  zainstalowane. Przygotowany source wiąże `VISION_WORKER_ROOT` z D: i wyprowadza
  z niego także `worker/vision-job.js` oraz `node_modules`; przeniósłby więc kod,
  executable dependencies i CWD pod dane. Jest to sprzeczne z zatwierdzonym
  `SINGLE_INSTALL_ROOT`, dlatego zatrzymano wyłącznie zależny krok workera.
- Preimages czterech zmienionych plików są zachowane pod
  `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R04-DATA-BACKUP-20260926T160500Z\preimages`;
  rollback nie był potrzebny.

## Docker Desktop data relocation

- Wspierana zmiana Docker Desktop przeniosła dyski do
  `D:\DockerDesktopData\DockerDesktopWSL`.
- Stary `C:\Users\domai\AppData\Local\Docker\wsl\disk\docker_data.vhdx` jest
  nieobecny. Nowe VHDX mają `48207233024` B i `100663296` B.
- Sześć produkcyjnych kontenerów zachowało exact container IDs i image IDs;
  PostgreSQL i Open WebUI są healthy. Te same container IDs bez recreate
  zachowują niezmienne konfiguracje mount/port. Nie wykonano
  `compose up/create/recreate/build/pull` ani rebootu Windows.

## Jeden controlled schedule proof

- Właściciel wybrał `F:\dump`. Cel istniał, był zapisywalny i miał
  `490183430144` B wolnego miejsca; probe został usunięty. Nie zastosowano
  fallbacku.
- Przed startem nie znaleziono queued/running Vision ani Analysis, aktywnego
  backupu/importu/maintenance ani listenera Supervisora.
- Zmieniono wyłącznie istniejący plan `daily baza danych` ID `2`: destination
  `F:\dump`, revision `2`; reconciliation `1/1`, status `synced`. Nie utworzono
  planu ani dodatkowego taska.
- Historyczne rozmiary wynosiły około `466.5 MB`, a czasy `51–82 s`.
- Supervisor został uruchomiony tymczasowo przez istniejący task, a następnie
  istniejący `NEXT Stabil - Backup - 2` uruchomiono dokładnie raz.
- Run `48`, operation `9131309f-2a14-4564-95bf-7d5737183482`, zakończył się po
  około 6 s jako `failed / backup_runner_failed`: verified false, artifact count
  `0`, total bytes `0`, checkpoint i manifest absent. `F:\dump` pozostał pusty.
  Supervisor zachował tylko kod ogólny i nie zachował stderr, więc dokładniejsza
  przyczyna nie jest dowodem. Nie wykonano retry.
- Po proofie aktywne backup runs `0`, Supervisor task `Ready`, proces `0`,
  listener 8787 `0`. Nie pozostawiono dużego payloadu ani nowych temporaries na
  C:/D:. Plan ID 2 pozostaje pojedynczy, `synced`, a kolejne `next_run_at` to
  `2026-09-26T23:00:00Z`.

## Compatibility i wynik R04

`R04_COMPONENT_COMPATIBILITY_MANIFEST.json` zachowuje rozdzielone tożsamości
backend/Web/Windows/Android. Windows cold/list/detail pozostaje owner-confirmed;
publiczne `/control*` pozostaje 404. Web list/detail nie było powtarzane przy
wygasłej sesji, Android runtime pozostaje owner-deferred. Nie nadano im
nieudokumentowanego PASS.

R04 pozostaje `IN_PROGRESS`. Konkretny K1 to brak udanego dowodu
`schedule -> runner -> F:\dump`; drugi K1 to sprzeczne wiązanie kodu Workera do
data root w commicie `18f142d...`. Stan produkcji jest rozliczony, bez aktywnej
operacji i bez nierozstrzygniętej mutacji. D-22 pozostaje `NOT_RUN`.

Następny bezpieczny krok: source correction rozdzielająca kanoniczny worker
code root `C:\ai-lab-core` od state root na D: oraz diagnostycznie obserwowalny
runner backupu; review i nowa jawna zgoda są wymagane przed kolejną instalacją
lub proofem. Nie wykonywać automatycznego retry.
