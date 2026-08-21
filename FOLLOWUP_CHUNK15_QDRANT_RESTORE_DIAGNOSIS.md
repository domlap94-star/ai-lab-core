# FOLLOW-UP CHUNK 15 — Qdrant Snapshot Remediation Diagnosis

Date: 2026-08-21

Status: `PRODUCTION_STORAGE_REMEDIATION_COMPLETE`

Remaining gates: `FOLLOWUP_BACKUP_SCHEDULER_CHANGE_APPROVAL_REQUIRED`,
`FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED`

## Scope and safety

The investigation used Qdrant `1.18.3` at the exact pinned production image
digest, isolated test-only ports, collections, containers, host directories and
Docker volumes. Production was limited to read-only health/config/count/log
checks. No production point, collection, storage mount, image, scheduler or
restore target was changed.

## Production baseline

- Image: `qdrant/qdrant@sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286`.
- Version/build: `1.18.3` / `db8fa43f`.
- Collection: `ai_lab_document_chunks`.
- Vector configuration: `1024`, `Cosine`.
- Points before/after: `57 / 57`.
- Storage: Windows bind mount `C:\ai-lab-core\data\qdrant` to
  `/qdrant/storage`.
- Storage footprint at audit: `348330230` bytes in `89` files.

The canonical script uses the official collection snapshot API: create with
`POST /collections/{collection}/snapshots`, then download with
`GET /collections/{collection}/snapshots/{name}`. The previously captured
fresh production artifact is byte/hash-valid but contains fifteen NUL bytes in
`0/wal/first-index`; official recovery fails while reading that WAL metadata.

## Controlled topology matrix

The two sources used identical Qdrant image/version, `1024`-dimensional Cosine
vectors, 400 deterministic synthetic points/payloads, one-MiB WAL capacity and
the same official snapshot API.

| Topology | Snapshot WAL result | Official restore | Result |
| --- | --- | --- | --- |
| Docker named volume | no `first-index` entry was required | HTTP 200; 400/400 points | PASS |
| Windows bind mount | snapshot creation failed while archiving missing `closed-0` | no valid artifact to restore | FAIL |
| stopped bind storage copied to named volume | valid 15-byte `{"ack_index":4}` | HTTP 200; 400/400 points | PASS |

The bind source itself remained readable with 400/400 points before the stop.
Qdrant returned HTTP 500 from the official snapshot creation path with:

`Error while archiving WAL: No such file or directory ... 0/wal/closed-0`

This is a second deterministic bind-mount failure mode in addition to the
production NUL-filled `first-index`. The named-volume control passed on the
same version and data, so a version-wide Qdrant 1.18.3 restore defect is not
proven. The differing variable is the Docker storage topology.

## Stopped-storage migration and rollback proof

An isolated bind-backed source was cleanly stopped. Its complete storage was
copied read-only into a new Docker named volume. The same pinned Qdrant image
started from that copy and preserved:

- 400/400 points,
- vector size `1024` and distance `Cosine`,
- representative IDs and payload markers.

It then created an official snapshot with valid WAL metadata. A second clean
named-volume container restored the snapshot and returned the same count,
configuration, IDs and payload markers. Finally, the migrated container was
stopped and the untouched bind-backed source was restarted; its 400 points and
payload proof were still intact. This proves both the migration mechanism and
the rollback direction in isolation.

## Root cause

Classification: `WINDOWS_BIND_MOUNT_SNAPSHOT_DEFECT_CONFIRMED`.

The production-specific WAL history affects the visible symptom (NUL
`first-index` versus missing `closed-0`), but is not required to make snapshot
creation fail. Concurrent application writes are not supported as the cause:
the production logs around the fresh snapshot show reads and the snapshot
request, not point mutations, while the controlled bind failure is reproducible
with the test source otherwise idle.

## Early validation

`qdrant_snapshot_validator.js` now performs a lightweight, bounded structural
check before Full restore eligibility:

- archive must be readable and contain safe paths,
- `config.json`, `version.info` and shard metadata must exist,
- every present `wal/first-index` must be non-empty, non-NUL JSON with a
  non-negative integer `ack_index`.

An absent `first-index` is valid because official healthy snapshots can omit it
when no closed WAL metadata is required. This check is not presented as a
restore proof. The manifest/discovery contract distinguishes:

- `artifact_hash_verified`,
- `qdrant_snapshot_structurally_valid`,
- `qdrant_restore_verified`.

Known historical corrupt artifacts are retained and dynamically classified as
`qdrant_snapshot_invalid`; Database restore remains independently eligible,
while Full/System restore remains unavailable for those specific checkpoints.
New checkpoints become Full-eligible only after their own structural and
isolated restore-drill verification passes.

## Executed production topology change

The owner-approved target is now active: Docker-managed Linux named volume
`qdrant_storage`, using the same pinned Qdrant image.

Conceptual Compose change:

```yaml
services:
  qdrant:
    volumes:
      - qdrant_storage:/qdrant/storage

volumes:
  qdrant_storage:
    name: qdrant_storage
```

The stopped source was copied in full and verified by file count, aggregate
bytes and per-file SHA-256 before startup. Production then passed 57-point,
`1024`/`Cosine`, representative-payload and backend read checks. The original
`C:\ai-lab-core\data\qdrant` source remains retained and untouched as the
rollback asset.

## Approved-change procedure (executed and accepted)

1. Verify the exact image digest, collection config, 57-point count, storage
   footprint, health and no running backup/purge operation.
2. Enter maintenance/write-quiescent mode and stop all Qdrant writers.
3. Stop Qdrant cleanly.
4. Retain `C:\ai-lab-core\data\qdrant` unchanged and capture its file inventory.
5. Create `qdrant_storage`; copy the stopped source into it through a testable,
   read-only source mount.
6. Change only the Qdrant mount and start the same pinned image.
7. Verify collection, `1024`/`Cosine`, exactly 57 points and representative
   canonical ownership payloads; verify backend reads.
8. Create/download/hash a fresh official snapshot, run structural validation,
   and restore it into a clean isolated Qdrant target.
9. Re-enable writers only after all validation passes.

Rollback on any failure: stop the named-volume Qdrant, restore the Compose
mount to the untouched Windows source, start the pinned image, and reverify
collection configuration and 57 points. Neither the old bind storage nor the
new volume is deleted during acceptance.

## Production acceptance evidence

- Image digest remained
  `sha256:0bd98fa7977f1e75694779359ca4e212822e5a71334e28421182f72f209d5286`.
- Production collection remained 57 points at `1024` dimensions / `Cosine`.
- Fresh official snapshot:
  `ai_lab_document_chunks-1085445014110947-2026-08-21-14-20-44.snapshot`,
  `348404224` bytes, SHA-256
  `7794a462b6bc2907f1694ec94d1c8377e901724e984b955225b4bedefdb01947`.
- Snapshot `0/wal/first-index` is valid `{"ack_index":5}` metadata.
- Clean isolated Qdrant `1.18.3` recovery returned HTTP 200 and preserved all
  57 points, configuration and representative ownership payloads.
- Full checkpoint `C:\ai-lab-core-backups\20260821T142509Z` records structural
  validation and restore-drill verification; isolated Full/System proof passed.

## Remaining gates

- Backup scheduler changes:
  `FOLLOWUP_BACKUP_SCHEDULER_CHANGE_APPROVAL_REQUIRED`.
- Any production restore:
  `FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED`.

No Qdrant upgrade or vector rebuild is recommended by the current evidence.
