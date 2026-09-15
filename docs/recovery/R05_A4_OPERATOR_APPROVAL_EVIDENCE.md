# R05-A4 — exact-copy operator approval evidence

## Scope and identity

The owner accepted R05-A3 evidence
`1ae3f99edd5cb39b9cb795ba573878e9ded6b30e` for product functions
`d1b0518ad9aefb5bc05cd89308de923ca54d2809` as
`LOCAL_BROWSER_FILE_INPUT_ACCEPTED / TEST_ONLY / NOT_DEPLOYED`. R05-A4 adds
only the source and isolated tests for an administrator-facing exact-copy
preview, approve and revoke flow. The source/test commit is
`f3cbe58bed0de34cfd39a57d481abb2c61c2f4ac`; it is not deployed.

The additive preview route is:

`GET /api/v1/documents/{document_id}/vision/export-approval/{analysis_job_id}/sources/{source_ref}/preview`

It requires the existing admin dependency and candidate package, binding and
source hashes. The service independently re-derives the current document
scope and staged package, resolves only the server-owned `source_ref`, reads a
bounded final raster once, hashes that same buffer and returns it with
`no-store`. It neither approves nor schedules work. A changed source, raster,
scope, package, job/document relation or path fails closed.

The existing candidate response was extended with the binding hash, document
scope, sensitivity, selected/omitted coverage, preview type/size and the
current approval/revoke capabilities. The existing approve route remains the
action that persists permission and may enqueue the existing background path;
the Flutter label and confirmation text say so explicitly.

## Operator flow

The Documents details dialog exposes the action only for the existing admin
roles and supported Visual document types. The new dialog:

- loads every selected final raster through authenticated Dio requests;
- independently checks response headers, byte count, SHA-256, candidate
  package hash and image decodability before enabling approval;
- shows full-size zoomable copies, document/client/project/inspection scope,
  channel, policy, approval state and honest selected/omitted coverage;
- requires an explicit `public_safe` or `locally_redacted` selection and a
  positive validity period; neither has a default;
- sends the exact displayed job/package/binding/source hashes, blocks a second
  click while the request is pending and never retries an uncertain result;
- closes without any decision when cancelled and offers revoke only when the
  durable server state says the approval is still unused.

`locally_redacted` does not create a redaction. The UI warns that it may be
selected only for an already locally prepared copy. A user-facing creation
path for such a copy remains outside A4 and is not claimed here.

## Executed validation

All backend commands used local image
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`,
read-only source, tmpfs and `--network none`. Required settings were synthetic;
no company `.env` or runtime mount was used. Flutter used the existing SDK,
lock and cache with `--no-pub`.

| Scope | Result | Evidence SHA-256 |
|---|---:|---|
| Python `compileall` for changed backend/source tests | exit `0` | `1D3236C4A5EC6B4BEC243D028723179C6CA138BB6CB4782F89985758DCF17E0A` |
| final focused backend: `test_visual_v2_service.py test_r05_visual_export_api.py` | `78 passed`, exit `0` | `781EFE361C70A1B2AAE5AC3FC45E2D12678DCBA5B4F1EB77A9F5050EB060F603` |
| Vision/Visual/Assistant regression on completed product logic | `319 passed`, exit `0` | `D2623FAD8D7C94D3623C38EFEC755DC28B66DE0EE8AFCD300DB8892538871F8B` |
| final focused Flutter dialog/API/page | `12 passed`, exit `0` | `B1551A49A89A9F1652CF64A77A3FBE302B978319E867F72DB3CE9B48CA5F20CA` |
| Flutter Documents/Auth regression | `21 passed`, exit `0` | `1FC31CA674B7E905B33027DC8BC3FFB6E3066A22228611A5E5629CA52ECFE252` |
| `flutter analyze --no-pub` | no issues, exit `0` | `BD614C778D8711289E761F8CA716A408CFA17D5D89A124603FB816C90542DE69` |

The 319-test run preceded only an internal Pydantic field-alias cleanup (the
wire field remains `schema`) and an additional negative test. The final
78-test run covers the exact resulting backend implementation. A redundant
attempt to repeat all 319 tests after the source commit produced no test output
because the local Docker CLI/daemon stopped responding; the client was
interrupted after the bounded wait and the run is `NOT_VERIFIED`, not PASS.
The raw incomplete transcript is indexed separately. This infrastructure
limitation does not replace or rewrite either completed result.

The focused matrix verifies real service/router and dialog/adapter behavior:
admin 200 versus unauthenticated 401/non-admin 403; exact final bytes rather
than the original hash; foreign source/job/document and changed scope/bytes
409; restricted material denied; candidate state persists across HTTP request
sessions; public-safe and an existing synthetic locally-redacted copy; no
auto-approval, double-click, cancel-without-decision, stale preview rejection,
unused revoke, and conservative handling of possible contact. The positive
backend path reaches only the existing fake Supervisor boundary.

## Effects and evidence boundary

Raw transcripts are `LOCAL_ONLY` under
`C:\ai-lab-core-staging\recovery\R05_A4_OPERATOR_APPROVAL_20260912T121418Z`.
Their filenames, sizes and hashes are in
`docs/recovery/R05_A4_LOCAL_EVIDENCE_MANIFEST.csv`. Development-only failures
were harness/configuration failures and are retained as such; they are not
product failures or hidden PASS results.

No application server, browser, worker CLI, real background dispatcher,
Supervisor HTTP, Temporary Chat, model, Qdrant, Gmail or n8n was started. No
real export, Web runtime smoke, build, deployment, migration or production
data/config write occurred. The only product-like writes were synthetic SQLite
records and files inside container tmpfs; `--rm` was used. The final redundant
Docker status probe was unavailable, so exact daemon-side observation of that
aborted duplicate container is `RESOURCE_OBSERVABILITY_BLOCKED`; no Docker CLI
process from the probe remains.

R05-A4 is therefore
`OPERATOR_APPROVAL_SOURCE_READY_FOR_REVIEW / NOT_DEPLOYED` with
`API_AND_WIDGET_EXACT_PREVIEW_APPROVAL_TESTS_PASS`. Operator Web runtime,
Temporary Chat mode, remote upload and external end-to-end remain
`NOT_RUN / NOT_VERIFIED`. R05, R04 and R03 retain their existing package-level
states; Android remains deferred and D-15/D-16 AI acceptance was not run.

## Continuation review fix — RV05-A4-01/02

This continuation started from documentation HEAD
`c7db3550228d50ed37b121eb8596ee6145c90f8a`; it does not rewrite the earlier
source commit or its historical test evidence. Review found two bounded gaps:

- the preview response carried the three integrity headers, but cross-origin
  JavaScript was not granted access to them;
- the dialog reported every approve/revoke exception as a certain refusal and
  continued to label the pre-mutation candidate state as current.

The local, uncommitted fix adds an endpoint-only expose-header response for
exactly `X-Source-Ref`, `X-Content-SHA256` and `X-Package-SHA256`. It does not
change allowed origins, methods, credentials or the global middleware. The
corresponding real-router test verifies allowed-origin access, same-origin
behavior, absence of an allow-origin response for a disallowed origin, and no
preview integrity-header leakage on 401/403/409 responses.

The local Flutter fix treats a received 4xx response as an explicit server
refusal and all transport/time-out/unreadable-success outcomes as unknown. An
unknown approve response says that permission and queuing may have occurred;
an unknown revoke response says revocation may have occurred. Neither path
automatically retries or renders raw exception data. Confirmed success uses
the state returned by the mutation and renders it separately from the
candidate state captured at preview time.

| Scope | Result | Evidence SHA-256 |
|---|---:|---|
| focused Flutter fail-before | exit `1`; `6 passed / 4 failed` as expected | `4F2534E0B6388C1AF465BCEF18A0B6546285039322449BA0784F65FF9ED7B29E` |
| final focused Flutter | `11 passed`, exit `0` | `F41FD3FCF0DCFD1001C773A574DAB0C5AB4B9C6A875BE25851BBF4AC01419A60` |
| Flutter Documents/Auth regression | `28 passed`, exit `0` | `902B5D88CD8D7396C15E5CE19BEE196239C2D37B899BA03233564756D855E9AD` |
| `flutter analyze --no-pub` | no issues, exit `0` | `5F3620CF2A1933C2D5490996E2A6E5DDCE7EBE65B1DED4A4793E76D06FF8E3AD` |
| real backend ASGI/CORS test and Python compile | `NOT_RUN / RESOURCE_OBSERVABILITY_BLOCKED` | no PASS evidence |

The required backend environment could not be safely used: an authorized,
exact-name Docker observation did not return in the bounded window, and its
client was terminated without changing Docker/WSL/Windows. No retry loop,
daemon restart, substitute environment or historical-result reuse was used.
Consequently the four source/test changes are preserved only as patch
`81E311E7C129FC7ACC8829BC8B2E3FB31CDFEA6F800D56EE46E16E9E58A17914`
under the protected continuation evidence root. They are not staged,
committed, pushed, deployed or described as source-ready.

Continuation status:
`PREVIEW_TRANSPORT_AND_DECISION_SOURCE_PARTIAL / LOCAL_ONLY / NOT_DEPLOYED`.
Flutter decision tests pass, but `API_CORS_AND_WIDGET_DECISION_TESTS_PASS` is
not claimed until the real backend test and compile step are executed. Browser
runtime, real Supervisor/Temporary Chat, remote upload and external end-to-end
remain `NOT_RUN / NOT_VERIFIED`.

## Backend resume — bounded Engine preflight

The owner accepted documentation checkpoint
`215432831278c0c417bc950ccc8406718be604a1` only as the record of partial work.
The four WIP files, patch size `18039 B`, patch SHA-256
`81E311E7C129FC7ACC8829BC8B2E3FB31CDFEA6F800D56EE46E16E9E58A17914`
and reverse apply-check remain unchanged. Current file SHA-256 values are:

- router: `F535DFB48E0819B9824651767E558065F25E4898E3A42A5ACED4B57D36BA9AD5`;
- backend test: `92DA442A61AA6651F2DF031C7CBC1107F3413D58812946492193589BC7A9475C`;
- Flutter dialog: `5208A68125A3127D0A8A8DCA482FCB9E13C8319DF211B6F92AA256A87E26A375`;
- Flutter test: `53C1F0C43DBD9C27345C18FBD35B8675F41D230348DAA8A5279480C4C659FECE`.

The preserved Flutter logs were re-hashed and match E014, E018, E016 and E019.
They are prior executions against the unchanged frontend WIP, not new runs.

One bounded observation sequence used the selected local Docker CLI, no
`DOCKER_HOST` or `DOCKER_CONTEXT` override, context `desktop-linux` and endpoint
`npipe:////./pipe/dockerDesktopLinuxEngine`. Local context reads succeeded.
The server-version request, PID `37684`, returned no stdout or stderr and was
terminated after `20.235 s`; no exit code was available. That exact CLI process
is no longer present. This is `TIMEOUT_NO_STDERR`, not access denial.

At `2026-09-12T15:27:15Z`, Windows reported `25.802 GiB` physical total,
`6.052 GiB` available and commit `35.994 / 70.802 GiB`, leaving `34.808 GiB`.
The matching `docker-desktop` WSL pool read succeeded: `17.563 GiB` total,
`14.198 GiB` available, swap `8.0 GiB` with `1.9 MiB` used. These measurements
pass the numeric reserves but cannot replace a response from Docker Engine.

Because the Engine server did not answer, the exact old container
`next-stabil-r05-a4-20260912t121418z-regression-final` remains `UNKNOWN`; no
container or image inspection was attempted. No old resource was stopped and
no new test container was created. The required backend ASGI/CORS test, small
API regression and `compileall` therefore remain `NOT_RUN`. No source/test file
is committed or pushed by this resume.

Current status remains
`PREVIEW_TRANSPORT_AND_DECISION_SOURCE_PARTIAL / LOCAL_ONLY / NOT_DEPLOYED /
RESOURCE_OBSERVABILITY_BLOCKED`. A later attempt requires a real change in the
Engine condition and separate authorization for any infrastructure recovery;
it must first repeat one bounded server read and account for the old exact-name
resource. R06, runtime, browser, Supervisor, Temporary Chat and external export
remain outside scope.

## Docker service operation and partial recovery

The owner first confirmed that the same `desktop-linux` server read timed out
from an ordinary non-elevated PowerShell session. Docker Desktop was responsive
only partially and displayed `Data unavailable at this time`. The GUI showed
the historical backend container prefix `9d9b46c53041`, but its Inspect view
did not load. Therefore the current mount was explicitly classified `UNKNOWN`;
the repository Compose declaration was not used as runtime evidence.

After an informed risk statement, the owner authorized exactly one standard
Docker Desktop restart despite that unknown. Docker Desktop reported
`Wsl/Service/CreateInstance/0x800705b4` and remained at `Starting the Docker
Engine`. A bounded post-operation check found no Engine-ready response and all
five health probes were temporarily unreachable. No second restart,
`wsl --shutdown`, kill, reset, prune, context change or service recreation was
performed.

The owner later reported that Docker started after an update performed outside
Codex. This update was not requested or executed by Codex and its prior version
is not reconstructed here. Read-only observation through the formally approved
execution path then confirmed Docker Desktop `4.91.0`, Engine `29.8.0`, and:

- backend full ID
  `9d9b46c530412e48562b5427a0586b08c1e919ff293ec2cbd1489faffc98615a`;
- backend image ID
  `sha256:6342b36fa2cdd2501ea4e0e9fada9a9ffaa4894f0c512f19f822f009e8d63702`;
- `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend` and
  `/data=C:/ai-lab-core/data`, both bind mounts;
- no recovery or A4 WIP mount in that container;
- the same production container IDs restarted at approximately `14:41Z`;
- pinned R02 image
  `sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`
  remained available;
- exact old test container
  `next-stabil-r05-a4-20260912t121418z-regression-final` returned
  `no such object`.

At `2026-09-14T14:45:58Z`, backend, n8n and Open WebUI returned HTTP `200`.
Supervisor `127.0.0.1:8787` and public gateway `127.0.0.1:8789` remained
unreachable. Because production service recovery was incomplete, the procedure
stopped before a new resource gate or test container. Backend ASGI/CORS, API
regression and compileall remain `NOT_RUN / PRODUCTION_PARTIAL_UNHEALTHY`; the
four WIP paths remain unstaged and are not source-ready.

Sanitized local evidence is under
`C:\ai-lab-core-staging\recovery\R05_A4_PREVIEW_DECISION_20260912T140056Z\docker-recovery-20260914T143943Z`.
The current status is
`ENGINE_RECOVERED / PRODUCTION_PARTIAL_UNHEALTHY / SOURCE_PARTIAL / LOCAL_ONLY /
NOT_DEPLOYED`. R06, product runtime tests, browser, Supervisor calls, Temporary
Chat and external export remain outside this execution.

## Host-service continuation and Supervisor safety stop

At `2026-09-14T17:09:04Z`, after a current resource gate passed, the existing
Windows task `\NEXT Stabil - Public Gateway` was started exactly once. PID
`41784` runs the clean, main-identical
`C:\ai-lab-core\operations\gateway\public_web_server.cjs` through the existing
Node binary. It listens on `127.0.0.1:8789`; `/gateway-health`, proxied
`/health`, `/version` and existing Web returned `200`. The Web root hash
matched the existing live artifact, and `/control`, `/control/` and
`/control/health` returned `404`. This is restoration of an existing endpoint,
not a new frontend or recovery deployment.

The existing Supervisor was deliberately not started. Its task points to
`C:\ai-lab-core\operations\supervisor\server.js`; the active main/original
VisionQueue does not contain the accepted but undeployed R05-A2 replay guard.
The on-disk Vision spool contains one valid `UI_CHANGED` item and the analysis
root contains three incoming directories. More importantly, a bounded,
content-free database read with `transaction_read_only=on` found
`advanced_queued=16`, `document_preparation queued=18`, `assistant waiting=1`
and `vision not_evaluated=5956`. Effective runtime flags enable Vision
automation, Advanced analysis, KB processing/vector writes and Assistant
Pipeline V2. Three backup schedules are enabled/synced, although active
backup/restore runs are zero.

Those facts fail the prompt's no-unapproved-resume condition. No Supervisor
task start, queue resume, flag/config/schedule change, spool mutation, model,
Temporary Chat or export occurred. The current blocker is
`SUPERVISOR_START_BLOCKED_PENDING_OWNER_DECISION`, not the historical Docker
Engine timeout. Backend ASGI/CORS/API and compileall remain `NOT_RUN`; no test
container was created and the four source/test WIP files remain unstaged and
`LOCAL_ONLY / NOT_DEPLOYED`.

D-21 separately records the owner requirement
`SINGLE_INSTALL_ROOT=C:\ai-lab-core / SINGLE_START_ENTRYPOINT` as
`REQUIRED_AFTER_A4_REVIEW`. It does not authorize a current mount/task change,
deployment, directory move or cleanup. Sanitized local evidence is indexed as
E030–E031; detailed logs remain protected outside Git.

## Isolated backend completion with Supervisor intentionally stopped

The owner explicitly authorized leaving the Supervisor
`INTENTIONALLY_STOPPED` and running one isolated A4 backend campaign. Current
preflight confirmed Engine `29.8.0`, the pinned R02 image, the unchanged active
backend mount `/app=C:/ai-lab-core/build/deploy-main-483f9bf8/backend`, no
recovery/WIP consumer and no previous exact-name A4 container. Resource gates
passed before and after the campaign.

The new CORS test was run first against the committed router preimage
`f3cbe58bed0de34cfd39a57d481abb2c61c2f4ac`. It failed as expected with exit
`1`, `1 failed`, because `access-control-expose-headers` was absent. Against
the protected WIP, the entire `test_r05_visual_export_api.py` module passed
`3 passed`, exit `0`; compileall of the changed router and backend test exited
`0`. The test used the real ASGI router and CORS middleware, synthetic settings
and SQLite, without product lifespan.

The single container
`next-stabil-r05-a4-20260914t183454z-backend-final`, full ID
`9fbb55aab1aa51375e57a62daa1b255af6907bde32368e0d35abf52f3c1a446d`,
used the pinned image
`sha256:4b12cf0e2501981eff4d7ce6cfd5eb55fcc83ae41bf5561b565e7aa8aed37651`,
`network=none`, read-only root/source, tmpfs, no ports, privilege, socket or
production mounts. It was stopped and removed after identity verification.
No matching container remains.

The four tested source/test files were committed as
`04ab5e58cf86896ffd946cabffde13367d343f53`. Earlier Flutter fail-before
`6 passed / 4 failed`, focused `11 passed`, Documents/Auth `28 passed` and
analyze PASS remain prior evidence for unchanged frontend bytes and were not
rerun. Current health checks at `2026-09-14T18:37:38Z` returned `200` for the
Public Gateway, proxied API, Web, backend, n8n and Open WebUI; `/control*`
returned `404`. Supervisor remained unreachable and was not started.

This establishes
`PREVIEW_TRANSPORT_AND_DECISION_FIX_READY_FOR_REVIEW / NOT_DEPLOYED` and
`API_CORS_AND_WIDGET_DECISION_TESTS_PASS`. It is not owner acceptance, a Web
runtime test, Temporary Chat verification, remote upload or external
end-to-end proof. Local logs E032–E035 remain protected outside Git.

## Owner acceptance and transition back to R04 / D-21

On 2026-09-15 the owner accepted R05-A4 for the implementation rooted in
`f3cbe58bed0de34cfd39a57d481abb2c61c2f4ac`, the final four-file source
`04ab5e58cf86896ffd946cabffde13367d343f53`, and evidence HEAD
`8620871711321a42e62291e52865b5a668a4955d` as
`SOURCE_AND_API_WIDGET_TESTS_ACCEPTED / NOT_DEPLOYED`.

The accepted scope is the preview of final bytes, the additive exposure of
exactly `X-Source-Ref`, `X-Content-SHA256` and `X-Package-SHA256`, and the
correct distinction between confirmed and unknown approve/revoke results. The
ASGI/CORS result remains a protocol-response test, not a browser execution of
the operator dialog. Earlier Flutter results remain earlier executions against
the same unchanged files; they were not rerun for this acceptance record.

Operator Web runtime, real Temporary Chat, remote upload, external end-to-end,
the production of `locally_redacted` material, deployment and the whole R05
remain unaccepted/unverified. Supervisor remains `INTENTIONALLY_STOPPED`.
D-21 now authorizes only read-only inventory and reviewed documentation for
the single-root/single-start map; it does not authorize cutover, relocation,
cleanup or startup implementation.
