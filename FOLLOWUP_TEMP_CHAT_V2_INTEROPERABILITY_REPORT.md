# PRE-CHUNK23 TEMPORARY CHAT V2 INTEROPERABILITY REPORT

Date: 2026-08-24

Source baseline: `02b2284176237a5b4f02a4d83e957d563f83bd02`

Stable release: NEXT Stabil `1.0.2+29` (unchanged)

Scope: exact 15 frozen F0 escalation cases; synthetic/public-safe only

## Verdict

The worker/Supervisor interoperability defect is repaired. All 15 primary
submissions emitted strict `NEXT_STABIL_TEMP_CHAT_RESULT_V2`, all 15 result
artifacts bound to the exact job/request/contract, and no format retry was
needed. V1, prose, malformed, stale, partial and mismatched artifacts continue
to fail closed. There is no V1 fallback for a V2-requested job.

F0 is **not yet declared end-to-end qualified**. The combined 50-case numerical
gates pass (94.80 overall, 94.50 factual/evidence, one hard-failure case, zero
wrong-source and privacy failures), but X04 proves that the bounded package
does not yet carry an opaque target-scope identity that distinguishes its two
same-type sources. The external result safely returned `MISSING`; it did not
bind the wrong source. This unresolved critical scope/semantic-completeness
defect prevents qualification under the owner's explicit rule. It is separate
from the now-passing V2 transport/binding layer.

## Root cause

The local request already carried `contract_version =
NEXT_STABIL_TEMP_CHAT_RESULT_V2` and a V2 requested-output description. The
browser worker then appended a later hard-coded V1-only final prompt, parsed
only V1, and used its one retry to demand V1 again. The dominant final worker
instruction—not prompt truncation—caused the legacy results.

Classification of the 12 historical legacy/unstructured results:

- V2 instruction absent from the package: 0;
- model ignored an unambiguous final V2 boundary: 0 (the old final boundary was
  V1); one direct X04 response used V1 while the nested package asked for V2;
- prompt truncation: 0;
- wrong assistant-response extraction: 0;
- parser downgraded a valid V2 object: 0;
- stale/hard-coded V1 worker protocol: 12/12;
- V1 format-retry path produced the final legacy result: 11/12;
- conflicting nested V2 and final V1 instructions: 12/12.

The historical X05 `RESULT_BINDING` failure was not a half-written/stale file.
The external V1 result existed in the browser, but the V1 protocol required the
model to reproduce internal analysis/package identifiers. Binding failed after
the bounded retry, so no result artifact/manifest was published. The repaired
path creates those identifiers locally and binds exact job ID, request ID and
contract version.

## V2 worker contract

- explicit per-job contract version, never inferred from prose;
- final answer-boundary instruction requires one JSON object only, without
  markdown, surrounding prose, V1 shape, external claim IDs or disposition;
- compact schema rendered from the worker's canonical V2 module;
- only supplied fact/tool/visual handles can be referenced;
- canonical `C01...` claim IDs and accepted/review/rejected disposition remain
  local deterministic responsibilities;
- exact JSON or an exact single outer code fence is accepted; arbitrary prose
  is not repaired;
- one representation-only retry is available; it does not relax semantics;
- V1 for a V2 job is `INTEROPERABILITY_FAILURE`, not a compatibility fallback.

The artifact is written temp -> file flush -> atomic rename, and its manifest is
published last. It includes schema, job/request/contract IDs, attempt, UTC,
raw-result SHA-256, parsed V2 and `validation_pending=true`. Supervisor verifies
the exact artifact field set, hashes, IDs, contract, attempt and V2 content
before marking the job complete. Pre-existing output is `STALE_RESULT`.

## Offline regression

- V2 contract corpus: 30/30 valid variants accepted;
- unsafe/privacy corpus: 75/75 rejected;
- false acceptance / false rejection: 0 / 0;
- worker prompt, exact extraction, code-fence boundary and one-retry controls:
  PASS;
- legacy, malformed, unknown-handle, external-claim-ID: rejected;
- wrong job, wrong request, stale copy, partial output and duplicate/preexisting
  binding: rejected;
- V1/V2 queue routing and existing queue/recovery/idempotency suites: PASS;
- backend exact binding and privacy checks: PASS.

## Exact 15 primary acceptance

All cases were the frozen F0 escalations: B05, B09, T09, T10, T11, D02, D04,
D10, X01, X02, X04, X05, X10, A04 and A05.

- primary V2: 15/15 (100%);
- exact result binding: 15/15;
- legacy / malformed / binding failure: 0 / 0 / 0;
- retries: 0; total external submissions: 15;
- deterministic contract disposition: 15 accepted, 0 review, 0 rejected;
- external-subset frozen score: 88.10 overall, 81.67 factual/evidence;
- wrong sources / privacy failures: 0 / 0;
- hard-failure cases: 1 (`D10`, frozen scorer's `unjustified_estimate`);
- material handle provenance: complete for every FACT/ESTIMATE/HYPOTHESIS;
  MISSING intentionally carries no invented provenance.

Primary external generation was 11.91–25.68 s (mean 17.61 s, median 15.65 s).
Result binding averaged 0.372 s. End-to-end worker terminal time was
12.30–26.02 s (mean 17.98 s, median 15.99 s). No retry latency was incurred.

## Semantic controls requiring separate follow-up

### B05

The result is semantically supported and recommends a new visit or scaled
photos. The frozen lexical expected term `wizj` does not match Polish `wizyta`,
so factual coverage remains 50%. This is a safe-paraphrase scorer mismatch;
the factual threshold was not changed.

### X04

The package carried `S1` and `S2`, but no opaque field expressed which handle
belonged to target scope A. The model safely refused with `MISSING` and cited no
wrong source. Future qualification needs a deterministic target-scope handle
mapped locally to source handles, without names, email, phone or address. No
extra PII was sent and no provenance was guessed in this execution.

### Tool/refusal boundary

T11 preserved `T1`; local resolution retains the deterministic invocation and
its underlying source. T09, A04, D04 and D10 demonstrate MISSING/NOT_ESTIMABLE
representation. The worker cannot choose local disposition. D10's response is
substantively a refusal, but its ESTIMATE used `LOW` rather than the canonical
`NOT_ESTIMABLE`, so the frozen hard-failure label remains unchanged.

## F0 end-to-end reconstruction

Combining the unchanged 35 accepted-local cases with the 15 strict V2 results:

- auto-local / auto-advanced / review / failed: 35 / 15 / 0 / 0;
- automatic coverage: 50/50 (100%);
- overall: 94.80;
- factual/evidence: 94.50%;
- technical-documentation: 95.04;
- cross-domain: 89.85;
- estimate/refusal: 80.00%;
- hard failures: 1/50 (2%);
- wrong-source / privacy failures: 0 / 0;
- local coverage / external rate: 70% / 30%.

The numeric gates pass, but the unresolved X04 scope-package defect means the
full qualification rule does not. The appropriate state is
`TEMP_CHAT_V2_INTEROPERABILITY_PASS / F0 NOT QUALIFIED`.

## Production boundary and safety

Production model routing was not changed. Stable remains `1.0.2+29`. No model
was pulled or deleted; Gemma3 12B was not downloaded. No DB migration,
business-data write, Qdrant write/delete, Gmail send, n8n change, real-customer
Temporary Chat/Vision job or resource-limit change occurred. The 15 synthetic
jobs created only their canonical analysis-ledger/status metadata and private
ignored spool/report artifacts. Backend, Supervisor, Vision, Postgres and
Qdrant health passed after the run; DB head is
`followup_contact_person_20260822`, customer/KB Qdrant counts remain 57/0.
