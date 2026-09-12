# R05-20260912T080832Z-A3-BROWSER-FILEPAYLOAD

- UTC start: `2026-09-12T08:08:32Z`.
- Repo/worktree: `domlap94-star/ai-lab-core`, branch
  `recovery/next-stabil-repair-completion`, `C:\ai-lab-core-recovery`.
- Start local/remote HEAD: `60b1736db9eb18ef5445a2d8407988106ff96407`;
  tree clean, staged/unstaged/untracked `0/0/0`.
- Owner decision: R05-A2 source
  `d1b0518ad9aefb5bc05cd89308de923ca54d2809` and evidence
  `60b1736db9eb18ef5445a2d8407988106ff96407` are accepted as
  `SOURCE_AND_OFFLINE_BOUNDARY_ACCEPTED / NOT_DEPLOYED`. R05-A3 is authorized
  only as `LOCAL_BROWSER_FILE_INPUT / TEST_ONLY`; A3 and the whole R05 are not
  accepted.
- Code under test: accepted A2 source
  `d1b0518ad9aefb5bc05cd89308de923ca54d2809`; `origin/main` remains
  `483f9bf8b1a591ded8a42df5da87663c664ed5d4`, rescue remains read-only at
  `5cd8f86e63e1ab829692ca2601096fd0c0d9d53a`.
- Preflight: remote refs matched; recovery has no executing consumer; original
  worktree remains `72950657ac79b50d0afe72753632ba4cde810b95`, 203 entries,
  staged `0`. Existing Node `v24.18.0`, Playwright `1.62.1` at the preserved
  worker dependency root and Edge `151.0.4129.72` are available without
  installation. Resource gate at `2026-09-12T08:09:06.9364274Z`: Windows
  available physical RAM `6.494 GiB`, commit spare `36.153 GiB` — PASS.
- Evidence root created with protected ACL:
  `C:\ai-lab-core-staging\recovery\R05_A3_LOCAL_BROWSER_20260912T080832Z`.
- Exact source/test allowlist before implementation:
  `operations/vision-worker/test_browser_filepayload.js` only. Documentation
  allowlist: this checkpoint, roadmap §0/R05 evidence pointer, D-20 and R05
  mirrors, `docs/recovery/R05_A3_BROWSER_FILEPAYLOAD_EVIDENCE.md`, and
  `docs/recovery/R05_A3_LOCAL_EVIDENCE_MANIFEST.csv`.
- Initial state: `R05-A3 IN_PROGRESS / TEST_ONLY`; browser matrix A–E was
  `NOT_RUN`. No application, worker CLI, ChatGPT, Temporary Chat, Supervisor,
  model or external upload was started.
- Initial next safe step: add the opt-in harness, verify its no-flag `NOT_RUN`
  behavior, then run one isolated offline browser matrix against copied
  synthetic A2 inputs.
- STOP: no `run(jobDir)`, persistent/existing profile, public navigation,
  external upload, product-source change, R06, deployment or production write.

Previous checkpoint:
`docs/recovery/checkpoints/20260911T232156Z-R05-A2-UPLOAD-REPLAY.md`.

## Handoff result

- Test UTC: `2026-09-12T08:15:50.873Z`–`2026-09-12T08:15:52.487Z`;
  exit `0`; result `REAL_BROWSER_FILELIST_EXACT_BYTES_PASS`.
- Real local boundary: Node `v24.18.0`, Playwright `1.62.1`, nonpersistent
  headless Edge `151.0.4129.72`, executable SHA-256
  `E73E04DACDB48557C13D9F93F90A248F3E5A0BF55BB738F2FC548A768A9A10AF`.
  One context used `offline=true`, service workers blocked and abort routing
  for HTTP(S)/WebSocket. It stayed on `about:blank` with in-memory HTML.
- A/public-safe: one real delegated `setInputFiles`, DOM `S1.jpg`,
  `image/jpeg`, `2087 B`, SHA-256
  `3956F8ED4074E3AB3531A9A821159A65A8A12441E6E5328021D6A09914DD3206`;
  `input=1/change=1`.
- B/locally-redacted: one real delegated `setInputFiles`, DOM `4688 B`,
  SHA-256
  `7A89CB69AE2D29BDB1F8F2311177CB128B877B75F00C6B2A94B33661631B431C`;
  differs from the synthetic forbidden original; `input=1/change=1`.
- C/tamper-after-read: disk changed to
  `0503AE270E808AECF54D1FE44AF5438ACBF7F9A35277C632F7CD3154E8EA732B`,
  while DOM received the previously verified public-safe buffer.
- D/same-job retry: `UPLOAD_HANDOFF_ALREADY_EXISTS`; additional locator,
  input and change calls all `0`; FileList unchanged.
- E/denials: `INPUT_CHECKSUM` and `TEMPORARY_CHAT_NOT_VERIFIED`; both DOM
  FileLists empty, successful selections `0`.
- The positive synthetic jobs were marked confirmed only after independent
  DOM `File.arrayBuffer()` verification and recorded as `LOCAL_TEST_ONLY`.
  `temporaryChatVerified=true` was a synthetic test input, not an observation
  of Temporary Chat.
- Isolation result: page-context public navigation `0`, unexpected HTTP(S)/WS
  requests `0`, external upload `0`, normal worker `run(jobDir)` calls `0`.
  This is not whole-host packet monitoring. Edge processes: 13 before/13
  after, no new PID left. Browser/context closed.
- Focused checks: harness `node --check`, no-flag opt-in guard, A2 replay
  regression and A2 boundary regression all exit `0`; the latter retained 17
  local cases and two accepted synthetic chain cases.
- Raw result/logs and reviewed synthetic screenshot remain `LOCAL_ONLY` under
  the protected evidence root. Result JSON SHA-256
  `ED60261E417E0D700F23200103F737E7071C2BBED1FEE223F2FF5C001AE7BE90`;
  screenshot SHA-256
  `13343DFCC8A1000DB0D596B2D00FE30BA8E055ED774184261C58A44E4F0F1B9A`.
- Source changes: one new opt-in test only; product source/config unchanged.
  Application/backend/worker CLI/Supervisor/ChatGPT/Temporary Chat/model/
  Qdrant/Gmail/n8n/production DB and remote upload were `NOT_RUN`.
- Final state: `R05 A3 LOCAL_BROWSER_FILE_INPUT_READY_FOR_REVIEW / TEST_ONLY`;
  `TEMPORARY_CHAT_MODE_AND_REMOTE_UPLOAD_NOT_VERIFIED`; R05 and R04 remain
  `IN_PROGRESS`; R03 remains `WAITING_APPROVAL / WAITING_ESCROW_DECISION`;
  Android `DEFERRED_BY_OWNER / NOT_TESTED`; D-15/D-16 AI acceptance `NOT_RUN`.
- Staged state at this checkpoint is finalized only after the documented
  allowlist/diff/secret/registry checks. No process or long task remains.
- One next safe step: owner review of this bounded A3 result. No automatic
  real upload, R06, rollout or deployment.
