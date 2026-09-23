# R04 / D-21 / P4-B — USABLE-WARM package prepared, live preflight formally blocked

- UTC: 2026-09-23
- Window ID: `R04-D21-P4B-USABLE-WARM-20260923T170936Z`
- Entry/evidence HEAD: `3afe74be23ad6bbd413b4c90d3153bdccaaef0dc`
- Accepted source: `49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc`
- Source evidence: `3afe74be23ad6bbd413b4c90d3153bdccaaef0dc`

## Owner acceptance and unchanged production state

The owner accepted the host-service process/listener observation source only as
`SOURCE_AND_OFFLINE_ACCEPTED / NOT_DEPLOYED`. Installed run01 was not changed:
Host remains historically disabled/no-trigger, warm runs remain `0/2`, and
Supervisor remains `INTENTIONALLY_STOPPED`. D-22 remains `NOT_RUN`.

## Inactive derivative

One LOCAL_ONLY derivative was prepared under
`C:\Users\domai\AppData\Local\Temp\P4B-UW-01`:

| Item | SHA-256 | State |
|---|---|---|
| recipe | `74E5664F50CCAE9E641BC076390CE17A769C2E6F1D6F109FB6990C80220B7D6D` | only the exact window/operation ID differs from accepted recipe `CA6A5DCC...87157` |
| package index | `6F379DC5330D902CEC30F72E5B4C2CD190FC923AF195B275FF9FF7BA56D64698` | authorization flags false |
| launcher | `686F4EC877AADC93D46D2B67858864BF9C728B00093037A266B257099BA14B66` | accepted source bytes |
| runtime | `959768E297BCB93FF1AF3D7EE5A174313F9DC053707EDE8C45D3A84D024B0732` | unchanged |
| recorder | `D21A3E6B5D49E68711C5584138C47C2201B861A80DD4A4F89F173DC57217452A` | unchanged |
| candidate manifest | `E139CEC5E8011EF38A6A641DF7E68399F968ACF5350E216179395E895C8357F0` | `NOT_APPROVED`, installation/startup false |

The protected root is not a reparse point, its owner is `DOMAI\domai`, sentinel
write/read passed, and reserved later output
`C:\Users\domai\AppData\Local\Temp\P4B-UW-01\apply` is absent. Windows
PowerShell 5.1 package integrity passed all `8/8` payload bindings, JSON/XML/PS1
parsing, and exact recipe-ID-only comparison. The first local XML parser attempt
is preserved as a tooling failure: it opened a historical preimage by byte
encoding instead of the recipe's safe text/StringReader path. The corrected
local parser passed without changing XML or contacting the host. Both local
Windows PowerShell 5.1 child processes settled; the corrected run exited `0`.

## Formal block before live read-only preflight

The prescribed execution-approval path rejected the exact ordinary-token
`VerifyOnly` launch before process start. The non-secret reason was that the
newly prepared package would read live task/system state and the current formal
mechanism did not recognize authorization for this new window. The earlier
attempt to flip the derivative manifest to `APPROVED_FOR_START` was also
rejected because preparation was authorized only as inactive/not approved.

The refusal was not bypassed. Consequently this window performed:

- Task Scheduler reads/writes/starts: `0/0/0`;
- Docker/CIM/TCP/HTTP reads: `0`;
- UAC/InstallAndWarm/Host starts/warm runs/rollback: `0`;
- production file/task/container/data changes: `0`.

Status: `P4B_USABLE_WARM_INACTIVE_PACKAGE_LOCAL_INTEGRITY_PASS /
LIVE_READ_ONLY_PREFLIGHT_FORMALLY_BLOCKED_NOT_RUN /
MANIFEST_NOT_APPROVED / STAGE_B_NOT_ELIGIBLE_NOT_AUTHORIZED`.

## One next decision

Use the prescribed approval path to authorize the exact read-only preflight for
window `R04-D21-P4B-USABLE-WARM-20260923T170936Z` and, separately, explicitly
include any future transition of the exact candidate manifest from
`NOT_APPROVED` to an approved Stage-B payload. Until both are available there is
no UAC confirmation sentence and no Stage B.

## ANTI_EXCESSIVE_WORK — mandatory read

Read roadmap section 0, `ANTI_EXCESSIVE_WORK`, the active R04 card and this
checkpoint. Existing Host22/NUP and D-23 review `2/2` acceptances remain. No
K2/K3 search or new micro-fix follows from this formal blocker.
