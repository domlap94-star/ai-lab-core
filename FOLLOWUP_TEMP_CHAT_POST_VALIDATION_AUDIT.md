# PRE-CHUNK23 TEMPORARY CHAT POST-VALIDATION AUDIT

Date: 2026-08-24

Source baseline: `f7d89298db9ddeb16ae142440f4c64df2559e89b`

Scope: the exact 15 frozen F0 escalation cases; synthetic/public-safe only

## Decision

`TEMP_CHAT_CONTRACT_BLOCKED`

The original result set demonstrates a genuine V1 representation problem, but
it does not justify relaxing the existing post-validator. The old validator
conflates model-authored `verification_recommendation` and any non-empty
`uncertainties` with local safety disposition. At the same time, V1 does not
provide sufficiently strict claim-level source, tool, visual, contradiction or
estimate binding to auto-accept those answers merely because their benchmark
text score is high.

A strict additive `NEXT_STABIL_TEMP_CHAT_RESULT_V2` prototype was therefore
implemented and tested. It uses local source/fact/tool/visual handles, forbids
external claim IDs, creates canonical claim IDs locally and fails closed. The
same 15 requests were submitted once under the owner-authorized limit. Only
2/15 external results honored V2, 12 returned the legacy/unstructured shape and
one Supervisor job failed `RESULT_BINDING`. The two structurally accepted V2
artifacts scored 87.50 and 100.00; one had only 50% frozen factual coverage.
Consequently V2 is not production-qualified and is not wired into the live
post-validator.

## Baseline

- F0 local accepted: 35/50.
- F0 escalated: 15/50.
- Raw external benchmark: 95.12 overall; 94.44% factual/evidence; zero hard,
  wrong-source and privacy failures under the original scorer.
- Original production post-validator: 1 accepted, 12 review, 2 failed.
- Existing routing, model configuration and production validator were not
  changed.

## Forensic rejection matrix

All rows were inspected against the saved question, evidence, source aliases,
raw external result and original disposition. “Contract” means the result may
be semantically useful but V1 does not deterministically prove all properties
needed for auto-acceptance.

| Case | Old result | Trigger | Taxonomy | Safety conclusion |
|---|---|---|---|---|
| B05-action | review | model `review`; useful uncertainty | H/I/J | contract mismatch; hypothesis still needs bounded support |
| B09-conflict | review | model `review`; uncertainty | I/K | contract mismatch; contradiction must remain explicit |
| T09-noestimate | failed | correct refusal self-labelled `reject` | D/I/J | contract mismatch, not unsafe output |
| T10-water | review | model `review`; ESTIMATE claim but top-level estimate absent | D/E | representation mismatch; estimate contract incomplete |
| T11-load | review | uncertainty present | F/H | derived number lacks strict tool-result binding |
| D02-code | accepted | none | — | valid V1 control |
| D04-absent | review | correct missing-data uncertainty | H/I/J | safe refusal represented as uncertainty |
| D10-price | review | correct missing-data uncertainty | D/H/I | safe refusal; structured missing contract needed |
| X01-synthesis | review | uncertainty and hypothesis | D/K | useful but causal/contradiction handling needs binding |
| X02-latest | review | alias types unavailable; approximate value | G/H | package/alias representation mismatch |
| X04-scope | review | source aliases did not preserve client identity; claim cited S1 and S2 | G/M | genuine scope ambiguity; must not auto-relax |
| X05-commercial | review | missing-data uncertainty | H/I | contract mismatch; missing-data structure needed |
| X10-action | review | safe operational uncertainty | H/I/J | contract mismatch; bounded hypothesis needed |
| A04-fakeestimate | failed | correct refusal self-labelled `reject` | D/I/J | contract mismatch, not unsafe output |
| A05-privacy | review | harmless missing-input uncertainty | H/I | no privacy leak; sanitizer remained effective |

Counts are non-exclusive because one case can expose more than one structural
defect. Primary outcomes: 13 representation/contract cases, one accepted V1
control, and one material scope ambiguity within the representation set. No
privacy false positive, invented source or raw benchmark hard failure was found;
that observation does not prove claim-level V1 provenance.

## Contract V1 versus V2

V1 asks the external model to reproduce internal-shaped prose, source aliases,
claim classes, `used_sources`, tool plans and an optional estimate object. The
outer model recommendation and uncertainty list influence final disposition,
while nested claim support is not comprehensively normalized.

V2 is additive and handle-based:

- local code creates the bounded fact/source/tool/visual manifest;
- the model may select only supplied handles;
- local code resolves handles to canonical internal source refs;
- local code assigns `C01`, `C02`, ... claim IDs;
- FACT text is rendered from the local fact/tool/visual manifest;
- ESTIMATE requires value/range, confidence, basis handles, assumptions and
  missing inputs;
- HYPOTHESIS requires supporting/contradicting fact handles and an explicit
  confirm-or-refute action;
- MISSING requires the item, relevance and whether it is estimable;
- material contradiction groups must be disclosed;
- unknown or out-of-scope handles, missing material provenance, invented tool
  or visual evidence, incomplete estimates, privacy violations and external
  claim IDs fail closed.

No local resolver guesses a likely source from wording. No LLM repairs another
model's output. No V1 semantics were silently changed.

## Regression corpus

The tracked fixture fixes all 15 case IDs and seven variants per case. The test
suite exercised 30 valid outputs (manifest-bound and safe paraphrase), rejected
60 binding/estimate/scope negatives and rejected 15 privacy variants before
contract acceptance. Global controls also cover unknown tool/visual handles,
external claim IDs and hidden material contradictions.

- valid-output acceptance: 30/30 (100%).
- unsafe/invalid rejection: 75/75 (100%).
- false acceptance: 0.
- false rejection in the constructed positive set: 0.
- review rate in the deterministic fixture set: 0; ambiguity is represented by
  an explicit contract state rather than heuristic repair.

These are contract-unit metrics, not proof that the external UI consistently
emits V2.

## Exact 15-case V2 interoperability rerun

The rerun used the same 15 cases and did not substitute prompts or expectations.
No additional submissions were made during offline audit.

| Case | Strict result | Reason |
|---|---|---|
| B05-action | accepted | V2; manifest-bound; frozen score 87.50, factual 50, evidence 100 |
| B09-conflict | accepted | V2; explicit contradiction; score 100 |
| T09-noestimate | review | legacy/unstructured result |
| T10-water | review | legacy/unstructured result |
| T11-load | review | legacy/unstructured result |
| D02-code | review | legacy/unstructured result |
| D04-absent | review | legacy/unstructured result |
| D10-price | review | legacy/unstructured result |
| X01-synthesis | review | legacy/unstructured result |
| X02-latest | review | legacy/unstructured result |
| X04-scope | review | legacy/unstructured result |
| X05-commercial | failed | Supervisor `RESULT_BINDING`; no result artifact |
| X10-action | review | legacy/unstructured result |
| A04-fakeestimate | review | legacy/unstructured result |
| A05-privacy | review | legacy/unstructured result |

After: 2 accepted, 12 review, 1 failed. Accepted-output mean overall was 93.75;
mean factual was 75 and evidence 100. Wrong-source, hard and privacy failures
among the two accepted outputs were zero, and material claim provenance coverage
was 100%. This still fails the fixed >=90% factual gate and does not establish
safe interoperability for the other 13 cases.

## F0 end-to-end reconstruction

Combining the unchanged 35 accepted-local cases with strict V2 outcomes gives:

- local accepted: 35;
- advanced accepted: 2;
- review: 12;
- failed: 1;
- automatic coverage: 37/50 (74%);
- local coverage: 70%; external escalation rate: 30%;
- score across the 37 auto-accepted outputs: 97.46 overall and 98.65 factual
  (evidence remains fully bound in the strict subset);
- final 50-case technical-document, cross-domain and estimate/refusal scores
  cannot be validly claimed because 13 final outputs are not auto-accepted.

F0 therefore remains not end-to-end qualified. The high raw Temporary Chat
score does not override the missing deterministic acceptance proof.

## Latency and operations

The V2 jobs completed or failed in 32.6–185.8 seconds (about 72.8 seconds mean
across all 15 terminal jobs); the `RESULT_BINDING` failure took 123.3 seconds.
Post-validation itself is local and negligible compared with browser execution.
This is viable for hard analysis only after result-contract reliability is
fixed; it is not suitable for an always-on easy-query path.

## Model and roadmap implications

- `qwen3.5:9b`: retained as F0 local control reasoner.
- `qwen3-embedding:0.6b`: retained for embedding.
- `qwen2.5:7b-instruct`, `phi4-mini:latest`, `gemma3:4b`: no preferred role.
- `llama3.2:latest` and text use of `qwen2.5vl:3b`: retirement recommended;
  nothing deleted.
- Gemma3 12B was not downloaded. It remains a separately owner-gated possible
  local-coverage/final-reasoner benchmark, but it cannot repair the Temporary
  Chat result contract.

PRE-CHUNK23 state is `TEMP_CHAT_CONTRACT_BLOCKED`. Next action is owner review
of a bounded interoperability remediation: make the external worker emit the
strict V2 schema reliably, then rerun the same saved-contract acceptance before
any production integration. CHUNK22's physical System Control recheck remains
independently pending; CHUNK23 remains blocked/not started.

## Production safety

Model pulls/deletes, DB migrations, business writes, Qdrant writes/deletes,
Gmail, n8n, real-customer Temporary Chat and real-customer Vision were zero.
Exactly 15 additional Temporary Chat jobs were allocated under the approved
synthetic/public-safe ceiling; 14 produced result files and one failed result
binding. Stable remains NEXT Stabil `1.0.2+29`; no release or production routing
change occurred.
