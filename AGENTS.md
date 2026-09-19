# AI-Lab repository rules

## Scope and architecture

- Treat `AI_LAB_MASTER_PLAN.txt` as the product specification,
  `AI_LAB_FOLLOWUP_PLAN.md` as its supplements, decisions, and safeguards, and
  `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md` as the sole execution order and
  resume state. The three roadmaps retired by R01 remain recoverable in Git
  history but are not active instructions and must not be used to select or
  resume a package.
- Work in one small, reviewable, testable chunk at a time. Update the execution
  plan after every completed chunk.
- Supported Flutter targets are Windows, Android, and Web. Do not restore iOS
  or macOS support.
- Preserve the public/private boundary: public gateway `127.0.0.1:8789` may
  expose Web/API/updates but never `/control`; private gateway
  `127.0.0.1:8788` may proxy `/control` to supervisor `127.0.0.1:8787`.
- Target one installed NEXT Stabil root at `C:\ai-lab-core` and one ordinary,
  idempotent user start entrypoint. This is a gated R04 consolidation
  requirement, not permission to move/delete directories, change mounts/tasks,
  or deploy current work. R05-A4 source/API/widget tests are owner-accepted and
  committed. D-21/P1 authorizes launcher source and complete offline adapters
  only in recovery. P2 preservation/candidate is owner-accepted as NOT_DEPLOYED;
  the exact directory junction `C:\ai-lab-core\data -> D:\ai-lab-data` is the
  owner-approved `ACTIVE_DATA_ONLY` topology and may be validated offline.
  The owner-authorized D21-P3 backend-only switch now runs source
  `0ee0ea50943578e6e552aae23ce1688595ddc262` from the canonical backend path
  and is owner-accepted as `CORE_BACKEND_SOURCE_SWITCH_ACCEPTED /
  LIMITED_RUNTIME_SCOPE`; it is not acceptance of the global production set.
  D21-P4/A source `8756314f51a76091a483cfc9b677a05c7f67f315` and evidence
  `8a156e0c738699b4bfee01fb98f0d10f01c803ba` are owner-accepted as
  `SOURCE_OFFLINE_AND_IDENTITY_PACKAGE_ACCEPTED / NOT_INSTALLED`. A later bounded read-only campaign
  proved that four secondary draft IDs were transcription errors and reconciled
  all six exact container/image/digest identities in the inactive draft. This is
  `CURRENT_READ_ONLY_EVIDENCE`, not manifest approval. Phase A of bounded P4/B
  window `R04-D21-P4B-WINDOW-20260918T084652Z` prepared exact proposed
  manifest/task bytes and passed offline validation. The first exact Phase-B
  authorization was consumed after the Startup wrapper was moved and a
  disabled/no-trigger Host task was created; Windows then blocked the existing
  task updates and the first UAC was cancelled. A later single-use resume
  `R04-D21-P4B-RESUME-20260918T112015Z` was also consumed. Its one UAC was
  accepted and elevation/input checks passed, but the elevated pre-mutation
  Docker guard failed because Windows PowerShell 5.1 split the `docker inspect`
  Go-template argument passed through `Start-Process`. The resume recorded
  `mutation_started=false`. A later source/offline-only scope reproduced the
  split (56 received argv tokens instead of 7), prepared corrected LOCAL_ONLY
  recipe `5F310C64...1FD67`, passed PowerShell 5.1 17/17 cases and one exact
  read-only backend Docker inspect. The current installation state is still
  `PARTIAL_SAFE_INACTIVE`. A later owner-authorized static preflight confirmed
  the exact recipe/index bytes and all indexed inputs, but found that
  `Assert-ContainersUnchanged` resolved six baseline records under the new
  recipe root while those records were indexed under the previous consumed
  resume. A subsequent `SOURCE / LOCAL FILE READ / OFFLINE TEST ONLY` scope
  reproduced that fail-before and prepared LOCAL_ONLY input-bound recipe
  `733AA23F...D05B6A` plus package index `ED05FE26...875C`. The final Windows
  PowerShell 5.1 campaign passed 14/14 cases and 119 assertions with all 29
  indexed inputs and six baselines resolved by exact role/path/size/hash;
  Docker/task/HTTP/UAC/host mutations remained zero. This is `EXACT_PACKAGE_READY_FOR_REVIEW`,
  not operational authorization. Payload and
  manifest remain uninstalled, five existing tasks remain on their preimages
  and warm runs are `0/2`. A production manifest, further installation, task/shortcut changes, live
  start/rollback acceptance, relocation, cleanup and P4-B/P5 still require
  separate approval. Preserve
  existing runtime roots and historical A4 evidence until a later exact
  cutover/cleanup approval; production must never execute recovery, staging, or
  test WIP.

  A subsequent owner-authorized source/local-file/offline review reproduced
  `RV-P4B-FULL-01` through `RV-P4B-FULL-04` against the preserved preimage and
  prepared LOCAL_ONLY full-path recipe
  `16A35C328A091801A4713A7F282A72C7E143BE489BF847A1AEE15599F70C4DC8`
  with package index
  `1355EF0878C31202145E4E324C40A5D07E343FB78B0C6C7D029E2E932C43E3BF`.
  The final PowerShell 5.1 campaigns passed 14 input cases/110 assertions and
  10 orchestration cases/67 assertions; all 9 owned workers were accounted for
  and real Docker/Task/CIM/TCP/HTTP/UAC/host mutations remained zero. This is
  `FULL_ERROR_AND_SAFE_INACTIVE_ROLLBACK_PATH_READY_FOR_REVIEW / OFFLINE_ONLY /
  NOT_INSTALLED`, not P4/B acceptance or execution permission.

  The next owner-authorized source/local-file/offline review reproduced
  `RV-P4B-FULL-03B`, `RV-P4B-FULL-02B`, and `RV-P4B-FULL-02C` against that
  frozen preimage. The replacement LOCAL_ONLY recipe is
  `F6D3A8CC7AA57ED50244D773076700BCBE5771609762947B230E344C5C883F0E`;
  its package index is
  `FDF9FE7AF55A8285FB51506E3CBFA5368F366353748DC68BBCCBBC37164A977F`
  and its review ZIP is
  `D2B3263BE6ECB20E139CF63E7559C0E53605CE8827183989E37979247965DA1C`.
  Pending mutators now block competing rollback and dependent cleanup;
  restoring the legacy helper requires confirmed-safe Host and Compose
  consumers; rollback task writes require fresh, operation-owned identity.
  Final PowerShell 5.1 results were 14 input cases/110 assertions and 15
  orchestration cases/96 assertions with 437/437 workers accounted for and no
  real Docker/Task/CIM/TCP/HTTP/UAC/product mutation. Status is
  `ROLLBACK_DEPENDENCIES_AND_PENDING_MUTATIONS_READY_FOR_REVIEW /
  OFFLINE_ONLY / NOT_INSTALLED`; no live preflight or operation is authorized.

  On 2026-09-19 the owner accepted those exact recipe bytes only as
  `EXACT_ROLLBACK_SAFE_RECIPE_ACCEPTED / SOURCE_AND_OFFLINE_SCOPE /
  NOT_INSTALLED`. Local verification matched the 7-file review package, all
  six indexed package entries and all 29 external inputs. The unchanged recipe
  passed `VerifyInputsOnly` with external resume ID
  `R04-D21-P4B-EXACT-RESUME-20260919T094244Z`; the reserved execution output
  remained absent. The subsequent fresh read-only preflight did not produce a
  usable task projection: the preserved collector reached the first exact task
  read, then failed while writing its local XML because the selected evidence
  path exceeded the Windows path limit. Per the single-campaign rule, that
  task read was not repeated under a shorter path. Status is
  `PRE_UAC_BLOCKED / PREFLIGHT_EVIDENCE_NOT_PERSISTED_PATH_LENGTH`; UAC,
  Install, Docker/HTTP reads, warm runs and host mutations were not performed.
  A new owner decision is required for any replacement preflight. It is not
  permission to run Install or request UAC.

  The owner subsequently authorized one replacement read-only preflight under
  the fixed short root `C:\ai-lab-core-staging\recovery\P4B-PF-01`. Local
  UTF-8/XML/JSON and atomic-rename probes passed with a maximum planned path of
  90 characters. The frozen installer paths remain 205/252/275 characters and
  their future write compatibility is still `NOT_VERIFIED`. The bounded host
  collector persisted all six task XML files, including exact raw matches for
  the five pinned preimages, then exited `1` while projecting the Host trigger
  because the returned object had no `CimClass` property. Host static XML
  matches the disabled/no-trigger design after normalizing the exact owner SID
  and the task-schema default `LeastPrivilege`; dynamic Host state and
  `LastRunTime` were not persisted and were not read again. Docker, HTTP,
  remaining host/resource reads, UAC, Install, warm runs and installation/data
  mutations were not performed. Status is
  `REPLACEMENT_READ_ONLY_PREFLIGHT_PARTIAL /
  HOST_TASK_FORMATTER_CIMCLASS_FAILURE / NO_UAC / NOT_INSTALLED`. Another live
  read requires a new owner decision; this partial result grants no operational
  permission.

  The owner then authorized a collector-only correction and one bounded
  continuation under `C:\ai-lab-core-staging\recovery\P4B-PF-01\c2`.
  The corrected LOCAL_ONLY collector passed Windows PowerShell 5.1 offline
  tests (`13` cases, `61` assertions, owned workers `3/3`) and reprojected the
  six already saved XML files without another host read. The bounded campaign
  persisted all six task states, listeners, Windows resources, Docker-local
  metadata and six safe HTTP results. Six `TaskInfo` reads failed in the
  collector mapping layer and were not repeated; consequently `LastRunTime`
  and `LastTaskResult` remain `NOT_VERIFIED`. The Docker collector completed
  all six container, six image, one volume and one info reads; its final local
  formatter failed, so the safe projection was rebuilt only from the saved
  exit-zero records without another Engine read. All six pinned containers
  were running with unchanged exact identities/mounts/ports, restart count
  zero, and PostgreSQL healthy. Status is `P4B PREFLIGHT_EVIDENCE_PARTIAL /
  TASK_INFO_MAPPING_ERROR_NO_REREAD / NO_UAC / NOT_INSTALLED`. No task,
  service, container, installation or business-data mutation was performed.
  The exact installer recipe is unchanged; its reserved output path
  compatibility remains `NOT_VERIFIED_NO_IO`. This evidence grants no UAC,
  Install, warm-run or P4/B operational permission.

  A subsequent owner-authorized LOCAL_ONLY/read-only continuation fixed the
  exact TaskInfo child boundary and passed PowerShell 5.1 offline `16/126`;
  the single live campaign then persisted `TaskInfo 6/6`. It also prepared the
  exact short-output derivative recipe
  `F65DF7232ADC3DBFE6B35FC08D255D385748ED17CC3078CACB93501FB9BF8C9A`
  and package index
  `36623A0384F400D10D9FF0714FE7ED67B0090FC872C19751ED195D2E52C8D49E`.
  Input `14/110`, orchestration `15/96` with `437/437` workers, path/I/O
  budget `206<=220`, VerifyInputsOnly `29/29 + 6`, and ZIP roundtrip `17/17`
  passed. The bounded drift confirmed the six task/container identities,
  PostgreSQL health, backend/Public Gateway and public `/control*=404`;
  Docker/WSL pool available and swap-used remain `UNKNOWN`. Status is
  `SHORT_OUTPUT_DERIVATIVE_READY_FOR_REVIEW / TASKINFO_6_OF_6 / NO_UAC /
  NOT_INSTALLED`. `out\run01` remains absent. This is not acceptance of the
  derivative or authorization for RunAs/UAC, Install, task/file mutation,
  warm runs or rollback; those require the new exact single-use owner decision.

  The owner then accepted that exact derivative and authorized the single-use
  resume `R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z`. One RunAs/UAC was
  used. The exact three files and installed manifest were written and task
  definitions reached the recipe target, but the first Host warm attempt ended
  with `LastTaskResult=22` before Private Gateway started. The recipe consumed
  its one SAFE_INACTIVE and ended `PARTIAL_AFTER_FAILURE /
  SAFE_INACTIVE_PARTIAL_UNKNOWN`: Public Gateway remained `Running`, so
  dependent file/helper rollback was not allowed. Current confirmed state is
  Host `Disabled/no-trigger`, warm runs `0/2`, Private not started, Supervisor
  `INTENTIONALLY_STOPPED`, no Host logon trigger, and six unchanged running
  containers. Repository draft remains `NOT_APPROVED`; the exact installed
  manifest is the pinned `APPROVED_FOR_START` operation input. The operation,
  UAC and rollback authority are consumed. Do not retry Host/installer, perform
  another rollback or infer the cause of exit `22`; further diagnosis or
  mutation requires a new owner decision.

## Safety

- DEPLOYED BINARIES ARE API CONSUMERS. A source-code update does not mean that
  every API consumer has been updated. Before changing an existing response
  contract, account for current source, the latest stable Windows and Android
  builds, live Web, and integrations/imports. Do not break an existing public
  API response shape without a versioned/additive endpoint, compatibility
  layer, or an explicit release/migration strategy. Remove a legacy endpoint
  only when the minimum supported app version guarantees that no supported
  client still needs it.
- Never mutate production CRM data, merge/delete clients, run uncertain
  backfills, publish a release, change signing/secrets, or change network
  exposure without explicit human approval.
- Data cleanup must proceed through audit, read-only projection, dry-run,
  old-to-new report, conflict detection, approval, apply, and post-apply audit.
- Preserve provenance, source evidence, audit trails, and backward
  compatibility where reasonable.
- Use Alembic for schema changes. Destructive migrations require approval.
- Never commit `.env`, secrets, Android keys, keystores, release binaries,
  runtime data, generated reports, or backups.

## Tooling and verification

- Windows shell is PowerShell 5.1. Backend Python runs in Docker; do not assume
  a working host Python.
- Flutter SDK: `C:\FlutterSDK-New\flutter`.
- Do not run `flutter clean`.
- Read and write repository text as UTF-8 without BOM when practical.
- After every chunk run relevant backend tests, API auth tests, Flutter
  `analyze`/`test` when applicable, `git diff --check`, and `git status --short`.
- Never use `git add .`; stage explicit paths only.
- Do not commit a chunk whose acceptance criteria or required tests fail.

## NEXT Stabil — shared roadmap and checkpoint

- D-22 sets the first priority only after R04 is finished and owner-accepted:
  approved Excel/Google Sheets are the sole evidence source for historical
  Client field repair, followed by validation, then analysis and linking of
  only a closed set of still-unassigned mail. Never use mail, threads,
  attachments, or imported mail-note text to repair Client fields; never
  reanalyse or relink already assigned mail in that campaign. Preserve correct,
  manual, confirmed, and deliberately cleared values per field. After the
  future approved implementation, an unambiguous new Sheet row creates or
  links one Client directly and idempotently. Invalid or conflicting Sheet rows
  become import exceptions for review, never CRM candidates; CRM candidates
  originate only from qualifying unmatched mail. A changed linked row adds
  versioned information and visible provenance without deleting older CRM data;
  clearing/removing source cells or rows never deletes the Client or relations.
  Qualifying mail creates a candidate only when it cannot be matched to an
  existing Client; a later Client/contact may resolve one unambiguous mail
  candidate by email OR phone without rewriting Client fields from mail.
  Preserve the existing n8n 15-minute mechanism for incremental new Gmail and
  new/changed Sheet records, with stable checkpoints, idempotency and visible
  failures. These are documented future requirements, currently `NOT_RUN`;
  this priority does not interrupt R04 or authorize production audit, data
  writes, Gmail/Sheets/n8n access, models, import, merge/delete, or deployment.
- Before changing code, read section 0 of the shared roadmap, the active package
  card, linked requirements, and the latest note in `docs/recovery/checkpoints/`.
  Verify branch `recovery/next-stabil-repair-completion`, remote SHA, the correct
  local worktree, and uncommitted state. Do not assume default main or chat
  history describes the current stage.
- Execute only the authorized package and its remaining substep. Do not create a
  new roadmap, change scope/criteria, or replace 9B/KB/Temporary Chat. "Continue"
  does not consume operational approvals or authorize the next package.
  `WAITING_APPROVAL` requires the applicable decision.
- D-21 P3 authorized and completed exactly one backend-only source switch for
  OP_ID `R04-D21-P3-CORE-SWITCH-20260917T141404Z`. That consumed operation does
  not authorize another recreate, rollback without a new trigger/decision,
  Supervisor start, runtime/config/data/mount/task changes, migration, backup,
  restore, escrow, relocation, cleanup, or continuation into P4-B/P5. P4-A is
  owner-accepted only as source/offline plus an inactive local package; its
  repository draft manifest remains `NOT_APPROVED`. The bounded read-only
  identity evidence is complete 6/6 after a documented transcription
  correction. The P4/B authorization for OP_ID
  `R04-D21-P4B-WINDOW-20260918T084652Z` and the later resume authorization
  `R04-D21-P4B-RESUME-20260918T112015Z` are consumed. The later short-output
  resume `R04-D21-P4B-RESUME-SHORT-OUTPUT-20260919T202300Z` is also consumed.
  It installed the exact payload/manifest but stopped after Host result `22`;
  SAFE_INACTIVE remained partial, Host is disabled/no-trigger and warm runs are
  `0/2`. A later read-only diagnosis, without retry, showed an unsafe optional
  `.State.Health` projection and a broad Compose selector matching the approved
  backend plus four retained drill containers. Status is
  `HOST22_DIAGNOSED_READ_ONLY / SOURCE_FIX_REQUIRED / NO_RETRY_AUTHORIZED`.
  This is not P4/B acceptance. Any continuation requires owner review and a new
  narrowly defined SOURCE/OFFLINE decision before any later operational
  decision. No standing permission exists for another UAC, retry, rollback,
  reboot/logoff, Supervisor, backup/restore, relocation, P5 or R06.
- One writer at a time. ChatGPT may read concurrently, but checkpoint/source
  writes are serialized by the workflow; never automatically overwrite remote,
  force-push, or create a second "canonical" branch.
- After a meaningful substep/test/blocker change, before pausing, and at the end,
  update the checkpoint, actual results, and one next step. When package status
  changes, synchronize derived indexes in the same commit. Section 0.2 is the
  status authority; historical audit assessments stay unchanged.
- The ban on committing generated reports has a narrow exception for reviewed,
  sanitized planning maps and small resume notes under `docs/recovery/`. It does
  not cover dumps, raw logs, source copies, secrets, `.env`/cookies/keys,
  binaries, company data, backups, or runtime storage.
- A documentation checkpoint describing `FAIL`/`PAUSED` may be committed and
  pushed despite an unfinished feature. That is not authorization to commit
  failing source as ready or mark `SOURCE_PASS`/`ACCEPTED`. Source changes/tests
  and operations still require the package scope and all existing gates.
- Before publication, verify the staged allowlist, full diff, secrets, and CI
  safety. Push only the authorized branch; never main/tag/release/deploy. After
  push, compare local/remote SHA and read the file at that SHA. Report missing
  synchronization as `LOCAL_ONLY`.
- Protect work-in-progress code separately: a roadmap checkpoint does not save
  uncommitted work. After a crash, first determine whether the prior operation
  completed and what it changed; never repeat a non-idempotent apply blindly.
- Never write `ACCEPTED` without actual owner acceptance. Every decision names
  the evaluated SHA, scope, and evidence; a later implementation change can
  invalidate only the applicable evidence, not the whole roadmap.
