# R05-20260912T140056Z-A4-PREVIEW-DECISION

- UTC start: `2026-09-12T14:00:56Z`.
- Repo/worktree: `domlap94-star/ai-lab-core`, branch
  `recovery/next-stabil-repair-completion`, `C:\ai-lab-core-recovery`.
- Start local/tracking/verified remote HEAD:
  `c7db3550228d50ed37b121eb8596ee6145c90f8a`; worktree clean, staged /
  unstaged / untracked `0 / 0 / 0`; no Git lock or second recovery consumer.
- Protected refs: `origin/main@483f9bf8b1a591ded8a42df5da87663c664ed5d4`
  and rescue `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a` remain read-only.
  Original `C:\ai-lab-core` remains at
  `72950657ac79b50d0afe72753632ba4cde810b95` with 203 entries and staged 0.
- Owner scope: continue only R05-A4 SOURCE / ISOLATED TEST to expose exactly
  `X-Source-Ref`, `X-Content-SHA256` and `X-Package-SHA256` to an allowed
  cross-origin client, and distinguish confirmed mutation results from an
  unknown response-delivery outcome. A4 and R05 are not accepted.
- Code-supported preimage findings: the real preview response has all three
  raw headers, but neither endpoint nor current CORS middleware exposes them;
  the real dialog labels the candidate snapshot as current state, reports
  every approve/revoke exception as a certain non-write, and does not render
  the state returned by a confirmed mutation.
- Source/test allowlist selected before edits:
  `backend/app/api/documents/router.py`,
  `backend/test/test_r05_visual_export_api.py`,
  `frontend/lib/features/documents/presentation/vision_export_approval_dialog.dart`,
  `frontend/test/features/documents/vision_export_approval_test.dart`.
  `backend/app/main.py`, Documents API/domain and all A1–A3 claim/queue/worker
  files are not needed and remain unchanged.
- Evidence root:
  `C:\ai-lab-core-staging\recovery\R05_A4_PREVIEW_DECISION_20260912T140056Z`
  (`LOCAL_ONLY`). Inheritance is disabled; access is limited to the current
  user and SYSTEM. Adding a localized Administrators rule was refused by the
  host privilege boundary and did not widen access.
- Resource gate: Windows physical RAM total `25.802 GiB`, available
  `6.215 GiB`. One authorized exact-name Docker observation for the prior
  `next-stabil-r05-a4-20260912t121418z-regression-final` resource again did
  not return and its CLI was terminated. Daemon-side state remains
  `RESOURCE_OBSERVABILITY_BLOCKED`; Docker/WSL/Windows were not restarted and
  no second observation loop will be run.
- Tests at start: `NOT_RUN`. No runtime, lifespan, browser, listener,
  Supervisor, Temporary Chat, model, external export or production data was
  used.
- One next safe step: add focused fail-before tests for the real CORS/router
  and dialog outcome semantics, then apply only the two bounded fixes.
- STOP: no R06, Web/browser smoke, real background task, deployment, escrow,
  production write or cleanup of existing resources.

## Handoff

- UTC handoff: `2026-09-12T14:14:05Z`.
- Actual result: `R05 A4 PREVIEW_TRANSPORT_AND_DECISION_SOURCE_PARTIAL /
  LOCAL_ONLY / NOT_DEPLOYED`; R05 remains `IN_PROGRESS`. A4 is not accepted.
- RV05-A4-01: the local router WIP adds endpoint-only
  `Access-Control-Expose-Headers` for exactly `X-Source-Ref`,
  `X-Content-SHA256` and `X-Package-SHA256`. Its real ASGI/CORS test covers an
  allowed synthetic origin, same-origin access, a disallowed origin and
  401/403/409 responses without changing the global CORS policy.
- RV05-A4-02: the real Flutter dialog now distinguishes confirmed success,
  confirmed 4xx rejection and an unknown response-delivery result. It disables
  automatic repeat, does not expose raw error details, labels the candidate
  state as the state at preview time and shows the state returned by a
  confirmed mutation separately.
- Fail-before: focused Flutter command exited `1` with `6 passed / 4 failed`,
  reproducing the stale label and incorrect certain-failure messages. Evidence
  SHA-256: `4F2534E0B6388C1AF465BCEF18A0B6546285039322449BA0784F65FF9ED7B29E`.
- Pass-after: focused Flutter `11/11`, Documents/Auth regression `28/28`, and
  `flutter analyze --no-pub` with no issues, all exit `0`. Final evidence
  SHA-256 values are `F41FD3FCF0DCFD1001C773A574DAB0C5AB4B9C6A875BE25851BBF4AC01419A60`,
  `902B5D88CD8D7396C15E5CE19BEE196239C2D37B899BA03233564756D855E9AD`
  and `5F3620CF2A1933C2D5490996E2A6E5DDCE7EBE65B1DED4A4793E76D06FF8E3AD`.
- Backend ASGI/CORS fail-before/pass-after, Python `compileall` and focused
  backend tests are `NOT_RUN / RESOURCE_OBSERVABILITY_BLOCKED`. The exact-name
  Docker observation did not return within the bounded window, so daemon-side
  state could not be confirmed safely. Historical `78/319` results are not
  reused as current evidence.
- Source/test WIP is limited to
  `backend/app/api/documents/router.py`,
  `backend/test/test_r05_visual_export_api.py`,
  `frontend/lib/features/documents/presentation/vision_export_approval_dialog.dart`
  and `frontend/test/features/documents/vision_export_approval_test.dart`.
  It is not staged or committed. Reproducible patch:
  `C:\ai-lab-core-staging\recovery\R05_A4_PREVIEW_DECISION_20260912T140056Z\r05-a4-preview-decision-wip.patch`,
  size `18039 B`, SHA-256
  `81E311E7C129FC7ACC8829BC8B2E3FB31CDFEA6F800D56EE46E16E9E58A17914`;
  reverse apply-check against the current WIP passed.
- Operational effects: no app/runtime, browser, listener, backend server,
  dispatcher, Supervisor, Temporary Chat, model, external export, production
  data/config write or deployment was run. No existing Docker/WSL/Windows or
  foreign process was stopped or changed.
- Final Git publication for this continuation is documentation-only. The four
  WIP paths remain recoverable locally and must not be reported as remote.
- One next safe step: after an external restoration of reliable Docker
  observability, resume exactly the recorded patch and run the single pinned
  backend ASGI/CORS test plus `compileall`; only then assess a source commit.
  STOP before R06 or any runtime/export test.

Previous checkpoint:
`docs/recovery/checkpoints/20260912T130033Z-R05-A4-OPERATOR-HANDOFF.md`.
