# P0 Unified Assistant General/System Routing Report

Date: 2026-08-25

Source baseline: `05df7fbadbfaf68eb9d7428549555f32451027f8`

Stable: `NEXT Stabil 1.0.2+29`

Decision: `SOURCE PASS / PHYSICAL RETEST REQUIRED`

## Owner-observed defect

On Android +34, an unscoped request equivalent to “Czym się tu zajmujesz w
tym systemie? Ignoruj poprzednie zapytanie.” took multiple minutes and produced
an evidence-empty refusal, a `MISSING` card, and the internal marker
`VALIDATED_EVIDENCE`. Sources simultaneously described the answer as general
knowledge. This was a task-completion, routing, missing-semantics, latency,
internal-output, and possible conversation-reset failure. It was not a
hallucination, wrong-source result, or newly observed privacy incident.

## Reproduction and root cause

A synthetic reproduction of the production service before remediation proved:

- route/tool plan: empty;
- collected sources: 0;
- local Qwen call: yes;
- prompt contained the evidence-only contract;
- prior conversation remained present despite the reset phrase;
- `MISSING` with empty evidence passed validation;
- the visible answer retained `VALIDATED_EVIDENCE`.

The root cause was in `UnifiedAssistantService.ask()`, `_route()`, `_prompt()`,
`_validate()`, `_advanced_reason()`, and `_local_response()`: there was no
top-level query-mode distinction. All non-scoped requests reached the same
evidence-centric Qwen prompt and empty customer evidence was incorrectly
allowed to become missing customer data. Flutter also used a stale/general
“Analiza rozszerzona” label before an external job existed.

## Query modes and fast path

The router now deterministically classifies:

- `SYSTEM_META` — bounded questions about the implemented Assistant/system;
- `GENERAL_KNOWLEDGE` — unscoped/general explanation;
- `EVIDENCE_GROUNDED` — Client/Candidate/Document/Mail/Visit/Visual work;
- `GLOBAL_CRM_SEARCH` — explicit search/find requests only.

No LLM planner is used. High-confidence `SYSTEM_META` returns an immediate
local capability-manifest response. It performs no CRM retrieval, Qdrant call,
generator load, or Temporary Chat job. Its only optional source is the local
system source “Możliwości Asystenta NEXT Stabil”; it does not show a misleading
“no Client sources” statement or `MISSING`.

The exact synthetic owner-equivalent after remediation produced:

- mode: `SYSTEM_META`;
- effective history: 0;
- route/tools: 0/0;
- generator calls: 0;
- Advanced Analysis: no;
- missing claims: 0;
- internal-output leak: no;
- elapsed service time: 1.44 ms in the synthetic harness.

`GENERAL_KNOWLEDGE` has a separate local prompt. It permits general FACT and
HYPOTHESIS output without fabricated Client provenance, forbids `MISSING` that
exists only because no Client was selected, performs no CRM retrieval, and
does not enter Advanced Analysis. Evidence-grounded F0, target binding, named
document prerequisites, V2, and Vision constraints remain unchanged.

## Reset and output boundary

Normalized deterministic reset intents include Polish variants of “ignoruj
poprzednie pytanie/zapytanie”, “nie bierz pod uwagę wcześniejszej rozmowy”,
“zacznij od nowa”, and “nowy temat”. They clear only effective reasoning
history. Persisted UI/audit history and selected target scope are not deleted.

Before rendering, normal user-visible answer/claim text is checked for bounded
internal markers including `VALIDATED_EVIDENCE`, opaque target/source/tool/
visual handles, internal refs, Temporary Chat contract names, and quality-gate
language. Exact allowlisted citation handles are removed from prose while
structured provenance remains intact. Unknown/internal content fails closed
after one bounded correction; arbitrary semantic repair is not attempted.

Flutter now distinguishes local analysis, delayed local analysis, waiting for
external analysis, external analysis, and result verification. Local work is
never labelled Advanced Analysis before an external job exists.

## Verification

- Python syntax compilation: PASS.
- Focused Unified Assistant and supplementary backend suite: 76/76 PASS.
- Supplementary routing matrix: 30/30 PASS (10 system, 10 general, 5 reset,
  5 negative router cases).
- Supplementary task completion: 100%.
- Incorrect `MISSING`: 0.
- Internal term leaks: 0.
- Unnecessary CRM retrieval: 0.
- Unnecessary Advanced Analysis: 0.
- Named-document exact/ambiguous/not-found/cross-Client/content/Sources tests:
  PASS.
- Supervisor queue timeout, external timeout, cancel, late-result, retry ID,
  V2 interoperability, recovery, and idempotency regressions: PASS.
- Qwen unload-before-external-wait behavior: preserved and covered.
- Flutter analyze: PASS, zero issues.
- Focused Unified Assistant Flutter tests: 4/4 PASS.
- Full Flutter suite: 304/304 PASS.

## Frozen F0 replay

The immutable 50 cases were replayed through the implemented validation and
display-normalization path, reusing the already qualified saved local and
synthetic/public-safe V2 results. No new external submission was made.

| Metric | Result |
| --- | ---: |
| Overall | 88.66 |
| Factual / evidence | 95.50% |
| Technical documentation | 95.28 |
| Cross-domain | 85.85 |
| Estimate / refusal | 78.00% |
| Wrong source | 0 |
| Material hard failures | 1/50 (2.00%) |
| Privacy failures | 0 |
| Automatic coverage | 50/50 |
| Local / advanced | 35 / 15 |

This passes the unchanged requested thresholds. The replay score is reported
as observed; historical higher qualification scores are not substituted.

## Android candidate

VersionCodes 35 and 36 remain consumed. +36 was not overwritten and is
superseded for final acceptance because it lacks this remediation.

The canonical release flow created the non-stable physical-retest candidate:

`C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+37-unified-assistant-final-p0-candidate.apk`

- versionName/versionCode: `1.0.2` / `37`;
- application ID: `pl.ailab.app`;
- bytes: `67,398,751`;
- SHA-256: `E6E2742FCBACF193676E7CCB82E4E8D5AD6C75CA47034BC5C35B02E8BB662F31`;
- signer SHA-256:
  `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`;
- explicit API in ARM64 AOT payload: `https://domai.tail1927bd.ts.net`;
- emulator API fallback in ARM64 AOT payload: absent;
- debuggable: absent/false;
- cleartext traffic: false;
- published: no.

No physical PASS is inferred. Owner retest must cover the system/meta prompt,
general knowledge, the named Client PDF, Sources, bounded latency, accurate
progress/cancel, and Clients/Search/Mail/Documents/Backup/System Control smoke.

## Safety and roadmap

DB migration/write, business writes, Qdrant writes/deletes, Gmail, n8n, model
changes, resource-limit changes, backup deletion, real-customer external jobs,
and stable publication were all zero. The Release F Ignore-mail address/domain
UI reminder remains mandatory and unimplemented.

Roadmap after source acceptance:

- `P0 GENERAL/SYSTEM ROUTING = SOURCE PASS / PHYSICAL RETEST REQUIRED`;
- `P0 DOCUMENT RETRIEVAL/LIFECYCLE = SOURCE PASS / PHYSICAL RETEST REQUIRED`;
- `PRE-CHUNK23 = UNIFIED ASSISTANT IMPLEMENTED / PHYSICAL ACCEPTANCE REQUIRED`;
- `CHUNK23 = BLOCKED / NOT STARTED`.
