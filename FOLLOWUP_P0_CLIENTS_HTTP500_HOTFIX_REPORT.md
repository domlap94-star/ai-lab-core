# P0 POST-CHUNK22 CLIENTS HTTP 500 HOTFIX

Date: 2026-08-24

Source HEAD before hotfix: `ce2a63412358506ac566287f54e6a6e9bc6d0779`

Stable: NEXT Stabil `1.0.2+29` (unchanged)

Production DB head: `followup_backup_planner_retention_20260824`

## Reproduction and exact failure

The Windows Clients page issues authenticated
`GET /api/v1/clients/page?sort_order=newest&skip=0&limit=50`. Direct backend
reproduction returned HTTP 500 with the bounded body `Internal Server Error`;
no request-ID response header was present. Backend logs identified
`pydantic_core.ValidationError` while constructing `ClientPage` at
`client_service.py` line 140. The failing projection was
`items.21.addresses.1`: `Address must contain at least one address field`.

The SQL SELECT and effective-date/workflow projections completed. The failure
was response serialization, not SQL execution or connection acquisition.
Default list, a search selecting an affected Client and that Client detail
failed; limit=1, Global Search and Dashboard activity remained available.

## Root cause

Production contains six active historical `client_addresses` relation rows
whose street/building/unit/postal/city fields are all empty. Their bounded
metadata identifies origin `other` and source type `candidate_merge`; their
business contents were not printed or modified.

The older candidate-merge implementation included `country_code` in its
substantive-address test. Because the default country is `PL`, a country-only
candidate was incorrectly treated as a real address and persisted. The Client
read property then exposed that unusable relation, while the existing
`ClientAddressRead` validator correctly rejected it.

This is not caused by CHUNK22 Backup code. Diff review from
`08f4f7adc59f0357ffffa3debe27cf35d11b64bc` to
`3efa5bf0a6dfb19daf9569c3464953b4c60d3b37` found no Client projection change,
request-scoped Session captured by the Supervisor verification worker, or DB
session crossing the background-job boundary. Closure commit `ce2a634...`
changed reports/roadmap only.

## Database and job evidence

- Alembic current/head: `followup_backup_planner_retention_20260824`; pending 0.
- PostgreSQL: active 1 (the audit), idle 5, idle-in-transaction 0, blocked 0,
  max connections 100.
- SQLAlchemy engine uses QueuePool defaults: size 5, overflow 10, timeout 30s.
- Audit connection returned to its pool; checked out after audit: 0.
- Active queued/running Backup runs: 0.
- Active queued/running Restore runs: 0.
- Pending/processing scheduler sync events: 0.
- Legacy checksum jobs live in the loopback Supervisor and own no SQLAlchemy
  Session. API status polling uses request-scoped sessions closed by `get_db`.

There is no pool-exhaustion or connection-leak evidence for this incident.

## Fix

The hotfix preserves all historical rows and business evidence. `Client.addresses`
now omits active relations lacking every substantive address field from read
projection. `CandidateMergeService._address_text` no longer treats country code
alone as address content, preventing new country-only relations.

No schema, migration, response shape, Client value or historical row changed.
The backend was restarted only after the exception and job/connection state
were captured so the mounted source fix became active.

## Acceptance

Authenticated read-only requests through both the backend and public gateway
now return 200 for Clients default, limit=1, deployed legacy list, affected
search, affected Client detail, Global Search and Dashboard activity. Backend
health, Backup managed catalog, legacy discovery and storage locations return
200.

Focused isolated tests pass: 31 Client/status/search/global-search/candidate-
merge/P0 projection cases, CHUNK7 contact/address, Contact Person API/search/
attribution/lifecycle, legacy adoption, Supervisor storage and verification
jobs. Security and API-auth regressions pass. Frontend source did not change,
so Flutter rerun was not required.

## Safety and roadmap

Business/Client writes, historical rewrites, DB migrations, Qdrant writes or
deletes, Gmail, n8n, backup deletions, AI/model changes and release publication
are all 0. CHUNK22 remains COMPLETE. The P0 is RESOLVED and PRE-CHUNK23 Unified
Assistant implementation may return to NEXT / AUTHORIZED TO PREPARE. CHUNK23
remains BLOCKED / NOT STARTED.
