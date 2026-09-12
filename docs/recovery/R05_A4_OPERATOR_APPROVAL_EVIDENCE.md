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
