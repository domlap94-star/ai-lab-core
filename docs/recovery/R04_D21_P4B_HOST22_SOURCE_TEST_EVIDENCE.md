# R04 / D-21 / P4-B — Host 22 source/test evidence

Status: `HOST22_OBSERVATION_COMPLETENESS_DEADLINE_AND_STATE_SOURCE_READY_FOR_REVIEW /
OFFLINE_TESTS_PASS / NOT_DEPLOYED`

Entry HEAD: `a398e30c5c57c916d330378979798e71937db0cb`

Preimage source commit: `ed961d6980ebebe2e4d351319e2aa909437bc1ec`

Source commit: `b4269ffa7bacc95b4d1441bb196e572a34a4ec43`

Final campaign UTC: `2026-09-20T14:39:22Z–2026-09-20T14:40:07Z`

## Fail-before and change

The historical read-only diagnosis remains the source of the real Docker
template failure: the installed adapter dereferenced optional `.State.Health`
and the backend inspect failed before the plan. That evidence was not replayed
against the Engine and is not presented as recovered run01 output.

The exact `startup-runtime.ps1` from entry commit `e1f8e83d...` was executed
offline with five independent observations. Its real container phase returned
`CONTAINER_IDENTITY_AMBIGUOUS`, observation count `5`, starts `0`. Sanitized
stdout is `188` bytes, SHA-256
`850BBA29832D9F775BCBBBA1F5A28D5DC65F5B6FA7327C15B29AB8CBD9AD5912`.

The source change:

- projects a small inspect JSON object and accesses optional Health through a
  safe key lookup; missing/null Health becomes `NOT_CONFIGURED`, never
  `healthy`;
- rejects missing State, invalid Running, malformed/truncated JSON, timeout and
  nonzero results as incomplete observations;
- inspects the manifest's full `container_id` first and verifies the existing
  name, labels, image/digest, mounts and ports;
- uses the project/service list only as a bounded conflict scan. Four narrowly
  identified, positively stopped R03/A1 drill clients are accounted for but
  never selected or started. Every other rival or unreadable state blocks;
- reuses the same selection for readiness and cold-start rechecks. Only the
  verified pinned full ID can reach the start adapter. A missing pinned ID is
  `CONTROLLED_DEPLOY_REQUIRED`; no label/name fallback exists.

## OBS-01–03 continuation

- `RV-H22-OBS-01` — **REPRODUCED / FIXED**. The preimage accepted a
  success/exit-zero envelope even when `stdout_truncated=true` or completeness
  metadata was absent. The common guard now requires an explicitly complete,
  settled envelope and rejects timeout, nonzero, truncation or missing
  metadata before parsing or start.
- `RV-H22-OBS-02` — **REPRODUCED / FIXED**. Individually bounded reads could
  cumulatively exceed the stage timeout. The container phase now creates one
  monotonic deadline, passes only the remaining budget to every observation,
  checks it before and after each native read and again before success/start,
  and issues no later inspect or start after exhaustion. The package harness
  uses only the owner-approved deterministic test clock; production timeout
  values and code paths were not relaxed.
- `RV-H22-OBS-03` — **REPRODUCED / FIXED**. The preimage could treat a pinned
  `paused` or `restarting` instance as ready when `Running=true`, including a
  stale PostgreSQL `healthy` value. Readiness now requires exact
  `state_status=running`; only controlled `created/exited` states are eligible
  for the existing cold-start path, and no unpause/restart repair was added.

The final real-adapter regression initially exposed one synthetic RV05 cleanup
race. That failed iteration is retained LOCAL_ONLY. The test-only command
boundary was made cooperative so the existing production cleanup contract is
tested deterministically; the next and final campaign passed without changing
production timeout semantics.

## Final offline campaign

All tests ran in Windows PowerShell 5.1 with complete lower-boundary fakes.
Production-boundary calls were `0`.

| Test | Assertions | Exit | stderr |
|---|---:|---:|---:|
| `test-host22-container-observation.ps1` | 51 | 0 | 0 B |
| `test-start-host-services.ps1` | 57 | 0 | 0 B |
| `test-startup-real-adapters.ps1` | 51 | 0 | 0 B |
| `test-startup-data-junction.ps1` | 44 | 0 | 0 B |
| `test-p4-startup-package.ps1` | 40 | 0 | 0 B |

The focused test exercises the real `New-RealStartupAdapters`, parser,
identity validation and container phase. The continuation reproduced and fixed
all three review findings: `OBS-01` rejects a successful-looking but truncated
or incomplete native envelope, `OBS-02` applies one decreasing monotonic
deadline to the observation/readiness stage, and `OBS-03` requires both
`running=true` and exact `state_status=running` for the pinned instance.
Paused, restarting, removing, dead and unknown pinned states cannot inherit
readiness from a boolean or stale health value. The package test now runs the
6+4 plan through `New-RealStartupAdapters` with only the lowest boundaries
faked; it covers the one synthetic Private start and repeat, PostgreSQL
starting-to-healthy ordering before backend, truncation, aggregate deadline,
state failures and identity drift. Supervisor starts remain `0`.

Parser validation passed for seven touched PowerShell files. JSON, CSV, diff and
secret checks are recorded with the documentation commit. These overlapping
assertion sets are not reported as a count of application tests.

## Tested bytes

| Path | Bytes | Raw SHA-256 | Git blob |
|---|---:|---|---|
| `operations/runtime/start-host-services.ps1` | 72 755 | `1327FADC5BD21DBBE076E5CAD2DF587C6B9B5F274511A99E96E8DDC4FC0BA190` | `5270f8fe4f8939b1bdd612c306681125a14631ee` |
| `operations/runtime/startup-runtime.ps1` | 82 004 | `ECAF4239A6B6C7CDCE0C521FB6B518A72402262E17A6F0C06242CA852840541E` | `ab78069d56b8e8e6041bb1e285caa74c6c0406f2` |
| `operations/runtime/test-host22-container-observation.ps1` | 34 699 | `A7DB09E57663F28CF8BC4D622385684DE310E24266B14316017D6ED803CC5D72` | `42c68afe26d81432d3280b0b38f0060ed242c1d6` |
| `operations/runtime/test-p4-startup-package.ps1` | 45 829 | `3A3E58853D460B72BD1A4459196273C0095A3B42FDF0114D27223E35B6078724` | `9825fbe3deb22a02ad8ebfb0ef16a8eb999a55ee` |
| `operations/runtime/test-start-host-services.ps1` | 32 255 | `339C282ECDCFC405C35CEE745FB2902169188646A2CE23B6C22AAFBF8D7BAC01` | `3daeff64a5c389fc3f5e9143a42da7d66579c7d7` |
| `operations/runtime/test-startup-data-junction.ps1` | 28 274 | `35048616FA7F3A71F383383E77A66BE8F1AB68FE261145EBD9895C831C9B7B04` | `0ab43b3d77e0a572b4398e5b3517657c14fab51a` |
| `operations/runtime/test-startup-real-adapters.ps1` | 45 849 | `6938EAB51D675B5DC7401DE8D22DC11F716A3E5D37CDD91BB537BE2E2012948D` | `ce8ee5e3a81e8299996a99284d561d118d4da385` |
| `operations/runtime/README.md` | 11 067 | `2569B55EABF3B92B56383070FF95696AC3D4E54F4ED54645386948835E8A4E5E` | `f4360054f80e5784075bbba353f2c2dd33e88088` |

## Inactive review package

The requested existing staging parent refused non-elevated creation with
`Access is denied`. Elevation was not used because this scope permits only
non-elevated own test processes. The new package is therefore LOCAL_ONLY at:
`C:\Users\domai\AppData\Local\Temp\P4B-H22-OBS-01`.

- inactive package index: `3 808` bytes, SHA-256
  `CE373406DA49B35B01B20F4E8039A5F6F0060C54237C1B2D91193867B83B5763`;
- inactive candidate manifest: `27 273` bytes, SHA-256
  `A3B407D44F3595837D828D21839ED25D1D62618D434C7BC0CF0A260640C8B00E`;
- review ZIP: `102 476` bytes, SHA-256
  `4EB0706A365C2D46AD7F63047AE2DB253D1841C7E372A45F4F1947CA212ADBD9`,
  roundtrip `12/12` indexed entries plus the index itself (`13` ZIP entries).

The candidate remains `NOT_APPROVED_FOR_START / NOT_DEPLOYED`. Its only
runtime changes are the new launcher/runtime bytes and their hash bindings.
The six service identities and runtime policy are unchanged. The future update
list is descriptive and `NOT_EXECUTED / REQUIRES_SEPARATE_APPROVAL`.

## Operational boundary

No Docker, WSL, Task Scheduler, CIM, TCP, HTTP, UAC, RunAs, Host, container,
gateway, backend, backup, data or model operation occurred. Only own local
PowerShell processes, synthetic fixture I/O, Git and staging ZIP roundtrip ran.

Run01 remains `PAYLOAD_AND_MANIFEST_INSTALLED / HOST_DISABLED_NO_TRIGGER /
WARM_RUNS_0_OF_2`. Installed hashes remain the old run01 bytes. There was no
new host read, retry or success. Any future attempt must first review the exact
published source and ZIP, then separately authorize a narrow update. The next
real Host run must persist launcher JSON `code/events/details`, stdout/stderr
and exit under the Host account; `LastTaskResult` alone is insufficient.
