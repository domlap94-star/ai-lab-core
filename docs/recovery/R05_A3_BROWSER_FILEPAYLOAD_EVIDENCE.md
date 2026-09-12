# R05-A3 — local browser FilePayload evidence

## Scope and identity

The owner accepted R05-A2 source
`d1b0518ad9aefb5bc05cd89308de923ca54d2809` and evidence
`60b1736db9eb18ef5445a2d8407988106ff96407` as
`SOURCE_AND_OFFLINE_BOUNDARY_ACCEPTED / NOT_DEPLOYED`, then authorized only
the local R05-A3 browser input test. The product worker, queue, backend,
frontend and deployment configuration were not changed.

The opt-in harness is
`operations/vision-worker/test_browser_filepayload.js` (pre-commit Git blob
`fe4b2973c949b4d5fb4f3bbe621b25d0c1a514de`, SHA-256
`E7E13773E3263BFA1D873E76A6BA75319DE3BDA428E41142147B0E948AFD3840`). It
imports the accepted `loadVerifiedInputs()`, `uploadVerifiedInputs()` and
`markUploadConfirmed()` functions. It also uses the actual `VisionQueue` to
materialize a job while replacing only `spawnWorker` with a local inert child;
`run(jobDir)` and worker CLI are never invoked.

The test used preserved synthetic A2 chain inputs, after checking their
request/approval files and bytes:

| Case | Approval kind | Bytes | Expected and source SHA-256 |
|---|---|---:|---|
| `public-safe` | `public_safe` | 2,087 | `3956F8ED4074E3AB3531A9A821159A65A8A12441E6E5328021D6A09914DD3206` |
| `locally-redacted` | `locally_redacted` | 4,688 | `7A89CB69AE2D29BDB1F8F2311177CB128B877B75F00C6B2A94B33661631B431C` |

The redacted bytes remained different from the synthetic forbidden original
hash `3022375F32D5BD91BBB890B67B190F23A77B7F6BAF1BF68243AF44DC628A99B3`.

## Browser and isolation

- Evidence root: `C:\ai-lab-core-staging\recovery\R05_A3_LOCAL_BROWSER_20260912T080832Z`,
  protected ACL, `LOCAL_ONLY`.
- Node `v24.18.0`; Playwright `1.62.1` loaded from the preserved worker
  dependency root; no install or lock change.
- Microsoft Edge `151.0.4129.72`, executable SHA-256
  `E73E04DACDB48557C13D9F93F90A248F3E5A0BF55BB738F2FC548A768A9A10AF`.
- One `chromium.launch` session, headless and nonpersistent. It used a new
  context with `offline=true`, service workers blocked and HTTP(S)/WebSocket
  routing aborted. Every page began at `about:blank`; its visible
  `SYNTHETIC LOCAL FILE INPUT TEST` form came only from `page.setContent`.
- Observed page-context public navigation: `0`; unexpected page requests:
  `0`; remote uploads: `0`. This interception is evidence for the isolated
  Playwright context, not whole-host packet monitoring.
- Edge process count was 13 before and 13 after; no new Edge PID remained.
  Available physical RAM was 7.064 GiB before and 7.035 GiB after; commit
  spare was 36.437 GiB before and 36.553 GiB after.

The `temporaryChatVerified=true` value was an explicit synthetic test input to
the accepted local function. It is not an observation of Temporary Chat and
does not prove a real remote mode or upload.

## Executed commands

All commands ran from `C:\ai-lab-core-recovery`.

```powershell
node --check operations/vision-worker/test_browser_filepayload.js
node operations/vision-worker/test_browser_filepayload.js
$env:NODE_PATH='C:\ChatGPT-Vision-Worker\worker\node_modules'
node operations/vision-worker/test_browser_filepayload.js --local-browser-file-input --chain-root C:\ai-lab-core-staging\recovery\R05_A2_UPLOAD_REPLAY_20260911T230541Z\final-chain-source-20260911T231903Z --evidence-root C:\ai-lab-core-staging\recovery\R05_A3_LOCAL_BROWSER_20260912T080832Z --browser-executable 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node operations/vision-worker/test_upload_replay.js
node operations/vision-worker/test_upload_boundary.js --chain-root C:\ai-lab-core-staging\recovery\R05_A2_UPLOAD_REPLAY_20260911T230541Z\final-chain-source-20260911T231903Z
```

Exit codes were `0, 0, 0, 0, 0`. The no-flag invocation returned `NOT_RUN`,
`browser_launches=0`, `public_navigation=0`, `external_uploads=0` and left the
Edge process count unchanged.

## Browser matrix

| Case | Actual result |
|---|---|
| A — `PUBLIC_SAFE` | One real delegated `locator.setInputFiles`; DOM `FileList` contained `S1.jpg`, `image/jpeg`, 2,087 bytes and the expected SHA-256. Browser events: `input=1`, `change=1`. |
| B — `LOCALLY_REDACTED` | One real delegated `locator.setInputFiles`; DOM contained the approved redacted 4,688-byte buffer and never the forbidden original hash. Events: `input=1`, `change=1`. |
| C — tamper after read | The on-disk job input changed to SHA-256 `0503AE270E808AECF54D1FE44AF5438ACBF7F9A35277C632F7CD3154E8EA732B` after `loadVerifiedInputs`. DOM still received the previously verified 2,087-byte buffer with SHA-256 `3956F8E…DD3206`. |
| D — same-job retry | Second `uploadVerifiedInputs` returned `UPLOAD_HANDOFF_ALREADY_EXISTS`; additional locator calls, `input` events and `change` events were all `0`; `FileList` was unchanged. |
| E — denials | Bad bytes failed at `loadVerifiedInputs` with `INPUT_CHECKSUM`; missing synthetic temporary-mode input failed with `TEMPORARY_CHAT_NOT_VERIFIED`. Both pages retained empty `FileList`; successful selections `0`. |

The positive markers were confirmed only after independent DOM
`File.arrayBuffer()` reads and were labelled in the result as
`LOCAL_TEST_ONLY`. This does not assert delivery beyond the local file input.

Focused regressions also passed: `R05_A2_UPLOAD_REPLAY_GUARD_OK` (one winner,
one `UPLOAD_HANDOFF_ALREADY_EXISTS`) and
`R05_A2_UPLOAD_BOUNDARY_TESTS_OK` (`17` local cases plus the two accepted
synthetic backend-chain cases). No browser was launched by either regression.

## Evidence boundary and remaining work

`REAL_BROWSER_FILELIST_EXACT_BYTES_PASS` proves the exact approved buffers
reached a real local browser DOM `FileList` through Playwright. It does not
verify ChatGPT, Temporary Chat mode, a remote uploader, a persistent runtime
profile, operator approval UI, network delivery, response handling, rollout or
production. R05 therefore remains `IN_PROGRESS` and A3 is only
`LOCAL_BROWSER_FILE_INPUT_READY_FOR_REVIEW / TEST_ONLY`.

Raw JSON/logs, the synthetic working jobs and a reviewed synthetic screenshot
remain `LOCAL_ONLY`; their hashes are indexed in
`docs/recovery/R05_A3_LOCAL_EVIDENCE_MANIFEST.csv`. R03 remains
`WAITING_APPROVAL / WAITING_ESCROW_DECISION`; R04 remains `IN_PROGRESS`;
Android stays `DEFERRED_BY_OWNER / NOT_TESTED`; D-15/D-16 AI acceptance is
`NOT_RUN`.

## Owner acceptance and successor boundary

On 2026-09-12 the owner accepted this evidence at
`1ae3f99edd5cb39b9cb795ba573878e9ded6b30e` as
`LOCAL_BROWSER_FILE_INPUT_ACCEPTED / TEST_ONLY / NOT_DEPLOYED`. The acceptance
retains every limitation above: it is not evidence of Temporary Chat mode,
remote upload, normal worker CLI, operator UI, external end-to-end or deploy.
R05-A4 subsequently added only source and isolated tests for the operator
preview/decision flow; it did not repeat or relabel this browser test.
