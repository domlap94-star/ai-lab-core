# P0 Document Content + Capability / General Latency

Date: 2026-08-25

Source baseline: `b594e53d7bc7bfb3871470050d3b069bda154ac2`

Stable remains: `NEXT Stabil 1.0.2+29`

Decision: `P0_DOCUMENT_AND_GENERAL_RESOLVED_PHYSICAL_RETEST_REQUIRED`

## Scope and physical evidence

The owner physically accepted the deterministic `SYSTEM_META` answer for
"Czym zajmujesz się w tym systemie?". A named Client PDF resolved to the
correct row but was rejected because persisted extraction was empty. The
unscoped capability question about access to the document repository missed
the capability router, loaded Qwen and ended after several minutes with a
generic server error.

The exact prior document identifier was not durably recorded: terminal
document resolution returned before an `AnalysisJob` was created and request
bodies are intentionally absent from production logs. The investigation did
not guess among Client documents and did not read multiple production files.
Consequently the prior file's size, checksum result and extraction status are
`NOT RECOVERABLE FROM DURABLE METADATA`; the same named-file physical retest is
the final proof for that exact file. No filename, Client identity or document
content is included here.

## Root causes

1. `UnifiedAssistantService._document_has_content()` treated only
   `Document.extracted_text` or persisted `DocumentPage` text as content. It
   never checked whether the authoritative stored PDF was itself readable.
2. `SYSTEM_META` used a narrow phrase list. Capability/access language such as
   "masz dostęp do repozytorium dokumentów" fell into `GENERAL_KNOWLEDGE`.
3. The old general path used the full evidence F0 schema (`num_ctx=4096`,
   `num_predict=480`). Production logs for the physical failure show a Qwen9
   cold load, about 753 prompt tokens and cancellation at the 120-second local
   deadline. The cancelled Ollama request surfaced as HTTP 503.

## Read-only document content access

`UnifiedDocumentContentService` now applies this order:

1. persisted page extracted/OCR text;
2. persisted document text;
3. strict read-only extraction from the authoritative original;
4. explicit OCR-required state;
5. bounded unsupported/not-found/read-failed/integrity states.

The fallback resolves the file under `settings.data_dir`, rejects storage-root
escape, verifies the stored SHA-256 when present, and calls the existing
`DocumentExtractionService`. PDF extraction now preserves page numbers.
Query-relevant evidence is limited to eight pages, 800 characters per page and
12,000 characters total. Its provenance records document, original-file read,
extractor and page number; no fake `DocumentPage` identifier is created.

The service never adds, flushes or commits a `Document`/`DocumentPage`, never
changes processing state and never writes Qdrant. A live synthetic PDF smoke
after backend reload returned:

- state `FILE_FOUND_EPHEMERAL_TEXT_AVAILABLE`;
- extractor `pypdf`;
- 84 extracted characters from page 1;
- SQLAlchemy new/dirty/deleted sets `0/0/0`.

Scanned files without usable native text return
`FILE_FOUND_REQUIRES_OCR`. Existing persisted OCR remains supported. This
execution did not create temporary renders or implement a new historical OCR
pipeline. If the owner's exact physical PDF proves to be a scan without
existing validated visual evidence, the next gate is
`FOLLOWUP_ON_DEMAND_DOCUMENT_OCR_DESIGN_REQUIRED`; no backfill is implied.

User-visible terminal states now distinguish missing file, pending processing,
OCR required, unsupported format, read failure and integrity mismatch instead
of collapsing them into one unavailable message.

## Capability routing

The deterministic capability classifier now recognizes bounded combinations
of access/capability language and actual system domains: documents/repository,
mail, Client/Candidate data, images/Vision, Sources and the Assistant itself.
A specific filename or explicit action on a selected record remains evidence-
grounded. No LLM router was introduced.

The local capability manifest truthfully says that access is limited to data
stored and related in NEXT Stabil under the current user's permissions; it
does not claim arbitrary host filesystem access. Live authenticated smoke for
"Masz dostęp do repozytorium dokumentów?" returned HTTP 200 in 130.7 ms with:

- stage `SYSTEM_META`;
- model `null`;
- tools `[]`;
- no `MISSING`;
- local `system_capabilities` source.

The 25-case capability matrix routes all cases to `SYSTEM_META` with zero Qwen,
CRM or Advanced calls.

## General-knowledge contract and latency

General knowledge now uses a separate minimal JSON contract containing only
`answer`, `num_ctx=2048` and `num_predict=160`. Local output is converted to
the existing `UnifiedAssistantResponse`; it has no customer Sources and cannot
create CRM-driven `MISSING`. Internal markers still fail closed and allow at
most one format-only correction. Evidence-grounded F0 prompts and gates are
unchanged.

The selected model remains `qwen3.5:9b`. Final 20-case public-safe Polish
qualification of the optimized prompt produced 20/20 completed answers, no
customer fabrication and no material factual error observed. Timing:

| Path | cold p50 | cold p95 | warm p50 | warm p95 |
| --- | ---: | ---: | ---: | ---: |
| Qwen9 optimized | 64.739 s | 64.965 s | 12.863 s | 16.309 s |
| Qwen7 optimized comparison | 46.166 s | 53.141 s | about 10.9 s | 18.072 s |

Qwen7 is rejected for this role. It materially misdefined differential
settlement and thermal bridge, produced other weak technical statements, one
empty result and `sync` instead of the area result `28`. It therefore fails
the zero-material-error gate despite a lower cold load time.

The old physical path exceeded 120 seconds. The optimized live production
cold request completed as `accepted_local` in 62.561 seconds; the immediate
warm request completed in 13.669 seconds. The general-only hard deadline is 75
seconds, above measured cold p95 but below the old 120-second ceiling. A
timeout now returns typed `timed_out` with a bounded Polish message, not HTTP
500/503. Existing Flutter UX already shows "Analiza trwa dłużej niż zwykle",
keeps local work distinct from Advanced, cancels the HTTP wait and prevents a
late response from binding. Backend cancellation/timeout performs best-effort
Qwen unload.

Cold latency remains visible and is not represented as instant. The
high-confidence capability cases that caused this P0 do not incur it.

## Regression and safety

- focused Assistant/document tests: 101/101 PASS;
- expanded Assistant, contract, document, Advanced, Vision and Qdrant guard:
  118/118 PASS;
- Flutter analyze: PASS, zero issues;
- full Flutter suite: 305/305 PASS;
- saved immutable F0 replay: 35 local + 15 advanced, 50/50 automatic,
  overall 88.03, factual/evidence 94.50%, technical documentation 95.16,
  cross-domain 85.85, estimate/refusal 78.00%, wrong sources 0, privacy
  failures 0, hard failures 1/50 (2.00%);
- new external Temporary Chat/Vision calls: 0;
- public ingress check after reload: PASS; public `/control` remains 404.

The persistence regression test correctly refused to run against production
`ai_lab`; it was not bypassed. No DB migration or production mutation was used.

## Runtime and next gate

Before reload there were zero active backup/restore runs. Fifteen
`advanced_queued` rows were stale from 2026-08-24 07:08–07:19 UTC; they were
not modified. Only the backend container was restarted. Supervisor source was
unchanged and was not restarted. Backend `/health` and the public-ingress guard
pass after reload.

Android source did not change. Candidate `1.0.2+37` remains reusable;
versionCode 38 was not consumed and nothing was published. Physical retest must
cover the same named PDF, repository-capability question, real general query,
Sources, and existing cancel/regression checklist. PRE-CHUNK23 and CHUNK23
remain blocked until owner acceptance.

Production safety: DB migration 0; business writes 0; Document/Page historical
writes 0; Qdrant writes/deletes 0/0; Gmail 0; n8n 0; model downloads/deletes
0/0; backup deletion 0; stable publication 0.
