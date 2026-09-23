# R04 / D-21 / P4-B — USABLE-WARM read-only preflight formally refused

- UTC record: `2026-09-23T18:48:05.6626725Z`
- Window ID: `R04-D21-P4B-USABLE-WARM-20260923T170936Z`
- Entry/evidence HEAD: `2234d286df76aa7e410833b6d8262e9663b7f69c`
- Accepted source: `49c3f64c238e4bdb25e0d3fe9d7bb98c17677bbc`
- Scope: one consolidated read-only preflight; no UAC or Stage B

## Owner decision and frozen inputs

The owner explicitly authorized exactly one consolidated read-only preflight
of the existing window. The package was not rebuilt or edited:

| Item | SHA-256 / state |
|---|---|
| recipe | `74E5664F50CCAE9E641BC076390CE17A769C2E6F1D6F109FB6990C80220B7D6D` |
| package index | `6F379DC5330D902CEC30F72E5B4C2CD190FC923AF195B275FF9FF7BA56D64698` |
| launcher | `686F4EC877AADC93D46D2B67858864BF9C728B00093037A266B257099BA14B66` |
| candidate manifest | `E139CEC5E8011EF38A6A641DF7E68399F968ACF5350E216179395E895C8357F0`, `NOT_APPROVED` |
| index authorization | all operational fields `false` |
| reserved InstallAndWarm output | `C:\Users\domai\AppData\Local\Temp\P4B-UW-01\apply`, absent |

The new LOCAL_ONLY campaign root
`C:\Users\domai\AppData\Local\Temp\P4B-UW-01\preflight\campaign01` was
confirmed non-colliding and not a reparse point. Windows PowerShell 5.1
confirmed sentinel write/read, path limits, parsers and `8/8` exact package
bindings. These are local package checks, not runtime observations.

## Formal refusal before process start

Attempt ID:
`R04-D21-P4B-USABLE-WARM-20260923T170936Z-READONLY-PREFLIGHT-01-VERIFYONLY`.
The exact Windows PowerShell 5.1 `VerifyOnly` was submitted through the
prescribed execution-approval path. It was rejected before `CreateProcess`.
The non-secret reason stated that a live VerifyOnly against task/system state
for this new window lacked a recognized current explicit authorization and
must not be retried through a workaround or alternate channel.

The owner had supplied an explicit exact authorization in the current prompt;
this checkpoint records the mechanism's decision, not an inference that the
owner withheld consent. The refusal was obeyed: no retry and no alternate
runner. Because the first required live gate did not start, the rest of the
single consolidated campaign was not attempted.

| Boundary/effect | Count/state |
|---|---|
| VerifyOnly process | not created |
| result/output root | absent |
| Task reads/writes/starts | `0/0/0` |
| Docker/CIM/TCP/HTTP/resource reads | `0` |
| UAC/InstallAndWarm/Host/warm/rollback | `0` |
| package/manifest/installed run01 changes | `0` |

The sanitized refusal record is LOCAL_ONLY:
`formal-refusal.json`, `1998` B, SHA-256
`D9A547A45147DD60249EDBFA2FC295F181386F56D8E1F08D2AE148D385E64AFE`.

## Result and one next step

Status: `P4B_USABLE_WARM_READ_ONLY_PREFLIGHT_FORMALLY_REFUSED_NOT_RUN /
PACKAGE_LOCAL_INTEGRITY_8_OF_8 / MANIFEST_NOT_APPROVED /
STAGE_B_NOT_ELIGIBLE_NOT_AUTHORIZED`.

No Stage-B confirmation sentence is presented: six-container, host-service,
HTTP and resource gates do not have a result for this window. The one next
step is to resolve the formal mechanism's ability to execute this exact
owner-authorized read-only operation. Do not repeat this campaign, change the
runner, approve the manifest, request UAC or start Stage B on the local package
checks alone.

## ANTI_EXCESSIVE_WORK — OBOWIĄZKOWY ODCZYT PRZEZ CHATGPT

Przed oceną tej zwrotki i kolejnym promptem przeczytaj na SHA raportu
`NEXT_STABIL_REPAIR_COMPLETION_ROADMAP.md`: §0, `ANTI_EXCESSIVE_WORK`, aktywną
kartę R04 i ten checkpoint. Zachowaj odbiory Host22/NUP oraz D-23 `2/2`; nie
dodawaj K2/K3. `K0/K1` blokujące ten krok: formalna odmowa exact zatwierdzonego
read-only `VerifyOnly` przed procesem, więc wymagane runtime gates są
`NOT_RUN`. Efekt użytkowy pozostaje niewykonany: warm runs `0/2`, Host
historycznie disabled/no-trigger, Supervisor `INTENTIONALLY_STOPPED`. Następny
krok: wyłącznie rozstrzygnięcie formalnej ścieżki; brak zgody na UAC lub Stage B.
