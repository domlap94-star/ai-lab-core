# R04 / D-21 / P4-B — Host22 final observation conditions

- UTC: `2026-09-20T15:38:21Z`
- Branch: `recovery/next-stabil-repair-completion`
- Source commit: `8195e5cf8dacd1976ccd9f71a1f78175c3513acc`
- Scope: `SOURCE / LOCAL FILE READ / OFFLINE TEST ONLY`
- Status: `HOST22_FINAL_OBSERVATION_CONDITIONS_AND_MANIFEST_BINDINGS_READY_FOR_REVIEW / OFFLINE_TESTS_PASS / NOT_DEPLOYED`

## Result

`RV-H22-OBS-01B` and `RV-H22-OBS-02B` were reproduced against preimage
`b4269ffa7bacc95b4d1441bb196e572a34a4ec43`. Required native-envelope fields
now require actual Boolean/string/integer types, and the same container-stage
deadline is checked immediately before positive readiness. Earlier Health,
exact-ID-first, conflict, state and PostgreSQL dependency guards remain.

The inactive candidate is independently bound from manifest `files[]` through
exact payload path, size, raw SHA-256 and current source metadata. It remains
`NOT_APPROVED_FOR_START`.

## Tests

- focused Host22 / OBS: `70`, exit `0`;
- start-host-services: `57`, exit `0`;
- real adapters: `51`, exit `0`;
- DATA_ONLY: `44`, exit `0`;
- P4 package: `41`, exit `0`;
- candidate binding + P4: `59`, exit `0`;
- extracted ZIP binding: `18`, exit `0`;
- production-boundary calls: `0`.

PowerShell 5.1 parser, JSON/CSV, diff and secret checks passed. The preserved
first DATA_ONLY regression failure was a nondeterministic real-clock fixture;
only its test clock was made deterministic. Production deadlines were not
changed.

## Package

- Review ZIP: `C:\Users\domai\AppData\Local\Temp\R04-D21-P4B-HOST22-FINAL-REVIEW-20260920T153726Z.zip`
- ZIP: `98 281` bytes, SHA-256 `D6F48B9ED1178C6362A5BF8A8C79E6B08B72D569D5C0F880FA29990939C27AEA`
- Package index: `6 166` bytes, SHA-256 `75A0005D4963D1FF862D53D50FC28AE3E7ECF7B93C53FF4AD85661CB8D8BAFDB`
- Roundtrip: `20` indexed files plus index, `21/21` archive entries verified.

## Operational state

No Docker, Task Scheduler, CIM, TCP, HTTP, UAC, Host, product or data boundary
was contacted. Installed run01 remains on its historical bytes, Host remains
disabled/no-trigger and warm runs remain `0/2`. Supervisor remains historically
`INTENTIONALLY_STOPPED`. D-22 remains unchanged and `NOT_RUN`.

## Next step

Independent review of source `8195e5cf8dacd1976ccd9f71a1f78175c3513acc`
and the exact ZIP above. Any installed update or Host retry requires a new,
separate owner decision. STOP before live preflight, UAC, update, retry, P5 or
R06.
