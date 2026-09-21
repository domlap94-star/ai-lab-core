# R04 / D-21 / P4-B — NUP-03 Stage A blocked

UTC: `2026-09-21T08:47:15Z`

Status: `NUP03_HOST_COMPLETION_SOURCE_AND_OFFLINE_PACKAGE_ACCEPTED / NOT_DEPLOYED / P4B_STAGE_A_BLOCKED / NO_STAGE_B_AUTHORIZATION_REQUESTED`

## Scope and preserved acceptance

- The owner accepted the exact NUP-03 completion package only as source/offline:
  recipe `DC1295C3A82943C938521C404CD1F23302C4252FFDF25DB189A602BA14BC4A0A`,
  package index `B3B50FD3AE711EF817640B6E7B89A8A30B003A36C8708760C3720F9E84607919`
  and review ZIP `3ED49CB38370F8044DE76E596957CF07BAB92912ABB5BAFA37B6C3818BEFA09D`.
- D-23 review `2/2` remains complete. NUP-01/NUP-02 remain PASS in their
  reviewed scope, and the NUP-03 source/offline result is preserved. This
  checkpoint does not reopen those reviews or search for K2/K3.
- Stage A authorized integrity checks, exactly one non-elevated `VerifyOnly`,
  one bounded read-only projection and documentation. Stage B, UAC,
  `InstallAndWarm`, task writes, Host start and rollback remained forbidden.

## Package integrity

- Extracted index: `33/33`; ZIP entries: `34/34` including
  `REVIEW_INDEX.json`; payload bindings: `8/8`.
- ZIP: `125383` bytes, SHA-256
  `3ED49CB38370F8044DE76E596957CF07BAB92912ABB5BAFA37B6C3818BEFA09D`.
- `REVIEW_INDEX.json`: `14594` bytes, SHA-256
  `FB46215644B2960E68F49C27438B61F5ADF1A98B1B6E307617E697F4A3B063BE`.
- No package byte, XML, manifest, recorder, recipe or package index was
  changed.

## Exactly one VerifyOnly

- Evidence root: `C:\Users\domai\AppData\Local\Temp\P4B-NUP-EXEC-01`;
  preflight output: `pf01`; reserved Stage-B output `run01` remains absent.
- Window: `2026-09-21T08:36:13.4353323Z`–`08:36:15.5751824Z`, elapsed
  `2140 ms`, Windows PowerShell 5.1, `DOMAI\domai`, non-elevated.
- Exit `22`, status `TASK_DEPENDENCY_DRIFT`, exact blocker
  `NEXT Stabil - Docker Desktop`.
- `mutation_started=false`, `pending_mutation=false`, changed roles `0`, warm
  runs `0`, task starts `0`, rollback `NOT_NEEDED`, journal `NOT_OPENED`.
- `pf01\result.json`: `633` bytes, SHA-256
  `65D5E7A5BA0D2728AE2240BFB8B5166EFCDA18501AB14BCE783AFC11874E6FD8`.
- The command was not retried.

## One bounded read-only projection

The one projection persisted its answers before a local formatter expected a
nonexistent `status` member instead of the collector's `read_status` member.
The projection therefore exited `1`; no live read was repeated for formatting
and the four planned HTTP GETs were not run.

Preserved results:

- PostgreSQL, Qdrant, n8n, Open WebUI and Ollama matched their pinned full ID,
  image, configured mount/port identity and exact running state; PostgreSQL was
  `healthy`.
- The pinned backend was running with its expected full ID and image, but the
  production identity validator returned
  `CONTAINER_IDENTITY_MISMATCH:mounts`: the manifest uses
  `C:\ai-lab-core\...`, while the safe Docker projection returned
  `C:/ai-lab-core/...`. No container was adopted, started, stopped or changed.
- Public Gateway, Private Gateway and Supervisor observations each returned
  `CONFLICT / IDENTITY_MISMATCH`; no task or service was started or changed.
- `NEXT Stabil - Host` was observed `Disabled`, running/queued instances
  `0/0`, but with `trigger_count=1` and semantic hash
  `85C4C8176398B1D7C211684C119A6AE47426005F47E78252FF7F85336C2AF0F9`,
  not the pinned preimage hash
  `0EBD4DA250ADB2D033FCACF04B8ED41166FAA5DFF76A83C4C61A6C0120CDB702`.
- Windows resource thresholds passed: available memory `5.557 GiB`, commit
  reserve `34.929 GiB`, C: free `578.640 GiB`, D: free `854.574 GiB`.
  Docker/WSL pool availability and swap usage retain the acknowledged UNKNOWN
  limitation.
- The safe combined LOCAL_ONLY summary is `23453` bytes, SHA-256
  `E406F46D965B6B278FB2F4048B1F3B43192EAF1D4C67CFE542007471F63E68B4`.

## Decision and actual effects

Stage A is `BLOCKED`, not PASS. The exact package cannot progress because its
own `VerifyOnly` refused the current task dependency state. The independent
safe projection also found material identity/preimage mismatches and remained
incomplete after a local formatter error. These are concrete blockers to the
dependent Stage-B operation; this checkpoint does not prescribe or authorize
their repair.

Actual effects were limited to read-only Docker/Task/CIM/TCP/resource metadata,
local evidence files and short non-elevated PowerShell workers. Mutations,
UAC, `InstallAndWarm`, Host runs, service/container starts, rollback, SQL,
backup, restore, data/junction changes, P5, R06 and D-22 execution were `0`.
Installed run01 was not changed.

One documentation-path error occurred: the patch tool first created this new
checkpoint at
`C:\ai-lab-core\docs\recovery\checkpoints\20260921T084715Z-R04-D21-P4B-NUP03-STAGE-A-BLOCKED.md`
instead of in the recovery worktree. No existing file was overwritten. The
identical checkpoint was then written to the correct recovery path. The formal
request to remove only the accidental original-root file was rejected with the
non-secret reason that no trusted deletion approval exists outside recovery.
The file therefore remains pending an explicit owner-approved exact-path
removal; no alternate deletion channel was used.

Next step: owner review of this Stage-A blocker set. Do not request or execute
Stage B on this evidence, and do not repeat the consumed reads merely to obtain
a different formatting result.

> **ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT**
>
> Przed oceną tej zwrotki i kolejnym promptem przeczytaj
> `NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`: §0, `ANTI_EXCESSIVE_WORK`, aktywną
> kartę R04 i ten checkpoint na pełnym SHA publikacji.
>
> Zachowaj odbiory NUP-01/02, Host22 i source/offline NUP-03. Nie dodawaj K2/K3.
> K0/K1 blokujący ten krok: `P4B-STAGEA-GATE` — exact `VerifyOnly` zwrócił
> `TASK_DEPENDENCY_DRIFT`, a zachowana real-adapter projection wykazała dalsze
> identity/preimage mismatches; Stage B nie ma bezpiecznego PASS. Cykl review
> `2/2` pozostaje zakończony. Następny krok: jedna decyzja właściciela po review
> blokad; brak zgody na UAC lub operację hosta.
