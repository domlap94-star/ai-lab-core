# R05-20260914T144558Z-A4-DOCKER-UPDATE-PARTIAL-RECOVERY

- UTC window: owner-operated restart observed at approximately
  `2026-09-14T14:33Z`; final bounded state check `2026-09-14T14:45:58Z`.
- Repo/worktree: `domlap94-star/ai-lab-core`, branch
  `recovery/next-stabil-repair-completion`, `C:\ai-lab-core-recovery`.
- Start local/tracking HEAD:
  `4df09305b870626795036a3ea370929f03e92ce5`; staged `0`, untracked `0`.
- Four expected source/test WIP paths and patch
  `81E311E7C129FC7ACC8829BC8B2E3FB31CDFEA6F800D56EE46E16E9E58A17914`
  remain byte-identical, unstaged and `LOCAL_ONLY`.
- Independent operator PowerShell reproduced the original Docker Engine
  timeout. Docker Desktop GUI was only partially responsive and its Inspect
  view did not load, so pre-operation `CURRENT_BACKEND_MOUNT=UNKNOWN` was
  explicit. The Compose path was not treated as runtime evidence.
- The owner authorized exactly one standard Docker Desktop restart with the
  stated interruption, automatic-resume and unknown-mount risks. Docker Desktop
  reported `Wsl/Service/CreateInstance/0x800705b4`; no second restart,
  `wsl --shutdown`, kill/reset/prune, context change or compose action followed.
- The owner later reported that Docker started after an update performed
  outside Codex. Codex did not execute or approve that update as part of the
  service operation.
- Read-only runtime after the update: Docker Desktop `4.91.0`, Engine `29.8.0`;
  full backend ID
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`,
  image ID
  `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`,
  `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`,
  `/data=C:/ai-lab-core/data`. No recovery/WIP mount was present.
- Six existing AI-Lab containers and the unrelated `postgres:10` container
  were running with their existing full IDs from approximately `14:41Z`.
  Exact old container
  `next-stabil-r05-a4-20260912t121418z-regression-final` was absent
  (`no such object`). No container was manually started, stopped or removed.
- Health at `14:45:58Z`: backend, n8n and Open WebUI HTTP `200`; Supervisor
  `127.0.0.1:8787` and public gateway `127.0.0.1:8789` unreachable. The earlier
  pre-restart state was partly historical/GUI-derived and is not rewritten as
  a proven before/after identity.
- Pinned R02 image
  `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`
  remains available. A new resource gate and test container were not attempted
  because production service recovery was incomplete.
- Backend ASGI/CORS fail-before/pass-after, focused API regression and
  compileall: `NOT_RUN / PRODUCTION_PARTIAL_UNHEALTHY`. Prior unchanged Flutter
  results remain historical evidence for the same WIP; no Flutter rerun.
- Local sanitized evidence:
  `C:\ai-lab-core-staging\recovery\R05_A4_PREVIEW_DECISION_20260912T140056Z\docker-recovery-20260914T143943Z`.
- Status: `R05 A4 SOURCE_PARTIAL / LOCAL_ONLY / NOT_DEPLOYED`;
  `ENGINE_RECOVERED / PRODUCTION_PARTIAL_UNHEALTHY`. R05/R04 remain
  `IN_PROGRESS`; R03 remains `WAITING_APPROVAL / WAITING_ESCROW_DECISION`.
- One next safe step: the owner/operator separately authorizes the exact action
  needed to restore or intentionally keep disabled Supervisor and public
  gateway. Only after both services are accounted for and healthy, and a new
  bounded resource gate passes, may the already authorized backend test
  container be started. STOP before R06, runtime/export work or another restart.

Previous checkpoint:
`docs/recovery/checkpoints/20260912T152351Z-R05-A4-BACKEND-RESUME.md`.
