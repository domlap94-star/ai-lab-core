# PRE-CHUNK23 Unified Assistant implementation

Date: 2026-08-25
Source baseline: `9794932dc731fd2f0284b41e9b47586dd6c4ca29`
Stable release: NEXT Stabil `1.0.2+29` (unchanged)

## Outcome

The qualified F0 architecture is implemented as the single primary user-facing
`Asystent AI`. Source, production-like frozen replay, Web build smoke, and
automated Flutter/backend acceptance pass. The earlier Windows raw-build smoke
claim was invalidated on 2026-08-25 by direct Code Integrity evidence; see the
postscript below. The subsequent installed-current-source diagnostic passed
under the current policy and stable +29 was restored. PRE-CHUNK23 remains open
only for owner Android +33 physical acceptance. CHUNK23 remains blocked and was
not started.

The implementation is additive. The deployed +29 Business, Technical and Agent
API contracts remain present for compatibility; old `/ai?mode=...` deep links
now land on the Unified Assistant rather than exposing a mode selector. No AI
history or business data was deleted and no database migration was added.

## User experience

- One multiline composer replaces the Business/Technical/Agent selector.
- Six quick actions dispatch through the same orchestrator, never a parallel
  shortcut implementation.
- Client, Candidate, Document and selected-Mail entry points pass their current
  bounded context into the Assistant.
- The response renders only relevant FACT / ESTIMATE / HYPOTHESIS / MISSING
  semantics, with explicit estimate confidence.
- `Źródła` is directly below a substantive answer and collapsed by default.
  Expansion shows only evidence actually used, supported claim IDs and bounded
  redacted excerpts. Calculations and validated advanced analysis are labelled
  separately.
- Progress states are bounded Polish messages: data collection, document
  analysis, advanced analysis and result validation. Raw transport, worker and
  validation exceptions are not shown to the user.

## F0 production orchestration

The additive endpoint is `POST /api/v1/ai/assistant/ask`. The deterministic
router selects scoped registry tools without an LLM planner and does not widen
an unlinked selected entity or a general-knowledge question into a global CRM
dump. Explicit global CRM search remains supported.

The canonical local reasoner is exactly `qwen3.5:9b`, `num_ctx=4096`,
`think=false`, temperature 0.1 and five-minute bounded keep-alive. No other
generator is selected for final synthesis. The embedding model remains
`qwen3-embedding:0.6b`; no model was pulled, removed or reconfigured.

Evidence is bounded to `TARGET_01`, exact `Sxx` source handles and `Txx` tool
handles. Tool provenance expands only through the deterministic allowlist;
unknown sources/tools, detached material claims, incomplete estimates,
unverifiable hypotheses and unsupported visual statements fail closed. Routine
email, telephone and tax identifiers are removed from source-inspector excerpts.

The quality/difficulty gate reuses strict
`NEXT_STABIL_TEMP_CHAT_RESULT_V2`. V2 has no legacy fallback. External analysis
does not create canonical claim IDs or choose disposition; the deterministic
local contract remains authoritative. Vision facts require validated visual
observations. This implementation made zero real-customer Temporary Chat or
Vision submissions.

## Frozen F0 implementation replay

The immutable 50-case corpus was reconstructed through the implemented
production-like contract, reusing unchanged qualified saved results and the
already validated synthetic V2 advanced artifacts. No new external call was
needed.

| Metric | Implemented replay |
| --- | ---: |
| Overall | 89.66 |
| Factual / evidence | 97.00% |
| Technical documentation | 95.68 |
| Cross-domain | 89.85 |
| Estimate / refusal | 80.00% |
| Wrong source | 0 |
| Material hard failure | 0 |
| Privacy failure | 0 |
| Automatic coverage | 50/50 |
| Local / advanced | 35 / 15 |

The implementation therefore passes the unchanged production thresholds. The
historical design qualification (96.43 overall) remains historical evidence;
it is not substituted for this lower, independently reported implementation
replay score.

## Verification

- Backend focused Unified Assistant / V2 / Vision / System Control regression:
  50 passed in an isolated synthetic database container.
- Flutter analyze: no issues.
- Focused Unified Assistant widget tests: 2 passed.
- Full Flutter suite: 298 passed.
- Web release build: PASS; local `index.html` and `main.dart.js` both returned
  HTTP 200. The in-app browser was not granted localhost navigation, so no
  authenticated Web session was claimed or modified.
- Windows release build: INVALIDATED. The generated diagnostic payload was
  hash-normalized, but the bounded check only proved that a process remained
  alive and did not inspect a Bad Image dialog or the post-launch Code
  Integrity log. That was not sufficient Windows acceptance evidence.
- Authenticated production read-only smoke: Clients page/list/search/detail,
  Global Search, Dashboard, Backup managed/legacy/storage, Mail, Documents and
  System Control all returned HTTP 200. The P0 Clients HTTP 500 did not recur.
- Production DB head stayed
  `followup_backup_planner_retention_20260824`; Qdrant stayed 57 customer / 0 KB.

## Android physical candidate

The non-stable physical-acceptance candidate is
`NEXT-Stabil-1.0.2+33-unified-assistant-candidate.apk`:

- application ID: `pl.ailab.app`
- versionName / versionCode: `1.0.2` / `33`
- SHA-256: `C70E6EF82C8847DED6911F3E57FFE11D0A4D6581249A1C5A420C5F7F78F08725`
- signer SHA-256:
  `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`
- APK Signature Scheme v2: verified
- debuggable: absent/false
- cleartext traffic: false
- published: no

VersionCode 33 is consumed by this non-stable candidate. Owner physical
acceptance must cover a general question, technical-document question,
cross-domain question, Sources expansion, missing/estimate behavior, a hard
advanced case, quick actions and navigation.

## Safety and remaining gates

Execution-caused business/Client/Candidate writes, DB migrations, Qdrant
writes/deletes, Gmail sends, n8n changes, model changes, real-customer external
jobs and stable publication are all zero. The disposable isolated test database
is removed after final verification.

The Release F reminder remains mandatory and unimplemented here:
`RELEASE F REQUIRED UI MICRO-FIX — IGNORE MAIL ADDRESS/DOMAIN` in Candidate
Details, Global Mail and Client Emails, including exact-email/domain add and
undo actions.

Roadmap result:

`PRE-CHUNK23 = UNIFIED ASSISTANT IMPLEMENTED / PHYSICAL ACCEPTANCE REQUIRED`

`CHUNK23 = BLOCKED / NOT STARTED`

## 2026-08-25 Android +33 connectivity postscript

Owner physical acceptance of +33 is invalidated by an application transport
failure: the same phone reaches public `/health` in its browser, while the APK
cannot restore/check a session or log in. The exact APK contains the canonical
HTTPS API URL and has no transport-relevant source/manifest delta from the
working +32 candidate, so a missing endpoint define is not claimed without
evidence. Release/profile Android builds now fail closed when the explicit API
URL is absent or unsafe. Non-stable +34 adds bounded, token-free in-app
configuration and Dio `/health`/auth diagnostics and is staged with verified
identity. Unified Assistant physical acceptance remains blocked until the owner
proves +34 connectivity; see
`FOLLOWUP_P0_ANDROID_CONNECTIVITY_HOTFIX_REPORT.md`.

## 2026-08-25 Windows WDAC postscript

The owner subsequently observed Bad Image status `0xc0e90002` for the exact
repository-build `geolocator_windows_plugin.dll`. Its flat SHA-256 is the
CHUNK21 pinned value, but Code Integrity 3033/3077 records 51044/51046 confirm
that current policy rejected it. The policy was refreshed after the CHUNK21
raw smoke. The repository workflow now rejects raw/staged acceptance and
requires installed-root Managed Installer evidence plus a post-launch Code
Integrity audit. This report must not be used as Windows physical acceptance;
The owner-approved installed-current-source diagnostic subsequently passed.
The installed files received Managed Installer evidence, both pinned native
modules loaded, a normal app window opened, and no new relevant 3033/3077 event
occurred. The canonical +29 installer then restored stable in a mandatory
`finally` rollback and stable also launched without new blocks. Raw and staged
execution remain forbidden acceptance paths. PRE-CHUNK23 returns to Android
+33 physical acceptance required.

## 2026-08-25 named-document and lifecycle P0 remediation

Owner +34 evidence closes the Android transport P0: application `/health` was
200, the old token returned an ordinary 401, and fresh login passed. Physical
Assistant acceptance then exposed a separate named-document/lifecycle P0.

The production router required document-related keyword stems when no
`document_id` was supplied. A natural filename reference could therefore reach
Qwen without the PDF. The local request also had a six-minute client receive
window and five-minute Qwen residency. No durable `AnalysisJob` exists for the
physical request, so advanced worker/binding timestamps are `NOT OBSERVED` and
are not reconstructed. The primary observed stall is classified `LOCAL_MODEL`;
keyword routing, stale UI progress, missing task-completion validation, PII
over-collection, and cancel that stopped only Flutter polling are secondary.

Source now resolves supported quoted/unquoted filenames inside the exact Client
scope before any model call, distinguishes ambiguous/not-found/unavailable,
and never escalates retrieval failure. Resolved documents receive relevance-
ranked page/OCR evidence with page-specific provenance. The usefulness gate
requires the requested document to support a material claim. A technical
document target no longer fetches the Client identity card solely due to scope.

Advanced jobs now expose bounded stage metadata, enforce a 60-second queue and
180-second external hard limit, propagate authenticated cancel to the private
Supervisor, use fresh `attempt_id` values for retries, reject late/stale
binding, and explicitly unload Qwen before external wait. V2 source/privacy
rules are unchanged and fail closed.

Focused backend/V2 tests pass 31/31; Supervisor timeout/cancel, recovery,
idempotency and V2 interoperability pass; Flutter analyze passes and the full
suite passes 303/303. Saved-output frozen replay preserves 0 hard failures,
0 wrong sources and 0 privacy failures without a new external call. Physical
named-PDF and cancel retest remains required. PRE-CHUNK23 stays implemented /
physical acceptance required, and CHUNK23 remains blocked.

The exact final source is staged for owner physical retest as non-stable
Android `1.0.2+36` at
`C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+36-unified-assistant-retrieval-hotfix-candidate.apk`,
SHA-256
`3C9229AE5191FD8156EDD7198151A382A5C59862BFA8B7C05DBF93E8D7AABE36`.
VersionCode 35 was consumed by a pre-final build and left untouched; it is
superseded and must not be used for acceptance. +36 is not published.

## 2026-08-25 general/system routing P0 remediation

The owner subsequently found that an unscoped system-capability question with
an explicit conversation-reset phrase entered the evidence-only prompt, took
minutes, returned an irrelevant `MISSING`, and exposed
`VALIDATED_EVIDENCE`. Source now has deterministic `SYSTEM_META`,
`GENERAL_KNOWLEDGE`, `EVIDENCE_GROUNDED`, and `GLOBAL_CRM_SEARCH` modes; a
model-free capability fast path; reasoning-only conversation reset; a separate
general-knowledge prompt; a fail-closed user-output marker guard; and truthful
local/external progress states.

Focused backend tests pass 76/76, the 30-case supplementary general-routing
matrix passes all zero-error targets, Flutter analyze passes, focused Flutter
tests pass 4/4, and the full Flutter suite passes 304/304. The immutable
50-case replay remains above the unchanged gates at 88.66 overall and 95.50%
factual/evidence, with zero wrong sources/privacy failures and one material
hard failure (2.00%). No external call was made.

+36 remains untouched but is superseded for final acceptance. The new
non-stable source candidate is Android `1.0.2+37`, SHA-256
`E6E2742FCBACF193676E7CCB82E4E8D5AD6C75CA47034BC5C35B02E8BB662F31`,
at `C:\ai-lab-core\staging\android\NEXT-Stabil-1.0.2+37-unified-assistant-final-p0-candidate.apk`.
PRE-CHUNK23 remains physical-acceptance required and CHUNK23 remains blocked.
Detailed evidence: `FOLLOWUP_P0_UNIFIED_ASSISTANT_GENERAL_ROUTING_REPORT.md`.

## 2026-08-25 Android +37 HTTP 422 contract-sync postscript

Owner physical +37 evidence showed immediate HTTP 422-equivalent errors for
both system/meta and Client quick-action requests. Live OpenAPI proved the
running bind-mounted backend process had imported an older request/response
contract: it rejected `attempt_id`, omitted the new lifecycle fields, and had
no cancel endpoint. A direct current-shape control returned
`body.attempt_id / extra_forbidden`; the old shape passed validation and
entered the old model path. Flutter generated a valid 24-character attempt ID.

After confirming DB head, zero active backup/restore work and an idle private
Supervisor queue, only the backend container and exact NEXT Stabil Supervisor
scheduled task were reloaded. Post-deploy live OpenAPI matches current source.
The exact +37-shaped SYSTEM_META request returns HTTP 200 in 21.95 ms locally
and 75.08 ms through the public gateway, with no model. GENERAL_KNOWLEDGE also
returns HTTP 200 locally with no external analysis.

A shared cross-stack request fixture now validates actual Flutter serialization
against the actual FastAPI Pydantic schema; backend/Unified tests pass 82/82
and focused Flutter tests pass 5/5. Flutter analyze and full 305/305 pass;
post-restart authenticated read-only Clients/Backup/System Control/Mail/
Documents smoke returns HTTP 200. No application source or APK changed, so +37
remains the candidate and versionCode 38 was not consumed. Physical
general, Client, named-PDF, Sources and cancel retest remains required. See
`FOLLOWUP_P0_UNIFIED_ASSISTANT_CONTRACT_SYNC_REPORT.md`.
