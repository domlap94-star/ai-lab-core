# PRE-CHUNK23 F0 scope and semantics final acceptance

Date: 2026-08-24
Source baseline: `178797012154c93a2df6be73ced6d8675b5c71f7`
Stable release: `NEXT Stabil 1.0.2+29`

## Outcome

F0 is end-to-end qualified. The remaining X04 defect was a semantic package
boundary, not a reasoning failure: two safe opaque source handles were present,
but the package did not say which one belonged to the requested target. The
package now carries a locally generated opaque `TARGET_01` scope and a
deterministic allowed/global source map. No customer identity is serialized.

D10 exposed a separate ambiguity between a low-confidence estimate and a
substantive refusal. V2 now represents this structurally with `ESTIMABLE` and
`NOT_ESTIMABLE` states. The refusal state requires a reason, provenance and
missing inputs, and forbids a numerical value, confidence or assumptions.

## Target-scope contract

- `target_scope.scope_handle` is an opaque `TARGET_01...TARGET_08` value with
  no external business meaning.
- `allowed_source_handles` binds target evidence; `global_source_handles`
  explicitly identifies scope-neutral public/reference evidence.
- unknown, duplicate, mixed target/global and out-of-scope handles fail closed;
- tool and visual handles are usable only when every underlying source is in
  the target/global allowlist;
- all internal target identity remains local. Names, email, phone, address and
  tax identifiers were not added for disambiguation.

Current production analysis is single-target. Multiple-target semantics are
reserved for a future explicit contract revision rather than being inferred.

## Exact X04 repair

The frozen question, the two source excerpts, thresholds and expected reasoning
were unchanged. Before, `S1` and `S2` were indistinguishable relative to the
target and the model safely returned `MISSING`. The repaired package adds only:

```json
{"target_scope":{"scope_handle":"TARGET_01","allowed_source_handles":["S1"],"global_source_handles":[]}}
```

The first external V2 attempt returned FACT `F1`, bound only to `S1`, with 100%
claim provenance and factual coverage, no MISSING, wrong source, privacy failure
or retry. The unchanged frozen scorer nevertheless awards 50% evidence because
its legacy X04 `expected_sources` lists both candidate clients. The conservative
frozen score is therefore 83.50; this known benchmark limitation was not
"fixed" by changing the case or threshold.

## Estimation semantics and D10

The prior schema used confidence to carry both confidence and estimability.
That permitted a semantically inconsistent refusal with `LOW`. The worker
template, prompt, JavaScript validator and local Python normalizer now use an
explicit estimate state. Legacy valid V2 remains parseable for deployed-job
compatibility, but new jobs are instructed to emit the structural form.

D10 passed on the first attempt with `estimate_status=NOT_ESTIMABLE`, a reason,
fact provenance and the missing inputs `zakres robót`, `ilości`, and `ceny`.
It contained no number, confidence or assumptions and scored 100 with no hard
failure. No case-specific branch or threshold exception was introduced.

## Regression evidence

Offline scope/estimate suite: 7/7 groups PASS. It covers target and global
sources, cross-target rejection, same-type sources, tool/visual inheritance,
unknown/duplicate handles, valid states and invalid mixed estimate states.
Existing V2 contract 9/9 and backend binding tests pass. Supervisor queue,
failure, recovery, idempotency, Vision queue and Qdrant snapshot validation
pass. Backend advanced-analysis privacy/calculation, Vision 10/10 and Qdrant
production guards pass.

Nine synthetic/public-safe external submissions were used: X04 and D10 first,
then B05, T09, T10, T11, D04, A04 and A05. All nine emitted and bound V2 on the
first attempt. Wrong sources, privacy failures and hard failures were zero.
External generation was 10.74-26.96 s (mean 16.36 s); binding averaged 0.374 s;
end-to-end worker terminal time averaged 16.73 s.

B05 remains a known scorer-only Polish inflection limitation (`wizyta` versus
the frozen lexical stem `wizj`). Neither production behavior nor frozen
thresholds were changed. T09 and T11 retain imperfect subscores but no hard
failure or safety defect.

## Frozen F0 reconstruction

The unchanged 35 accepted-local outputs were combined with the prior validated
advanced results and the nine superseding semantic results:

- auto-local / auto-advanced / review / failed: 35 / 15 / 0 / 0;
- automatic coverage: 50/50 (100%);
- overall: 96.43;
- factual/evidence: 97.00%;
- technical documentation: 95.56;
- cross-domain: 93.85;
- estimate/refusal: 82.00%;
- hard failures / wrong-source / privacy failures: 0 / 0 / 0;
- local coverage / external rate: 70% / 30%.

All production gates pass, target scope is deterministic, and estimation
semantics are contractually sound. The qualified architecture is:

deterministic router -> scoped retrieval/tools -> target-aware unified evidence
artifact -> `qwen3.5:9b` at 4096 (`think=false`) -> deterministic gate ->
Temporary Chat V2/Vision when required -> strict local validation.

Gemma3 12B is **not required** for quality qualification. The 70/30 local to
external split is an intentional engine-extension design and was operationally
acceptable in this bounded acceptance. No model was downloaded or deleted.

## Production boundary and safety

Production Assistant routing was not rewired and no release was performed.
No DB migration, business/Qdrant write or delete, Gmail/n8n action,
real-customer Temporary Chat/Vision job, or WSL/pagefile/GPU change occurred.
The synthetic acceptance created only canonical analysis-ledger/status metadata
and ignored private spool/report artifacts. DB head remains
`followup_contact_person_20260822`; customer/KB Qdrant remain green at 57/0;
backend and Supervisor are healthy and the arbiter is READY with no owner or
waiters.

PRE-CHUNK23 is now `F0 END-TO-END QUALIFIED / ARCHITECTURE READY FOR OWNER
IMPLEMENTATION DECISION`. CHUNK22 physical System Control recheck remains
pending and CHUNK23 remains blocked/not started.
