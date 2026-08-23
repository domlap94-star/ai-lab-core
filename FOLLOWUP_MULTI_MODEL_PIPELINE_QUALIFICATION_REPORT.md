# PRE-CHUNK23 MULTI-MODEL PIPELINE QUALIFICATION

Status: **COMPLETE — NEW MODEL BENCHMARK REQUIRED**

Date: 2026-08-24

Source HEAD: `1bb69a5564c9ed0cf49c37e52b8f55809ed82a6a`

Stable release: `NEXT Stabil 1.0.2+29`

This benchmark is isolated and synthetic. It did not pull or delete a model,
change production routing, submit real customer content, mutate Qdrant or
publish a release. Raw model responses and telemetry remain in the ignored
private test-report directory.

## Decision

The preferred architecture is **Pipeline F: deterministic router and scoped
retrieval/tools -> `qwen3.5:9b` at 4096 -> deterministic quality/privacy/source
gate -> controlled Temporary Chat or Vision only when required -> local
post-validation**.

Pipeline F is Pareto-optimal among the installed choices, but it is **not yet a
qualified end-to-end final-answer pipeline**. It accepted 35/50 cases locally
at 97.67 overall and 100% factual/evidence with zero accepted-local hard
failures. It correctly routed the remaining 15/50 to escalation according to
the frozen gate. Those exact 15 final external answers were deliberately not
fabricated and were not re-executed in this run; existing CHUNK17 acceptance
proves the bridge contract, not the quality of these particular answers.

Consequently `FOLLOWUP_LLM_MODEL_DOWNLOAD_APPROVAL_REQUIRED` remains **READY /
NOT CONSUMED**. The next justified role is a stronger final local synthesizer.
The preferred bounded next benchmark remains `gemma3:12b` at `num_ctx=4096`,
consistent with the completed hardware verdict `SAFE_ONLY_AT_4096`.

## Fixed method

- Frozen qualification matrix: 50 cases, unchanged (10 business, 15
  technical, 10 document, 10 cross-domain and 5 adversarial; 11 estimation
  cases).
- Supplementary orchestration matrix: 15 deterministic fault-injection cases.
- Fixed gates: overall >=80, factual/evidence >=90%, material hallucination
  <=2%, wrong-client/source =0 and privacy hard failures =0.
- Installed models only: `gemma3:4b`, `qwen3.5:9b`, `llama3.2:latest`,
  `qwen2.5vl:3b`, `qwen3-embedding:0.6b`.
- Local generation: `num_ctx=4096`, `think=false`, temperature 0.1.
- Model stages ran serially. Gemma and Qwen were never intentionally resident
  together.
- Deterministic calculations used the existing
  `DeterministicCalculationValidator`; calculated claims inherited their
  underlying source refs.
- Long structured responses were retried only after JSON-cap truncation. The
  case, prompt, expected answer and thresholds did not change.

## Canonical structured handoff

The tracked schema is
`backend/test/fixtures/unified_evidence_artifact_v1.json`. Its mandatory
top-level fields are:

```text
request_id, scope, facts, estimates, hypotheses, missing, contradictions,
tool_results, visual_observations, unresolved_questions
```

Facts require `claim_id`, statement, confidence and non-empty allowlisted
`source_refs`. Estimates require a value/range, categorical confidence,
`basis_refs`, assumptions and missing inputs. Hypotheses retain support and
contradiction refs plus a confirm/refute step. Every specialist artifact is
schema-, scope-, source-, support- and privacy-validated before another model
may see it. Invalid output is discarded and never silently detached from its
provenance.

## Pipeline definitions

| Pipeline | Definition | Empirical execution |
|---|---|---|
| A | structured evidence/tools -> Qwen 9B | 50 final responses |
| B | Gemma 4B planner -> evidence/tools -> Qwen 9B | 50 planner artifacts; same frozen final responses as A to isolate routing value |
| C | Gemma 4B document specialist -> validated graph -> Qwen 9B | 40 eligible specialist artifacts; all rejected, so safe fallback equals A and no redundant synthesis was run |
| D | Qwen 9B -> gate -> Temporary Chat on hard fail | A output plus frozen gate decisions |
| E | Gemma planner -> Qwen 9B -> gate -> Temporary Chat | B output plus frozen gate decisions |
| F | deterministic router -> tools/evidence -> Qwen 9B -> gate -> Temporary Chat | A output with deterministic routing plus frozen gate decisions |

Qwen 2.5 VL was not used as a text synthesizer. No visual claim was accepted
without a validated visual result. Llama 3.2 was not forced into an artificial
role after its prior qualification failure.

## Frozen benchmark results

The reported overall score includes deterministic tool-plan accounting.
Factual/evidence and hard-failure gates are independent and remain binding.

| Pipeline | Overall | Factual/evidence | Hard-failure cases | Wrong-source cases | Privacy failures | Technical-document score | Cross-domain | Median local latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 91.86 | 88.83 | 6 | 5 | 1 | 89.04 | 87.52 | 26.00 s |
| B | 91.33 | 88.83 | 6 | 5 | 1 | 89.04 | 85.85 | 26.00 s + 6.94 s planner |
| C | 91.86 | 88.83 | 6 | 5 | 1 | 89.04 | 87.52 | 26.00 s + 25.43 s specialist |
| D | 91.86 local | 88.83 local | gated | gated | gated | 89.04 local | 87.52 local | 26.00 s local |
| E | 91.33 local | 88.83 local | gated | gated | gated | 89.04 local | 85.85 local | 32.94 s warm local |
| F | 91.86 local | 88.83 local | gated | gated | gated | 89.04 local | 87.52 local | 26.00 s local |

Pipelines A/B/C fail the independent factual/evidence, wrong-source, privacy
and hard-failure gates even though their weighted overall score exceeds 80.
This is why overall score alone is never used for acceptance.

### Gate outcome for D/E/F

| Item | D | E | F |
|---|---:|---:|---:|
| Accepted locally | 35/50 | 35/50 | 35/50 |
| Accepted-local overall | 97.67 | 97.10 | 97.67 |
| Accepted-local factual/evidence | 100% | 100% | 100% |
| Accepted-local hard failures | 0 | 0 | 0 |
| Escalation decisions | 15/50 | 15/50 | 15/50 |
| Exact external final outputs rerun | no | no | no |

The 15 gated cases were `B05`, `B09`, `T09`, `T10`, `T11`, `D02`, `D04`,
`D10`, `X01`, `X02`, `X04`, `X05`, `X10`, `A04` and `A05`. They cover answer
completeness, contradiction/source binding, refusal discipline, calculation,
cross-domain coverage and synthetic-identifier reintroduction. The gate missed
none of the locally failing cases and passed no hard failure locally. Calling
this “correct escalation” validates the routing decision; it does not claim a
Temporary Chat answer that was not generated.

## Router comparison

The deterministic router matched the exact expected tool set on 47/50 cases,
covered 100% of required tool classes and selected an additional bounded tool
on 3 cases. It adds no model load.

Gemma planner results:

- 50/50 structured attempts;
- 43/50 failed deterministic domain/source/tool validation;
- 2/50 exactly matched the expected tool set without fallback;
- 6.94 s warm median plus the previously measured ~27 s cold model load;
- invalid plans fell back to the deterministic router.

Therefore the LLM router is strictly dominated. Its failures are observable
and safely repaired, but it contributes no quality gain.

## Specialist validation

The document specialist ran only for 40 relevant technical, document,
cross-domain and adversarial cases; 10 business-only cases bypassed it.

- final syntactically valid artifacts: 40/40 after bounded truncation retries;
- admissible artifacts: 0/40;
- unsupported-fact failures: 40/40;
- invalid source-ref failures: 38/40;
- duplicate/invalid claim ID failures: 2/40;
- warm median latency: 25.43 s plus cold load.

The common failure was replacing canonical refs such as `document:T1` with
invented aliases such as `T1`, then adding unsupported interpretations or
estimates. Validation discarded every artifact. Pipeline C is safe because it
falls back, but it offers zero quality gain and doubles warm latency.

## Supplementary orchestration matrix

All 15/15 deterministic cases pass:

- valid document handoff accepted;
- unknown source rejected;
- FACT without source rejected;
- unsupported specialist fact rejected;
- contradiction retained;
- wrong planner domain repaired by deterministic routing;
- invented tool rejected;
- estimate without basis rejected;
- bounded estimate accepted;
- cross-domain source refs preserved;
- absent visual result requires visual routing;
- allowlisted visual observation accepted;
- restricted material blocked from escalation;
- hard public-safe local failure requires Temporary Chat;
- easy grounded result remains local.

## Sources contract

- Local claim/source coverage across all 50 final outputs: 90%.
- Wrong/irrelevant source cases: 5/50 (10%); all are rejected by the final
  validator.
- Accepted-local claim/source coverage: 100%.
- Accepted-local wrong-source leakage: 0.
- Synthetic PII reintroduction: 1/50; rejected by the privacy gate.
- Accepted-local PII reintroduction: 0.

The future `Źródła` artifact must be generated only after validation. It maps
accepted claim IDs to the allowlisted source refs and bounded supporting
excerpts/tool results actually used; rejected claims never reach the UI.

## Temporary Chat and Vision

The CHUNK17 bridge remains the only external path: sanitizer, Temporary Chat
verification, no normal Chat fallback, strict result/package/source binding
and local post-validation. This benchmark created **zero external jobs**.
Existing accepted synthetic CHUNK17 evidence establishes bridge mechanics but
was not substituted for the missing 15 benchmark outputs.

Visual cases correctly requested the controlled Vision route and made no
fictional raw-image claim. Qwen 2.5 VL remains unsuitable as a default text
synthesizer; any future use would be bounded preclassification only and would
not replace Vision validation.

## Resource and switching results

Normal NEXT Stabil services stayed running. Clean serial Qwen execution
observed:

- Ollama container about 6.92 GiB during the clean run (capacity report peak
  7.30 GiB for Qwen 4096);
- lowest bounded Windows snapshot: 4.05 GiB available;
- lowest bounded WSL snapshot: 5.47 GiB available;
- Windows pagefile: 53 MiB, no growth;
- WSL swap: zero;
- CPU-only execution; no Ollama GPU allocation;
- Qwen median response: 26.00 s warm.

An early diagnostic attempt left overlapping orphaned generations after
client interruption, inflated Ollama to 9.59 GiB and crossed the 3 GiB Windows
abort reserve. The exact benchmark processes were stopped, Qwen unloaded, and
Windows memory recovered from 2.89 to 12.49 GiB. The accepted run used one
model request stream only and retained the safe reserve. This is additional
evidence that production orchestration must prevent concurrent local
generator calls.

From the hardware report and this run:

| Pipeline | Local model loads | Peak model class | Paging/swap | Resource verdict |
|---|---:|---|---|---|
| A/D/F | 1 | Qwen 9B | pagefile flat; WSL swap 0 | safe serially, tight Windows reserve |
| B/E | 2 serial | Gemma 4B then Qwen 9B | no coexistence required | dominated by latency/quality |
| C | 2 serial | Gemma 4B then Qwen 9B fallback | no coexistence required | dominated by latency/invalid handoff |

Recommended residency is embedding persistent, deterministic router always
available, Qwen 9B on demand with 1–5 minute keep-alive, and no persistent
Gemma 4B planner/specialist. Qwen 9B + a future 12B must not be resident
simultaneously.

## Complexity and Pareto analysis

| Pipeline | Quality | Latency | Memory | Complexity/debuggability | Pareto |
|---|---|---|---|---|---|
| A | best raw installed local | best local | one generator | simple | yes, but unsafe without gate |
| B | slightly worse | slower | serial second model | 43 validation fallbacks | no |
| C | no gain | much slower | serial second model | 40/40 rejected handoffs | no |
| D | safe local subset + unmeasured external finals | local fast | one generator | moderate | yes |
| E | same gap as D | slower | serial second model | highest complexity | no |
| F | safe local subset + unmeasured external finals | local fast | one generator | simplest safe routing | **best balanced** |

Pipeline F dominates E and is easier to debug than D because tool selection is
explicit and deterministic. More local models do not improve the measured
quality.

## New-model role and shortlist

The remaining limitation is the final local reasoner: exact technical answer
coverage, abstention/estimate discipline, multi-source completeness and strict
source-ref emission. It is not a routing-model or specialist-handoff gap.

| Candidate | Intended role | Hardware | Assessment |
|---|---|---|---|
| Gemma 3 12B @4096 | stronger final synthesizer | `SAFE_ONLY_AT_4096` | preferred next bounded benchmark; materially different capacity |
| Qwen 3 8B | final synthesizer alternative | comfortable <=9B class | likely duplicates current 9B role; lower priority |
| Qwen 2.5 7B Instruct | document specialist alternative | comfortable | specialist stage is not justified by current results |
| Phi-4-mini | planner/router | comfortable | unnecessary; deterministic router wins |

No candidate was downloaded. `gemma3:12b` remains absent and the owner gate is
unconsumed.

## Model-role disposition

- `qwen3.5:9b`: KEEP — current local reasoner behind deterministic gate.
- `qwen3-embedding:0.6b`: KEEP — embedding; CHUNK18 backfill decision unchanged.
- `gemma3:4b`: no role in the preferred unified pipeline; retain until a
  separately approved retirement decision.
- `qwen2.5vl:3b`: RETIREMENT_RECOMMENDED; no action taken.
- `llama3.2:latest`: RETIREMENT_RECOMMENDED; no action taken.

## Production safety

- Ollama pulls/deletes: 0/0.
- Production routing/model configuration changes: 0.
- Stable release/manifest changes: 0; stable remains `1.0.2+29`.
- DB migrations/business writes: 0/0.
- Customer/KB Qdrant writes/deletes: 0/0.
- Gmail/n8n/Vision production jobs: 0/0/0.
- Real-customer Temporary Chat: 0.
- Synthetic Temporary Chat jobs in this benchmark: 0.
- Final DB head: `followup_contact_person_20260822`.
- Final Qdrant: customer 57 green; KB 0 green.

## Exact next action

Owner decision on `FOLLOWUP_LLM_MODEL_DOWNLOAD_APPROVAL_REQUIRED` for a bounded
`gemma3:12b` @4096 final-synthesizer benchmark. CHUNK22 physical System Control
recheck remains pending and CHUNK23 remains blocked/not started.
