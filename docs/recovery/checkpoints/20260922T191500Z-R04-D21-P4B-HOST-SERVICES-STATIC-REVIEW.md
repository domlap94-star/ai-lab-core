# R04 / D-21 / P4-B — host-services static security-review material

- entry HEAD: `1b36cf679828a8283cdbca1e77aeaa4c8757f724`
- owner decision base HEAD: `09834d928017032f0e29c62163e04d8af3c52274`
- scope: `SOURCE / LOCAL FILE READ / STATIC SECURITY-REVIEW DECISION RECORDING`
- status: `STATIC_SOURCE_REVIEW_ACCEPTED / NOT_EXECUTED / NOT_AV_CLEARANCE /
  REFUSAL_SOURCE_NOT_ATTRIBUTED / FORMAL_APPROVAL_PATH_NOT_AVAILABLE_IN_SESSION /
  STAGE_B_BLOCKED_NOT_AUTHORIZED`

## Preserved history

The historical LOCAL_ONLY wrapper was recorded as `17386` bytes with SHA-256
`02ACD6700BD6551491F41907C1A9F5FB7C125ECB7C49577F8B58A96E2AB57F56`.
Its only requested execution was refused before process creation with:

`This script contains malicious content and has been blocked by your antivirus software.`

A later exact-path read returned `ERROR_FILE_NOT_FOUND`. No broad search,
quarantine restoration, reconstruction or alternate runner was used. The owner
states that a NEXT Stabil exception was configured earlier in Bitdefender
Advanced Threat Defense. This statement is not a current configuration read and
does not attribute the historical refusal to Bitdefender.

## New review-only material

LOCAL_ONLY root:
`C:\ai-lab-core-recovery\build\P4B-HS-REVIEW-01`

| File | Bytes | Raw SHA-256 |
|---|---:|---|
| `observe-host-services.candidate.ps1` | 7940 | `4DCFE146ED51A8F68FECEB8DCB10FD1A873F4D88CC0892EDC372574B8B7890F9` |
| `REVIEW_INDEX.md` | 3706 | `2B0C9015616AF64151652DF208C58B904309C037890E92AFA58CDF9C1032FE8B` |
| `SECURITY_REVIEW_REQUEST.md` | 2616 | `6F0898F13EC7E412D175DD4EA5D4E798EB13AFA339F476D8A57B6F9CE8A8429B` |
| `FILE_HASHES.txt` | 289 | `047C26E112E1802C7F068C10053DBD5FE342879C3B3D901211AE32C88E856548` |
| `P4B-HS-STATIC-REVIEW.zip` | 7042 | `D176B9689CE8576576B001699E06BCD1174FAAFFFB41CC1CC57CF2D2FCB35CFE` |

The archive lists exactly the four non-ZIP files above. The candidate pins the
accepted launcher/runtime hashes
`B4143A6934E6723E3293A6D5A4806A4F01D34CB53037C6417B16830BD4EC7892`
and
`959768E297BCB93FF1AF3D7EE5A174313F9DC053707EDE8C45D3A84D024B0732`.
It exposes only the existing bounded `OBSERVE` operation for Public Gateway,
Private Gateway and Supervisor. Docker, HTTP, desktop and start boundaries are
explicit refusal stubs. The glue was inspected as text only; it was not
dot-sourced, imported, parsed by PowerShell or executed.

Secret scan found only descriptive occurrences of `authorization` and
`credentials`; credential material found: `0`. This is not a claim that the
candidate is safe, a false positive, or security-approved.

## Owner static acceptance and formal boundary

The owner accepted the static review of the exact candidate
`4DCFE146ED51A8F68FECEB8DCB10FD1A873F4D88CC0892EDC372574B8B7890F9`
only as `STATIC_SOURCE_REVIEW_ACCEPTED / NOT_EXECUTED / NOT_AV_CLEARANCE`.
Read-only .NET SHA-256 checks on the decision base confirmed the candidate,
the `7042`-byte ZIP and the two pinned dependencies without invoking the
candidate or a PowerShell parser.

No Bitdefender, ATD, antivirus or endpoint-protection approval mechanism is
available among the tools exposed to this session. Sandbox command approval is
not an antivirus clearance and was not used as a substitute. Consequently the
candidate was not submitted to a protection-layer decision and was not run.
There is no `FALSE_POSITIVE_CONFIRMED` finding.

If a real formal clearance is later obtained, execution still requires a new
current owner confirmation binding the exact candidate hash, the three-role
read-only scope and output
`C:\ai-lab-core-recovery\build\P4B-HS-REVIEW-01\o1\host.json`. The exact future
executable remains Windows PowerShell 5.1 with `-NoLogo -NoProfile
-NonInteractive -File` and `-OutputPath`, under the already specified bounded
runner. None of those execution steps are authorized or performed here.

## Effects and decision

PowerShell processes, wrapper executions, Task/CIM/TCP/Docker/HTTP reads,
workers, task writes, starts, UAC, install, warm runs and rollback: `0`.
Public/Private/Supervisor remain `NOT_OBSERVED`. Installed run01 is unchanged.

Only missing approval: a formal decision by the responsible protection layer
on these exact candidate bytes. The required mechanism is not available in the
current session. After a real clearance, a separate current owner authorization
would still be required. No protection change, exception, retry, alternate
channel or Stage B is authorized here.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Before evaluation and the next prompt, read roadmap §0,
`ANTI_EXCESSIVE_WORK`, the active R04 card and this checkpoint from the full
published SHA. Preserve D-23 review `2/2` and all accepted stages. K0/K1:
`P4B-PREFLIGHT-HOST-RUNNER — static review of the exact new bytes is owner-
accepted, but no formal protection-layer clearance or authoritative PS5.1
host-service observations exist.` Effect: Stage B remains blocked. Next step:
one formal protection-layer decision on the exact candidate; do not add K2/K3,
retry the host operation or treat sandbox approval as AV clearance.
