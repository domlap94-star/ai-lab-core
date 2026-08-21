# NEXT Stabil restore runbook

This runbook covers the verified `NEXT_STABIL_BACKUP_V1` checkpoint for
NEXT Stabil 1.0.2+21. A production restore is destructive and requires an
explicit human gate. Always restore to an isolated target first.

## Pinned checkpoint

| Service | Verified version | Production image |
| --- | --- | --- |
| PostgreSQL | 17.10 | `postgres@sha256:a426e44bac0b759c95894d68e1a0ac03ecc20b619f498a91aae373bf06d8508d` |
| Qdrant | 1.18.3 | `qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286` |
| Ollama | 0.32.3 | `ollama/ollama@sha256:ec24bcaa2a810eb74171ce7c517813ef4821ed678988845e8d76cf62467036d4` |
| n8n | 2.31.6 | `docker.n8n.io/n8nio/n8n@sha256:3c07c723326dd72e46a6969181c66a75260b7a204b9b77ba1ece6d594489c684` |
| Open WebUI | revision `ecd48e2f...` | `ghcr.io/open-webui/open-webui@sha256:a26effeb220e132482bf7e0560b3404843e7bc40d23051144e062960df8df6b0` |
| Backend | Python 3.12.13 | local image `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`; base `python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36` |

Flutter is 3.44.8 / Dart 3.12.2. The Vision worker requires Node 24.18.0,
Playwright 1.62.1 and the Microsoft Edge channel. The supervisor uses the
same host Node runtime.

## Checkpoint contents and prerequisites

Run `backup-production.ps1` from PowerShell 5.1. It creates a timestamped,
non-overwriting directory outside the repository and active data tree. It
first checks free space, applies a restricted ACL, creates hashes, and writes
`backup-manifest.json` last.

Required artifacts:

- `postgres.dump`: PostgreSQL custom-format logical dump;
- `document-storage.tar.gz`: `documents`, `document-pages`,
  `document-assets`, and `archive-extracted`;
- `qdrant.snapshot`: official collection snapshot;
- `n8n-workflows.json` and `n8n-credentials.encrypted.json`;
- `release-stable.tar.gz` and `configuration.tar.gz`.

The checkpoint does not copy `.env`. Credential recovery therefore also
requires the separately protected environment-secret escrow. Never commit or
print it. Verify every artifact against the manifest before restore.

## Recovery order

1. Restore the supported Windows/WSL2/Docker Desktop host.
2. Check out the recorded source HEAD and verify the pinned image digests.
3. Restore the protected environment-secret escrow outside Git.
4. Start an empty pinned PostgreSQL and restore `postgres.dump` with
   `pg_restore --no-owner --exit-on-error`.
5. Restore the document archive to a new empty data root; do not overlay a
   partially running tree.
6. Verify Alembic head, counts, PK/FK integrity, storage paths and checksums.
7. Start the backend and verify `/health` before enabling ingestion.
8. Restore Qdrant only through a manifest-verified official snapshot whose
   structural check and isolated exact-version restore drill have passed. Do
   not improvise a live storage copy.
9. Restore n8n workflow/credential exports using the original protected
   encryption key. Keep workflows inactive until credential resolution and
   source idempotency are verified.
10. Restore Ollama model storage or re-provision the exact recorded model
    digests. Vision continues to use the Temporary Chat worker, not Ollama.
11. Start supervisor, private/public gateways and validate the Vision worker
    dedicated profile with a synthetic Temporary Chat smoke.
12. Restore the stable release channel and verify artifact hashes before
    re-enabling public traffic and ingestion.

## Verified isolated drill

The PostgreSQL dump was restored to an ephemeral PostgreSQL 17.10 `tmpfs`
container with no host port. Counts matched for users, clients, candidates,
documents, pages, assets, projects, inspections and Agent audits. Three
aggregate relation hashes matched production, PK uniqueness passed and no
unvalidated FK was found. Alembic had one head; downgrade from
`chunk16audit_20260819` to `chunk15vision_20260818` and re-upgrade passed.

The document archive was restored outside `/data`. All four directory counts
and byte totals matched. All 5,925 available document/asset checksums matched;
there were zero missing paths and zero path escapes. Twenty-nine files have no
current DB reference. They are an audit finding only and must not be removed
without the historical-cleanup approval flow.

The n8n workflow imported into an ephemeral SQLite instance without ports or
external source connections. It was deliberately deactivated by import.

The 2026-08-21 owner-approved storage remediation moved Qdrant from a Windows
bind mount to Docker-managed `qdrant_storage` without changing the pinned
1.18.3 image or the 57-point collection. A fresh official snapshot passed WAL
structural validation and official upload recovery into a clean isolated
same-version container. Recovery preserved 57 points, `1024` dimensions,
`Cosine` distance and representative ownership payloads. Full checkpoint
`20260821T142509Z` carries both structural and restore-drill verification. The
old bind source remains retained as a rollback asset.

## Migration and application rollback

Never downgrade production as a diagnostic action. On an isolated restored
DB, run `alembic heads`, `alembic current`, downgrade only to an explicitly
reviewed revision, then re-upgrade and repeat structural checks. Migrations
that drop audit or Vision columns can discard the data held in those columns;
application rollback across such a schema boundary is unsafe without a DB
restore plan.

Release rollback means repointing the stable manifest/Web deployment to a
previous known-good artifact only after verifying DB compatibility and with a
human release gate. Preserve the current artifacts and manifest first.

## Abort rules

Abort before production mutation if any hash differs, the DB revision is not
the recorded head, counts or FK checks differ, a storage path escapes its
root, secrets are unavailable, a required image digest cannot be obtained, or
the target is not demonstrably isolated. Never use `docker compose down -v`,
volume prune, or an in-place restore over running data.

## Standalone Recovery tool (PRE-CHUNK16)

Source lives under `tools/windows-disaster-recovery`. The portable native
WinForms tool reads a manually selected checkpoint folder and never queries
the backend, JWT/auth, `backup_runs`, `restore_runs` or `backup_schedules`.
It validates `NEXT_STABIL_BACKUP_V1`, relative artifact paths, exact sizes and
SHA-256, PostgreSQL custom-archive identity, compatibility metadata and Qdrant
WAL structure. Bundled helpers have a separate
`NEXT_STABIL_RECOVERY_TOOL_V1` hash manifest.

The shared `restore-checkpoint.ps1 -ProofOnly` engine is the only implemented
execution path in the development build. It proves PostgreSQL in
`ai_lab_restore_test_*`, stages archives outside active data and restores
Qdrant into a temporary named volume/non-production port. Any non-proof call
fails before service stop or live mutation with
`production_restore_approval_required`. A reviewed host-specific cutover
module requires the separate permanent operational gate; never interpret an
isolated PASS as authorization to overwrite production.
