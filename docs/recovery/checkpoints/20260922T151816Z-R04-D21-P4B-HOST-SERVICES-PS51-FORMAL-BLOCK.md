# R04 / D-21 / P4-B — PS5.1 host-services-only read formally blocked

- UTC verification: `2026-09-22T15:18:16.1903470Z`
- entry/evidence HEAD: `1895fb3f25348960be1fe23826a32f58b2318f97`
- package operation ID: `R04-D21-P4B-HOST22-NUP-20260920T200422Z`
- status: `P4B_HOST_SERVICES_PS51_READBACK_NOT_RUN /
  FORMAL_ANTIVIRUS_BLOCK_BEFORE_PROCESS / STAGE_B_BLOCKED_NOT_AUTHORIZED`

## Preserved accepted evidence

The successful VerifyOnly remains accepted only as
`P4B_VERIFYONLY_TASK_AND_FILE_EVIDENCE_ACCEPTED / READ_ONLY_SCOPE`. The earlier
package `4/4 + 8/8`, pinned containers `6/6`, PostgreSQL `running+healthy`,
HTTP `200/200/200/404/404` and Windows/disk evidence remain preserved. They were
not repeated. Docker/WSL pool availability and current swap use remain
`UNKNOWN`.

## Exact attempted read

The owner authorized one read-only replacement campaign for Public Gateway,
Private Gateway and Supervisor under exact
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`. The closed
LOCAL_ONLY wrapper is:

- path:
  `C:\Users\domai\AppData\Local\Temp\P4B-WIN-01\hs51\observe-host-services.ps1`
- size: `17386` B
- SHA-256: `02ACD6700BD6551491F41907C1A9F5FB7C125ECB7C49577F8B58A96E2AB57F56`
- Windows PowerShell 5.1 static parser: `PASS`

Its only actual launch was rejected before the process started:

`This script contains malicious content and has been blocked by your antivirus
software.`

The refusal came from the formal security boundary. It was not bypassed, no
alternate runner/channel was used, and the operation was not retried.

## Result and effects

No `engine-identity.json`, campaign result/failure, runner metadata,
stdout/stderr or sentinel exists. Therefore:

| Layer | Result |
|---|---|
| PS5.1 process identity | `NOT_OBSERVED_PROCESS_NOT_STARTED` |
| Public Gateway / 8789 | `NOT_OBSERVED` |
| Private Gateway / 8788 | `NOT_OBSERVED` |
| Supervisor / 8787 | `NOT_OBSERVED` |
| Task/CIM/TCP reads | `0` |
| owned workers | `0` |
| service/task/Docker starts or writes | `0` |
| HTTP/resource/VerifyOnly repeats | `0` |
| UAC/install/warm runs/rollback | `0` |

This checkpoint does not convert missing evidence to absence or conflict. The
historical installed run01 remains unchanged; Host remains historically
disabled/no-trigger with warm `0/2`, and Supervisor remains historically
`INTENTIONALLY_STOPPED`, not freshly observed here.

## One next decision

Owner/security review must decide whether the prescribed approval mechanism may
authorize these exact wrapper bytes, or whether the read remains blocked. There
is no automatic retry and no permission to change execution channel. Until a
future authoritative PS5.1 result exists, Stage B remains
`BLOCKED / NOT_AUTHORIZED`.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Before evaluation and the next prompt, read
[roadmap §0, ANTI_EXCESSIVE_WORK and the active R04 card](../../../NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md)
from the full published SHA containing this checkpoint. Preserve accepted
evidence and do not search for K2/K3. K0/K1:
`P4B-PREFLIGHT-HOST-RUNNER — the required PS5.1 host-service gate is still
missing because formal security blocked the process before Task/CIM/TCP reads;
evidence is the absent process/output metadata and the exact nonsensitive
refusal.` Effect: no Stage-B confirmation or mutation. D-23 review `2/2`
remains completed. Next step: one owner/security decision through the prescribed
approval path; no host operation is authorized.
