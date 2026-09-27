# R04 final execution — immutable source checkpoint

Status: `SOURCE_AND_OFFLINE_PASS / READY_FOR_AUTHORIZED_UAC_1`.

- Installer records `EXACT_BYTES` or `ABSENT_PREIMAGE` for every file target, including package manifests, and restores/removes only operation-owned targets on failure.
- Worker code/modules remain assigned to `C:\ai-lab-core\operations\vision-worker`; mutable state remains assigned through `C:\ai-lab-core\data` to D:.
- Backup runner uses `python -m app.scripts.run_backup_schedule`.
- Qdrant-inclusive backup stops the original container, mounts the same named volume into one operation-owned helper on the same pinned image, places snapshot and temp under `F:\dump\.next-stabil-qdrant-staging`, removes the helper, restarts the original container and verifies identity/data invariants.
- Direct results: PS5.1 parsers PASS; Python compile PASS; Worker topology, Vision queue, Analysis queue, Worker contract, backup scheduler/storage and Qdrant helper contract PASS. Node `24.18.0`; Playwright lock and existing modules `1.62.1`; no network dependency install.
- No production mutation, backup proof, Supervisor start, reboot/logoff, restore, D-22, P5 or R06 occurred in this source checkpoint.

The commit containing this checkpoint is the immutable source revision for the authorized execution window.
