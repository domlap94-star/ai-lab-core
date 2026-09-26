# R04 — final closure window / consolidated K1

Status: `R04_IN_PROGRESS / FINAL_CONSOLIDATED_K1`.

## Wynik użytkowy

- Zachowano `USABLE_WARM_ACCEPTED / LIMITED_RUNTIME_SCOPE` oraz `ONE_ENTRY_COLD_COMPLETE / OWNER_CONFIRMED`; nie powtarzano warm/cold/reboot ani CRM.
- Docker VHDX pozostaje pod `D:\DockerDesktopData\DockerDesktopWSL`; aktywne ciężkie dane pozostają fizycznie na D:, memory retention i backup retention są niezmienione.
- Bounded audit `C:\Ollama-Vision-Pilot` nie znalazł procesu, taska, usługi, Run key, manifest/source/n8n bindingu ani reparse consumer. Klasyfikacja: `LEGACY_PRESERVED_NO_ACTIVE_CONSUMER`; katalog zachowano bez zmian.
- Worker source/offline i exact preimages przeszły. Jeden wspólny UAC zakończył się przed startem: brak OutputRoot, journalu, resultu i mutacji. Produkcja nadal używa starego Workera, więc deployment/workflow nie są PASS.
- Pierwszy nowy proof uruchomił istniejący task `NEXT Stabil - Backup - 2`, który zakończył się result `1` przed utworzeniem backendowego runu. Fail-before odtworzył `ModuleNotFoundError: No module named 'app'` dla file-path invocation. Source zmieniono na `python -m app.scripts.run_backup_schedule`; PS5.1 transport `--help`, parser i scheduler/storage tests przeszły. Drugi UAC dla tej wąskiej poprawki został anulowany; bez retry i bez drugiego proofu. Historyczny run 48 pozostaje FAIL, `F:\dump` nie ma nowego checkpointu.
- Public health/Web są 200, publiczne `/control` i `/control/status` są 404. Windows `1.0.2+29` zachowuje exact SHA-256 i jeden proces. Public `/version` nadal zgłasza backend `1.0.0`, latest `1.0.0`, development/debug true, UNKNOWN release/image i `REVIEW_REQUIRED`.
- Android APK `1.0.2+29`, SHA-256 `33EBF3DB7A5547A55AEC540173A65AE57EC881657DDA3B039ECF66DBA3F8DA5E`, przechodzi APK Signature Scheme v2; cert SHA-256 `5E223DA2DA7C893D089D7333E99AAEEE8D98C9CDF72BE80609020967368FE018`. Emulator uruchomił się, lecz instalacja została bezpiecznie odrzucona przez `INSTALL_FAILED_UPDATE_INCOMPATIBLE`: obecny `pl.ailab.app` to `1.0.0` z innym podpisem. Nie odinstalowano aplikacji i nie usunięto danych.

## Otwarte materialne K1

1. `WORKER_CODE_STATE_SPLIT_NOT_DEPLOYED_UAC_DID_NOT_START` — brak production workflow PASS.
2. `BACKUP_RUNNER_MODULE_FIX_NOT_DEPLOYED_SECOND_UAC_CANCELLED` — brak nowego runu/checkpointu/artefaktu proof na `F:\dump`.
3. `PUBLIC_VERSION_RELEASE_CONFIGURATION_NOT_PRODUCTION_SAFE` — backend version policy/evaluator nie jest VERIFIED.
4. `ANDROID_EXISTING_INSTALL_SIGNATURE_MISMATCH` — zatwierdzony APK nie może zaktualizować istniejącej instalacji bez destrukcyjnego uninstallu, którego nie wykonano.
5. `QDRANT_API_SNAPSHOT_CREATES_FULL_TEMP_INSIDE_D_VHDX` — obecny `backup-production.ps1` tworzy service-native snapshot przez `POST /collections/{name}/snapshots` w named volume na D: przed pobraniem do zewnętrznego checkpointu. Nie wykazano wspieranego restore-compatible exportu bez pełnego temporary na C:/D:; produkcyjnego restore nie wykonywano.

Supervisor pozostaje `INTENTIONALLY_STOPPED`; brak pending mutation, reboot/logoff/restore/purge, D-22/P5/R06 nie zostały uruchomione.
