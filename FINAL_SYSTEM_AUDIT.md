# FINAL SYSTEM AUDIT — FULL MASTERPLAN RECONCILIATION

Audit date: 2026-08-20 (Europe/Warsaw)

Audited source HEAD: `b375b2184ae5bb87742fb870153fa92953a343ae`

Production release: `NEXT Stabil 1.0.2+22`

Live database revision: `followup_change_history_entity_types_20260820`
(single Alembic head)

## Executive verdict

- Production readiness: **PRODUCTION_READY_WITH_RESIDUAL_RISKS**.
- Masterplan completion: **MASTERPLAN_COMPLETE_WITH_DEFERRED_ITEMS**.
- Project closure: **IMPLEMENTATION_PHASE_CLOSED_WITH_FOLLOW_UPS**.
- Audit decision: **FINAL_AUDIT_PASS**.

The delivered system is coherent end-to-end for the released scope. Web,
Windows and Android release artifacts agree with the stable manifest; the live
database is at the repository head; the pinned Docker stack, private
supervisor, Vision dispatcher, backup task and public gateway are healthy.
The remaining items are explicit operational or product follow-ups rather than
hidden unfinished release work. No business write, migration, backfill,
retention deletion or release was performed by this audit.

## Evidence and audit boundary

The audit reconciled Git, tracked plans/runbooks, runtime container metadata,
read-only PostgreSQL aggregates and constraints, authoritative document
storage, Qdrant, n8n workflow metadata, Ollama, Windows scheduled tasks,
Tailscale state, release artifacts and the public Web surface. Synthetic or
isolated tests were used where a live mutation would otherwise be required.
Names, message bodies, extracted document content, credentials, tokens and
other customer PII were not included in the evidence.

## Current production

| Component | Audited state |
|---|---|
| Release | NEXT Stabil `1.0.2+22` |
| Web | Public HTTP 200; login route and direct `/ai?mode=agent` auth guard render correctly |
| Windows | Installer `NEXT-Stabil-Setup-1.0.2+22.exe`; ProductVersion `1.0.2`, FileVersion `1.0.2.22` |
| Android | APK `NEXT-Stabil-1.0.2+22.apk`; versionName `1.0.2`, versionCode `22`, minSdk 24, targetSdk 36 |
| Public API | `https://domai.tail1927bd.ts.net`; dev literals remain source fallbacks but release tooling supplies and verifies the production define |
| Stable manifest | channel stable, version `1.0.2`, build 22, minimum `1.0.0`, published 2026-08-20 |
| Windows SHA-256 | `A8A5F6B5305D93F2C54CC78FAB25DE68D6BB780F246BB3C52A93BFE625B216E8` local = public = manifest |
| Android SHA-256 | `0E3C8FDE0F9AE9BD86C99E4EAD49F3A234301CA762ABC855A3BA7B5BA4BE0D85` local = public = manifest |
| Web bundle SHA-256 | `A24711FA2F9E0AC609FA966D6C302BEEA45DF59D6CF42901ACA39329878DFFBE` local = public login bundle build evidence |
| Android signing SHA-256 | `5e223da2da7c893d089d7333e99aaeee8d98c9cdf72be80609020967368fe018`; continuity confirmed without exposing key material |

The backend legacy `/version` response still labels its environment
`development`, reports `debug=true` and carries old application version
metadata. Flutter updates use the stable release manifest, and FastAPI is not
constructed with that debug flag, so this is configuration/diagnostic drift,
not an active update-path or traceback exposure. It remains a follow-up.

## Toolchain and build provenance

| Tool | Canonical current value |
|---|---|
| Flutter | `3.44.8` stable, SDK `C:\FlutterSDK-New\flutter` |
| Dart | `3.12.2` |
| Android | SDK/API 36, build-tools 36, bundled JDK `21.0.10` |
| Windows | Visual Studio 2022 `17.14.37`, Windows SDK `10.0.26100` |
| Node/npm | Node `24.18`, npm `11.16` |
| Playwright | `1.62.1` in `C:\ChatGPT-Vision-Worker` |
| Edge | Microsoft Edge channel, host build 151 at audit |
| NSIS | `makensis` unavailable on the current host |

The older CHUNK 17 report value Flutter 3.38.5 / Dart 3.10.4 is
**DOCUMENTATION_STALE**. The SDK repository was already at Flutter 3.44.8
before the +21 build, repository instructions point at the same SDK path, and
release scripts invoke Flutter from that toolchain. No SDK change was made in
this audit. The current Windows artifact is intact, but reproducing its
installer is blocked until the approved NSIS tool is present.

## Database and relational integrity

Alembic has one head and the live `alembic_version` equals
`chunk16audit_20260819`; the migration chain includes both CHUNK 15 Vision
state and CHUNK 16 Agent audit migrations. No unapplied revision was found.

| Table/domain | Live count |
|---|---:|
| users | 6 |
| clients | 3,243 |
| candidates | 3,561 |
| documents | 5,915 |
| document_pages | 271 |
| document_assets | 10 |
| projects | 0 |
| inspections | 3 |
| agent_executions | 1 |
| candidate_sources | 6,984 |
| client contact points | 5,060 |
| client addresses | 9 |
| document_chunks | 57 |

Read-only integrity checks found no orphan document/client, page/document,
asset/document, inspection/client, contact/client, address/client or
AgentExecution/user foreign keys; no duplicate critical IDs, request IDs or
source external identities; and no ungranted locks. Agent constraints and
Vision state values were valid. Counts legitimately grew from historical
checkpoints and are not treated as regressions.

Two document-processing anomalies remain: Document IDs 1913 (`extracting`,
Gmail attachment) and 5626 (`failed`, invalid JSON text representation). They
were reported by ID and error class only and were not repaired or retried.

## Document storage

- Authoritative path: repository `data` junction to `D:\ai-lab-data`.
- Unique referenced files: 6,160; referenced bytes: 6,389,269,586.
- Referenced files missing: 0; path escapes: 0.
- Checksums evaluated: 5,925; mismatches/errors: 0.
- Files in authoritative storage: 6,185; bytes: 6,393,064,693.
- Unreferenced files: 25 (3,795,107 bytes), report-only.

No file was moved, rewritten or removed. The 25 unreferenced files require a
separate provenance-led cleanup decision.

## Ingestion and n8n

- Live source records: Gmail 4,262; Google Sheets 2,722.
- After the forward-correctness patch commit `d88e6283`, 12 real Gmail and 4
  real Sheets records exist. The old `REAL_SOURCE_INGESTION_BLOCKED — NO
  POST-PATCH RECORDS` checkpoint is therefore **OBSOLETE**.
- The active n8n workflow is ID `23i1FJJ6dZJbuMRo`, name `My workflow`, with
  48 nodes, 39 connections, one schedule and two credential references.
- Four current Sheets branches and their explicit ingestable/skipped-no-
  identity branches are present. Gmail attachment processing is present.
- Source identity and fake-repository Sheets replay/idempotency tests pass.
- No duplicate active workflow was observed; no workflow was changed or
  production source replay invoked.
- n8n execution-history pruning is not explicitly configured in runtime env;
  retention is documented but not demonstrably enforced.

## CRM, Candidates, Projects, Inspections and Timeline

Clients, statuses, contact points, addresses, provenance, bounded search,
details/deep links and authorized bulk operations exist in source and the
released UI. Candidate review/promotion, source linkage and duplicate guards
remain active. The named multi-person `ClientContactPerson` model from CHUNK
7B was not implemented: the current contact-point model supports multiple
email/phone values but does not group them into named people. CHUNK 7B is
**DEFERRED / REQUIRES_DECISION**, not a release blocker.

Projects remain implemented for legacy read access but have zero live rows;
new inspections are Client-first and Project selection is not required.
Current-state text describing Projects/Case as the active central entity is
obsolete; historical architecture drafts are now labelled as such.

Inspection creation, location capture, best-effort camera/gallery GPS, inline
notes autosave, Android speech-to-text, denied-GPS behavior, AI entry and Back
navigation are released. Timeline retrieval is bounded, chronologically
ordered, source-typed and deep-linkable; duplicate prevention is exercised by
the focused regression suites.

## Search and Qdrant

Global Search combines structured and lexical paths with optional semantic
retrieval, Gmail FTS, bounded typed results, scope checks and fail-open behavior
when Qdrant/Ollama semantic search is unavailable.

| Metric | Live value |
|---|---:|
| Collection | `ai_lab_document_chunks` |
| Status | green |
| Points | 57 |
| Dimensions | 1,024, cosine |
| Documents covered | 11 / 5,915 (0.186%) |
| Points with document_id | 57 |
| Points with valid client_id | 0 |
| Client-scoped usable vectors | 0 |

Semantic coverage is intentionally very limited and scoped retrieval safely
falls back to lexical/structured evidence. No backfill, rebuild, image
embedding, Qdrant upgrade or Qdrant write occurred. Historical vector rebuild
and `client_id` payload repair items are **DEFERRED** under the present product
strategy, not silently complete.

## AI feature reconciliation

### Client AI

`POST /api/v1/clients/{client_id}/ai/ask` is released. It uses strict client
scope, deterministic direct answers where possible, `llama3.2`, backend source
mapping, semantic fail-open and request-local/non-persistent conversation.

### Business Assistant

`POST /api/v1/ai/business/ask` is released and read-only. Deterministic
analytics and entity retrieval are reused; citations are assigned from actual
backend evidence, not model-invented IDs. Model: `llama3.2`; no conversation
persistence.

### Technical AI

`POST /api/v1/ai/technical/ask` is released with Client/Inspection scope,
intent classes, facts/hypotheses/missing-information separation, cautious
measurement handling, deterministic citations and persisted visual evidence.
Pending Vision is surfaced as a limitation. Historical Vision remains an
explicit on-demand path rather than an automatic backfill.

### Vision

- Production automation is enabled for genuinely new Documents; historical
  auto-eligible count is 0 and historical automatic Vision is disabled.
- Document statuses: 3 `complete`/auto-eligible and 5,912
  `not_evaluated`/historical. Pages: 3 complete with validated analyses and 268
  not evaluated. Assets: 10 not evaluated.
- Unfinished auto-eligible, retry-overdue, pending-auth and current UI-changed
  database rows: 0.
- Deterministic classifier, maximum eight automatic pages per document,
  bounded manifests, per-job source references/checksums and strict V1 schema
  are implemented. Whole PDFs are not uploaded.
- The private supervisor queue has concurrency one. Health was READY with zero
  active/queued work.
- Executor: isolated Edge/Playwright ChatGPT Temporary Chat, one job/one chat;
  normal-chat fallback is forbidden. OpenAI API and local Vision are not used.
- Credentials/tokens are not exported. Selected pages/images and minimal
  source refs are sent, without unnecessary CRM context.
- Temporary Chat does not use normal history/personalization memory, but is not
  a zero-retention guarantee; the OpenAI retention caveat is documented.
- Spool at audit: 47 job directories (36 complete, 10 cancelled, one retained
  UI_CHANGED diagnostic), 3.55 MB. Incoming is empty. Terminal-only 72-hour
  cleanup is implemented; no original or active file is eligible.

### Agent

`POST /api/v1/ai/agent/ask` is JWT protected and uses `llama3.2`. The registry
contains exactly these 16 read-only tools:

`search_clients`, `get_client`, `get_client_contacts`,
`get_client_timeline`, `search_documents`, `get_document_summary`,
`get_document_pages`, `get_visual_analysis`, `search_inspections`,
`get_inspection`, `search_projects`, `get_project`, `search_emails`,
`get_email_metadata`, `global_search`, `business_analytics`.

It is deny-by-default, capped at five planner rounds, eight tool calls and 180
seconds, with duplicate/no-progress termination and deterministic source maps.
Client and Inspection scopes are server-enforced. Write, SQL, shell,
PowerShell, Docker/supervisor, general browser and live Vision execution tools
are absent. Conversation is request-local and not persisted.

The live audit table contains one completed failure record from a legitimate
bounded Agent execution (tool_count 0, duration about 180 seconds). It is not
orphaned. Metadata contains only `tools`, `rounds` and `final_status`; forbidden
prompt/body/token fields and customer content were absent. Orphan `started`
rows: 0.

## Auth, Admin and public surface

Passwords use bcrypt. Access JWTs carry bounded expiry and token identity;
current users are reloaded and inactive users are rejected. Flutter uses
secure storage and a generation-aware stale-401 guard. Admin lifecycle routes
enforce admin scope; AI/Agent routes do not amplify roles. No token logging or
tracked secret was detected.

All production container ports bind to loopback. Public Funnel:
`https://domai.tail1927bd.ts.net` to `127.0.0.1:8789`; tailnet-only private
Serve route `:8443` goes to `127.0.0.1:8788`. Supervisor `8787`, backend
`8000`, PostgreSQL, Qdrant, Ollama, n8n and Open WebUI are not directly public.
Public `/control/status` returns 404.

CORS is an explicit localhost development allowlist, not `*`; production Web
uses the same-origin public gateway. The public response currently lacks HSTS,
X-Content-Type-Options, Referrer-Policy, framing protection and CSP. This is a
**DEFERRED — EXPLICIT SECURITY HARDENING** item of MEDIUM priority because CSP
must first be proven compatible with Flutter Web/CanvasKit/workers. No header,
CORS, Tailscale, gateway, firewall or port change was made. Application-level
login rate limiting was not found and is a separate MEDIUM-HIGH hardening
follow-up for the Internet-reachable login surface.

## Production service versions and resources

| Service | Pinned/current runtime |
|---|---|
| PostgreSQL | 17.10, pinned digest |
| backend | local known-good image, Python 3.12.13 pinned base |
| Ollama | 0.32.3, pinned digest |
| Qdrant | 1.18.3, pinned digest |
| n8n | 2.31.6, pinned digest |
| Open WebUI | pinned digest/revision |

All external images in the production Compose are pinned and runtime mounts,
loopback ports, log settings and restart policies agree with repository
configuration. An unrelated, non-exposed `postgres:10` container exists
outside the production Compose and requires an owner/cleanup decision; it was
not altered.

Docker json-file rotation is `10m × 5` for all main containers. System disk C
had about 732.8 GB free and data/backup disk D about 921.7 GB. Docker accounted
for about 21.3 GB images, 1.5 GB containers, 6.1 GB volumes and 5.6 GB build
cache. Windows had about 10.9 GB free physical RAM; WSL retains the audited
18 GB memory / 8 GB swap limit and used no swap at the snapshot.

Installed Ollama models are `llama3.2` (production generation),
`qwen3-embedding:0.6b` (production embeddings), plus non-production
`qwen3.5:9b`, `qwen2.5vl:3b` and `gemma3:4b`. The latter models and
`C:\Ollama-Vision-Pilot` are **NON-PRODUCTION / DEFERRED CLEANUP** and were not
deleted.

## Backup, restore, startup and retention

Scheduled Task `NEXT Stabil - Daily Backup` is enabled for 03:00 local time,
runs as the limited interactive user, contains no plaintext secret arguments,
and last completed successfully. Latest validated checkpoint:
`C:\ai-lab-core-backups\20260819T080526Z`.

The manifest and hashes validate PostgreSQL dump, document-storage archive,
Qdrant snapshot, n8n workflow/encrypted-credential exports, stable release
artifacts and non-secret configuration inventory. The checkpoint is about
7.07 GB; ACL is restricted to SYSTEM, Administrators and the owning user.
Plain `.env` is absent. Protected environment-secret escrow remains a manual
external requirement and was not assumed complete.

Isolated PostgreSQL restore, relational counts/FKs/aggregate hashes, document
storage restore, n8n parse/import and Alembic downgrade/re-upgrade drills pass.
The 2026-08-21 owner-approved Qdrant remediation migrated production storage
from the Windows bind mount to Docker-managed `qdrant_storage` while retaining
the exact pinned 1.18.3 image/digest and all 57 points. Representative ownership
payloads and `1024`/`Cosine` configuration match. A fresh official snapshot has
valid WAL metadata and restores into a clean isolated exact-version target with
57/57 points. Full checkpoint `C:\ai-lab-core-backups\20260821T142509Z` passes
manifest/hash, isolated Database, Document staging, Qdrant restore and aggregate
Full/System validation. The old bind source remains retained for rollback.

The 2026-08-19 controlled host reboot recovered gateways/supervisor in about
19 seconds, containers in 46 seconds, Qdrant in 48 seconds, PostgreSQL in 55
seconds, backend in 57 seconds and full stack/n8n in about 71 seconds, without
manual service intervention. Docker Desktop/Compose, supervisor, gateway and
backup scheduled tasks remain enabled.

Backup retention (7 daily / 5 weekly / 12 monthly) is documentation only;
automatic purge is disabled. Backup root held five directories/two valid
manifest checkpoints and about 37.25 GB at audit. Agent audit is deliberately
persistent. n8n history retention is not demonstrably configured. No
destructive cleanup was run.

## Release compatibility and legacy contracts

`minimum_version` remains 1.0.0. Controlled compatibility tests cover:
too-old → forced update, supported-old → optional update, current → no update,
malformed/offline manifest → friendly safe behavior. Existing legacy/additive
API contracts remain necessary while 1.0.0 is supported and must not be removed
without a future minimum-version decision. The release rollback runbook
correctly warns that application rollback after a schema migration needs a
human compatibility gate.

The current Windows installer cannot be reproduced on this host because NSIS
`makensis` is absent; no tool was installed during this audit. Existing local,
public and manifest artifacts remain byte-identical. No ADB device was
available, so the final physical Android smoke remains **UNVERIFIED**. Static
APK version/signing/permission/API audits pass. A currently installed Windows
client was not available for a live launch, so Windows runtime smoke in this
audit is also unverified; installer integrity and metadata pass.

## Roadmap reconciliation

| Chunk | Actual implementation/release state | Key evidence | Remaining limitation |
|---|---|---|---|
| 0 Baseline | DONE | `9f8a937` | Old untracked/hygiene artifacts retained |
| 1 Client list | DONE | `c7a7ef3` | Legacy compatibility retained |
| 2 Document read | DONE | `da25ce4` | None in released scope |
| 3 Repository UI / 3A compatibility | DONE | `fdd98df`, compatibility checkpoints | Old clients constrain endpoint removal |
| 4 Client 360 documents | DONE | `3fad189` | None in released scope |
| 5 Email history / 5A scope | DONE | `4b73ad4` and scope tests | Historical notes cleanup separate |
| 6 Identity quality/apply | DONE for approved apply | `4bb2f20`, `1c00ac0`, `b45645a`, `d0d7f9a` | CHUNK 6D cleanup remains blocked/deferred |
| 7 Contact/address | DONE | `323f74d` | CHUNK 7B named persons deferred |
| 8 Document matching | DONE | `68ba972` | Historical ambiguous data not bulk-cleaned |
| 9 Upload/photos | DONE | `4f92c13` | No historical Vision backfill |
| 10 Projects/Inspections/Timeline | DONE with Projects legacy | `5ffad8c`, `5331571`, `bab9f9b` | Projects have zero rows and are no longer mandatory |
| 11 Global Search | RELEASED +14 | `f5cb6e6`, `7c6940e` | Semantic coverage 0.186%, scoped vectors zero |
| 12 Client AI | RELEASED +15 | `7c7b426`, `5ee7f25` | Semantic fail-open used for most documents |
| 13 Business Assistant | RELEASED +17 | `caff3b7`, `a519137`, `4f1b99c` | Read-only by design |
| 14 Technical AI | RELEASED +19 | `50358c8`, `188e5b8` | Engineering output remains evidence/uncertainty bounded |
| 15 Vision | RELEASED +20 | `f102b64`, `8db57be`, `31b257e`, `f0752f3`, `b13d413` | Browser UI/auth dependency and retention caveat |
| 16 Agent | RELEASED +21 | `7550453`, `17e9e5b`, `4441e335`, `bbe37db` | Read-only; no write tools by design |
| 17 Hardening | COMPLETE / VERIFIED; no client bump | `e83d81f`, `9b4ff83`, `9d59c30`, `c3f388a` | Explicit residual gates below |

## Marker and stale-document reconciliation

The literal scan found 700 keyword/marker occurrences across
`AI_LAB_MASTER_PLAN.txt` and `CODEX_MASTER_EXECUTION.md`. Most are repeated
target checklists or historical checkpoint statements, not 700 independent
unfinished defects. Every occurrence was mapped through the following grouped
ledger; repeated occurrences in the stated source/section inherit the listed
classification.

| Source / section | Topic | Classification | Current evidence / recommended action |
|---|---|---|---|
| Masterplan §§1–46 target checklists | Broad target capabilities and future automation | DONE where represented by chunks 0–17; otherwise DEFERRED | Use roadmap table and residual register as current status; retain target vision as historical scope |
| Execution headings 12, 13, 15, 16, 17 | `TODO` despite releases | DOCUMENTATION_STALE → corrected | Commits/releases above |
| Execution current-release/reconciliation table | old head, +4 manifest and test counts | DOCUMENTATION_STALE → corrected | Live DB/release/tests from this audit |
| Historical release checkpoints +5..+19 | `WAITING`, `NOT STARTED`, `UNVERIFIED` at that date | FALSE_POSITIVE / historical-correct | Do not rewrite historical evidence |
| Masterplan current checkpoint lines 25–71 and delivery end | final audit required | DONE → corrected | This report |
| CHUNK 6D / notes cleanup / candidate reconstruction | cleanup or AI reconstruction blocked | DEFERRED / BLOCKED | Requires separate data-quality approval; no hidden dependency for current release |
| CHUNK 7B | named Contact Person model | REQUIRES_DECISION | Multiple contact points exist; person grouping does not |
| Golden backup +5/+6/+7 waiting entries | old golden checkpoint | OBSOLETE / superseded | CHUNK 17 verified scheduled checkpoint and restore drill replace it |
| Data artifact cleanup tied to golden backup | historical cleanup | DEFERRED | Backup prerequisite is satisfied, but cleanup itself was never approved |
| Vector backfill/rebuild/client_id repair | semantic coverage expansion | DEFERRED | Current 57-point collection is safe fail-open; no backfill approval |
| Projects/Case-centric target architecture | active core entity expectation | OBSOLETE / DOCUMENTATION_STALE | Production is Client/Inspection-centric; architecture drafts now carry banners |
| CHUNK 14 historical “no image analysis” | state at CHUNK 14 | FALSE_POSITIVE / historical-correct | CHUNK 15 later added Vision; keep temporal context |
| Vision local-model plans | qwen/gemma CPU/Vulkan path | OBSOLETE for production | Browser Temporary Chat is released executor; models retained pending cleanup decision |
| Public headers | missing hardening | DEFERRED | Separate compatibility/security approval required |
| Qdrant isolated restore | restore proof | DONE | Named-volume remediation and exact-version 57-point restore drill pass |
| Environment secret escrow | protected off-host copy | REQUIRES_DECISION / MANUAL_REQUIRED | Checklist exists; actual escrow not verified |
| Android physical smoke / Windows live smoke | device/runtime validation | UNVERIFIED → DEFERRED | Static artifact evidence passes; device/install needed |
| Old real-source ingestion blocker | no post-patch real records | OBSOLETE | 12 Gmail + 4 Sheets records now postdate patch |
| Old count snapshots | lower historical counts | FALSE_POSITIVE / historical-correct | Growth is legitimate; current counts above are canonical |
| `domain-model.md`, `database-design.md` | Case-centric future schema presented as current | DOCUMENTATION_STALE → labelled historical | Migrations/models are as-built authority |
| Old tracked/untracked hygiene TODOs | backups, `before_*`, reports | DEFERRED | No cleanup approval; keep out of product runtime and Git staging |

Canonical grouped classifications: 19 DONE/superseded topics, 12 DEFERRED
topics, 2 BLOCKED topics, 7 OBSOLETE topics, 5 REQUIRES_DECISION topics, 8
DOCUMENTATION_STALE topics and historical FALSE_POSITIVE occurrences. Counts
refer to canonical topics, while the 700 count is the raw repeated-marker scan.

## Residual backlog

| ID | Item | Classification | Priority | Risk | Blocks current production? | Recommended action | Human approval |
|---|---|---|---|---|---|---|---|
| R01 | Public HSTS/XCTO/Referrer/framing/CSP | DEFERRED | P1 | MEDIUM | No | Compatibility-test proposed headers, especially Flutter Web CSP, then deploy separately | `CHUNK17_PUBLIC_SECURITY_CHANGE_APPROVAL_REQUIRED` |
| R02 | Qdrant isolated restore | DONE | P2 | LOW | No | Retain verified named-volume topology and require per-checkpoint restore-drill evidence | Scheduler/production restore remain separately gated |
| R03 | Protected environment secret escrow | REQUIRES_DECISION | P1 | MEDIUM-HIGH | No today; raises full-host DR risk | Create encrypted, ACL-controlled off-host escrow using documented variable-name checklist | Manual operational authorization |
| R04 | Physical Android final smoke | DEFERRED / UNVERIFIED | P2 | MEDIUM | No | Run login/Vision/Agent/Back smoke on signed APK when device is available | Device/operator |
| R05 | NSIS/makensis missing | BLOCKED | P1 | MEDIUM | No for current artifact; yes for Windows rebuild | Restore approved NSIS build dependency and reproduce in isolated release gate | Software installation approval |
| R06 | Semantic coverage 11/5,915; scoped vectors 0 | DEFERRED | P2 | LOW-MEDIUM | No; lexical fail-open works | Decide whether benefit justifies controlled text-vector backfill | Explicit Qdrant/backfill approval |
| R07 | Old Vision models and pilot directory | REQUIRES_DECISION | P3 | LOW | No | Retain or remove only after storage/rollback decision | Cleanup approval |
| R08 | Backup purge disabled; 37.25 GB currently retained | REQUIRES_DECISION | P2 | MEDIUM | No | Approve/test 7/5/12 retention with manifest-aware fail-closed deletion | Destructive retention approval |
| R09 | External alerting absent | DEFERRED | P2 | MEDIUM | No | Select an external notification channel for health/backup/disk/Vision pauses | External integration approval |
| R10 | CHUNK 7B named Contact Person | REQUIRES_DECISION | P2 | LOW-MEDIUM | No | Validate business need; otherwise mark explicitly out of scope | Product/schema approval if pursued |
| R11 | Historical notes/data-artifact cleanup and auto-promotion | DEFERRED | P3 | LOW-MEDIUM | No | Re-run provenance dry-run and conflict report before any apply | Data cleanup approval |
| R12 | Real-source Gmail/Sheets post-patch verification marker | OBSOLETE | P3 | LOW | No | Close old marker; retain current 12/4 aggregate evidence | No |
| R13 | Documents 1913 extracting and 5626 failed | REQUIRES_DECISION | P1 | MEDIUM | No global blocker | Diagnose by ID with read-only evidence, then approve bounded retry/remediation | Business-processing write approval |
| R14 | Backend `/version` environment/debug/version drift | DOCUMENTATION_STALE / config drift | P2 | LOW | No | Align non-secret production metadata in a future tested config-only release | Deployment approval |
| R15 | No application-level login rate limiting found | DEFERRED SECURITY | P1 | MEDIUM-HIGH | No immediate exploit observed | Design proxy/app throttling without breaking Tailscale/login UX | Public security approval |
| R16 | n8n execution-history retention not explicit | DEFERRED | P2 | MEDIUM | No | Measure history growth and configure tested non-business retention | Retention/config approval |
| R17 | 25 unreferenced storage files | DEFERRED | P3 | LOW | No | Produce provenance/dry-run deletion ledger; do not infer orphan safety from path alone | Cleanup approval |
| R18 | Unrelated `postgres:10` container outside production Compose | REQUIRES_DECISION | P2 | LOW-MEDIUM | No | Identify owner/data purpose, then retain or remove under separate approval | Container/data owner |
| R19 | Legacy operational scripts and untracked artifacts | DEFERRED | P3 | LOW | No | Separate repo-hygiene chunk; keep generic discovery disabled | Cleanup approval |
| R20 | Installed Windows runtime smoke unavailable | DEFERRED / UNVERIFIED | P2 | LOW-MEDIUM | No | Install/launch existing signed artifact on a controlled Windows target | Operator |

## Risk matrix

| Area | Level | Rationale |
|---|---|---|
| Data durability | LOW-MEDIUM | Canonical DB/storage are consistent and backed up; secret escrow is still manual |
| Backup/recovery | LOW-MEDIUM | PostgreSQL/storage/n8n/Qdrant isolated proofs pass; scheduler changes and production restore remain explicitly gated |
| Auth/security | MEDIUM | Strong hashing/JWT/scope controls pass; Internet-facing login lacks confirmed rate limiting |
| Public Web security | MEDIUM | Loopback gateway boundary is sound, but defense-in-depth headers remain deferred |
| AI grounding/hallucination | LOW-MEDIUM | Deterministic citations, facts/hypotheses and bounded tools reduce but cannot eliminate model error |
| AI data isolation | LOW | Client/Inspection scope, source maps, deny-by-default tools and tests pass |
| Vision privacy | MEDIUM | Inputs are minimized and Temporary Chat is isolated, but external retention and UI/auth dependency remain |
| Ingestion correctness | LOW-MEDIUM | Real post-patch Gmail/Sheets records and idempotency exist; two processing anomalies remain |
| Release/update | LOW-MEDIUM | Hash/signing/manifest compatibility pass; Windows reproducibility and physical Android smoke remain open |
| Operational recovery | LOW-MEDIUM | Reboot and scheduled backup passed; external alerting is absent |
| Hardware/resources | LOW | Ample disk/RAM and zero WSL swap pressure; unused model storage is non-critical |

## Test and health evidence

- Backend/contract: 107 focused approved tests pass (25 CHUNK 17/Vision/
  migration contracts, 13 Agent tests, 69 Search/Client AI/Business/
  Technical/Projects/Inspection/Timeline/document tests).
- Sheets fake-repository idempotency: PASS.
- Admin lifecycle isolated-schema rollback E2E: PASS; production writes 0.
- Supervisor queue contract and Vision worker contract: PASS.
- Flutter analyze: PASS, no issues.
- Flutter full suite: **168/168 PASS**.
- Public Web: HTTP 200; login and direct Agent route auth guard PASS; no browser
  console errors in the controlled unauthenticated smoke.
- Health aggregate: PostgreSQL, backend, Ollama, Qdrant, n8n, Open WebUI,
  supervisor, Vision dispatcher, disk, backup freshness and migration revision
  PASS.
- Generic `unittest discover` was intentionally not used: the test tree also
  contains operational/audit scripts, including historically mutating scripts.
  A broad live CRM/intake E2E bundle was not re-executed after the safety
  reviewer rejected it; current read-only evidence and earlier release gates
  are recorded instead of bypassing that control.
- Current audit DB counts were rechecked after tests and remained unchanged.

## Secret and repository hygiene

Safe tracked-file scans found no committed credential, token, private key,
cookie, `.env`, Edge profile, dump, backup or release binary. `.gitignore`
covers environment files, data/spool, logs/temp, dumps/backups, Edge profile,
keystores and generated release artifacts. Existing unrelated untracked audit
reports, corrupted backups, `releases/` and `staging/` were not touched.

## Final safety accounting

- Business writes: 0.
- Qdrant writes/backfill/upgrade: 0 / NO / NO.
- n8n business/workflow writes: 0.
- Vision or historical backfill: 0.
- Historical cleanup or retention deletion: 0.
- Production restore: NO.
- Migration: NO.
- Release/version bump: NO; current stable remains 1.0.2+21.
- Public network/security configuration changes: 0.

## Explicit future approvals

The implementation phase is closed, but the following future actions remain
human-gated: public header/rate-limit changes, environment secret escrow,
Qdrant restore proof or vector backfill, NSIS installation, destructive backup
or data retention, CHUNK 7B schema/product work, production document retries,
container/model/pilot cleanup and external alerting integration.

## Release B addendum — NEXT Stabil 1.0.2+22 — 2026-08-20

Release B was published from source commit
`b375b2184ae5bb87742fb870153fa92953a343ae`. It contains completed FOLLOW-UP
CHUNK 06, 07, 09, 10 and 05: Client Activity/Timeline V2, Admin Change History,
Global Mail read/send and bounded refresh/reconciliation, shared image
thumbnails/internal viewer, Client status filters, ignored email/domain rules,
responsive User Management and audited User Edit.

Production DB remained at
`followup_change_history_entity_types_20260820`; no schema or business-data
write occurred during release. Backend health and the Release B regression
matrix passed. Flutter analyze passed, the full discovered suite passed
`223/223`, and the focused updater/version smoke passed `16/16`. Public Web
rendered the `1.0.2+22` login screen without console errors. Windows installer
and Android APK metadata are `1.0.2.22` and versionCode `22`; their public
SHA-256 values match the stable manifest. `minimum_version` remains `1.0.0`,
and previous `1.0.2+21` artifacts remain available for rollback. No Gmail send,
n8n workflow/schedule change, Vision job or Qdrant write occurred. Phase C /
FOLLOW-UP CHUNK 13 was not started and requires a new owner prompt.

## Release C addendum — NEXT Stabil 1.0.2+23 — 2026-08-20

Release C was published from Phase C source commit
`3e7f71a60f409185eabd0b8d89b39e4fffa51417`. It contains CHUNK 13 operational
Calendar, WorkItems, notes/Documents, absences and Android Home Screen Widget;
CHUNK 12 live Dashboard; and CHUNK 14 bounded Last Activity. Production DB
remained at `followup_calendar_tasks_20260820` with no pending migration and no
release-attributable business-data write.

Flutter analyze passed, focused Phase C passed `23/23`, updater/hash tests
passed `10/10`, and the full discovered suite passed `240/240`. The public Web
bundle loaded the NEXT Stabil login bootstrap with zero console errors. The
Windows installer is 13,100,722 bytes with SHA-256
`51AA30535141B7856467DB3D58FE17EF56A1B5C2A5F0C3480129A8B30CCC61A3`; the
signed Android APK is 63,907,499 bytes with SHA-256
`E0393523A437470B09DD66844771FB1930EEB281379D0813E911729C82DD4E1C`; and
`main.dart.js` is 4,092,259 bytes with SHA-256
`88ACB133F7485F7D2BAF923BC11698BC835BE2EA66B059A9BFD73EFEF26344DC`. Public
bytes matched these local hashes before the stable manifest advanced to build
`23`. `minimum_version` remains `1.0.0`; +22 artifacts remain available.

No Gmail send, n8n workflow/schedule change, Vision job or Qdrant write
occurred. Qdrant remains at 57 points. Physical Android widget and CHUNK 13
smokes are `UNVERIFIED` because no ADB device was connected. Next planned work
is FOLLOW-UP CHUNK 15, which was not started.

## Pre-CHUNK15 Trash lifecycle addendum — 2026-08-21

The approved `followup_admin_trash_retention_20260820` migration is active with
no backfill and an initially empty `trash_entries` ledger. Documents, Clients
and Users now use a seven-day recoverable Trash lifecycle with Administrator
restore, safe active-query exclusions, Change History evidence and User JWT
`auth_version` invalidation. Clients and Users permanently become anonymized
tombstones; non-vector Documents retain a minimal provenance tombstone after
safe content/file purge.

The Windows task `NEXT Stabil - Trash Purge` is enabled every four hours with a
100-entry limit, singleton advisory lock, row-lock revalidation and per-entry
failure isolation. The production acceptance run reported zero eligible and
zero purged entries. The approved Qdrant completion now verifies each canonical
DB `document_chunks.vector_id` against the Qdrant point's `document_id` and
`chunk_id`, rejects foreign or untracked points, deletes only the exact verified
IDs and verifies absence before content/file purge. Missing exact points support
idempotent retry; outages and ownership drift fail closed. Destructive tests
refuse `ai_lab_document_chunks` and use a temporary `ai_lab_test_*` collection.
Production empty-queue acceptance left Qdrant unchanged at 57 points. Flutter
analyze and the full discovered `246/246` suite pass. No real Client, Document,
User or the owner's WorkItem realization was modified for acceptance; CHUNK 15
was not started, the owner-requested Flutter patch scope remains pending, and no
release was performed.

## Interim owner patch release addendum — NEXT Stabil 1.0.2+24 — 2026-08-21

The completed Admin Trash / seven-day retention hotfix and Calendar / Task
Detail / Realization owner patch were published from source commit
`d06707cef5da0e94cbc92e9c9843d67cdbcac7c6`. This is an interim stable release
between Release C and Phase D, not Release D. Production DB remains at the
single head `followup_work_item_realization_link_20260821`; no release migration
or production business-data write occurred. The legacy owner realization stayed
unchanged with `project_id = NULL`.

Flutter analyze passed, focused Trash/Calendar/Realization tests passed `17/17`,
updater/hash tests passed `10/10`, and the full discovered suite passed
`250/250`. The backend release matrix passed on guarded isolated databases and
test-only Qdrant collections. A flaky test expectation was corrected to compare
the already canonical sorted Qdrant purge plan rather than random UUID creation
order; production purge behavior was unchanged.

The Windows installer is 13,383,505 bytes with SHA-256
`4C2B4F6C9A44F8C76B5BA16A66A523B5F7D288545D30059B55630721448331F7`
and FileVersion `1.0.2.24`. The signed Android APK is 66,611,147 bytes with
SHA-256
`9B84EF8F350B6A2199C4304F35BE78012088C3800F2FEBF6CD2C820A5912C3DF`,
versionName `1.0.2`, versionCode `24`, and the same signing certificate as
`1.0.2+23`. Web `main.dart.js` is 4,803,350 bytes with SHA-256
`53939AC05FFEB53F4B9521070D20BDCC5612EA5B867F09B29F715B181316BAEC`.
Public bytes matched local hashes before the stable manifest advanced to build
`24`. The public Web login bootstrap loaded with no console warnings/errors.

`minimum_version` remains `1.0.0`, so update from `1.0.2+23` is optional;
`1.0.2+23` and `1.0.2+22` Windows/Android artifacts remain available for
rollback. Trash Scheduler remains enabled/Ready every four hours with batch
100. Production Qdrant remains at 57 points. Gmail sends, n8n changes, Vision
jobs and Qdrant writes/deletes attributable to release are zero. Physical
Android and widget smokes remain `UNVERIFIED` because ADB is unavailable.
Canonical next work is FOLLOW-UP CHUNK 15, which was not started.

## Post-1.0.2+24 consistency hotfix addendum — 2026-08-21

No schema or release change was required; production remains NEXT Stabil
`1.0.2+24` at DB head `followup_work_item_realization_link_20260821`. Client
Details Documents now use the same Administrator-only canonical Trash action
as the global repository, including seven-day confirmation, broad active-cache
invalidation and valid pagination after removal. Acceptance did not Trash a
production Document.

The default admin User list is now server-side active-only. Exact inactive test
User `phase2f_103833` (ID `2`) was moved through the approved User Trash service:
the row remains, `auth_version` advanced from `0` to `1`, Trash entry `2` is
recoverable until `2026-08-28T09:16:45.648286Z`, and no other User changed.

The exact active orphan realization `fundament 600kg` (WorkItem `1`, Client
`Szymon Pastuszak`, 2026-08-25 through 2026-08-28) had zero matching Projects.
The guarded owner-approved transaction created Project `1080`, linked the same
WorkItem, preserved its `todo` → `planned` mapping and wrote safe Change
History. WorkItems stayed at `1`, Projects changed `0 → 1`, and no broad
realization backfill ran.

Guarded isolated backend suites for Trash, realization integration, Auth,
Change History, Recent Activity and Client Search passed. Flutter analyze
passed, focused tests passed `45/45`, and full tests passed `252/252`.
Production Documents, Clients, Candidates, Absences, Qdrant points, Gmail,
n8n and Vision were unchanged. CHUNK 15 and release `1.0.2+25` were not started.

## Post-1.0.2+24 hotfix release addendum — NEXT Stabil 1.0.2+25 — 2026-08-21

The post-`1.0.2+24` consistency hotfix was published from source commit
`0fe990ffdaedc5d60da2146672c7720a3ba5b095`. This is a bounded interim hotfix,
not Release D. Production DB remains at the single Alembic head
`followup_work_item_realization_link_20260821`; no release migration ran.
Exact test User `phase2f_103833` remains inactive with `auth_version = 1` and
recoverable Trash entry `2`. WorkItem `fundament 600kg` remains linked to
canonical Project `1080`; neither record was modified during release.

Flutter analyze passed, focused hotfix/updater tests passed, and the full
discovered suite passed `252/252`. Public Web loaded the NEXT Stabil login
screen without console errors. The Windows installer is 13,385,453 bytes,
FileVersion `1.0.2.25`, SHA-256
`A132C6FC9FEF54800E18C769D759F45779839005107FF137B53AA5F3DB3B9A1F`.
The signed Android APK is 66,693,111 bytes, versionName `1.0.2`, versionCode
`25`, SHA-256
`BC14297ADFAB348D30DCC5360816945321FE39EA3FB603AE3FF82795FA07CB6C`;
its signing certificate matches `1.0.2+24`. Web `main.dart.js` is 4,806,823
bytes with SHA-256
`FCF527218ADC73EBD43C5E8EB8D982A027B57EA24940E30C3FC8CBC5AEF1FE34`.
Public bytes matched local artifacts before stable moved to build `25`.

`minimum_version` remains `1.0.0`, making the update from `1.0.2+24`
optional. The +24 and +23 Windows/Android artifacts remain available. Backend
health is HTTP 200, Trash Scheduler remains enabled/Ready every four hours,
and Qdrant remains at 57 points. Release-attributable business writes, Gmail
sends, n8n changes, Vision jobs and Qdrant writes are zero. Physical Android
smoke is `UNVERIFIED` because ADB is unavailable. Canonical next work remains
FOLLOW-UP CHUNK 15, which was not started.

## CHUNK 15 scheduler completion addendum — 2026-08-21

FOLLOW-UP CHUNK 15 Administrator Backup + Controlled Restore is complete at
production DB head `followup_admin_backup_restore_ui_20260821`. The canonical
03:00 Europe/Warsaw Full schedule is stored in `backup_schedules` as ID `1`
and synchronized to the single enabled managed Windows task
`NEXT Stabil - Backup - 1`. The historical `NEXT Stabil - Daily Backup` task
is retained disabled, eliminating duplicate execution; Trash Purge remains
enabled/Ready with its original four-hour, batch-100 definition.

Scheduled-path acceptance used temporary database-only schedule `2` and
created retained checkpoint `20260821T154344Z`. Backup run `1` records
`trigger=scheduled`, completed/verified, 464,454,695 bytes, manifest schema
`NEXT_STABIL_BACKUP_V1`, and a matching PostgreSQL artifact SHA-256
`ad20ed8b52982bb9e8db3dcbabfcfa0d9f19076437daffdb62f34c8bd207228e`.
The acceptance schedule is disabled and its managed task removed; history and
checkpoint remain. No retention deletion was introduced.

Isolated guarded backend Backup/Restore tests, Node scheduler tests and
PowerShell parsing pass. Actual Windows proofs cover missing-task creation,
trigger update, disabled-task removal and fail-closed unmanaged-name collision.
Flutter analyze and focused `8/8` pass; the full discovered suite passes
`268/268`. Android, Web and Windows debug builds pass. Qdrant points, CRM data,
Gmail, n8n and Vision were unchanged, and no production restore occurred.
Production restore remains a permanent destructive operational gate:
`FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED`. The next roadmap item is the
owner-inserted PRE-CHUNK16 Windows Disaster Recovery App, not started; CHUNK 16
is not started and no release was performed.

## PRE-CHUNK16 Recovery App trust checkpoint — 2026-08-21

The standalone C# WinForms/.NET Framework 4.8 Recovery Tool `1.0.0` source is
implemented and remains independent of Flutter, backend authentication and
PostgreSQL backup-history tables. Unit tests pass `11/11`; the canonical real
checkpoint validates for Database and Full modes and earlier isolated Database
and Full restore proofs pass without production cutover.

Executable acceptance remains blocked. Bitdefender Virus Shield quarantines the
unsigned 53,248-byte build at file-write time as
`Gen:Variant.MSILHeracles.239070`, before SHA-256 retention or UI smoke. No valid
Code Signing certificate with an accessible private key exists in
`CurrentUser\My` or `LocalMachine\My`. No antivirus protection, SmartScreen,
firewall or trust policy was weakened. Recovery App status is `PARTIAL` behind
`RECOVERY_APP_TRUST_POLICY_APPROVAL_REQUIRED`; CHUNK 16 and release remain not
started.

## PRE-CHUNK16 PowerShell Disaster Recovery completion — 2026-08-21

The owner replaced the blocked custom executable path with the canonical
Windows PowerShell 5.1 operator tool
`operations/recovery/NEXT-Stabil-Recovery.ps1`. It reuses the single offline
restore engine, supports manual folder selection and explicit Database/Full
`-ProofOnly` modes, and has no Flutter, backend/JWT, Supervisor or PostgreSQL
backup-history dependency. The seven-artifact checkpoint `20260821T142509Z`
passed manifest, size, SHA-256, DB format, compatibility and Qdrant structural
validation; isolated Database and Full proofs passed without production
cutover. Wrapper/fail-closed tests pass `15/15`.

The WinForms source is retained as DEFERRED / ENTERPRISE TRUST BLOCKED. WDAC,
Bitdefender, certificate stores and SmartScreen were unchanged. Production
restore remains behind `FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED`, no
business data changed, no release occurred, and CHUNK 16 remains not started.
