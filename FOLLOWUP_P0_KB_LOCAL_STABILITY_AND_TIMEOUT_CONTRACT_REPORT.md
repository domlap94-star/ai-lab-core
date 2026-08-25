# P0 KB local stability and timeout contract

Date: 2026-08-25

Source baseline: `6d5401553f6b68db99f465875e806222e137b431`

Stable: `NEXT Stabil 1.0.2+29`

## Forensics

The named `fundamentowanie` item was retrieved and bound correctly. External
use remained blocked because KB has no per-item sensitivity classification;
that privacy behavior is correct and unchanged.

The pre-change live backend failed 3/3 bounded exact-item repetitions as HTTP
200 `review_required/knowledge_base_local_only`, with zero accepted claims or
sources, at 118.49, 47.21 and 48.46 seconds. The old branch discarded its
validator reason before returning the generic state, so a narrower historical
raw-output class cannot be reconstructed honestly. Source proof found one
stochastic generation, no representation repair, then the generic fallback.
A synthetic case reproduces `hypothesis_contract` and proves one bounded
representation correction can repair it without changing evidence.

Recent backend logs contain long Assistant requests ending in 503. Together
with the source contract (120-second generation versus 130-second Flutter
receive deadline), this proves the physical document error was analysis-
deadline/cleanup behavior, not loss of network connectivity.

## Fix

- Exact named-KB overview now uses a deterministic extractive fast path over
  ranked original KB page excerpts. It creates no facts, invokes no generator
  or external analysis, preserves page Sources and passes the normal validator.
- The model fallback retains exactly one representation-only correction. It
  cannot add facts, sources or general knowledge and is not used for timeout,
  retrieval, integrity or privacy failures.
- The accepted local KB analysis artifact was audited but not introduced as a
  second truth source; original pages remain canonical.
- Evidence-grounded local work has one 105-second total hard budget, including
  correction. Expected expiry returns HTTP 200, `timed_out`, stage
  `local_analysis_timeout`, and a bounded Polish message.
- Android waits 160 seconds, leaving 55 seconds for bounded unload/response.
  Connection error, connection timeout, send timeout and receive timeout now
  have different messages. Unified Assistant specializes receive timeout as a
  local-analysis deadline.
- Cancel aborts the local Dio request and clears result binding before any
  best-effort durable Advanced cancellation, so the composer recovers promptly
  and stale results cannot bind.
- Descriptive Client document discovery is bounded to that Client. Filename,
  metadata and optional address tokens select only a unique match; ties are
  ambiguous and address tokens never enter model evidence.

## Repeatability and runtime

The final service-level exact-query gate is 10/10 `accepted_local`, with zero
model calls, wrong sources, external jobs or privacy failures. Live probes were
bounded by the execution safety reviewer to five across iterative post-fix
states. Transitional builds returned correct terminal timeouts at 106.23,
106.26 and 106.24 seconds. The final deterministic runtime returned HTTP 200
`accepted_local` twice, with two claims and two KB sources, in 0.84 and 0.79
seconds (p50 0.815; bounded p95 0.84). No KB text is recorded here.

Backend was actually restarted. Supervisor source did not change and was not
restarted. Backend health is `ok`; public ingress guard passes and `/control`
remains 404. Only `qwen3-embedding:0.6b` remained resident.

## Verification

- focused KB/Unified/document: 141/141 PASS;
- broader non-mutating Unified/V2/Advanced: 166/166 PASS;
- final KB/Unified/contract: 140/140 PASS;
- Flutter analyze: PASS;
- focused Assistant/error/cancel: 6/6 PASS;
- inspection timeout: 7/7 PASS;
- full Flutter: 305/305 PASS;
- saved affected F0 remains 88.03 overall, 94.50% factual/evidence, wrong
  source 0 and privacy failures 0.

## Android and safety

Flutter changed, so +37 is superseded. Non-stable candidate:

- `C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+38-kb-timeout-hotfix.apk`
- version `1.0.2+38`, application ID `pl.ailab.app`;
- SHA-256 `02DF6A8F72C664CDE36FF8A860133CFC200B1BC5BBCE38D33027D40AF9DF84E1`;
- signer SHA-256 `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`;
- release non-debuggable, cleartext disabled, published: no.

DB migrations, business/Client/Document/KB writes, Qdrant writes/deletes,
external KB jobs, Gmail, n8n, model downloads/deletes, backup deletion,
Tailscale changes and publication are all zero.

Status: `SOURCE/RUNTIME PASS / OWNER PHYSICAL RETEST REQUIRED`. PRE-CHUNK23
remains physical acceptance required. CHUNK23 remains blocked/not started.
Release F Ignore Mail address/domain reminder remains unchanged.
