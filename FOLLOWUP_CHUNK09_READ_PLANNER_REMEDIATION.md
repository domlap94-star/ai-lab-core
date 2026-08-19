# FOLLOW-UP CHUNK 09 — READ PLANNER REMEDIATION

Date: 2026-08-19

Source baseline: `b2621f6902fd016abfd398e2b4302391577e42c1`

Production DB revision: `followup_mail_read_index_supersession_20260819`

Decision: `FOLLOWUP_CHUNK09_QUERY_ARCHITECTURE_BLOCKED`

## Approved production outcome

Approval was applied through revision
`followup_mail_read_index_supersession_20260819`. The upgrade used
`DROP INDEX CONCURRENTLY` in an Alembic autocommit block and removed only the
legacy read-state index. The ordered replacement remained valid/ready; waiting
locks were zero and backend health remained HTTP 200. The exact plan improved
from 18,527.250 ms with a 4,242-row top-N sort to 348.775 ms without a sort and
then 102–111 ms warm. Downgrade recreates the exact historical expression index
concurrently.

The common `read` query passed, but Stage 1 did not. A strict audit found one
Gmail source without a labels array. The historical expression used by the
ordered index classifies that missing value as `read`; a semantically correct
`unknown` filter took 13,364 ms. The unaccepted API/UI prototype was removed.
Current decision is `FOLLOWUP_CHUNK09_QUERY_ARCHITECTURE_BLOCKED`; a corrected
online nullable read-state index or separately approved canonical projection
is required before Stage 1 can continue. CHUNK 10 and release remain stopped.

## Scope and safety

This was an isolated planner experiment only. The fresh target database was
`ai_lab_chunk09_planner_20260819`; `SELECT current_database()` verified that
identity before the experiment and before the test-only index drop. Production
database `ai_lab` received no DDL or data write.

The full-size clone contained 4,262 non-deleted Gmail sources / 6,984 total
CandidateSource rows and both current indexes. `ANALYZE candidate_sources` was
required after restore to reproduce production statistics and planner choice.

## Exact baseline

The intended GlobalMailService ID-page query filters the canonical read-state
expression to `read`, orders by canonical message time descending and source ID
descending, and limits the page to 50.

After `ANALYZE`, PostgreSQL selected
`ix_candidate_sources_gmail_read_state`, scanned 4,242 matching rows and
performed a top-N heapsort (28 KiB). It used 567,604 shared-buffer hits and
65,419 reads; the legacy index scan itself accounted for 567,598 hits and
65,419 reads. Execution time was 17,907.796 ms. The large buffer footprint is
consistent with repeated heap/TOAST JSON access needed to calculate message
time after selecting by the single expression index.

## Isolated supersession experiment

Only `ix_candidate_sources_gmail_read_state` was dropped on the isolated
clone. The normal test-only drop completed in approximately 20.3 ms. The
ordered `ix_candidate_sources_gmail_read_time`, message-time, search,
direction and received/time indexes remained present.

After a new `ANALYZE`, the exact query selected
`ix_candidate_sources_gmail_read_time`, scanned only the bounded ordered rows,
required no sort and completed in 87.232 ms with 10,884 shared-buffer hits.

The first 200 ordered IDs (four normal pages) were captured before and after:

- ID-set mismatches: 0;
- position/order mismatches: 0;
- before/after counts: 200 / 200.

Therefore removal changes only planner choice, not result semantics or stable
ordering.

## Regression matrix after isolated removal

- `read LIMIT 50`: 87.232 ms, ordered read/time index;
- `unread LIMIT 50`: 29.990 ms, 20 rows, ordered read/time index;
- nullable/unknown read state: 0.039 ms, 0 rows, ordered read/time index;
- latest 50: 132.239 ms, canonical message-time index;
- received 50: 205.964 ms, received/time index;
- sent/outgoing 50: 2,878.154 ms, direction index plus bounded sort.

All measured queries remained below the 10-second UI timeout. The common read
query is comfortably below the preferred two-second target.

## Dependency audit

The exact index name appears only in its historical Alembic create/drop
revision and the CHUNK 09 evidence documentation. PostgreSQL `pg_depend`
reported zero dependent objects. No query hint, operational script or runtime
code assumes the index exists. The ordered replacement index is valid and
ready.

## Proposed production operation

Index to supersede: `ix_candidate_sources_gmail_read_state`.

Production method, only after approval:

`DROP INDEX CONCURRENTLY IF EXISTS ix_candidate_sources_gmail_read_state`

This must run outside a normal transaction using an Alembic autocommit block.
Concurrent drop avoids blocking normal reads/writes, but may briefly acquire
catalog/relation locks and may wait for old transactions. Pre-flight must
check health, waiting locks and long transactions; no session may be killed
without separate approval.

Rollback is to recreate the exact prior partial expression index with
`CREATE INDEX CONCURRENTLY`, using `READ_STATE_SQL` and the Gmail/non-deleted
predicate from `followup_mail_query_indexes_20260819.py`, then verify
`indisvalid` and `indisready` and rerun the query matrix.

No production operation was performed in this diagnosis. Global Mail API/UI,
CHUNK 10, email sending and release remain stopped.
