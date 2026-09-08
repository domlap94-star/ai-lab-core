# NEXT Stabil restore runbook

This runbook covers legacy `NEXT_STABIL_BACKUP_V1` checkpoints and the additive
`NEXT_STABIL_BACKUP_V2` recovery-point capture contract. A production restore
is destructive and requires an explicit human gate. Always restore to an
isolated target first.

## Recovery-point V2 capture (no restore)

`RecoveryPointV2` is an explicitly selected mode; existing schedules continue
to use `LegacyV1`. The V2 writer requires exactly both
`ai_lab_document_chunks` and `ai_lab_knowledge_base_chunks`, records each
snapshot as a separate artifact, aliases and observed vector configuration,
and requires a bounded `NEXT_STABIL_RUNTIME_INVENTORY_V1` JSON whose
`contains_secret_values` is `false`. Tool identity is read from the Git root
containing the invoked script. `RepositoryRoot` identifies data/config source;
it never changes which helper files execute.

Current V2 captures additionally carry
`storage_contract_version = NEXT_STABIL_STORAGE_COVERAGE_V1`. The writer
archives exactly `documents`, `document-pages`, `document-assets`,
`archive-extracted` and `knowledge-base`. Before any checkpoint write it reads
all persistent `knowledge_base_items` references in a bounded read-only
transaction and verifies that every source stays under the KB root and matches
its recorded size and SHA-256. It repeats the inventory around the storage
archive and refuses to finalize a manifest if the reference or file set moves.
An empty KB corpus is accepted only after a successful zero-row inventory and
is recorded as `EMPTY_CONFIRMED`.

Before capture, choose a new UTC checkpoint ID, verify the directory does not
exist, check the applicable free-space and operational gates, and independently
review the runtime inventory for secret values. A representative command is:

```powershell
& "C:\ai-lab-core-recovery\operations\hardening\backup-production.ps1" `
  -RepositoryRoot "C:\ai-lab-core" `
  -BackupRoot "E:\ai-lab-backup" `
  -Release "<version from the active stable manifest>" `
  -ManifestFormat RecoveryPointV2 `
  -QdrantProofMode CaptureOnly `
  -QdrantCollections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") `
  -CheckpointId "<YYYYMMDDTHHMMSSZ>" `
  -RuntimeInventoryPath "<reviewed non-secret runtime inventory JSON>"
```

This mode performs structural validation and writes hashes, collection/source
mapping and component capture windows. It deliberately records:

- `restore_status = NOT_RUN_WAITING_APPROVAL`;
- `escrow_status = NOT_RUN_WAITING_OWNER_DECISION`;
- `rto_status = NOT_MEASURED`;
- a non-transactional cross-component consistency limitation.

It does not invoke `verify-qdrant-snapshot-restore.ps1` and does not set
`qdrant_restore_verified=true`. Absence of either required collection,
duplicate mapping, invalid structure/hash, interrupted capture or an existing
target prevents the final manifest. Older V1-only readers refuse V2 as an
unsupported format; they do not reinterpret it as a single-collection backup.
Use the shared `restore-checkpoint.ps1 -ValidateOnly` reader for V2 integrity.
Historical V2 manifests created before the storage coverage contract remain
readable in their recorded four-directory scope, but the reader reports
`storage_coverage_status=NOT_RECORDED`, keeps `capture_complete=false` for the
current full contract and will not run a Full proof from that narrower capture.

An isolated V2 proof remains a separate owner-approved operation. It requires
an explicit PostgreSQL container, owner label, pinned client image and test
state directory. The target must be on one owned internal network, have no host
ports, bind mounts, Docker socket or privileged mode, and use an owned named
volume. Qdrant proof creates collision-checked resources derived from the
approved operation ID and likewise exposes no host port. Never point proof at
the production `postgres` container. The R03 A1 synthetic invocation is
captured by `operations/recovery/test-r03-a1-recovery-tools.ps1`; company data
must not be supplied without the separate drill approval.

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

Required V1 artifacts:

- `postgres.dump`: PostgreSQL custom-format logical dump;
- `document-storage.tar.gz`: `documents`, `document-pages`,
  `document-assets`, and `archive-extracted`;
- `qdrant.snapshot`: official collection snapshot;
- `n8n-workflows.json` and `n8n-credentials.encrypted.json`;
- `release-stable.tar.gz` and `configuration.tar.gz`.

Current V2 additionally requires `knowledge-base` in the storage archive,
`runtime-inventory.json`, an explicit storage coverage record and two
separately named Qdrant snapshot artifacts bound by `qdrant_collections` in the
manifest. Historical V1 and pre-A3 V2 checkpoints retain their narrower scope;
validation success for those bytes does not prove current KB-source coverage.

The checkpoint does not copy `.env`. Credential recovery therefore also
requires the separately protected environment-secret escrow. Never commit or
print it. Verify every artifact against the manifest before restore.

## Recovery order

1. Restore the supported Windows/WSL2/Docker Desktop host.
2. Check out the recorded source HEAD and verify the pinned image digests.
3. Restore the protected environment-secret escrow outside Git.
4. Start an empty pinned PostgreSQL and restore `postgres.dump` with
   `pg_restore --no-owner --exit-on-error`.
5. Restore the storage archive, including KB source files when declared by its
   coverage contract, to a new empty data root; do not overlay a partially
   running tree.
6. Verify Alembic head, counts, PK/FK integrity, storage paths and checksums,
   including every restored `knowledge_base_items.storage_path` source.
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

## EMERGENCY RESTORE — OPERATOR COMMAND

The canonical interface is Windows PowerShell 5.1:

```powershell
& "C:\ai-lab-core\operations\recovery\NEXT-Stabil-Recovery.ps1"
```

This opens the standard Windows checkpoint-folder picker. Validation does not
require elevation. A production restore requires PowerShell started with **Run
as administrator** and remains blocked without the separate
`FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED` operational approval.

Explicit Database proof:

```powershell
& "C:\ai-lab-core\operations\recovery\NEXT-Stabil-Recovery.ps1" `
  -CheckpointPath "C:\PATH\TO\BACKUP" -Mode Database -ProofOnly -NonInteractive
```

Explicit Full proof:

```powershell
& "C:\ai-lab-core\operations\recovery\NEXT-Stabil-Recovery.ps1" `
  -CheckpointPath "C:\PATH\TO\BACKUP" -Mode Full -ProofOnly -NonInteractive
```

Read-only validation:

```powershell
& "C:\ai-lab-core\operations\recovery\NEXT-Stabil-Recovery.ps1" `
  -CheckpointPath "C:\PATH\TO\BACKUP" -ValidateOnly -NonInteractive
```

Do not add `-ExecutionPolicy Bypass` to the normal operator command. The current
host accepts the tracked script under its existing PowerShell policy. The
wrapper verifies `operations/recovery/recovery-tool-manifest.json` before use,
then delegates all validation and staging to the shared
`restore-checkpoint.ps1` engine. It never queries backend auth, `backup_runs`,
`restore_runs` or `backup_schedules`.

Database proof restores only to `ai_lab_restore_test_*`. Full proof additionally
extracts archives to temporary staging and restores Qdrant to a temporary named
volume/non-production port. Any non-proof execution remains fail-closed before
service stop or live mutation with `production_restore_approval_required`.

The earlier source under `tools/windows-disaster-recovery` is retained as
**DEFERRED / ENTERPRISE TRUST BLOCKED**. It is not the canonical emergency
interface and should not be built during routine recovery validation.
