# FOLLOW-UP CHUNK 15 — Qdrant Restore Diagnosis

Date: 2026-08-21

Status: `FOLLOWUP_CHUNK15_QDRANT_RESTORE_BLOCKED`

## Scope and safety

The audit used one fresh official production collection snapshot, read-only
collection checks, isolated Qdrant containers/volumes and synthetic control
data. It did not delete or update production points, change the collection,
upgrade Qdrant or perform a production restore.

## Production source

- Qdrant: `1.18.3`, build `db8fa43f`.
- Collection: `ai_lab_document_chunks`.
- Points before/after snapshot: `57 / 57`.
- Vector configuration: `1024`, `Cosine`.
- Storage: Windows bind mount `C:\ai-lab-core\data\qdrant` to
  `/qdrant/storage`.

The canonical backup script already uses the supported collection snapshot
API:

1. `POST /collections/ai_lab_document_chunks/snapshots`,
2. download through
   `GET /collections/ai_lab_document_chunks/snapshots/{snapshot_name}`.

Fresh snapshot:

- name:
  `ai_lab_document_chunks-1085445014110947-2026-08-21-13-12-01.snapshot`,
- size: `348376576` bytes,
- SHA-256:
  `80a9be68521b20f479d75d04bbfbf949c75cd79e3a24695f7decc6aa2958d999`.

## Exact failure

The live file
`/qdrant/storage/collections/ai_lab_document_chunks/0/wal/first-index` is 15
bytes of valid JSON:

`{"ack_index":5}`

The same `0/wal/first-index` entry in the fresh official snapshot is 15 NUL
bytes. Official multipart recovery:

`POST /collections/ai_lab_restore_test_document_chunks/snapshots/upload?priority=snapshot`

on a separate exact-image Qdrant 1.18.3 container fails with:

`Wal error: Can't init WAL: failed to read first-index file ... expected value at line 1 column 1`

No production collection or volume was mounted into the recovery container.

## Control proof

A synthetic collection was created in a temporary exact-version Qdrant 1.18.3
container backed by a Docker named volume. Its official snapshot was uploaded
to a second clean exact-version container through the same multipart recovery
endpoint.

- snapshot size: `119808` bytes,
- restored points: `1/1`,
- restored vector configuration: `4`, `Cosine`,
- payload identity: preserved,
- temporary containers and volumes: removed.

This proves the selected recovery endpoint and isolated topology work. The
production snapshot artifact is already corrupt before recovery.

## Classification and gate

Root-cause classification: `SNAPSHOT_CORRUPT_AT_SOURCE`.

The evidence is consistent with Qdrant 1.18.3 snapshot creation over the
current Windows bind-mounted storage, but it does not yet prove that a newer
production version is the required remedy. No production version change is
authorized.

Until a supported fix is approved and proven:

- Database restore candidates remain eligible independently,
- Full/System restore candidates are fail-closed,
- the UI reports that Qdrant restore verification is missing,
- production restore remains separately gated,
- no raw-storage fallback is silently substituted for Full restore.

Smallest next decision: approve a bounded infrastructure/remediation design
for reliable Qdrant snapshot creation (for example, separately proven storage
topology or an approved version test). Any production Qdrant upgrade requires
`FOLLOWUP_QDRANT_RESTORE_UPGRADE_APPROVAL_REQUIRED`.
