# R04 final execution — consolidated result

Status: `R04_IN_PROGRESS / FINAL_CONSOLIDATED_K1`.

## Completed independent result

- Source/offline worker, backup and Qdrant-helper changes are published at `90c5531a3f330aa2d1068402db0cda3ba0907381`.
- UAC-1 stopped on `WORKER_PROCESS_ACTIVE`; durable journal/result prove `FAILED_ROLLED_BACK`, rollback `COMPLETE`, all 12 exact/absent preimages restored and no pending mutation. The guard matched its own PowerShell audit command; the node-only correction is published at `eb1adf1` but was not redeployed or retried.
- Therefore Worker code/data split and backup runner/helper are not installed, no new schedule proof was run, and `F:\dump` has no new verified checkpoint artifact.
- UAC-3 completed the backend-only version policy. Backend image stayed `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`; the five non-backend container IDs remained exact. Installed version override hash is `4F55994D8258090BC92120A46C48E053877971307297C5CF06F4EF4FC29F0D82`; installed startup manifest hash is `51EC9B4D58F32CD8D72A21A24F3AAEEA14994EEF92E943933788209C2128EAB9`.
- Live `/version` reports application/backend `1.0.2`, minimum `1.0.0`, release `NEXT-STABIL-R04-c35b6bd64f094777`, source `90c5531a3f330aa2d1068402db0cda3ba0907381`, `environment=production`, `debug=false` and `runtime_configuration=SAFE`. Health/public gateway return 200; public `/control` and `/control/status` return 404.
- Windows remains `1.0.2+29`. Approved Android APK `1.0.2+29` is SHA-256 `33EBF3DB7A5547A55AEC540173A65AE57EC881657DDA3B039ECF66DBA3F8DA5` and APK v2 verified. Emulator snapshot `r04-before-signature-migration-20260927` exists; bounded inventory found only application runtime/cache and encrypted preferences. The uninstall/install command was rejected by the formal execution path before process creation, so the existing emulator app was not mutated.
- Docker VHDX remains at `D:\DockerDesktopData`; active heavy data and Qdrant backing remain previously verified on D:. Supervisor was not started. No reboot, logoff, restore, purge, D-22, P5 or R06 occurred.

## Material K1

1. `WORKER_SPLIT_NOT_DEPLOYED_AFTER_ROLLBACK`: production still uses the preimage worker topology.
2. `BACKUP_PROOF_NOT_RUN_NO_ARTIFACT`: the corrected production runner/helper is not installed; no successful task -> runner -> checkpoint proof exists on `F:\dump`.
3. `ANDROID_SIGNATURE_MIGRATION_NOT_EXECUTED`: the approved APK and rollback snapshot exist, but the formal execution path rejected the mutation before start.

These failures directly prevent the frozen R04 criteria. `R04_READY_FOR_OWNER_REVIEW` and `R04_ACCEPTED` are not assigned. Historical USABLE-WARM and ONE-ENTRY-COLD acceptance remains unchanged; D-22 remains `NOT_RUN`.
