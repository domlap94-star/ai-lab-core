# R04 / D-21 / P4-B — host-services static security-review material

- entry HEAD: `1b36cf679828a8283cdbca1e77aeaa4c8757f724`
- scope: `SOURCE / LOCAL FILE READ / STATIC SECURITY-REVIEW PREPARATION`
- status: `STATIC_SECURITY_REVIEW_MATERIAL_PREPARED / NOT_EXECUTED /
  REFUSAL_SOURCE_NOT_ATTRIBUTED / APPROVAL_PATH_NOT_ESTABLISHED /
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

## Effects and decision

PowerShell processes, wrapper executions, Task/CIM/TCP/Docker/HTTP reads,
workers, task writes, starts, UAC, install, warm runs and rollback: `0`.
Public/Private/Supervisor remain `NOT_OBSERVED`. Installed run01 is unchanged.

Next decision: identify the responsible protection layer and use its documented
review mechanism for these exact candidate bytes, followed by a separate current
owner authorization if execution is to be considered. No protection change,
exception, retry, alternate channel or Stage B is authorized here.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Before evaluation and the next prompt, read roadmap §0,
`ANTI_EXCESSIVE_WORK`, the active R04 card and this checkpoint from the full
published SHA. Preserve D-23 review `2/2` and all accepted stages. K0/K1:
`P4B-PREFLIGHT-HOST-RUNNER — exact new review bytes are available, but the
responsible refusal layer/formal approval path is not established and no
authoritative PS5.1 host-service observations exist.` Effect: Stage B remains
blocked without a new execution authorization. Next step: one security review
decision on the exact candidate; do not add K2/K3 or retry the host operation.
