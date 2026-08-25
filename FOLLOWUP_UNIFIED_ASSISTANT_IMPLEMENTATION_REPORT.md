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
