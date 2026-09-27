# R04 three-K1 closure attempt

Status: `R04_IN_PROGRESS / FINAL_CONSOLIDATED_K1`.

## Source and authorization

- Start state was clean and synchronized at `7345736676f294264c146893ff7e7b57d42c0903`; installed manifest and version override matched `51EC9B4...EAB9` and `4F55994D...D82`.
- Guard A/B/C passed: PowerShell text did not match, exact worker `node.exe` matched, unrelated `node.exe` did not match.
- Direct Worker, queue, backup scheduler/storage and Qdrant helper regressions passed. Transactional source was published as `34fc84bd613738852437707d85029d49517d069b` before UAC.

## Common UAC result

- Operation `R04-FINAL-CLOSURE-WORKER-BACKUP-20260927` used the new OutputRoot `C:\Users\domai\AppData\Local\Temp\NEXT-STABIL-R04-FINAL-CLOSURE-20260927`.
- Exact file and absent-directory preimages were captured. The operation stopped before `MUTATION_STARTED` at `TREE_VERIFY_FAILED:worker_modules`: staged files, bytes and aggregate hashes matched, but the staging root ACL inherited from its new parent rather than the source root.
- Durable result is `FAILED_ROLLED_BACK`, rollback `COMPLETE`, `pending_mutation=false`. Worker module/state targets remain absent and staging residue is `0/0`; production Worker/backup files remain their preimages. No backup proof was started and `F:\dump` has no new checkpoint.
- The catch path unnecessarily recreated the backend despite the pre-mutation failure. Live backend is `4c4ca245...`, while the restored manifest still binds `b175fe4f...`. Version override and manifest bytes were restored to their exact hashes; live version remains `1.0.2`, minimum/latest `1.0.0/1.0.2`, production, debug false and SAFE. This identity mismatch is a new material K1.
- Source `b1a414d` now explicitly transfers the staging root ACL and performs no backend/file/directory rollback when `pending_mutation` was never opened. It is published but not deployed because the one common UAC was consumed and the conditional second UAC applied only after a real backup-proof source failure.

## Android emulator

- Exactly one target, `emulator-5554`, reported `ro.kernel.qemu=1`; no physical device was present. Snapshot `r04-before-signature-migration-20260927` existed and loaded successfully. Bounded sandbox inventory had 22 entries and zero company/client/mail/document/CRM path matches.
- Approved APK SHA-256 is `33EBF3DB7A5547A55AEC540173A65AE57EC881657DDA3B039ECF66DBA3F8DA5E`; APK Signature Scheme v2 is true and certificate SHA-256 is `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`.
- `adb uninstall pl.ailab.app` and the following streamed install both returned `Success`. The wrapper treated the multi-line install output as a failed scalar comparison and immediately executed the approved snapshot rollback. Final readback confirms restored `versionName=1.0.0`, `versionCode=1`. Per the no-retry rule, Android was not attempted again.

## Final reconciliation

- Backend health/version and public gateway return 200; public `/control` and `/control/status` return 404.
- Installed Windows executable SHA-256 remains `5BD959A30CE176D5E484D41EF1B5BF51D0D9FD38F5F99F7219AA07446BDB0865`; exactly one client process is present.
- Supervisor process/listener is `0/0`; active backup/restore is `0/0`; no reboot, logoff, restore, purge, D-22, P5 or R06 occurred. Memory and backup retention were not changed. Qdrant was never stopped because proof was not reached.

## Material K1

1. `WORKER_SPLIT_NOT_DEPLOYED_AFTER_ACL_STAGE_FAILURE`.
2. `BACKUP_PROOF_NOT_RUN_NO_ARTIFACT`.
3. `ANDROID_1_0_2_INSTALL_ROLLED_BACK_BY_WRAPPER_NO_RETRY`.
4. `STARTUP_MANIFEST_BACKEND_CONTAINER_ID_MISMATCH_AFTER_PREMUTATION_ROLLBACK_RECREATE`.

The frozen acceptance criteria are not met. `R04_READY_FOR_OWNER_REVIEW` and `R04_ACCEPTED` are not assigned; historical USABLE-WARM and ONE-ENTRY-COLD acceptance remains unchanged; D-22 remains `NOT_RUN`.
