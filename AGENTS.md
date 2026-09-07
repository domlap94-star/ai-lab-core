# AI-Lab repository rules

## Scope and architecture

- Treat `AI_LAB_MASTER_PLAN.txt` as the product specification,
  `AI_LAB_FOLLOWUP_PLAN.md` as its supplements, decisions, and safeguards, and
  `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md` as the sole execution order and
  resume state. Old roadmaps awaiting R01 consolidation are history, not an
  instruction to switch packages; do not remove them during R00.
- Work in one small, reviewable, testable chunk at a time. Update the execution
  plan after every completed chunk.
- Supported Flutter targets are Windows, Android, and Web. Do not restore iOS
  or macOS support.
- Preserve the public/private boundary: public gateway `127.0.0.1:8789` may
  expose Web/API/updates but never `/control`; private gateway
  `127.0.0.1:8788` may proxy `/control` to supervisor `127.0.0.1:8787`.

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
