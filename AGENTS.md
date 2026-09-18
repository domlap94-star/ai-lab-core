# AI-Lab repository rules

## Scope and architecture

- Treat `AI_LAB_MASTER_PLAN.txt` as the product specification,
  `AI_LAB_FOLLOWUP_PLAN.md` as its supplements, decisions, and safeguards, and
  `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md` as the sole execution order and
  resume state. The three roadmaps retired by R01 remain recoverable in Git
  history but are not active instructions and must not be used to select or
  resume a package.
- Work in one small, reviewable, testable chunk at a time. Update the execution
  plan after every completed chunk.
- Supported Flutter targets are Windows, Android, and Web. Do not restore iOS
  or macOS support.
- Preserve the public/private boundary: public gateway `127.0.0.1:8789` may
  expose Web/API/updates but never `/control`; private gateway
  `127.0.0.1:8788` may proxy `/control` to supervisor `127.0.0.1:8787`.
- Target one installed NEXT Stabil root at `C:\ai-lab-core` and one ordinary,
  idempotent user start entrypoint. This is a gated R04 consolidation
  requirement, not permission to move/delete directories, change mounts/tasks,
  or deploy current work. R05-A4 source/API/widget tests are owner-accepted and
  committed. D-21/P1 authorizes launcher source and complete offline adapters
  only in recovery. P2 preservation/candidate is owner-accepted as NOT_DEPLOYED;
  the exact directory junction `C:\ai-lab-core\data -> D:\ai-lab-data` is the
  owner-approved `ACTIVE_DATA_ONLY` topology and may be validated offline.
  The owner-authorized D21-P3 backend-only switch now runs source
  `0ee0ea50943578e6e552aae23ce1688595ddc262` from the canonical backend path
  and is owner-accepted as `CORE_BACKEND_SOURCE_SWITCH_ACCEPTED /
  LIMITED_RUNTIME_SCOPE`; it is not acceptance of the global production set.
  D21-P4/A source `8756314f51a76091a483cfc9b677a05c7f67f315` and evidence
  `8a156e0c738699b4bfee01fb98f0d10f01c803ba` are owner-accepted as
  `SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / NOT_INSTALLED`. A later bounded read-only campaign
  proved that four secondary draft IDs were transcription errors and reconciled
  all six exact container/image/digest identities in the inactive draft. This is
  `CURRENT_READ_ONLY_EVIDENCE`, not manifest approval. Phase A of bounded P4/B
  window `R04-D21-P4B-WINDOW-20260918T084652Z` prepared exact proposed
  manifest/task bytes and passed offline validation. The first exact Phase-B
  authorization was consumed after the Startup wrapper was moved and a
  disabled/no-trigger Host task was created; Windows then blocked the existing
  task updates and the first UAC was cancelled. A later single-use resume
  `R04-D21-P4B-RESUME-20260918T112015Z` was also consumed. Its one UAC was
  accepted and elevation/input checks passed, but the elevated pre-mutation
  Docker guard failed because Windows PowerShell 5.1 split the `docker inspect`
  Go-template argument passed through `Start-Process`. The resume recorded
  `mutation_started=false`. A later source/offline-only scope reproduced the
  split (56 received argv tokens instead of 7), prepared corrected LOCAL_ONLY
  recipe `5F310C64...1FD67`, passed PowerShell 5.1 17/17 cases and one exact
  read-only backend Docker inspect. The current installation state is still
  `PARTIAL_SAFE_INACTIVE`; the recipe is only `READY_FOR_REVIEW`. Payload and
  manifest remain uninstalled, five existing tasks remain on their preimages
  and warm runs are `0/2`. A production manifest, further installation, task/shortcut changes, live
  start/rollback acceptance, relocation, cleanup and P4-B/P5 still require
  separate approval. Preserve
  existing runtime roots and historical A4 evidence until a later exact
  cutover/cleanup approval; production must never execute recovery, staging, or
  test WIP.

## Safety

- DEPLOYED BINARIES ARE API CONSUMERS. A source-code update does not mean that
  every API consumer has been updated. Before changing an existing response
  contract, account for current source, the latest stable Windows and Android
  builds, live Web, and integrations/imports. Do not break an existing public
  API response shape without a versioned/additive endpoint, compatibility
  layer, or an explicit release/migration strategy. Remove a legacy endpoint
  only when the minimum supported app version guarantees that no supported
  client still needs it.
- Never mutate production CRM data, merge/delete clients, run uncertain
  backfills, publish a release, change signing/secrets, or change network
  exposure without explicit human approval.
- Data cleanup must proceed through audit, read-only projection, dry-run,
  old-to-new report, conflict detection, approval, apply, and post-apply audit.
- Preserve provenance, source evidence, audit trails, and backward
  compatibility where reasonable.
- Use Alembic for schema changes. Destructive migrations require approval.
- Never commit `.env`, secrets, Android keys, keystores, release binaries,
  runtime data, generated reports, or backups.

## Tooling and verification

- Windows shell is PowerShell 5.1. Backend Python runs in Docker; do not assume
  a working host Python.
- Flutter SDK: `C:\FlutterSDK-New\flutter`.
- Do not run `flutter clean`.
- Read and write repository text as UTF-8 without BOM when practical.
- After every chunk run relevant backend tests, API auth tests, Flutter
  `analyze`/`test` when applicable, `git diff --check`, and `git status --short`.
- Never use `git add .`; stage explicit paths only.
- Do not commit a chunk whose acceptance criteria or required tests fail.

## NEXT Stabil — shared roadmap and checkpoint

- Before changing code, read section 0 of the shared roadmap, the active package
  card, linked requirements, and the latest note in `docs/recovery/checkpoints/`.
  Verify branch `recovery/next-stabil-repair-completion`, remote SHA, the correct
  local worktree, and uncommitted state. Do not assume default main or chat
  history describes the current stage.
- Execute only the authorized package and its remaining substep. Do not create a
  new roadmap, change scope/criteria, or replace 9B/KB/Temporary Chat. "Continue"
  does not consume operational approvals or authorize the next package.
  `WAITING_APPROVAL` requires the applicable decision.
- D-21 P3 authorized and completed exactly one backend-only source switch for
  OP_ID `R04-D21-P3-CORE-SWITCH-20260917T141404Z`. That consumed operation does
  not authorize another recreate, rollback without a new trigger/decision,
  Supervisor start, runtime/config/data/mount/task changes, migration, backup,
  restore, escrow, relocation, cleanup, or continuation into P4-B/P5. P4-A is
  owner-accepted only as source/offline plus an inactive local package; its
  repository draft manifest remains `NOT_APPROVED`. The bounded read-only
  identity evidence is complete 6/6 after a documented transcription
  correction. The P4/B authorization for OP_ID
  `R04-D21-P4B-WINDOW-20260918T084652Z` and the later resume authorization
  `R04-D21-P4B-RESUME-20260918T112015Z` are consumed. The partial disabled Host
  task and relocated Startup wrapper must not be treated as an installed
  launcher. The corrected replacement recipe/index are ready for review but are
  not accepted or authorized for execution. Any continuation requires owner
  review of those exact bytes, a new current owner decision, a fresh bounded
  drift check and owner presence for one UAC prompt. That future decision is single-use and does not authorize
  reboot/logoff, Supervisor, backup/restore, relocation, P5 or R06.
- One writer at a time. ChatGPT may read concurrently, but checkpoint/source
  writes are serialized by the workflow; never automatically overwrite remote,
  force-push, or create a second "canonical" branch.
- After a meaningful substep/test/blocker change, before pausing, and at the end,
  update the checkpoint, actual results, and one next step. When package status
  changes, synchronize derived indexes in the same commit. Section 0.2 is the
  status authority; historical audit assessments stay unchanged.
- The ban on committing generated reports has a narrow exception for reviewed,
  sanitized planning maps and small resume notes under `docs/recovery/`. It does
  not cover dumps, raw logs, source copies, secrets, `.env`/cookies/keys,
  binaries, company data, backups, or runtime storage.
- A documentation checkpoint describing `FAIL`/`PAUSED` may be committed and
  pushed despite an unfinished feature. That is not authorization to commit
  failing source as ready or mark `SOURCE_PASS`/`ACCEPTED`. Source changes/tests
  and operations still require the package scope and all existing gates.
- Before publication, verify the staged allowlist, full diff, secrets, and CI
  safety. Push only the authorized branch; never main/tag/release/deploy. After
  push, compare local/remote SHA and read the file at that SHA. Report missing
  synchronization as `LOCAL_ONLY`.
- Protect work-in-progress code separately: a roadmap checkpoint does not save
  uncommitted work. After a crash, first determine whether the prior operation
  completed and what it changed; never repeat a non-idempotent apply blindly.
- Never write `ACCEPTED` without actual owner acceptance. Every decision names
  the evaluated SHA, scope, and evidence; a later implementation change can
  invalidate only the applicable evidence, not the whole roadmap.
