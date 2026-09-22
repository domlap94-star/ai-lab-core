# R04 / D-21 / P4-B — exact host-services OBSERVE

- entry HEAD: `d3666fd66e88ca8f17fbb880c8850f490eecdea0`
- scope: `EXACT SINGLE READ-ONLY OBSERVE / WINDOWS POWERSHELL 5.1`
- candidate: `7940` bytes / `4DCFE146ED51A8F68FECEB8DCB10FD1A873F4D88CC0892EDC372574B8B7890F9`
- status: `HOST_SERVICES_PS51_EXACT_OBSERVE_COMPLETED /
  CURRENT_LIMITED_READ_ONLY_EVIDENCE /
  PUBLIC_CONFLICT_PRIVATE_UNKNOWN_SUPERVISOR_UNKNOWN /
  NOT_AV_CLEARANCE / STAGE_B_BLOCKED_NOT_AUTHORIZED`

## Authorization and exact invocation

The owner preserved `STATIC_SOURCE_REVIEW_ACCEPTED`, removed the procedural
requirement for a separate unspecified AV certificate and authorized exactly
one execution through the current execution-approval path, provided existing
protection allowed it. This was not authorization to change protection or to
claim AV clearance.

Immediately before execution, read-only .NET SHA-256 matched the candidate,
the review ZIP and the pinned launcher/runtime. The new `o1` directory passed a
short sentinel write/read/delete check and `host.json` did not exist.

Executable:
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`

Candidate argv:
`-NoLogo -NoProfile -NonInteractive -File <exact-candidate> -OutputPath <exact-host.json>`

The accepted `Invoke-BoundedNativeCommand` supplied the `120000 ms` outer
deadline and bounded streams. It recorded:

- request UTC: `2026-09-22T22:26:20.9887177Z`;
- PID: `65440`;
- duration: `7411 ms`;
- status/exit: `SUCCESS / 0`;
- timeout/process left running: `false / false`;
- stdout/stderr truncated: `false / false`;
- stderr: empty.

There was one candidate attempt. Retry and alternate execution channels: `0`.

## Safe result

LOCAL_ONLY result:
`C:\ai-lab-core-recovery\build\P4B-HS-REVIEW-01\o1\host.json`

- size: `2561` bytes;
- raw SHA-256: `DA2274B770CBD5351BAB0B4A51B884739DD4CA49CA3D28FC32BA60533FE23CB8`;
- schema: `NEXT_STABIL_HOST_SERVICE_STATIC_REVIEW_RESULT_V1`;
- operation: `OBSERVE_ONLY`.

| Service | Policy | Status | Detail | Match count | PID | Listener ready |
|---|---|---|---|---:|---|---|
| Public Gateway | `REQUIRED` | `CONFLICT` | `PORT_OWNERSHIP_CONFLICT` | 0 | null | false |
| Private Gateway | `REQUIRED` | `UNKNOWN` | `OBSERVATION_UNKNOWN` | 0 | null | false |
| Supervisor | `INTENTIONALLY_STOPPED` | `UNKNOWN` | `OBSERVATION_UNKNOWN` | 0 | null | false |

Candidate-reported counters are `starts=0`, `task_writes=0`, `docker_reads=0`
and `http_reads=0`. They are fixed result fields, not independent supervisor
telemetry. The bounded parent independently proves only child-process and
stream settlement.

## Interpretation and stop

Exit `0` and a valid JSON file prove completion of the exact bounded read; they
do not turn the three service classifications into readiness. No cause is
assigned to the Public conflict and `UNKNOWN` is not converted to absence for
Private Gateway or Supervisor. `INTENTIONALLY_STOPPED` remains policy rather
than a substitute for a confirmed current observation.

No service/task/container start or write, Docker/HTTP/SQL operation, UAC,
installation, rollback or Stage B action was performed. Installed run01 and
all accepted source/offline stages remain unchanged. The one execution
authorization is consumed; no retry or follow-up diagnosis is authorized.

Next decision: owner review of the three actual classifications. Any targeted
diagnosis requires a new explicit scope. Stage B remains blocked.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Before evaluation and the next prompt, read roadmap §0,
`ANTI_EXCESSIVE_WORK`, the active R04 card and this checkpoint from the full
published SHA. Preserve D-23 review `2/2` and all accepted stages. Blocking K1:
`P4B-PREFLIGHT-HOST-RUNNER — exact PS5.1 evidence is complete, but Public is
CONFLICT and Private/Supervisor are UNKNOWN (result SHA-256 DA2274B7...23CB8).`
Effect: the runtime gate is not satisfied and Stage B remains unauthorized.
Next action: owner review only; do not add K2/K3 or retry automatically.
