# R04 / D-21 / P4-B — USABLE-WARM dependency continuation partial

UTC checkpoint: `2026-09-24T17:10:22.0479770Z`

Operation ID: `R04-D21-P4B-USABLE-WARM-CONTINUE-DEPS-20260924T164318Z`

Scope: LOCAL_ONLY dependency fix, one read-only preflight, one UAC and one
bounded continuation. No retry.

## Result first

- Host warm runs: `0/2`.
- Duplicate starts: `0`; no Host warm start occurred.
- Logon trigger: `NOT_CONFIGURED`.
- CRM/Web shortcut and client details: `NOT_OPENED / NOT_RUN`.
- Final operation result: `PARTIAL_PENDING_OPERATION_UNKNOWN`.
- Supervisor: `INTENTIONALLY_STOPPED`; preflight observed it absent.
- Private Gateway: preflight observed it absent; no Private start occurred.
- Six pinned containers: preflight `6/6` running; PostgreSQL healthy. They were
  not changed by this operation.

## Local fix and offline proof

The continuation keeps the accepted parameter/manifest-path guards and exports
only top-level functions from the exact hash-pinned runtime and launcher into
the fresh dedicated process before real adapters are created. It does not
change installed product bytes.

| Item | Size | SHA-256 |
|---|---:|---|
| continuation | 34754 B | `5F7F807A092133A76280671948DEB3088B6DA4B7BE326C81369752EDBA780BE4` |
| continuation index | 3903 B | `08DB292BEA197C43FF4178F9F256912D6B881A8F9D21F9D8D80B22A1E6EC7446` |
| harness | 38453 B | `98D76DF69760CC3C8CA86E9AD5A08FD6559F31259A7DBFCD9CDCA9E468DBE455` |
| offline result | 812 B | `8A5F6890DEC9AF06F03897AFC98980B369B482DAA1C39EDE8704B2C0769336DE` |

Windows PowerShell 5.1: `11` scenarios, `57` assertions,
`production_boundaries=0`. The full entry path used real imports, runtime
probe, `New-RealStartupAdapters`, parsing/decision logic and the recorder child;
only system leaves were substituted.

## Current read-only preflight

Status `READ_ONLY_PREFLIGHT_PASS`, mutation not authorized or attempted:

- installed files `4/4` exact;
- pinned containers `6/6` running and PostgreSQL healthy;
- backend pinned identity/image retained;
- Public Gateway present, Private Gateway absent, Supervisor absent;
- HTTP `200/200/200/404`;
- Docker/WSL available pool and swap remain
  `UNKNOWN_ACCEPTED_FOR_THIS_WINDOW`, not PASS.

Preflight: `9345` B / SHA-256
`F95787D4DE2FF1D83E1232EC2F4D8010033B59460246030C877FFCD7865A5CC3`.

## One-UAC operational attempt

Elevated PID `37316` ran from `2026-09-24T17:08:34.8844697Z` to
`2026-09-24T17:09:32.0591739Z` and exited `22`.

The journal persisted `ATTEMPT_OPEN`, `MUTATION_INTENT_PERSISTED` for the Host
on-demand registration, then `MUTATION_OUTCOME=PENDING_UNKNOWN` with
`possible_effect=true`, `settled=false`, `worker_cleanup=WORKER_SETTLED` and
`detail=TASK_POSTCHECK_NOT_CONFIRMED`. The attempt closed as partial.

| Evidence | Size | SHA-256 |
|---|---:|---|
| result.json | 966 B | `C943F95CC27CDD6A0BC2A01969453EE77CEED4822A522F2135A87B2B847F478E` |
| mutation-journal.jsonl | 1168 B | `F908C2332408652E31F70B954E3663E30741D7C5EF8AF31D5687CC887DBF935B` |

No warm run, Host start, Private start, logon registration or shortcut test
followed. `SAFE_INACTIVE=NOT_ATTEMPTED_PENDING_OPERATION`; no second write,
retry or destructive rollback was attempted.

## One bounded Host readback

At `2026-09-24T17:10:22.0479770Z`, the allowed post-operation read found:

- state `Ready`, enabled `true`, trigger count `0`;
- Running/Queued instances `0/0`;
- semantic SHA-256
  `66ECF75806986BE7624FBC2430D14AEEC6D79BE4C348A29E072018E1F00BB938`;
- comparable SHA-256
  `171956207D309EC3B5241835F158BA5129A1685DF5FF57E4A650A0C94212BA92`.

The observed hashes do not equal the pinned on-demand target. The read proves
that the Host definition changed, but it does not prove the intended exact
registration. The pending journal therefore remains material and blocks a
warm run, a competing registration and SAFE_INACTIVE.

## State and stop

`DEPENDENCY_FIX_OFFLINE_PASS / READ_ONLY_PREFLIGHT_PASS /
PARTIAL_PENDING_OPERATION_UNKNOWN / HOST_ENABLED_NO_TRIGGER_IDENTITY_MISMATCH /
WARM_RUNS_0_OF_2 / LOGON_NOT_CONFIGURED / CRM_WEB_NOT_OPENED /
UAC_CONSUMED_NO_RETRY`.

The installed four product files were not recopied or changed. Five dependency
tasks/helper, six containers, data, flags, junction, backups and shortcuts were
not modified. No P5/R06/D-22 work ran. R04 remains `IN_PROGRESS`; D-23 remains
`2/2`. The only next decision is an owner review of this exact Host state and
its unresolved registration; this checkpoint grants no retry, task write/start,
rollback or further UAC.
