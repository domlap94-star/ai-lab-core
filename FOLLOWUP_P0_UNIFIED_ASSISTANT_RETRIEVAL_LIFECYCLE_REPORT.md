# P0 Unified Assistant Retrieval + Advanced Lifecycle Report

Date: 2026-08-25

GitHub baseline: `89405c9ed3a1c5657e32cae10cda746efb390640`

Stable: `NEXT Stabil 1.0.2+29`
Decision: `SOURCE PASS / PHYSICAL RETEST REQUIRED`

## Preserved Android connectivity work

The bounded uncommitted +34 release-configuration/auth diagnostics were
preserved. Owner physical evidence establishes:

- explicit API: `https://domai.tail1927bd.ts.net`;
- application `/health`: HTTP 200;
- retained `/api/v1/auth/me`: HTTP 401 / expired session;
- fresh login and Dashboard: PASS.

The connectivity P0 is resolved. +33's generic connection error conflated an
HTTP authentication disposition with transport failure.

## Physical failure and forensic limits

The failing class was a Client-scoped natural-language request naming one PDF
and asking for technical interpretation and plausible localized-settlement
causes. The owner observed at least approximately six minutes of waiting and a
terminal response saying the PDF was unavailable to the Assistant even though
it was assigned to the Client. The response repeated unnecessary identity/
location context.

Read-only production metadata showed no durable `AnalysisJob` corresponding to
the physical request; the latest rows were older sanitized qualification jobs.
Broad backend logs were deliberately not exported because they may contain
customer content. Therefore request/job/source IDs and T0–T11 timestamps are
`NOT OBSERVED`; no fabricated timeline is reported.

Primary stall classification: `LOCAL_MODEL`.

Evidence: the request could spend up to the old six-minute Dio receive timeout
inside the initial synchronous local call, and no advanced job was persisted.
The UI could also display stale `Analiza rozszerzona` from a previous `result`
while a new first request was in progress. Secondary defects are deterministic
document routing, required-evidence/usefulness enforcement, PII minimization,
polling limits, resource residency, and cancel propagation.

## Root cause and retrieval repair

Before remediation, `_route()` searched Client documents only when a question
contained selected stems (`dokument`, `protok`, `instruk`, `norm`). Naming
`technical-report-001.pdf` alone was not a routing signal. `get_document_pages`
also selected the first eight pages and all page sources shared one route, so
page evidence could be deduplicated.

The implemented deterministic prerequisite now:

1. detects quoted/unquoted `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.csv`,
   `.txt`, `.jpg`, `.jpeg`, and `.png` references;
2. resolves only documents in the active Client scope using exact/casefolded/
   normalized and bounded unique matching;
3. returns `AMBIGUOUS`, `NOT_FOUND`, `UNAVAILABLE`, or `INVALID` before Qwen or
   Temporary Chat;
4. requires extracted document text or page/OCR content;
5. ranks pages by bounded query-term relevance and keeps page-specific routes;
6. requires the requested document source in `used_sources` and a material
   claim, otherwise returns `TASK_COMPLETION_FAIL` after one representation
   correction;
7. omits the Client identity source card for a selected technical document.

Retrieval failure is never converted into reasoning escalation. Cross-client
matches are not queried and cannot bind. Failure responses use only “wskazany
klient/dokument” and do not repeat name, address, email, phone, or tax IDs.

## Advanced lifecycle and cancellation

Compatibility DB statuses remain unchanged. The additive response exposes a
bounded equivalent stage plus `last_progress_at`, `can_cancel`, and delayed
state. Queue hard limit is 60 seconds; external worker hard limit is 180
seconds; Flutter stops after 185 seconds of advanced polling and requests
backend cancellation. The existing worker's selector/response loops already
have hard deadlines.

`POST /api/v1/ai/assistant/{request_id}/cancel` is authenticated and ownership-
bound. It cancels the exact private Supervisor job, records terminal
`cancelled`, stops Flutter polling, and restores the composer. A new client
`attempt_id` changes the request/analysis ID on retry. Cancelled/timed-out
database states cannot be overwritten by a late result, and Supervisor V2
still binds exact job/request/contract and rejects stale artifacts.

Qwen `qwen3.5:9b` is explicitly unloaded before a long external wait because
post-validation is deterministic. The accepted hardware report measured its
4096 allocation at about 5.795 GiB and unload below one second. Current
read-only telemetry after the incident showed only
`qwen3-embedding:0.6b` resident (2.4 GB, CPU) and WSL MemAvailable about 13.66
GiB with 0/8 GiB swap used.

Owner-observed incident telemetry remains approximate: host CPU ~66%, host RAM
~86%, vmmemWSL ~9.3 GB and ~52.6% CPU, Java ~2.5 GB. Classification: high
resource pressure; no proven OOM or swap thrash.

## Verification

- Python syntax compilation: PASS.
- Focused Unified Assistant + V2 contract suite: 31/31 PASS.
- Supervisor analysis queue/V2/recovery/idempotency/failure tests: PASS.
- New worker timeout/cancel test: PASS.
- Vision worker contract: PASS.
- Flutter analyze: PASS, zero issues.
- Focused Unified Assistant widget tests including backend cancel: 3/3 PASS.
- Full Flutter suite: 303/303 PASS.
- Saved-output immutable 50-case replay: 35 local accepted / 15 retained for
  qualified advanced handling; accepted-local overall 88.00,
  factual/evidence 100.00%, technical-documentation 97.37, hard failures 0,
  wrong sources 0, privacy failures 0. No new external call was made.
- One broader legacy Agent test selection could not start its synthetic DB
  because no ephemeral PostgreSQL service was attached; this was an
  environment setup failure, not a product assertion. All 32 DB-independent
  tests in that combined run passed.

No synthetic external Temporary Chat jobs were required. Consequently no new
external timing percentile is claimed. Hard timeout/cancel were verified
deterministically; physical latency remains an owner retest gate.

## Production safety

Business/Client/Candidate writes: 0. DB migrations: 0. Qdrant writes/deletes:
0/0. Gmail: 0. n8n: 0. model pulls/deletes: 0. resource-limit changes: 0.
Real-customer Temporary Chat/Vision jobs: 0 new. Backup deletes: 0. Stable
publication: 0.

The Release F Ignore-mail address/domain UI reminder remains mandatory and was
not implemented.

## Remaining gate

Owner physical retest must repeat the named Client PDF analysis, prove actual
page evidence and Sources, observe bounded latency/PII behavior, and cancel a
controlled advanced synthetic job. PRE-CHUNK23 remains incomplete and CHUNK23
remains blocked.

## Final physical-retest candidate

The first post-fix build, versionCode 35, was produced before the final
new-request stale-result reset and is therefore consumed/superseded. It was
not handed off as the final source artifact and was not overwritten.

The exact final source was built through the canonical Android release script
as the non-stable physical-retest candidate:

`C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+36-unified-assistant-retrieval-hotfix-candidate.apk`

- versionName/versionCode: `1.0.2` / `36`;
- application ID: `pl.ailab.app`;
- bytes: `67,398,747`;
- SHA-256: `3C9229AE5191FD8156EDD7198151A382A5C59862BFA8B7C05DBF93E8D7AABE36`;
- signer SHA-256: `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`;
- debuggable: false/absent;
- cleartext traffic: false;
- explicit API input: `https://domai.tail1927bd.ts.net`;
- published: no.

The final post-reset Flutter analyze and focused widget suite passed again
(3/3). No physical PASS is inferred from the source or artifact checks.
