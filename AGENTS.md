# AI-Lab repository rules

## Scope and architecture

- Treat `AI_LAB_MASTER_PLAN.txt` as the architectural source of truth and
  `CODEX_MASTER_EXECUTION.md` as the executable delivery plan.
- Work in one small, reviewable, testable chunk at a time. Update the execution
  plan after every completed chunk.
- Supported Flutter targets are Windows, Android, and Web. Do not restore iOS
  or macOS support.
- Preserve the public/private boundary: public gateway `127.0.0.1:8789` may
  expose Web/API/updates but never `/control`; private gateway
  `127.0.0.1:8788` may proxy `/control` to supervisor `127.0.0.1:8787`.

## Safety

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
