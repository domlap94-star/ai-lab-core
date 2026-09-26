# R04 DATA/BACKUP + COMPATIBILITY — wynik przed oknem operacyjnym

Status: `IN_PROGRESS / SOURCE_FOCUSED_PASS / OPERATIONAL_DECISION_REQUIRED`.

Zachowane bez ponawiania: `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` oraz
`ONE_ENTRY_COLD_COMPLETE / OWNER_CONFIRMED`.

## Backup planner

- Istniejący UI wymaga jawnego wyboru hostowego folderu przy tworzeniu planu,
  pokazuje bieżący cel przy edycji i nie zapisuje planu po anulowaniu.
- Task przechowuje wyłącznie ID harmonogramu; runner ponownie odczytuje zapisany
  cel z bazy. Nie ma pytania ani fallbacku podczas kolejnych terminów.
- Nowa granica odrzuca cały logiczny wolumin C: i D:, a hostowy preflight
  odrzuca także fizyczny cel C:/D: po rozwiązaniu ścieżki.
- Usunięto legacy domyślny cel `C:\ai-lab-core-backups`.
- PostgreSQL custom dump i eksporty n8n są strumieniowane wprost do artefaktów
  checkpointu na wybranym celu. Qdrant usuwa własny snapshot tymczasowy po
  pobraniu; po wymaganej relokacji Docker jego backing będzie na D:.
- Memory retention i backup retention nie zostały zmienione.

Focused evidence: backend policy `2 passed`; Flutter backup UI `11 passed`;
Node storage i scheduler `PASS`; PowerShell 5.1 parser `PASS`; worker direct
regressions `4/4 PASS`; `git diff --check` PASS.

## Fizyczne dane

Pełna bezpieczna projekcja znajduje się w `R04_DATA_PLACEMENT_INVENTORY.csv`.
Potwierdzone `RELOCATE`: Docker Desktop VHDX wraz z Qdrant/writable layers oraz
profil workera `C:\ChatGPT-Vision-Worker`. `C:\Ollama-Vision-Pilot` pozostaje
`UNKNOWN` i nie jest kandydatem do przeniesienia.

## Compatibility

`R04_COMPONENT_COMPATIBILITY_MANIFEST.json` zapisuje obserwowane tożsamości,
nie udaje spójności. Windows jest `SUPPORTED` na podstawie odebranego cold OP.
Web jest osiągalny i publiczne `/control` zwraca 404, lecz wygasła sesja i nie
wykonano list/detail. Android APK ma zgodny hash i poprawny podpis v2, lecz
runtime pozostaje owner-deferred. Live Web +41, stable Windows/Android +29 oraz
publiczne `latest_app_version=1.0.0` są materialnie niespójne.

## Bieżące blokady wykonawcze

1. Relokacje wymagają jednego zatwierdzonego okna: wspierany przez Docker
   Desktop ruch Disk image location na D: oraz atomowa migracja nieaktywnego
   profilu workera na `D:\ai-lab-data\workers\chatgpt-vision`.
2. Wdrożenie zmienionych plików do `C:\ai-lab-core` wymaga jednego UAC.
3. Rzeczywisty schedule proof zależy od backup Supervisora na 8787. Supervisor
   jest `INTENTIONALLY_STOPPED`, a bieżący zakres jawnie zabrania jego startu;
   bez nowej wąskiej zgody nie wolno uczciwie zaliczyć ścieżki task → runner →
   destination.
4. Wybór rzeczywistego celu poza C:/D: nastąpi dokładnie raz po wdrożeniu.
5. Web list/detail wymaga bieżącej zalogowanej sesji; Android runtime pozostaje
   `NOT_TESTED_WITH_REASON` zgodnie z D-17.

## Jedno proponowane okno operacyjne

Candidate startup manifest: `R04_DATA_BACKUP_STARTUP_SET_CANDIDATE.json`,
33547 B, SHA-256
`0F10B58E2D7FA8E6E8A2F958BBA7518962D1026BA20BF5190BD24D2F9BB9FF11`.
Zmienia set/approval binding oraz hash `supervisor_script` na
`EE62CA8E64C836093F6581EBF5724642B620055BE5E13BB4CEE974256595F8E3`;
pozostałe przypięte role startupu pozostają bez zmian.

Zakres instalacji ma preimages:

| Cel | Preimage SHA-256 | Candidate SHA-256 |
|---|---|---|
| `backend/app/schemas/admin_backup.py` | `BCE09DF...486D3` | `3FB3CBF...3F75F` |
| `backend/app/services/backup_restore_service.py` | `43716EC...558D` | `2D5BE8C...3F537` |
| `operations/hardening/backup-production.ps1` | `85DBED7...A72A1` | `25BD1F1...B4DDE` |
| `operations/supervisor/backup_storage.js` | `4172169...C5525` | `C39E5B6...0E80` |
| `operations/supervisor/server.js` | `4CFB7F9...170701` | `EE62CA8...5F8E3` |
| `operations/vision-worker/analysis-job.js` | `2D9E4B0...C971C` | `61FD954...AC70` |
| `operations/vision-worker/reliability_gate.js` | `C4A0F5C...3DED9` | `58A7E89...C058` |
| `operations/runtime/startup-set.json` | `53CA6E9...72EC9` | `0F10B58...9FF11` |

`operations/vision-worker/vision-job.js` z recovery nie jest payloadem
instalacji: produkcyjny worker zostaje przeniesiony byte-for-byte razem z
całym profilem. Preimages są kopiowane do operation-owned rollback directory
przed zapisem. Rollback plików jest dozwolony tylko przy rozliczonym braku
aktywnej operacji; relokacja Docker używa własnego wspieranego mechanizmu
Docker Desktop i jego cofnięcia lokalizacji, nie ręcznej kopii żywego VHDX.

Relokacje w jednym oknie:

| Obiekt | Z | Do | Rozmiar | Stop/start | Walidacja | Przerwa / ryzyko |
|---|---|---|---:|---|---|---|
| Docker Desktop disk image, Qdrant volume i writable layers | `C:\Users\<owner>\AppData\Local\Docker\wsl\disk\docker_data.vhdx` | `D:\DockerDesktopData` przez Settings → Resources → Advanced → Disk image location | 48207233024 B | Docker Desktop i sześć przypiętych kontenerów; bez create/recreate/build/pull | te same 6 IDs/images/mounts/ports, PostgreSQL healthy, Qdrant collection metadata, public 200/404 | ok. 15–45 min; przerwanie usług; rollback przez wspierany wybór poprzedniej lokalizacji |
| profil vision/analysis worker | `C:\ChatGPT-Vision-Worker` | `D:\ai-lab-data\workers\chatgpt-vision` | 890094670 B | Supervisor pozostaje zatrzymany | count/bytes oraz hash inventory przed/po; brak źródła na C po odbiorze | ok. 5–15 min; profil przeglądarki wymaga zachowania ACL i pełnej kopii |

Przed oknem trzeba potwierdzić brak aktywnego backupu/importu/maintenance.
Po relokacji uruchamiane są wyłącznie dotychczasowe zasoby Docker potrzebne do
readbacku; Supervisor pozostaje zatrzymany. Do controlled schedule proof
potrzebna jest osobna, wąska zgoda na jego tymczasowy start tylko na czas jednej
operacji, ponieważ bez procesu na 8787 istniejący runner fail-closed nie może
wykonać backupu.

R04 pozostaje `IN_PROGRESS`; D-22 pozostaje `NOT_RUN`.
