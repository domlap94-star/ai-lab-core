# R04 / D-21 / P4-B — exact ZIP restored and VerifyOnly PASS

UTC: `2026-09-22T07:48:37Z`

Status: `EXACT_REVIEW_ZIP_RESTORED_FROM_OWNER_SUPPLIED_IDENTICAL_BYTES /
P4B_VERIFYONLY_PASS / CURRENT_READ_ONLY_TASK_AND_FILE_EVIDENCE`.

## Exact package gate

The owner-supplied file
`G:\Mój dysk\cad\R04-D21-P4B-PS51-SHA256-REVIEW-20260921T192345Z.zip`
was a regular file with `223585` bytes and SHA-256
`0DE0E072A6030F00159CAFD32CEE73636AC2033B7AFE73F42BD4838BB73414F8`.
It was copied without overwrite to the previously absent exact target
`C:\Users\domai\AppData\Local\Temp\P4B-SHA-01\R04-D21-P4B-PS51-SHA256-REVIEW-20260921T192345Z.zip`.
The target has the same size and SHA-256; restoration completed at
`2026-09-22T07:39:48.9047726Z`. The archive was not rebuilt, repacked or
extracted over the existing package.

The complete preflight then matched all `4/4` top-level artifacts and all
`8/8` non-empty payload bindings. The unchanged operation ID is
`R04-D21-P4B-HOST22-NUP-20260920T200422Z`. The recipe/package/review index
hashes remain respectively:

- `CA6A5DCC4CD472332D32178FD3AEB659A9828FE9A746B02E3FCD188893387157`;
- `C2F6A77CC09869E26473BA85B1E21F4A1784E359D423A79A08C6E3086D12B8AA`;
- `A4D2A5DB4BAD4A9DAF93ED76DC36D5902AF799DB24986E9D3FF5A6DC6B1732DE`.

## One VerifyOnly execution

The previously absent `vfy1` directory passed an exact sentinel
write/read/delete check while `vfy1\out` remained absent. Exactly one
ordinary-token Windows PowerShell 5.1 process then ran the unchanged recipe
with `-NoLogo -NoProfile -NonInteractive`, `-Mode VerifyOnly`, the pinned
operation ID, package index and output root. Attempt ID:
`R04-D21-P4B-VERIFYONLY-ZIP-RESTORED-20260922T074412Z`.

Window: `2026-09-22T07:46:18.3640556Z`–`2026-09-22T07:47:13.7134368Z`;
duration `55349.381 ms`; PID `88332`; exit `0`; timeout `false`; child and both
output streams settled. `stdout` was complete (`544` bytes), `stderr` was
complete and empty (`0` bytes). No retry was made.

The persisted `out\result.json` reports:

- `mode=VerifyOnly`, `status=VERIFIED_NO_MUTATION`;
- `mutation_started=false`, `pending_mutation=false`;
- `changed_roles=[]`, `warm_runs=[]`;
- `journal=NOT_OPENED`, `rollback=NOT_NEEDED`;
- `five_other_tasks_changed=0`, `helper_changed=false`.

The recipe completed its bounded read-only observations of the five pinned
dependency tasks and `NEXT Stabil - Host`. Task writes/starts, UAC, Stage B,
InstallAndWarm, Host retry, warm runs, runtime/file installation and rollback
were `0`. Docker, WSL, HTTP, SQL, CIM, TCP and the fresh six-container preflight
were `NOT_RUN`. This result does not accept Stage A, P4/B or R04 and does not
change historical run01.

LOCAL_ONLY evidence under
`C:\Users\domai\AppData\Local\Temp\P4B-SHA-01\vfy1`:

| File | Bytes | SHA-256 |
|---|---:|---|
| `command-plan.json` | 1423 | `9E86158A7BC19A976EBA935A9FDAE0D31484543B629D012E27CBD1B054145D5D` |
| `stdout.txt` | 544 | `F0A51E55F354B97CDE9E4AC31C6FA61C078334A27661BA354B35D69DA20ED5A6` |
| `stderr.txt` | 0 | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| `command-metadata.json` | 2156 | `13782432D1408162806FE8900EA357453973D4FD1CF43DF110CEB7004138F9F4` |
| `out/result.json` | 544 | `F0A51E55F354B97CDE9E4AC31C6FA61C078334A27661BA354B35D69DA20ED5A6` |

## Handoff and STOP

One next decision: owner review of this exact read-only result. Any Stage B,
UAC, installation, Host retry/start, task write, warm run or rollback remains a
separate explicit authorization. D-23 remains `REVIEW_2_OF_2_COMPLETED`; no
K2/K3 search was opened.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Before evaluation read roadmap §0, `ANTI_EXCESSIVE_WORK`, the active R04 card
and this checkpoint at its published SHA. Preserve existing acceptances. Fix
only demonstrated material impact; K2/K3 do not block acceptance and do not
create automatic work. K0/K1: `BRAK NOWEGO PROBLEMU`; the exact package gate
and the single bounded VerifyOnly passed. Effect: current read-only task/file
evidence only, with zero mutation. D-23 remains review `2/2`. Next step is
owner review; there is no permission for host operations.
