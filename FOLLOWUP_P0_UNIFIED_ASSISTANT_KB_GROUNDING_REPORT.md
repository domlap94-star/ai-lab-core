# P0 Unified Assistant Knowledge Base grounding

Date: 2026-08-25

Source baseline: `3025b51d0c659cb6916ceab673fcb53002236911`

Stable remains: `NEXT Stabil 1.0.2+29`

## Decision

`P0 KNOWLEDGE BASE GROUNDING = SOURCE/RUNTIME PASS / PHYSICAL RETEST REQUIRED`.
PRE-CHUNK23 remains `UNIFIED ASSISTANT IMPLEMENTED / PHYSICAL ACCEPTANCE
REQUIRED`; CHUNK23 remains blocked/not started. No release was performed.

Knowledge Base is the persistent curated technical RAG memory of NEXT Stabil.
It does not retrain Qwen weights. A current, extracted and accepted item becomes
available to deterministic retrieval without a code change for that material.

## Owner defect and live forensics

The owner named the current item `fundamentowanie`, but the Assistant selected
the general-knowledge path and showed no KB provenance. Live read-only evidence
proves the material itself was not defective:

- exactly one current item matched, item ID 3, category `norms`;
- processing `processed/native_text`, analysis `local_accepted`, indexing
  `indexed`;
- 10,254 extracted characters and 56/56 pages with text;
- latest local artifact ID 5 is `accepted` / `structured_technical_knowledge`;
- authoritative file exists at the recorded size (6,627,171 bytes) and its
  SHA-256 matches the stored checksum;
- no item, page or artifact content was copied into this report.

The production collection `ai_lab_knowledge_base_chunks` is green,
1,024/Cosine, with 56 points. All 56 points belong to the exact item and retain
`source_type=knowledge_base`, item ownership and page/chunk provenance. No
Qdrant write, reindex or delete occurred.

Read-only controls for `fundamentowanie` found the exact item at rank 1 for
lexical, vector and hybrid search. Lexical returned pages 1-8; vector returned
relevant pages 49, 20, 43, 10, 40, 34, 55 and 31. Hybrid is now bounded and
interleaves both methods. If Qdrant or embedding search fails, hybrid returns
the already-safe lexical results instead of failing the Assistant.

## Root cause

CHUNK16 already supplied the correct retrieval service, but Unified Assistant
did not use it as a first-class domain. Its secondary branch recognized only a
narrow set of substrings after general/system routing, called
`KnowledgeBaseService.search()` instead of the canonical retriever, passed the
whole natural-language question into a single lexical substring query, and
had no exact-title prerequisite or required-item task-completion gate.

Consequently an explicitly named item could be skipped and general model
knowledge could be presented in its place.

## Implementation

The existing CHUNK16 services remain canonical. The remediation adds:

- deterministic explicit KB intent and bounded technical-domain intent;
- exact, case-insensitive, normalized and unique-partial title resolution over
  current, non-archived items before Qwen;
- terminal `AMBIGUOUS`, `NOT_FOUND` and `UNAVAILABLE` states without model or
  external work;
- item-scoped lexical/vector/hybrid retrieval, current-only by default;
- a 3-source KB reserve in joint Client/document requests and up to 5 sources
  for an explicitly named KB item;
- page-specific `knowledge_base` sources in the unified evidence artifact;
- required KB handles in the prompt and a post-generation rule requiring the
  named item in both material claim provenance and used sources;
- deterministic separation of case-specific facts from global technical
  reference evidence, with conflict acknowledgement required in the prompt;
- a compact local exact-item overview contract (answer plus no more than three
  FACT/HYPOTHESIS claims), converted into the full Unified response and passed
  through the same source/claim validator;
- no duplicate KB excerpt in tool payload and evidence manifest.

The compact overview exists because the full F0 JSON repeatedly exhausted its
generation budget or failed the representation retry on this simple source
overview. It does not weaken full F0: estimate-bearing requests and joint
Client/document + KB reasoning retain the full 4,096-context, 480-token F0
contract. It never repairs truncated JSON heuristically.

KB lacks a per-item sensitivity field sufficient to authorize proprietary
material for Temporary Chat. Any local failure involving KB therefore returns
`knowledge_base_local_only`; it cannot create an external job.

## Verification

Focused Unified/KB/Android-contract regression: 135 passed. Document, V2 and
Vision regression: 30 passed; the combined suite is 165/165. Global Advanced,
privacy and 30 calculation
fixtures pass.

The separate synthetic/public-safe KB matrix contains 35 cases: 10 KB-only,
10 Client/document + KB, 5 explicit-item, 5 no-match/adversarial and 5
current/superseded/conflict. Its deterministic routing and task-completion
contract is 35/35, with zero wrong/invented KB sources and zero explicit-
request general-knowledge substitutions. This matrix does not replace the live
model proof below.

Saved-output immutable F0 replay remains 50/50 automatic coverage:

| Metric | Result |
| --- | ---: |
| Overall | 88.03 |
| Factual/evidence | 94.50% |
| Technical documentation | 95.16 |
| Cross-domain | 85.85 |
| Estimate/refusal | 78.00% |
| Wrong source | 0 |
| Privacy failures | 0 |
| Material hard failures | 1/50 |
| Local / advanced | 35 / 15 |

No fresh external request was made for the replay.

## Runtime proof

Before reload, active KB processing, backup and restore counts were zero. The
15 active-looking analysis rows were old `advanced_queued` technical rows last
updated on 2026-08-24; they were not modified or cancelled. Only the backend
container was restarted. Post-reload:

- `/health` = 200/ok;
- live OpenAPI retains `attempt_id` and the Unified ask route;
- public-ingress guard passes and public `/control` remains 404;
- authenticated SYSTEM_META = HTTP 200 in 0.16 s, model none;
- authenticated exact-item query = HTTP 200 in 38.48 s,
  `accepted_local`, Qwen3.5 9B, 3 claims;
- Sources contain only item ID 3 titled `fundamentowanie`, pages 49 and 20,
  with all three claims mapped;
- external analysis = false.

The earlier current-source diagnostic also accepted the same local case in
59.11 s. No response text or KB excerpt is recorded here.

## Safety and next gate

DB migrations, business/Client/Document/KB writes, Qdrant writes/deletes,
Gmail, n8n, model downloads/deletes, backup deletes and stable publication are
all zero. Supervisor code did not change and was not restarted. Flutter did
not change; Android +37 remains reusable and versionCode 38 was not consumed.

The owner must physically repeat the named `fundamentowanie` query on +37 and
verify the KB source cards/page evidence. PRE-CHUNK23 and CHUNK23 remain open.

The Release F reminder remains unimplemented and mandatory:
`RELEASE F REQUIRED UI MICRO-FIX — IGNORE MAIL ADDRESS/DOMAIN` for Candidate
Details, Global Mail and Client Emails, including add/undo for exact email and
domain rules.
