# FOLLOW-UP LOCAL LLM QUALIFICATION REPORT

Date: 2026-08-23
Scope: sanitized, isolated, read-only local qualification; no customer content, model pull/delete, Qdrant write, production AI job or external Temporary Chat job.

## Decision summary

The current user-facing Business/Technical/Agent split is not an acceptable final product architecture. Qualification uses the unified contract in `backend/test/run_local_llm_qualification.py` and the 50 deterministic cases in `backend/test/local_llm_qualification_cases.py`. Thresholds were committed in the harness before results were inspected: overall `>=80`, factual/evidence `>=90`, material hallucination `<=2%`, wrong source `0`, privacy hard failure `0`.

No result below those gates may be routed as unreviewed final reasoning merely because it is local or schema-valid. Model roles below are evidence-based and do not authorize downloads, deletion, production rewiring or Qdrant backfill.

## Live hardware envelope

| Item | Observed |
|---|---|
| Host | GMKtec NucBox M6 Ultra, Windows 11 Pro build 26200 |
| CPU | AMD Ryzen 5 7640HS, 6 cores / 12 logical processors |
| Physical RAM | 27,704,942,592 bytes; 5,883,293,696 bytes free at inventory |
| GPU | AMD Radeon 760M integrated; Windows reports 4,293,918,720 bytes adapter memory |
| Ollama acceleration | `size_vram=0` for resident models; qualification is CPU/RAM bound |
| WSL2 RAM | 18,858,254,336 bytes total; 9,411,567,616 available at inventory |
| WSL swap | 8,589,934,592 bytes; effectively unused at baseline |
| Docker/Ollama baseline | Ollama 5.976 GiB; all containers share the 17.56 GiB WSL limit |

Runtime versions observed: Ollama `0.32.3`; Docker Engine `29.6.2`.

Stable operating envelope: one 3–4B reasoning model can be always resident beside the embedding model. The installed 9.7B Q4 model is on-demand only. A 12–14B Q4 model is the maximum sensible qualification class with conservative context and strict unloading; a 24–27B Q4 model has inadequate headroom in the current WSL limit and risks sustained swap.

## Live Ollama inventory

| Model | Family / parameters / quantization | Disk | Advertised max context | Runtime context | Wiring and status |
|---|---|---:|---:|---:|---|
| `llama3.2:latest` | llama / 3.2B / Q4_K_M | 2,019,393,189 | 131,072 | production default 4,096; qualification 8,192 | ACTIVE generation in Business, Technical, Agent, Client Knowledge and RAG |
| `gemma3:4b` | gemma3 / 4.3B / Q4_K_M | 3,338,801,804 | 131,072 | qualification 8,192 | AVAILABLE / UNWIRED; legacy YAML chat entry does not wire current services |
| `qwen2.5vl:3b` | qwen25vl / 3.8B / Q4_K_M | 3,200,627,168 | 128,000 | qualification 8,192 | AVAILABLE / UNWIRED; multimodal candidate only |
| `qwen3.5:9b` | qwen35 / 9.7B / Q4_K_M | 6,594,474,711 | 262,144 | qualification 8,192 | AVAILABLE / UNWIRED; on-demand only |
| `qwen3-embedding:0.6b` | qwen3 / 595.78M / Q8_0 | 639,150,858 | 32,768 | active 4,096 | ACTIVE embedding, 1,024-dimensional output |

Historically mentioned `qwen3:4b` is MISSING. No model was pulled or deleted. The embedding model is qualified separately as the existing `KEEP — EMBEDDING`; this does not alter CHUNK18's `BACKFILL NOT RECOMMENDED / NOT APPROVED / NOT PERFORMED` decision.

## Benchmark design

The corpus contains 10 business/client, 15 technical/geotechnical, 10 document, 10 cross-domain and 5 insufficient/adversarial cases. Eleven cases require an explicit estimate. Fixtures include exact passages, OCR noise, tables, contradictions, deterministic calculations, same-looking cross-customer evidence, prompt injection, missing visual-tool output and removable synthetic identity markers.

Every request uses the same Polish system contract and a strict JSON schema with answer, typed claims, source references, tool plan and structured estimate. Temperature is 0.1, `num_ctx=8192`, structured output is enabled and model thinking is disabled for the comparable primary matrix. The result scorer is deterministic; the model never defines ground truth.

Score components cover factual correctness, evidence grounding, relevance, expected tool selection, estimate behavior, information-class separation, privacy and Polish quality. Hard failures are foreign/wrong source, unsupported FACT, unjustified estimate, forbidden/private content and a visual claim without visual processing. The raw checkpointed JSONL is kept in the untracked private test-report area; committed reports contain aggregate metrics only.

## Failure taxonomy represented

- irrelevant or generic answer;
- wrong/weak source selection and evidence not retrieved;
- irrelevant or hallucinated missing-data inference;
- invented technical fact or estimate-as-fact;
- shallow synthesis or ignored tool output;
- document question replaced by generic advice;
- visual claim without visual evidence;
- unnecessary identity exposure;
- domain restriction caused by the mode split;
- schema-valid but useless content.

## Primary model results

The table is populated from the generated `*.summary.json` artifacts after all four installed generative models complete the same 50-case run.

| Model | Overall | Factual/evidence | Hard failures | Tools | Estimation pass | Polish | Median / p95 latency | Production final reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `llama3.2:latest` | 57.17 | 34.17 | 42 cases / 84% | 37.50 | 81.82% | 97.0 | 11.25s / 16.39s | NO |
| `gemma3:4b` | 69.75 | 60.67 | 29 cases / 58% | 51.67 | 54.55% | 91.6 | 13.93s / 25.52s | NO |
| `qwen2.5vl:3b` | 69.74 | 52.83 | 37 cases / 74% | 49.17 | 100.0% | 95.8 | 12.09s / 14.59s | NO |
| `qwen3.5:9b` | 81.88 | 87.00 | 7 cases / 14% | 26.67 | 72.73% | 97.0 | 35.69s / 54.62s | NO |

`llama3.2` produced well-formed classes and good Polish, but frequently copied evidence text or generic labels into `used_sources` instead of immutable source IDs, selected wrong tools, failed cross-domain synthesis and supplied estimates where refusal was required. Strict local post-validation would reject these results; this is evidence that schema validity alone is not usefulness.

The dedicated 10-case routing probe used a second bounded configuration (`temperature=0`, `num_ctx=4096`, strict tool schema). Exact-match rates were only 30% Llama, 20% Gemma, 30% Qwen 2.5 VL and 10% Qwen 3.5. Qwen 3.5's think-enabled five-case probe scored 23.5 with empty final answers because its bounded generation budget was consumed without producing the required result contract; `think=false` is therefore the only viable tested configuration. Free-form output is not eligible for the strict production contract and was not promoted as a competing configuration.

Detailed primary metrics:

| Model | Factual | Evidence | Wrong source | Refusal when estimation forbidden | Separation | Privacy failures | Cross-domain |
|---|---:|---:|---:|---:|---:|---:|---:|
| `llama3.2:latest` | 49.67 | 18.67 | 33 | 0.00% | 100% | 0 | 48.83 |
| `gemma3:4b` | 79.33 | 42.00 | 28 | 72.22% | 94% | 0 | 78.35 |
| `qwen2.5vl:3b` | 67.67 | 38.00 | 31 | 5.56% | 100% | 1 | 68.93 |
| `qwen3.5:9b` | 86.67 | 87.33 | 2 | 77.78% | 96% | 0 | 75.43 |

All primary runs completed 50/50 without request failure. Resource/latency is treated as a separate feasibility gate rather than used to rescue a failing quality score. Llama plus the embedding model used about 5.98 GiB in the Ollama container; Qwen 2.5 VL plus embeddings used 5.60 GiB; Qwen 3.5 plus embeddings peaked around 9.60 GiB. Qwen 3.5 left about 5.15 GiB WSL memory available and swap remained at 4 KiB. Observed cold first-request wall time was approximately 37.5s Llama and 71.0s Qwen 3.5; warmed Qwen 3.5 median was 35.69s. Explicit unload completed normally; no crash or uncontrolled growth occurred.

## Per-model role verdict

- `llama3.2:latest` — **RETIREMENT_RECOMMENDED**, after an approved replacement exists. It is the current production generator but is not qualified for the reconstructed Assistant: 57.17 overall, 33 wrong-source events and zero reliable refusal-to-estimate performance. No deletion or immediate production rewire is authorized.
- `gemma3:4b` — **KEEP — ROUTING / EXTRACTION** only behind deterministic allowlists and validators. It is fast enough and its business/cross-domain surface score is useful, but wrong-source binding excludes final answers.
- `qwen2.5vl:3b` — **RETIREMENT_RECOMMENDED**. It is unwired, fails final reasoning and produced the only privacy hard failure. This text-only qualification does not establish a safe visual role; controlled production Vision remains the existing Temporary Chat path.
- `qwen3.5:9b` — **KEEP — SPECIALIZED** as an on-demand local technical/document synthesis candidate with mandatory strict post-validation. It is the strongest installed model, but misses the factual/evidence threshold, has two wrong-source events, seven hard-failure cases, weak tool routing and high CPU latency. It is not qualified as unreviewed final reasoning.
- `qwen3-embedding:0.6b` — **KEEP — EMBEDDING**. It returns the canonical normal 1,024-dimensional shape and remains separate from generative qualification.

No installed model earns **KEEP — FINAL REASONING**. Existing production wiring is unchanged until the reconstructed path and a qualified replacement are separately approved.

## Candidate models if no installed model qualifies

Only official Ollama library metadata was used for the shortlist; no pull occurred.

1. `gemma3:12b` Q4 class — official artifact approximately 8.1 GB, 128K advertised context, multilingual/multimodal. Expected working RAM at bounded 8K context: roughly 10–13 GB. This is the preferred next controlled qualification because it fits the WSL envelope with one model resident and directly tests whether the stronger member of the best-performing installed family closes reasoning/grounding gaps.
2. `qwen3:14b` Q4 class — expected artifact roughly 9–10 GB and working RAM roughly 12–15 GB at bounded context. It is a secondary tool-planning/reasoning candidate but leaves less safety margin.

`qwen3.5:27b` (official Q4 artifact 17 GB) and `mistral-small3.2:24b` (15 GB) are not recommended on the current 18.86 GB WSL cap: model plus KV cache, Ollama and the rest of the stack would leave no stable headroom. Sources: [official Gemma 3 library](https://ollama.com/library/gemma3), [official Qwen3 library](https://ollama.com/library/qwen3), [official Qwen3.5 tags](https://ollama.com/library/qwen3.5/tags), [official Mistral Small 3.2 library](https://ollama.com/library/mistral-small3.2).

Recommended next controlled download: **`gemma3:12b`** (official default Q4
class, approximately 8.1 GB disk). Expected role: candidate normal local final
reasoning; reason: the installed 4B family member is materially stronger than
current Llama on business/cross-domain quality. Exact gate:
`FOLLOWUP_LLM_MODEL_DOWNLOAD_APPROVAL_REQUIRED`.

Subsequent pre-download host measurement supersedes the provisional 8192
capacity assumption: `FOLLOWUP_LLM_HARDWARE_CAPACITY_REPORT.md` classifies the
candidate **SAFE_ONLY_AT_4096**. Any approved download benchmark must begin at
4096 with the documented host/WSL abort gates; 8192 is not authorized by the
capacity evidence.

Any deletion requires `FOLLOWUP_LLM_MODEL_RETIREMENT_APPROVAL_REQUIRED`. Estimated disk recoverable if both retirement recommendations are later approved: about 5.22 GB (2.02 GB Llama + 3.20 GB Qwen 2.5 VL). Deletion is not part of this execution.

## Architecture consequence

The benchmark does not authorize a full Assistant rewrite. The target architecture is defined in `FOLLOWUP_AI_ASSISTANT_RECONSTRUCTION_DESIGN.md`: one interface, deterministic scope and tool plan, minimum multi-domain evidence, qualified local reasoning, usefulness/privacy/grounding gate, controlled Temporary Chat/Vision escalation, local post-validation and a collapsed claim-linked source inspector.

## Final recommendation

**FOLLOWUP_LLM_MODEL_DOWNLOAD_APPROVAL_REQUIRED.** The reconstruction design is ready, but its final-reasoning role is not. Qualify `gemma3:12b` with the same frozen 50-case corpus before implementing the unified UI/orchestrator. Qwen 3.5 may remain an on-demand specialist; Gemma 4B may be evaluated inside a deterministic router/extractor path. Do not lower thresholds or route their rejected results directly to users.

CHUNK23 remains blocked until the model/routing verdict and CHUNK22 physical System Control recheck are accepted. Production remains on stable `1.0.2+29`; current model wiring, advanced-analysis policy and Qdrant state remain unchanged.
