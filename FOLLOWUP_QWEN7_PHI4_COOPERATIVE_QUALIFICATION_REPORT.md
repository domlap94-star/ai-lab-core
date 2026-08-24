# PRE-CHUNK23 Qwen 7B + Phi-4 Mini Cooperative Qualification

Date: 2026-08-24

Source: `5b7ba965381a8fc6fbf056c6c73be66145c222cf`

Stable: NEXT Stabil `1.0.2+29`

Scope was isolated model download, capacity/quality qualification and an
architecture decision. Production AI routing, customer data, DB/Qdrant writes,
model deletion, host resource changes and release publication were excluded.

## Decision

**Qwen3.5 9B Pipeline F0 remains the best installed architecture. Neither new
model earns a production role. Gemma3 12B remains justified as the next bounded
final-reasoner benchmark at `num_ctx=4096`, behind a new owner decision.**

The owner approval was consumed only for these two pulls:

| Model | Digest | Parameters / quantization | Disk | Metadata context |
|---|---|---:|---:|---:|
| `qwen2.5:7b-instruct` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | 7.6B / Q4_K_M | 4,683,087,332 B | 32,768 |
| `phi4-mini:latest` | `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753` | 3.8B / Q4_K_M | 2,491,876,774 B | 131,072 |

Both were tested at context 4096. Existing models were retained. No other
model was pulled and the approval does not authorize Gemma3 12B.

## Method and frozen control

The immutable 50-case matrix contains 10 business, 15 technical, 10 document,
10 cross-domain and five adversarial cases, including 11 estimation/refusal
checks. Thresholds remained: overall >=80, factual/evidence >=90%, material
hallucination <=2%, wrong-source zero and privacy hard failures zero. Every
production-style run used deterministic routing, scoped evidence/tools,
`unified_evidence_artifact_v1` and deterministic source/privacy/quality gates.

The canonical F0 result file is `A.tools.jsonl`; it exactly reproduces all
previously published F0 metrics. `A.jsonl` is an interrupted partial run and
`A.clean.jsonl` is diagnostic. Neither was used as the final control. Raw
per-case/model telemetry remains ignored below `backend/test/reports/private/`.

## Hardware and residency

| Configuration | Runtime | Windows min | WSL min | Pagefile max | Swap | Cold | Warm | tok/s | Unload |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen7 | 4.715 GiB | 9.043 GiB | 9.968 GiB | 759 MiB | 0 | 26.52 s | 13.39 s | 10.79 | 0.51 s |
| Qwen7 + embedding | 4.715 GiB | 7.976 GiB | 8.877 GiB | 762 MiB | 0 | 26.28 s | 13.66 s | 10.78 | 0.52 s |
| Phi | 2.882 GiB | 10.675 GiB | 11.634 GiB | 765 MiB | 0 | 15.70 s | 8.85 s | 18.43 | 0.52 s |
| Phi + embedding | 2.882 GiB | 9.731 GiB | 10.520 GiB | 765 MiB | 0 | 15.73 s | 8.30 s | 18.36 | 0.52 s |

Pagefile use remained the pre-existing small safety-buffer level; WSL swap was
zero. Services remained healthy and unload recovered memory. Qwen7 and Phi are
`SAFE_SHORT_KEEPALIVE` individually, but neither has a qualified role.

`Phi + Qwen7 + embedding` was safe in a narrow test (Windows minimum 5.024
GiB, WSL minimum 5.93 GiB, swap zero), though serial execution remains safer.
`Phi + Qwen9 + embedding` was rejected predictively: adding Phi to the measured
Qwen9 coexistence floor would breach the 3 GiB abort boundary.

## Final-answer pipelines

| Pipeline | Overall | Factual/evidence | Hard | Wrong source | Privacy | Tech docs | Cross-domain | Local | Escalation | Median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F0 / Qwen9 | 91.86 | 88.83 | 6 | 5 | 1 | 89.04 | 87.52 | 35/50 | 30% | 26.00 s |
| Q7 final | 89.03 | 84.33 | 4 | 1 | 0 | 84.88 | 82.70 | 30/50 | 40% | 30.37 s |
| Phi final | 86.88 | 78.00 | 14 | 11 | 2 | 76.94 | 86.43 | 23/50 | 54% | 10.98 s |
| Q7 -> Q9 | 92.10 | 88.67 | 8 | 6 | 0 | 89.04 | 88.70 | 32/50 | 36% | 27.08 s final stage |
| Phi -> Q7 | 88.63 | 83.33 | 4 | 1 | 0 | 84.88 | 82.70 | 30/50 | 40% | 30.37 s final stage |

No raw local pipeline meets every hard gate. F0 remains the strongest balance.
Qwen7 is slower and weaker. Phi is faster/smaller but unsafe as a final model.

## Cooperative-role evidence

Qwen7 specialist output was eligible on 40 cases: 18 artifacts were admissible
and 22 rejected. Rejections included unsupported facts (18), invalid claim IDs
(6) and out-of-scope sources (7). The resulting Q7->Q9 pipeline gained 0.24
overall points but increased hard failures from six to eight and wrong-source
cases from five to six. The quality gain does not justify the safety regression,
model switch and added validation boundary.

Phi planning produced only 2/50 admissible artifacts; 48 selected a mismatched
domain, nine invented/selected an unknown tool and one violated source scope.
Phi specialist output was admissible on only 1/40 cases.

As validator, Phi rejected two genuine Qwen7 failures but also falsely rejected
two and missed 17 (4.57 s median overhead). Against canonical F0 it rejected
none, missing all 16 expected failures (6.16 s median). It is not a useful
validator. The Qwen7/Qwen9 structured cross-check yielded 30 agreements and 20
material disagreements; agreement was never treated as evidence, and the broad
trigger adds cost without adequate precision.

## Temporary Chat end-to-end proof

Exactly the 15 previously gated F0 cases were submitted through the canonical
Temporary Chat worker. Inputs were synthetic/public-safe; no customer data or
PII was used. All 15 jobs completed.

Raw external results scored 95.12 overall and 94.44 factual/evidence, with zero
hard failures, wrong-source cases or privacy failures. The strict local
post-validator accepted one as `accepted_advanced`, held 12 for review and
failed two. The accepted result scored 98.5 overall and 100 factual/evidence.
End-to-end all-case acceptance is therefore false.

This proves that external reasoning quality is adequate on this fixture while
the current strict result/post-validation contract is mismatched or
over-restrictive for 14/15 results. It must be reconciled without weakening
privacy, source binding or local validation before production qualification.

## Pareto, roles and architecture

- Best quality/balance and local coverage: F0.
- Best technical-document score: F0 and Q7->Q9 tie; F0 wins on safety and
  complexity.
- Fastest/lowest RAM: Phi, but quality and safety disqualify it.
- No cooperative pipeline is Pareto-superior to F0.

| Model | Evidence-based role |
|---|---|
| `qwen3.5:9b` | `KEEP — FINAL REASONING CONTROL`, on demand / 1–5 min keep-alive |
| `qwen3-embedding:0.6b` | `KEEP — EMBEDDING`; no vector backfill implied |
| `qwen2.5:7b-instruct` | `NO_USEFUL_ROLE`; not production-wired |
| `phi4-mini:latest` | `NO_USEFUL_ROLE`; not production-wired |
| `gemma3:4b` | prior `NO_USEFUL_ROLE` |
| `llama3.2:latest` | `RETIREMENT_RECOMMENDED`; no deletion |
| `qwen2.5vl:3b` | `RETIREMENT_RECOMMENDED` for text; Vision unchanged |

Preferred control remains:

```text
deterministic router -> scoped retrieval/tools -> unified evidence artifact
  -> qwen3.5:9b @4096, think=false
  -> deterministic quality/source/privacy gate
  -> controlled Temporary Chat or Vision
  -> strict local post-validation
```

F0 still misses the raw factual/source gate, and external post-validation
accepts only 1/15. Thus the architecture is not qualified. Gemma3 12B remains
justified for a final-reasoner-only benchmark at 4096, under a new owner gate.
The post-validation mismatch must also be isolated. CHUNK23 remains blocked,
independently of the pending CHUNK22 physical System Control recheck.

## Safety ledger

- Authorized model pulls: 2; unauthorized pulls: 0; model deletes: 0.
- Production AI wiring, pagefile, WSL and GPU/runtime changes: 0.
- DB migrations, business writes, Qdrant, Gmail, n8n and Vision jobs: 0.
- Temporary Chat: 15 synthetic/public-safe jobs; real-customer jobs: 0.
- Stable release/manifest: unchanged at NEXT Stabil `1.0.2+29`.
