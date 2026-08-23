# FOLLOW-UP LLM HARDWARE CAPACITY REPORT

Date: 2026-08-23

Scope: pre-download capacity qualification using only installed models and the
normal NEXT Stabil stack. No model pull/delete, memory-limit change, service
shutdown, database write, Qdrant mutation, Vision job or external analysis was
performed.

## Decision

`gemma3:12b` is **SAFE_ONLY_AT_4096** for a controlled download and subsequent
quality benchmark. This is a hardware-capacity verdict, not a model-quality
approval. It assumes one on-demand 12B Q4 generator, the embedding model, all
normal NEXT Stabil services, a short keep-alive and the existing Windows
pagefile only as an emergency buffer.

`num_ctx=8192` is not approved for the 12B candidate on this host. The expected
case approaches the Windows physical reserve target and the conservative case
crosses the 3 GiB safety-abort boundary. A 14B Q4 candidate is **MARGINAL** at
4096 and **UNSAFE** at 8192; it is not the recommended next download.

The exact unchanged owner gate is
`FOLLOWUP_LLM_MODEL_DOWNLOAD_APPROVAL_REQUIRED` for `gemma3:12b`, with the
qualification configuration bounded to `num_ctx=4096`. It is ready for an
owner decision and was not consumed.

## Method and safety

The reusable PowerShell 5.1 probe is
`operations/ai/measure-local-llm-capacity.ps1`. It records sanitized host,
pagefile, WSL, Docker, GPU, Ollama and service-health telemetry. Four
configurations ran the same five short synthetic prompts:

- Qwen 3.5 9B, 4096, generator only;
- Qwen 3.5 9B, 4096, embedding co-resident;
- Qwen 3.5 9B, 8192, generator only;
- Qwen 3.5 9B, 8192, embedding co-resident.

The probe fails below 3 GiB Windows available RAM, below 2 GiB WSL available
RAM, above 2 GiB WSL swap, or on backend/Postgres/Qdrant/Supervisor health
failure. Raw per-second telemetry remains in the private local temporary area
and is not committed. The first probe completed its workload and unload but
hit a PowerShell 5.1 generic-list serialization error; no partial record was
accepted. The serialization-only issue was fixed, the model absence was
verified, and all four clean recorded runs passed.

## Windows physical memory, commit and pagefile

| Item | Observed |
|---|---:|
| Physical RAM | 27,055,608 KiB / 25.80 GiB |
| Initial available RAM | 14,325,932 KiB / 13.66 GiB |
| Idle committed range during audit | 18.6-20.2 GiB |
| Commit limit | 70.80 GiB |
| Highest measured commit | 27.51 GiB / 38% |
| C: pagefile | system-managed; 13,312 MiB currently allocated |
| D: pagefile | 32,768 MiB minimum/current; 65,536 MiB maximum |
| Total currently allocated pagefile | 46,080 MiB |
| Initial pagefile use | 53 MiB |
| Maximum current use during tests | 55 MiB |
| Boot-session peak reported | 63 MiB |
| D: free space | approximately 851 GiB |
| Pagefile storage | healthy NVMe SSD |

The pagefile did not grow materially. High `Pages Input/sec` spikes occurred
during cold model loading while Ollama memory-mapped model files; pagefile use
stayed flat and WSL swap stayed zero. Warm inference averaged roughly 75-85
page reads/sec with no sustained pagefile allocation or responsiveness loss.
This is **ACCEPTABLE SAFETY BUFFER**, not paging-dependent inference. Windows
pagefile capacity is not counted as model RAM.

Largest summarized host consumers at baseline were WSL/Docker, Windows memory
compression, the Codex/ChatGPT desktop process group, endpoint security,
Google Drive, Explorer and Edge. No unrelated process was terminated.

## WSL and Docker ceiling

The unchanged `.wslconfig` is:

```ini
[wsl2]
memory=18GB
swap=8GB
```

No processor limit is configured; WSL/Docker sees 12 logical processors. Linux
reports 17.56 GiB effective RAM and 8.00 GiB swap. Baseline WSL available RAM
after model unload was approximately 14.6 GiB. WSL swap remained exactly zero
through every accepted run.

Container baseline at the initial inventory:

| Component | Memory |
|---|---:|
| Backend | 0.21-0.24 GiB |
| Qdrant | 0.20 GiB |
| n8n | 0.47-0.52 GiB |
| Open WebUI | 0.66 GiB |
| Postgres plus isolated auxiliary Postgres | 0.09 GiB |
| Non-Ollama total | approximately 1.72 GiB |
| Ollama idle before runner load | 0.03 GiB; 0.17 GiB after runner use |
| Ollama with embedding resident | approximately 1.26 GiB container usage |

Ollama `/api/ps` reports the embedding allocation as 2.208 GiB, but the
observed incremental container cost was approximately 1.09 GiB because shared
and mapped memory accounting differs. Capacity predictions use the observed
full-container and WSL deltas rather than summing incompatible counters.

## GPU and acceleration

| Item | Observed |
|---|---|
| GPU | AMD Radeon 760M Graphics |
| Driver | 32.0.12033.1030 |
| Reported adapter memory | 4,293,918,720 bytes |
| GPU memory during probes | approximately 1.35 GiB dedicated and 0.74 GiB shared host graphics use |
| Ollama backend | CPU |
| Ollama model `size_vram` | 0 for generator and embedding |
| Ollama discovery | `total_vram=0 B`; default context 4096 |

Although `OLLAMA_VULKAN=true` is present, Ollama 0.32.3 in the current Docker
stack discovers only the CPU backend. The integrated GPU's shared allocation
is not usable Ollama VRAM in this configuration. No proven supported
optimization is available without changing drivers/runtime/integration, so GPU
tuning is deferred and is not needed for the 4096 recommendation.

## Qwen 3.5 9B control results

### 4096

| Metric | Generator only | With embedding |
|---|---:|---:|
| Ollama model allocation | 5.795 GiB | 5.795 + 2.208 GiB reported |
| Ollama container peak | 7.30 GiB | 8.39 GiB |
| Windows available minimum | 6.191 GiB | 5.629 GiB |
| Windows commit maximum | 26.415 GiB | 27.511 GiB |
| WSL available minimum | 7.541 GiB | 6.517 GiB |
| WSL swap maximum | 0 | 0 |
| Pagefile current maximum | 55 MiB | 51 MiB |
| Cold wall/load time | 58.78 / 40.81 s | 59.74 / 42.55 s |
| Warm median wall time | 17.89 s | 18.04 s |
| Median generation rate | 8.44 tok/s | 8.02 tok/s |
| Ollama CPU average/peak | 281% / 595% | 314% / 595% |
| Model unload | 0.51 s | 0.51 s |

### 8192

| Metric | Generator only | With embedding |
|---|---:|---:|
| Ollama model allocation | 6.026 GiB | 6.026 + 2.208 GiB reported |
| Ollama container peak | 7.38 GiB | 8.46 GiB |
| Windows available minimum | 6.168 GiB | 5.162 GiB |
| Windows commit maximum | 26.534 GiB | 27.385 GiB |
| WSL available minimum | 7.420 GiB | 6.418 GiB |
| WSL swap maximum | 0 | 0 |
| Pagefile current maximum | 51 MiB | 46 MiB |
| Cold wall/load time | 56.23 / 40.04 s | 59.79 / 41.27 s |
| Warm median wall time | 18.23 s | 18.04 s |
| Median generation rate | 8.35 tok/s | 8.21 tok/s |
| Ollama CPU average/peak | 319% / 596% | 286% / 596% |
| Model unload | 0.52 s | 0.52 s |

The compact prompts did not fill either context window. Moving 4096 to 8192
increased the resident Qwen allocation by 0.231 GiB and did not materially
change warm latency. This is evidence for the control architecture only; Gemma
and Qwen do not have identical KV-cache structures, and longer retrieved
contexts can allocate more working memory.

Every run retained backend, Postgres, Qdrant and Supervisor health. The final
analysis bridge state was `READY`, with no owner, job or waiter. No UI stall,
OOM, container restart or model-runner crash was observed.

## Switching and recovery

| Operation | Observed |
|---|---:|
| Gemma 3 4B cold wall/load | 31.07 / 27.21 s |
| Gemma 3 4B rate | 17.08 tok/s |
| Gemma 3 4B allocation at 4096 | 2.684 GiB, CPU-only |
| Gemma 3 4B unload | 0.55 s |
| Qwen 3.5 9B cold wall/load | 52.16 / 44.49 s |
| Qwen 3.5 9B rate | 8.55 tok/s |
| Qwen 3.5 9B allocation at 4096 | 5.795 GiB, CPU-only |
| Qwen 3.5 9B unload | 0.77 s in switch probe |

After all unloads, Ollama reported no resident model. WSL available memory
returned to approximately 14.63 GiB. After a further 30 seconds Windows
available RAM recovered to 12.99 GiB, commit fell to 19.54 GiB, pagefile use
was 48 MiB, and page reads/input were zero. On-demand operation is practical;
the current global `OLLAMA_KEEP_ALIVE=24h` is inappropriate for a future 12B
production role and must be overridden by bounded per-request keep-alive.

## Empirical memory model

Observed Qwen 9.65B Q4 results are primary evidence:

- mapped/resident model allocation: 5.80 GiB at 4096;
- full Ollama container increment: approximately 7.1 GiB;
- embedding coexistence increment: approximately 1.1 GiB;
- 4096-to-8192 resident delta for compact prompts: 0.23 GiB;
- non-Ollama containers: approximately 1.72 GiB;
- WSL kernel/cache/runtime reserve: approximately 1.0-1.3 GiB.

The prediction ranges account separately for Q4 weights, architecture-specific
KV/context, runner overhead, transient inference allocation, embeddings and
the unchanged service/kernel reserve. They do not use the simplistic
`parameters x 0.5 byte` formula alone.

## Gemma 3 12B Q4 prediction

The previously audited official artifact is approximately 8.1 GB decimal
(about 7.54 GiB). Actual memory cannot be proven until an approved pull; ranges
are deliberately conservative.

### 4096

| Component/outcome | Best | Expected | Conservative |
|---|---:|---:|---:|
| Q4 weights/mapped data | 7.4 GiB | 7.7 GiB | 8.1 GiB |
| Runner + KV + inference overhead | 1.1 GiB | 1.7 GiB | 2.3 GiB |
| Generator peak | 8.5 GiB | 9.4 GiB | 10.4 GiB |
| Windows available reserve with embedding | 4.8 GiB | 3.7-4.2 GiB | 2.6-3.2 GiB |
| WSL available reserve | 4.7 GiB | 3.7-4.3 GiB | 2.5-3.1 GiB |
| Pagefile behavior | none | transient safety buffer possible | abort if sustained |
| WSL swap | none | none expected | possible only near abort; not acceptable steady state |

Confidence is **MEDIUM**. The expected case fits physical RAM without normal
paging and remains above WSL inference reserve. The conservative Windows case
approaches the hard abort boundary, so concurrent large optional applications
must not be treated as free capacity. The benchmark should be serialized and
must retain the same abort gates.

Expected warm generation is about 6-7 tok/s. A compact 120-token answer is
roughly 17-22 seconds after load. Cold load plus answer is predicted at 65-100
seconds: slow but acceptable for hard analysis, not interactive routing.

### 8192

| Component/outcome | Best | Expected | Conservative |
|---|---:|---:|---:|
| Q4 weights/mapped data | 7.4 GiB | 7.7 GiB | 8.1 GiB |
| Runner + KV + inference overhead | 1.5 GiB | 2.2 GiB | 3.1 GiB |
| Generator peak | 8.9 GiB | 9.9 GiB | 11.2 GiB |
| Windows available reserve with embedding | 4.2 GiB | 2.9-3.6 GiB | 1.7-2.5 GiB |
| WSL available reserve | 4.0 GiB | 2.9-3.6 GiB | 1.7-2.4 GiB |
| Pagefile behavior | none/transient | likely transient under contention | paging-dependent/abort risk |
| WSL swap | none | possible under long context | likely near conservative peak |

Confidence is **MEDIUM-LOW** because the model is absent and Gemma KV
architecture differs. The expected/conservative cases do not preserve the
required host reserve. NEXT Stabil uses bounded retrieval and can escalate hard
multi-document cases, so 8192 is not justified as the initial production
context.

## 14B Q4 prediction

The architecture-dependent artifact/working ranges are wider than for Gemma.

### 4096

- generator peak: approximately 10.5-12.5 GiB;
- Windows reserve with embedding: best 3.2 GiB, expected 1.8-2.7 GiB,
  conservative below 1 GiB;
- WSL reserve: approximately 1.4-3.0 GiB;
- ordinary inference is likely to touch the Windows safety buffer and can
  cross WSL/host abort thresholds under concurrent load;
- predicted warm rate: roughly 5-6 tok/s; cold answer roughly 80-120 seconds;
- confidence: LOW-MEDIUM.

Verdict: **MARGINAL**. Starting may succeed, but the preferred production
reserves are not met reliably.

### 8192

- generator peak: approximately 11.2-13.8 GiB;
- Windows reserve: expected below 2 GiB and potentially exhausted;
- WSL reserve: expected near/below 2 GiB;
- sustained pagefile/WSL-swap dependence or safety abort is likely;
- predicted cold answer can exceed 120 seconds;
- confidence: LOW-MEDIUM.

Verdict: **UNSAFE**.

## Binding resources

- **Fit:** Windows physical RAM becomes binding first. The 18 GiB WSL ceiling
  is second; Windows commit limit is ample but does not make paging acceptable.
- **Latency:** CPU throughput is binding. The 760M provides zero Ollama
  acceleration in the current stack.
- **Stability:** host physical reserve, followed by WSL available memory. WSL
  swap and the Windows pagefile did not bind in the control runs.

Increasing WSL memory would reduce Windows reserve and does not solve the
physical binding resource. Therefore
`FOLLOWUP_WSL_RESOURCE_TUNING_APPROVAL_REQUIRED` is not justified. GPU/runtime
changes are also not required for the bounded 4096 trial.

## Residency recommendation

- embedding: persistent as required by existing workflows;
- Gemma 4B router/extractor: persistent only if measured concurrent demand
  justifies it; otherwise short-lived;
- Gemma 12B candidate: on-demand, serialized, `num_ctx=4096`, per-request
  `keep_alive` initially 1 minute and at most 5 minutes after operational proof;
- simultaneous 9B + 12B: rejected;
- simultaneous persistent 4B + 12B + embedding: not recommended on this host;
- after large-model work, explicitly unload and verify `/api/ps` plus memory
  recovery.

Option C—embedding persistent, 12B on-demand, router loaded only when needed—is
the safest target. It avoids the current 24-hour generator residency behavior
and accepts cold-load latency for hard analysis.

## Final health and safety

- Backend: healthy throughout and after testing.
- Postgres: healthy; schema head `followup_contact_person_20260822`.
- Qdrant: both collections green; customer 57, KB 0.
- Supervisor: healthy; analysis arbiter `READY`, no owner/job/waiter.
- Model pulls/deletes: 0/0.
- Windows pagefile, `.wslconfig`, GPU/runtime settings: unchanged.
- Production DB/Qdrant/business writes: 0.
- Gmail/n8n/Vision/Temporary Chat activity attributable to this test: 0.
- Stable release: unchanged at NEXT Stabil `1.0.2+29`.
