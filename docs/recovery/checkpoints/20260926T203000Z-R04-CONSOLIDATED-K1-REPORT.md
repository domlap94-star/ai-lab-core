# R04 — skonsolidowany wynik końcowego okna

Status: `R04_IN_PROGRESS / CONSOLIDATED_K1_REPORT`.

## Wykonane niezależne części

- Publiczny checkpoint `3a2cd163ebd7d3edd5853663302b129b90dc2e77` został wysłany fast-forwardem i odczytany ze zdalnego SHA.
- `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` i `ONE_ENTRY_COLD_COMPLETE / OWNER_CONFIRMED` zachowują ważność; nie powtarzano warm/cold/reboot/recordera ani ręcznego odbioru CRM.
- Docker Desktop używa `D:\DockerDesktopData\DockerDesktopWSL`; stary VHDX na C: jest nieobecny. Sześć kontenerów zachowuje exact IDs/images. Qdrant named volume znajduje się pod DockerRootDir `/var/lib/docker` wewnątrz przeniesionego VHDX. PostgreSQL nie ma zewnętrznych tablespaces.
- Junction `C:\ai-lab-core\data -> D:\ai-lab-data` jest zachowany. PostgreSQL, WAL, n8n, Open WebUI, Ollama, dokumenty oraz spools fizycznie rosną na D:.
- Source rozdziela Worker code/modules root `C:\ai-lab-core\operations\vision-worker` od mutable state root `C:\ai-lab-core\data\workers\chatgpt-vision`; kod nie zawiera bezpośredniego D:. PS5.1 parse, worker topology, Vision/Analysis queues i kontrakt przeszły.
- Source samodzielnego schedule runnera usuwa zależność backup proof od zatrzymanego Supervisora, wiąże schedule/run/checkpoint, zachowuje jawny błąd i weryfikuje manifest, rozmiary i SHA-256. Python compile, PS5.1 parse, backup storage i scheduler tests przeszły.
- Publiczne health/version odpowiadają 200, `/control` i `/control/status` 404. Web `1.0.2+41` pokazuje ekran logowania; sesja jest wygasła, więc bez poświadczeń nie wykonano authenticated list/detail. Windows `1.0.2+29` zachowuje wcześniejszy owner-confirmed cold/list/detail. Android `1.0.2+29` ma zachowany APK v2/certificate evidence, runtime nie był uruchamiany.
- Memory retention i backup retention nie zostały zmienione. Supervisor pozostał `INTENTIONALLY_STOPPED`; proces/listener/active backup wynoszą 0.

## Materialne K1

1. `WORKER_CODE_STATE_SPLIT_NOT_DEPLOYED_UAC_CANCELLED`: pierwszy zatwierdzony UAC zakończył się przed startem. Brak outputu, preimages i mutacji; produkcja nadal używa starego Workera na `C:\ChatGPT-Vision-Worker`. Mutable state nie został skopiowany pod logiczny data root. Nie wykonano retry.
2. `BACKUP_RUNNER_FIX_NOT_DEPLOYED_UAC_CANCELLED`: drugi zatwierdzony UAC także zakończył się przed startem, bez outputu/preimages/mutacji. Produkcyjne dwa pliki zachowują stare hashe. Historyczny run 48 nadal ma `backup_runner_failed`, zero artefaktów i brak checkpointu. Ponieważ przyczyna source nie została wdrożona, nie uruchomiono żadnego z maksymalnie dwóch nowych proof runs. `F:\dump` nie zawiera zweryfikowanego artefaktu.
3. `COMPATIBILITY_ACCEPTANCE_INCOMPLETE`: Web authenticated client list/detail jest zablokowany wygasłą sesją; live Web +41, stable Windows/Android +29 i publiczne latest/minimum `1.0.0` pozostają materialnie niespójne, backend nadal zgłasza development/debug true; Android runtime pozostaje NOT_TESTED.
4. `OLLAMA_VISION_PILOT_CONSUMER_UNKNOWN`: `C:\Ollama-Vision-Pilot` ma około 6.74 GB na C:, ale brak dowodu aktywnego konsumenta i bezpiecznego bindingu. Zgodnie z regułą UNKNOWN nie został przeniesiony.

Nie można nadać `R04_READY_FOR_OWNER_REVIEW`. Stan końcowy jest rozliczony: brak pending mutation, brak retry, brak reboot/logoff/restore, brak startu Supervisora oraz brak D-22/P5/R06.
