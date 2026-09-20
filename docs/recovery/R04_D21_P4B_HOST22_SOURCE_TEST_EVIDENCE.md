# R04 / D-21 / P4-B — Host 22 source/test evidence

Status: `HOST22_HEALTH_AND_EXACT_ID_SOURCE_READY_FOR_REVIEW /
OFFLINE_TESTS_PASS / NOT_DEPLOYED`

Entry HEAD: `e1f8e83d0e205dba5e1ac5366ceb29b87a5c57a1`

Source commit: `ed961d6980ebebe2e4d351319e2aa909437bc1ec`

Campaign UTC: `2026-09-20T00:26:05.9154727Z–2026-09-20T00:26:35.2501798Z`

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

## Final offline campaign

All tests ran in Windows PowerShell 5.1 with complete lower-boundary fakes.
Production-boundary calls were `0`.

| Test | Assertions | Exit | stderr |
|---|---:|---:|---:|
| `test-host22-container-observation.ps1` | 37 | 0 | 0 B |
| `test-start-host-services.ps1` | 53 | 0 | 0 B |
| `test-startup-real-adapters.ps1` | 51 | 0 | 0 B |
| `test-startup-data-junction.ps1` | 44 | 0 | 0 B |
| `test-p4-startup-package.ps1` | 16 | 0 | 0 B |

The focused test exercises the real `New-RealStartupAdapters`, parser,
identity validation and container phase. It covers Health missing/null,
healthy/starting/unhealthy/invalid, missing State, truncated JSON, nonzero and
timeout; exact-ID ordering and no-adoption; identity mismatches; stopped,
running, paused, restarting and unreadable competitors; exact-ID cold start;
and the stricter PostgreSQL `HEALTHY` gate. The package test covers the 6+4
topology, the one synthetic Private start and repeat without duplication,
PostgreSQL starting-to-healthy ordering before backend, and blocked dependency
paths. Supervisor starts remain `0`.

Parser validation passed for five touched PowerShell files. JSON, CSV, diff and
secret checks are recorded with the documentation commit. These overlapping
assertion sets are not reported as a count of application tests.

## Tested bytes

| Path | Bytes | Raw SHA-256 | Git blob |
|---|---:|---|---|
| `operations/runtime/start-host-services.ps1` | 70 697 | `CF98B7BEB2710265509FBA0662857207FC10FCE38E95731004B8A54EFF378E55` | `255d9e132611d657417de045e6780f71e11fdcb0` |
| `operations/runtime/startup-runtime.ps1` | 75 055 | `85A9589461AAB91643C9B351F4F5A0872AFDB2777056E96ABE299C3F734D85FB` | `46224cf5c21adfb06a274d4ce70c589b75517a8d` |
| `operations/runtime/test-host22-container-observation.ps1` | 22 879 | `35B6D89F2D21CD6351BE9B29FC6F226A34394D7C4D79DE4364DFD4B4F855F11C` | `609e01e2f6956cd4e72234c29f478ceac754c44b` |
| `operations/runtime/test-p4-startup-package.ps1` | 23 651 | `C1CA01070D84E1D200A9B636E88735F274E17C79AEB8A790615E594E0676826C` | `ffe3d5eae571b6e7f50dc29339a62475b9a880e0` |
| `operations/runtime/test-startup-real-adapters.ps1` | 45 325 | `4504F3BFF1390AFF0F412F99E2024FF3D547185D0B9369EA992B03654670F254` | `1124e1c330bf68f02b5df0db2a4f214f3f9ee3ff` |
| `operations/runtime/README.md` | 9 892 | `67316E25ECCA65F44043F44FE401F40F8A296334E44B572B3AE31CC9201107AF` | `f7657e51c027a41e7463bfe17dbbce1b75645261` |

## Inactive review package

LOCAL_ONLY root:
`C:\ai-lab-core-staging\recovery\P4B-H22-SRC-01`.

- inactive package index: `1 411` bytes, SHA-256
  `34CD1F8E32A39B530FB55B8C8FDE0C4DA240E5F6A52B3F4CC65500C172B82937`;
- candidate manifest: `27 353` bytes, SHA-256
  `1C7B2BA6DB5415CA90475EE26C8A490A648A270624B387B3057151245B8E3B87`;
- future update changeset: `1 545` bytes, SHA-256
  `2D01813E7BFE0178854AA72ABBE9E6D2231A1E207602397FB8E37686612C9BDB`;
- review ZIP: `80 143` bytes, SHA-256
  `76A8999E9D9BEB3EE87A888E159BB37A8F980093EF7A3DB8ACFCD223F5E74DBC`,
  roundtrip `10/10`, maximum path length `141`.

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
