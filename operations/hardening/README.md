# Production hardening operations

This directory contains non-destructive operational checks for NEXT Stabil.
They do not install services, change firewall/Tailscale, purge data, rotate
credentials or change the release minimum version.

## Commands

- `backup-production.ps1`: creates a protected, versioned checkpoint outside
  the repository. It never overwrites an older checkpoint and writes the
  manifest only after every artifact and SHA-256 succeeds.
- `check-production-health.ps1`: aggregates local/private service health,
  migration revision, DB locks, stale Agent/Vision state, disk capacity and
  backup freshness without exposing secrets or internal content.
- `RESTORE_RUNBOOK.md`: recovery order, isolated drill evidence and abort
  rules.
- `VISION_WORKER_RUNBOOK.md` and `AGENT_OPERATOR_RUNBOOK.md`: bounded operator
  response procedures.

## Monitoring baseline

Run the health check after host/stack restart, after a release, and at least
daily. Treat a failed backend, DB, Qdrant, Ollama, n8n, supervisor or migration
check as an incident. `AUTH_REQUIRED` and `UI_CHANGED` are explicit Vision
pause states rather than generic crashes. Warnings cover stale jobs, orphaned
Agent audits and low disk.

Disk thresholds are 20 GiB minimum free by default. Operational alerting
should also warn at 15% free on the system/data/backup volumes. No production
file is automatically deleted by this check.

There is no external notification integration in CHUNK 17. Adding email,
Teams, Slack or another channel requires a separate approval and credential
scope.

## Retention policy

- Vision spool: terminal jobs are eligible after 72 hours; active jobs and
  originals are excluded by canonical path and state checks.
- Docker JSON logs: recreated production containers use 10 MiB x 5 files.
  Services were recreated individually without removing volumes, and their
  image IDs, mounts, ports and health were reverified after each step.
- Agent audit: persistent; no automatic deletion policy is authorized.
- n8n executions: existing history is preserved. No destructive pruning was
  enabled in this chunk.
- Backups: proposed policy is 7 daily, 5 weekly and 12 monthly checkpoints.
  No automatic purge or Scheduled Task is installed. A scheduler and any
  destructive retention require separate approvals.

## Startup and recovery readiness

Docker Desktop, Compose, supervisor and both gateways already have dedicated
Windows Scheduled Tasks. The Compose task waits for Docker and then backend
health. The Vision worker is on-demand and does not require a persistent
browser process. Host reboot was not performed during CHUNK 17; a reboot proof
requires `CHUNK17_HOST_REBOOT_APPROVAL_REQUIRED`.

## Security baseline

All service ports (PostgreSQL 5432, n8n 5678, Qdrant 6333/6334, backend 8000,
Ollama 11434, Open WebUI 3000 and supervisor 8787) bind to `127.0.0.1`.
Public/private gateways retain their 8789/8788 boundary and public `/control`
must remain unavailable. CORS uses an explicit origin list from configuration;
secret values are never emitted by these scripts.

Document uploads are bounded at 250 MiB. ZIP extraction is bounded to 500
members, 250 MiB per member, 2 GiB total and a 500x compression ratio, with
canonical path enforcement. PDF/OCR processing is bounded to 250 pages,
72–300 DPI and 60 seconds per Tesseract page. Vision has a single worker and
maximum eight automatically selected pages. Agent and other AI contexts keep
their existing explicit evidence/call/time limits.

Security headers remain an audited deployment gap: CSP must not be introduced
without Flutter Web compatibility testing, and any change to public HSTS/frame
policy requires `CHUNK17_PUBLIC_SECURITY_CHANGE_APPROVAL_REQUIRED`.

## Release compatibility

The stable manifest remains 1.0.2+21 with `minimum_version` 1.0.0. The decision
engine semantics are:

- version older than minimum: required update;
- supported older version/build: optional update available;
- current version/build: no update;
- malformed manifest: rejected with a friendly update-check failure;
- network failure: existing app remains usable and no fabricated update is
  installed.

Never raise `minimum_version`, republish artifacts or repoint the stable
channel as part of an operational health check.
