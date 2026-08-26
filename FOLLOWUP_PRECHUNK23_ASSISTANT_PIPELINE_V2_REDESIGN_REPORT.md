# PRE-CHUNK23 Assistant Pipeline V2 redesign

Date: 2026-08-26
Source baseline: `b2c6d8f840bdc0e722066f3720e5351e5a8a219b`
Stable: `NEXT Stabil 1.0.2+29`
Production DB head: `followup_assistant_file_pipeline_20260826`
Decision: `FOLLOWUP_ASSISTANT_PIPELINE_V2_SCHEMA_APPROVAL_REQUIRED`

## Outcome

The owner-rejected +40 architecture has been forensically reproduced and its
boundary is proven. It durably prepares bytes and text, but it does not create
a reusable document-intelligence artifact and does not make final reasoning a
durable stage. A prepared-text request is still executed inside one call to
`UnifiedAssistantService.ask()` with a 105-second evidence deadline.

A clean additive V2 schema has therefore been created at revision
`followup_assistant_pipeline_v2_20260826`, parent
`followup_assistant_file_pipeline_20260826`. It introduces first-class
Assistant runs, auditable stage attempts, material/source dependencies and
checksum/generation-bound document intelligence with normalized page/asset
provenance. The exact migration passed isolated upgrade, downgrade and
re-upgrade. It creates no historical work and changes no existing jobs.

The migration was **not applied to production**. Runtime/API/Flutter V2 work is
intentionally blocked until the owner approves this exact schema. +40 remains
superseded and unpublished. CHUNK23 remains blocked/not started.

## Read-only production preflight

- backend `/health`: PASS (`{"status":"ok"}`);
- production DB head: `followup_assistant_file_pipeline_20260826`;
- active Backup runs: `0`;
- active Restore runs: `0`;
- active Document preparation jobs: `0`;
- active KB processing jobs: `0`;
- Supervisor analysis queue: `READY`, active `0`, queued `0`, arbiter owner
  `none`, waiters `0`;
- Ollama residency: `qwen3-embedding:0.6b` only, 2.4 GB; Qwen9 not resident;
- Qdrant: `ai_lab_document_chunks` green / 57 points and
  `ai_lab_knowledge_base_chunks` green / 56 points;
- public ingress guard: PASS, public origin targets `127.0.0.1:8789`, public
  `/control` remains 404;
- no current critical restore, migration or business write was found.

The database still contains 15 old `advanced_queued` rows created on
2026-08-24, last updated no later than 07:19 UTC. The private Supervisor proves
that none is active or queued. They were not changed. Their divergence is a
useful recovery test case for V2, not evidence of current compute activity.

The running backend files exactly match the +40 Git worktree:

| Runtime file | SHA-256 |
| --- | --- |
| `unified_assistant_service.py` | `43c0445c74890ca5aba93a1bcfea63304f53ed330f3ad40d7bd571c3809bb4a7` |
| `document_preparation_service.py` | `2c0616d18357c89930cf94d859369e1f847fa9da3beef28d2c8f61880ab07c8a` |
| `document_preparation_dispatcher.py` | `2e8f6c4b687c9b0a7004485600b9b39314d431ef6d384e3d3f85574b07aa1322` |
| `document_preparation_job.py` | `7e98c0e85a0cd817575d641911acde557c8d71cd0edd639984f29034fb6d0328` |
| `knowledge_base.py` | `11dbebdaba0a729cf04c2f3c20962c2f236a0607b76e51d3a3cf2936f080d92b` |

## +40 physical-request forensics

No customer identity, filename, prompt text or document content is recorded in
this report. The selected Client is represented only by the redacted hash
`2fa382a80d7c`; its active SQL allowlist contained eight Documents.

The physical-equivalent job resolved a unique Document (`document_id=5848`).
Its structural state was:

- `processing_status=processed`;
- PDF, 331,458 bytes, canonical checksum present;
- `Document.extracted_text`: 5,583 characters;
- pages: 2/2 with extracted text, 2/2 with OCR, 2/2 rendered;
- preparation generation: `document-preparation-v1`;
- preparation job: queued 06:24:48.934 UTC, started 06:24:50.296, marked
  `ready/ready_for_ai` 06:24:52.586;
- `_document_needs_preparation(document_id)`: `false` after preparation;
- planner route: `EVIDENCE_GROUNDED`, unique document match;
- collected evidence: six sources (`document` + `knowledge_base`), three tools,
  2,896 evidence characters;
- generated prompt: 10,177 characters. Exact tokenizer count was not exposed;
  no estimate is presented as a measurement.

The initial `/assistant/ask` returned HTTP 200 and the client polled the durable
wait ID. When preparation became ready, `resume_waiting_analysis()` loaded the
stored request and called `UnifiedAssistantService.ask()` again. The resumed
call entered the normal evidence prompt and the same 105-second local deadline.
The waiting AnalysisJob finished at 06:26:39.196 as:

- persisted job status: `failed`;
- response status: `timed_out`;
- response stage: `local_analysis_timeout`;
- model result: none;
- total run duration: approximately 110.3 seconds;
- duration after preparation READY: approximately 106.6 seconds.

There is no persisted Qwen-start or token heartbeat in +40, so an exact model
start timestamp cannot be proven. The transition timing and source path prove
that Qwen began only after the preparation completion and exhausted the
105-second deadline.

The current broad-KB path has the same architectural risk. An explicit broad
KB question without one resolvable item enters `EVIDENCE_GROUNDED`, retrieves
bounded KB evidence and then uses the same synchronous evidence reasoning
deadline. It has no durable catalog/plan stage. The V2 planner must instead use
a deterministic catalog fast path for broad inventory questions and durable
reasoning only when actual synthesis is requested.

### Proven semantic error

The physical document had:

- `FILE_VALIDATED`: yes;
- `CONTENT_READY`: yes;
- `INTELLIGENCE_READY`: no durable artifact exists;
- `QUERY_READY`: no; query-specific evidence selection and synthesis had not
  completed.

Therefore:

`CONTENT_READY != DOCUMENT_ANALYZED != QUERY_READY`.

The +40 name `ready_for_ai` is only a legacy text-readiness marker. Under V2 a
new processor generation may mark a material ready only after a validated
intelligence artifact exists for the exact checksum.

## V2 responsibility model

```text
AssistantRun
|- AssistantRunStage attempts and heartbeats
|- AssistantRunMaterial allowlist/source manifest
|- DocumentPreparationJob(s)             FILE_VALIDATED / CONTENT_READY
|- DocumentIntelligenceArtifact(s)        INTELLIGENCE_READY
|- AnalysisJob(s)                         bounded local/advanced compute child
|- private Vision/Supervisor job(s)       validated visual child
|- controlled Temporary Chat V2 job       optional external child
`- persisted final response + claim-linked Sources
```

`AssistantRun` is the user-owned orchestration aggregate. `AnalysisJob` is no
longer overloaded as conversation, file waiter, local call, external call and
final answer. `DocumentPreparationJob` remains the canonical material job and
will advance a new V2 processor generation through validation, extraction,
OCR/Vision and baseline intelligence. KB keeps its separate CHUNK16 processing
and artifact tables and exposes equivalent readiness to the run planner.

## Material levels

1. `FILE_VALIDATED`: authoritative bytes exist; checksum, declared MIME,
   extension and magic agree; ownership and provenance are known.
2. `CONTENT_READY`: native text, OCR text or validated visual observations are
   available with page/asset provenance and bounded retrieval units.
3. `INTELLIGENCE_READY`: an accepted artifact exists for exact
   `(document_id, checksum, analyzer_generation, kind)` and its normalized
   source bindings validate.
4. `QUERY_READY`: a particular run has selected relevant original evidence,
   optional relevant KB/tool evidence, and completed source-bound synthesis.

Level 2 never implies Level 3. Level 3 is reusable across later questions;
Level 4 belongs to one AssistantRun.

## Exact additive schema

Migration:
`backend/alembic/versions/followup_assistant_pipeline_v2_20260826.py`.

### `document_intelligence_artifacts`

The artifact is bound to Document, exact checksum, analyzer generation and
kind. It records status, validation state, sensitivity, bounded JSON payload,
payload hash, preparation job, processor/version, optional model/tool identity
and lifecycle timestamps. The unique generation constraint prevents duplicate
artifacts. A partial unique index permits only one accepted, validated,
non-superseded artifact of a kind for a Document.

The payload may contain only product-level intelligence such as document
class/language, concise summary, topics, explicit facts, measured parameters
and units, conclusions, recommendations, warnings, limitations, evidence
quality and unreadable/missing sections. It must not contain hidden
chain-of-thought.

### `document_intelligence_sources`

Provenance is normalized rather than hidden inside unrelated JSON. Each
artifact source handle binds to a canonical document/page/asset/chunk or
validated Vision observation, source entity, page, source checksum, optional
excerpt hash and a bounded role. Final artifact claims may use only these
allowlisted handles.

### `assistant_runs`

The run records owner, idempotent attempt ID, V2 API version, input fingerprint,
bounded request, opaque target scope, deterministic complexity, state/current
stage, plan, result, sensitivity, priority, recovery generation, heartbeat,
cancellation and lifecycle timestamps. `(user, attempt_id)` is unique. Tokens,
credentials, raw external session data and chain-of-thought are forbidden by
the application contract.

### `assistant_run_stages`

Every attempt is auditable. A row records run, stable stage key/type, ordinal,
attempt/max attempts, queued/waiting/running/terminal state, progress
current/total/unit, lease, heartbeat, inactivity timeout, absolute cap, error,
and typed references to a preparation job, intelligence artifact, AnalysisJob
or private external job. The schema prevents negative progress, over-total
progress and invalid timeout/attempt bounds.

### `assistant_run_materials`

Every allowed material/source is bound to a run-local handle, domain, canonical
entity, case/reference/visual/tool role, required flag, readiness level,
checksum, relevance, preparation/artifact references, sensitivity and a
bounded source manifest. It is the fail-closed source allowlist used by local,
Vision and Advanced validation.

No existing table is altered. Existing `analysis_jobs` and
`document_preparation_jobs` remain intact.

## Additive API and compatibility

After schema approval, implement:

- `POST /api/v1/ai/assistant/runs` — validate, persist plan/run and return 202
  within a 5–10 second bound;
- `GET /api/v1/ai/assistant/runs/{id}` — owner-authorized durable state,
  progress and final response;
- `POST /api/v1/ai/assistant/runs/{id}/cancel` — cancel the run consumer and
  suppress stale result binding, without automatically cancelling shared
  material preparation.

Stable +29 and deployed consumers remain supported. Existing `/assistant/ask`,
status and cancel contracts must remain until the minimum supported app
version permits retirement. The compatibility adapter may create/read a V2 run
but may not change the legacy response shape.

No API route or runtime worker is enabled in this schema-gated checkpoint.

## New-file and historical pipelines

The already-audited canonical ingress set contains 13 classes: Documents,
Client, Candidate/import, incoming Mail, Task, Note, Project, Realization,
Visit, Inspection/local vision, camera/gallery, bounded ZIP children and the
separate Knowledge Base pipeline. Derived page/assets are not independent
business ingresses.

After approval every supported new Document ingress must atomically create/join
the exact V2 material generation after the business relation is committed.
Heavy work remains asynchronous:

`validate -> extract/render/OCR/Vision -> sections -> baseline intelligence -> validate -> INTELLIGENCE_READY`.

Images use only validated Vision observations; scanned PDFs use native
extraction, bounded renders and OCR, with Vision only where required. No raw
file is sent to Temporary Chat during ingestion. Executables, encrypted or
unsupported containers and extension/MIME/magic mismatches fail closed with
actual supported alternatives. New parser dependencies remain behind
`FOLLOWUP_FILE_FORMAT_SUPPORT_APPROVAL_REQUIRED`.

Historical files are lazy only. An exact resolved Document creates or joins a
new checksum/analyzer generation, wakes all authorized waiting runs after the
artifact passes, and reuses the result later. There is no historical scan,
bulk OCR or customer-vector backfill.

## Planning, KB and reasoning

Top-level routing remains deterministic:

- `FAST`: system/capability/UI help and bounded KB catalog/status;
- `STANDARD`: one prepared source and limited synthesis;
- `DEEP`: long/multiple sources, calculations, contradictions or conclusions;
- `VISUAL`: validated visual evidence required;
- `EXTERNAL_CANDIDATE`: local path plus current difficulty/quality/privacy gate.

An exact KB item remains deterministic and source-bound. A broad catalog
question returns a bounded list of current categories/topics rather than
loading the KB into Qwen. Technical case planning derives search concepts from
the question plus prepared document topics, runs hybrid current-only KB
retrieval, keeps only relevant hits and continues with general inference if no
KB is relevant. KB is reference knowledge and never overwrites case-specific
measurements. Conflicts are surfaced. Proprietary KB remains blocked from
external analysis without per-item sensitivity classification.

Long documents use persistent map/reduce/synthesize stages:

- map bounded sections into page-bound findings;
- reduce duplicates, conflicts and missing inputs;
- synthesize from the intelligence artifact plus query-relevant original
  pages, relevant KB and tools;
- reuse completed intermediates after interruption.

General model reasoning is an inference/hypothesis, not a Client fact. Existing
FACT/ESTIMATE/HYPOTHESIS/MISSING, TARGET/source, Temp Chat V2, Vision and hard
privacy gates remain unchanged.

## Progress-aware time model

The following policy is the implementation benchmark, not production runtime
configuration in this checkpoint:

| Stage class | Inactivity target | Absolute cap | Notes |
| --- | ---: | ---: | --- |
| Create/plan HTTP | 5 s | 10 s | Persist run only; no model work |
| Deterministic FAST | 10 s | 30 s | No generator for high-confidence fast paths |
| Retrieval | 30 s | 120 s | Heartbeat per source/domain |
| Native preparation | 120 s | 3,600 s | Progress by bytes/pages |
| OCR/Vision preparation | 180 s | 21,600 s | Progress by page/asset |
| Standard local call | 90 s | 300 s | Active compute only; benchmark 180–240 s normal cap |
| Deep local stage | 120 s | 1,200 s | Multiple bounded stages; run may total 10–20 min |
| Controlled Vision | 180 s | 3,600 s | Private durable child |
| Temporary Chat V2 | 180 s | 1,800 s | Durable polling; larger than former 180 s wall limit |
| Queue/backoff/wait | heartbeat/state based | 86,400 s | Does not consume active compute budget |

A stage is reclaimed only after lease expiry and scope/checksum revalidation.
It fails on bounded inactivity, absolute cap, retry exhaustion or a hard
integrity/privacy/authorization failure. Queue and paused time do not consume a
model budget.

The current `OllamaClient.generate()` accepts a `stream` argument but posts once
and calls `response.json()`, so it does not consume NDJSON streaming and cannot
persist load/prompt/token heartbeats. V2 implementation must add a bounded
streaming adapter that records only stage telemetry (load/prompt/generation,
token count/rate and last progress), never generated reasoning text or hidden
chain-of-thought.

Qwen9 is loaded only during active local stages and unloaded before long
material, Vision or external waits. Heavy generator/Vision work remains serial
under the existing arbiter, with P0/P1/P2/P3 priority and fair aging.

## Frontend contract after approval

Flutter create/status/cancel calls use short transport deadlines. Analysis
lifetime is the durable run, never a 160-second receive timeout. On reopen the
app lists/restores the user's active runs, shows only proven stages and binds a
late result only to the matching run/attempt/recovery generation. Multiple runs
must not overwrite one request ID.

Truthful messages derive from persisted stages, including material lookup,
page progress, KB retrieval, local synthesis, source validation and Advanced
analysis. Sources remain collapsed and claim-linked. Cancel ends the run
consumer immediately; shared preparation may finish for future use.

No Flutter source changed and no APK was built. +40 remains superseded and
unpublished.

## Migration proof

Test:
`backend/test/test_followup_assistant_pipeline_v2_migration.py`.

On the disposable database
`ai_lab_isolated_assistantv2_20260826` the following passed:

- parent -> V2 upgrade;
- V2 -> parent downgrade;
- parent -> V2 re-upgrade;
- all five new tables and required constraints/indexes;
- existing AnalysisJob row count unchanged;
- existing DocumentPreparationJob row count unchanged;
- AssistantRun backfill: `0`;
- document intelligence backfill: `0`.

The isolated database was verified, disconnected and removed after proof.
Alembic reports one source head. Production remains at the parent revision.

## Tests deferred by the schema gate

Owner-case execution, new-ingress processing, historical lazy material
analysis, >130-second local completion, >180-second external completion,
stall/restart recovery, Flutter polling and F0 runtime replay require the new
tables and V2 services. They were not fabricated or marked PASS here. They are
the mandatory implementation acceptance matrix after schema approval.

## Resource snapshot

- Windows RAM: 27,704,942,592 bytes total; 10,820,759,552 bytes free;
- WSL RAM: 18,858,258,432 bytes total; 14,461,112,320 bytes available;
- WSL swap: 8,589,934,592 bytes total; 0 used;
- Qwen9 resident: no;
- embedding resident: yes;
- Supervisor heavy owner/waiters: none/0;
- proposed heavy concurrency: one generator/Vision owner; native extraction
  remains bounded and fair.

No resource limits were changed.

## Production safety

- production migration: not applied;
- production DB head: unchanged;
- production Assistant/Document/KB/business writes: 0;
- historical jobs/backfill/OCR: 0;
- Qdrant writes/deletes: 0/0;
- external customer jobs: 0;
- model pulls/deletes: 0/0;
- Gmail/n8n: 0/0;
- backup deletion: 0;
- Tailscale/WDAC/firewall: unchanged;
- release/publication/APK build: 0.

The Release F reminder remains mandatory and unimplemented:
`RELEASE F REQUIRED UI MICRO-FIX — IGNORE MAIL ADDRESS/DOMAIN` for Candidate
Details, Global Mail and Client Emails, including add/undo exact-address and
domain rules.

## Required next owner gate

Approve only the exact additive revision:

`FOLLOWUP_ASSISTANT_PIPELINE_V2_SCHEMA_APPROVAL_REQUIRED`

- revision: `followup_assistant_pipeline_v2_20260826`;
- parent: `followup_assistant_file_pipeline_20260826`;
- production backfill: none;
- purpose: first-class durable runs/stages/materials and reusable,
  source-bound Document intelligence;
- rollback: downgrade removes only the five new empty/V2-owned tables;
- after approval: create a CHUNK15 database checkpoint, repeat the isolated
  proof, apply only this revision, then implement the versioned API, workers,
  ingress adapters and Flutter durable-run UX in a bounded execution.

PRE-CHUNK23 remains blocked on this schema approval and subsequent source,
runtime and owner physical acceptance. CHUNK23 remains blocked/not started.
