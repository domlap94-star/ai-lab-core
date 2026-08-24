# FOLLOW-UP AI ASSISTANT RECONSTRUCTION DESIGN

Status: design only; implementation is blocked until local-model qualification and owner decisions are complete. This document does not authorize production data use, model downloads, Qdrant backfill, or a user-interface rewrite.

## Problem statement

The current UI presents Business, Technical and Agent as separate modes. The backend repeats retrieval, prompting, source formatting and failure handling across those paths. Physical acceptance exposed the user-visible consequences: shallow synthesis, irrelevant missing-data lists, weak or mismatched source selection, ignored tool output, document questions answered with generic expertise, and valid JSON that does not answer the question. The mode choice also prevents a normal question from using all relevant domains.

The replacement is one read-only **Asystent AI**. Existing Business/Technical/Agent services may remain temporary internal adapters during migration, but no longer define the user's reasoning boundary. No further feature accretion should be made to those mode-specific prompts.

## Unified user experience

The page has one natural-language input and one response stream. Useful quick commands remain, but are merely prefilled queries routed through the same orchestrator:

- Podsumuj ten przypadek
- Co sprawdzić podczas wizji lokalnej?
- Jakich danych brakuje?
- Co mówi dokumentacja?
- Znajdź najnowsze dokumenty
- Podsumuj ostatnią aktywność

The normal answer leads with the answer, then only useful labelled sections. Empty FACT/ESTIMATE/HYPOTHESIS/MISSING sections are omitted. A substantive answer always has a collapsed **Źródła** control immediately below it.

## Canonical orchestration

```text
user query
  -> deterministic identity/scope binding
  -> intent + difficulty assessment
  -> minimum evidence-domain plan
  -> read-only tools and bounded retrieval
  -> local reasoning
  -> deterministic usefulness/privacy/grounding gate
     -> accept local, or
     -> sanitize minimal package and controlled Temporary Chat/Vision
  -> strict result/schema/source/package validation
  -> deterministic calculations and local post-validation
  -> minimized natural answer + claim/source graph
```

The orchestrator owns request identity, user/client scope, evidence allowlist, tool budget, model routing, escalation and the final response contract. A caller cannot force external processing. A model cannot bypass a deterministic gate by declaring confidence.

## Intent, difficulty and tools

Intent assessment identifies the evidence needed rather than choosing a persona. Available read-only domains are Client, Contact Persons, Mail, Documents/pages, Activity, Work Items, Projects, Visits, Knowledge Base, deterministic calculations and validated visual observations. Retrieval is scoped before ranking. Similar customer records are never pooled, and every source is bound to the request's client/analysis identity.

Difficulty signals include multi-document synthesis, contradiction density, technical calculation requirements, table/standard comparison, visual evidence, coverage loss, model uncertainty and local validation disagreement. Small qualified models may route, classify, rewrite queries or extract. Only a model meeting the final-reasoning threshold may produce a final local answer.

## Evidence and information classes

Every material internal claim is one of:

- `FACT`: directly supported; at least one allowlisted source reference is mandatory.
- `ESTIMATE`: a bounded approximation. It includes value/range, `HIGH|MEDIUM|LOW` confidence, basis, assumptions and missing inputs. Confidence is categorical, never a fabricated percentage.
- `HYPOTHESIS`: plausible but unproven; it includes supporting and contradictory evidence plus a confirm/refute step.
- `MISSING`: information materially needed for this question and absent from retrieved evidence; it states why it matters.

Missing data never means a generic CRM completeness checklist. After identifying a material gap, the orchestrator applies the estimation gate. An estimate is allowed only when it is relevant, has a defensible rule/evidence basis, assumptions are explicit, uncertainty is communicable and false precision can be avoided. Otherwise the canonical result is: `Brak wystarczających danych do wiarygodnej estymacji.` Deterministic tools take precedence over free-form model arithmetic.

## Quality and hallucination gates

Schema validity is necessary but insufficient. The usefulness gate checks whether the actual question was answered, required evidence is covered, cited sources are relevant, the synthesis is non-generic, tool results were used, contradictions were handled, unsupported claims are absent, uncertainty is calibrated and estimates satisfy the estimation contract.

Hard failures override numeric score:

- invented material fact or nonexistent tool result;
- wrong-client/source binding or irrelevant evidence used as proof;
- claim that a document/image was seen when its extractor/visual path did not run;
- estimate represented as fact or unjustified numeric precision;
- ignored explicit contradiction;
- unnecessary sensitive identity disclosure.

The production qualification threshold is fixed before model runs: overall at least 80/100; factual/evidence accuracy at least 90%; material hallucination at most 2%; wrong-client/source leakage zero; privacy hard failures zero.

## Sources inspector and traceability

`Źródła` is collapsed by default. It contains only evidence actually supplied to and used by the accepted reasoning result—not an entity dump. Each item contains source type, title/page descriptor, bounded relevant excerpt or fact, why it was used and supported claim IDs. Identity fields such as email, phone, address, NIP or REGON are excluded unless genuinely necessary to the question.

The response artifact stores a claim graph:

```text
claim_id -> class -> source_refs -> tool_result_refs -> validation state
```

For estimates the inspector shows facts, calculation/rule, assumptions and missing inputs; the estimate itself is not a source. For hypotheses it shows support, contradiction and missing confirmation. Visual claims point to the image/page and the structured visual observation actually consumed. Controlled external reasoning is disclosed as `Analiza rozszerzona: pakiet zsanityzowany, wynik zwalidowany lokalnie`; transport/session secrets and the unsanitized package are never shown. General-knowledge answers truthfully say that no customer-data source was used.

## Privacy minimization

Retrieval produces a bounded evidence envelope containing only necessary fields. Source text is untrusted data. Customer scope is enforced before retrieval and repeated in source binding. The existing sensitivity policy remains:

- `public_reference`: external eligible only after quality/difficulty gate;
- `customer_sanitizable`: external eligible only after sanitizer pass;
- `internal_non_sensitive`: local or review when insufficient;
- `restricted_never_external`: always review-required, never external.

External results cannot directly mutate CRM, documents, Knowledge Base, Qdrant, Gmail, n8n or files. External-result privacy scanning, manifest/package/source binding and local post-validation remain mandatory.

## Temporary Chat and visual analysis

The canonical local-first bridge from CHUNK17 remains first-class. Temporary Chat is for difficult technical reasoning, cross-domain synthesis, multi-document interpretation, standards/table/consistency work and defensible hard estimates only when the local gate fails and privacy permits. Normal persistent Chat is forbidden.

Visual requests route through the controlled visual-analysis pipeline. A text-only model cannot issue a visual fact. Structured observations are validated locally and then become allowlisted evidence for combined reasoning. Complex photo + document + CRM synthesis is an expected controlled-escalation case.

## Local model roles

Qualification assigns each installed model exactly one outcome: `KEEP — FINAL REASONING`, `KEEP — ROUTING / EXTRACTION`, `KEEP — EMBEDDING`, `KEEP — SPECIALIZED`, or `RETIREMENT_RECOMMENDED`. A small model failing final synthesis may still be retained for bounded routing/extraction. The embedding model is assessed separately and does not reopen the CHUNK18 production-vector decision.

## Evidence-based pipeline decision (2026-08-24, Qwen7/Phi round)

The frozen multi-model qualification rejects free-form and structured
Gemma-4B handoffs as production roles. Gemma planning failed deterministic
validation on 43/50 cases; its document-specialist artifacts were inadmissible
on 40/40 eligible cases. Both variants added an independent model load without
improving accepted final quality.

The preferred pipeline is therefore deliberately small:

```text
deterministic scope + intent/domain router
  -> bounded retrieval and deterministic tools
  -> unified evidence artifact v1
  -> qwen3.5:9b @4096, think=false, on demand
  -> deterministic usefulness/source/privacy gate
     -> accept local, or
     -> sanitize and use controlled Temporary Chat / Vision
  -> strict local post-validation
```

The evidence artifact is defined by
`backend/test/fixtures/unified_evidence_artifact_v1.json`. No downstream stage
may detach a claim from its allowlisted source refs; tool-result claims inherit
the tool result's underlying refs. Invalid specialist output is discarded,
never “cleaned up” by a later model.

This installed pipeline is not yet qualified end to end. It accepted 35/50
cases locally at 97.67 overall and 100% factual/evidence with zero local hard
failures, while 15/50 reached the escalation gate.

The owner-authorized second round pulled only `qwen2.5:7b-instruct` and
`phi4-mini:latest`. Qwen7 as final reasoner was weaker and slower than F0. Its
validated document-specialist handoff to Qwen9 increased comparable hard
failures from 6 to 8 and wrong-source cases from 5 to 6. Phi failed as planner,
extractor and validator; against canonical F0 it missed all 16 expected
rejections. No additional local model stage earns a production role.

The exact 15 synthetic/public-safe F0 escalations were executed. Raw Temporary
Chat output passed the benchmark quality measures (95.12 overall, 94.44
factual/evidence, zero hard/source/privacy failures), but strict local
post-validation accepted only 1/15, held 12 for review and failed two. The
remaining architecture gaps are (1) the local final-reasoning/source ceiling
and (2) reconciliation of the external result contract with the local
post-validator without weakening privacy or provenance.

### Temporary Chat result-contract audit (2026-08-24)

The rejection audit confirms that V1 conflates model-authored recommendation
and uncertainty metadata with local disposition, but V1 is also too weak for a
safe blanket relaxation: nested claim, tool, visual, estimate and contradiction
provenance is not fully normalized. A strict additive handle-based V2 prototype
therefore keeps source authority local, creates claim IDs locally and rejects
unknown/out-of-scope handles, missing material provenance, incomplete estimates,
privacy violations and hidden contradictions.

V2 unit controls passed with 30/30 valid variants accepted and 75/75 invalid or
privacy variants rejected. External interoperability did not pass: only 2/15
exact rerun results emitted V2, 12 returned the legacy shape and one failed
Supervisor result binding. One of the two V2 outputs also missed the frozen 90%
factual gate. V2 is consequently not integrated into the live post-validator.
The next safe step is to make the external worker reliably emit the bounded V2
schema and repeat the same acceptance corpus; heuristic V1 provenance repair is
forbidden. Evidence: `FOLLOWUP_TEMP_CHAT_POST_VALIDATION_AUDIT.md`.

F0 remains the preferred control. Neither downloaded model is wired into it.
`gemma3:12b` at 4096 remains justified only as a bounded final-reasoner
benchmark behind a new owner download decision. Full evidence is in
`FOLLOWUP_MULTI_MODEL_PIPELINE_QUALIFICATION_REPORT.md` and
`FOLLOWUP_QWEN7_PHI4_COOPERATIVE_QUALIFICATION_REPORT.md`.

## Migration plan

1. Freeze new behavior in the three user-facing modes.
2. Land the versioned unified request/result/source contracts and deterministic validators.
3. Wrap existing read-only tools behind one scoped registry; add claim/source binding tests.
4. Implement intent/difficulty planning and qualified local-model routing.
5. Reuse the CHUNK17 sanitizer, Supervisor arbiter, Temporary Chat/Vision bridge and post-validator.
6. Add the single Assistant UI, quick commands and collapsed source inspector behind a disabled feature flag.
7. Run isolated and public-safe acceptance; preserve existing APIs for deployed +29 clients.
8. Switch the UI only at an approved release boundary; retire legacy modes after minimum-version compatibility allows it.

No database migration is assumed. Any persisted contract change must be additive and compatible with stable +29 API consumers.

## Acceptance before implementation

Implementation can start only after the benchmark establishes a viable role/routing architecture or the owner approves a specific model download. Required fixtures cover source binding, similar-client isolation, missing data, estimation and refusal, hallucination hard failures, tool routing, cross-domain synthesis, privacy minimization, visual routing, Temporary Chat policy and source-inspector contracts. CHUNK23 remains blocked until this pre-CHUNK23 decision is resolved.
