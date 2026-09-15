# R04-20260915T201451Z-D21-P1-HOST-COEXISTENCE

## Completed

- Start/evidence parent: `ca250d47d91c63e229e551c43d79747d9fab141a`.
- Reviewed preimage source: `2e97b9f72bf2150cc395c19aa433174c0b2e933a`.
- Corrected source commit: `2e69622bc6a0b4888427f8ae5be119377aed26d9`.
- Owner authorization was `SOURCE / OFFLINE TEST ONLY` in
  `C:\ai-lab-core-recovery`; P1 remains not accepted and not deployed.
- `RV03-POSITIVE-01` and `RV03-POSITIVE-02` were reproduced against the
  preimage, then passed through the real worker/adapter/planner branches with
  complete in-process lower-boundary fakes.

## Verification

- Windows PowerShell `5.1.26100.8894` parser: changed `.ps1` files PASS.
- `startup-set.example.json`: PASS.
- `test-start-host-services.ps1`: 53/53 assertions, exit 0.
- `test-startup-real-adapters.ps1`: 48/48 assertions, exit 0.
- Shared public/private/unrelated Node process set: `BASE_READY_LIMITED`,
  Supervisor `INTENTIONALLY_STOPPED`, zero starts.
- Missing public service with free port and approved task: one fake start,
  readiness, then zero additional starts on the next plan.
- Exact process without listener: present/not ready, no duplicate start.
- Exact structural process/listener absence enables only the expected fake
  start path. Access denial, missing module/provider, incomplete evidence and
  unknown errors remain `UNKNOWN` and start nothing.
- Missing approved task returns `CONTROLLED_DEPLOY_REQUIRED`.
- Existing RV01–RV05, port/argument/mutex/deadline and fail-closed regressions
  remain green.

The first final-log wrapper attempt was invalid before collection because its
child PowerShell could not resolve `Get-FileHash`; those exit-1 logs are kept
and not counted. One corrected direct capture on unchanged source produced the
53/53 and 48/48 exit-0 logs.

LOCAL_ONLY evidence:
`C:\ai-lab-core-staging\recovery\R04_D21_SINGLE_ROOT_20260915T033112Z\p1-coexistence-20260915T193058Z`.
The preimage tar is 163,840 B, SHA-256
`C40DEB1DD96B0B88DCBC21D2132B0A59CCD9E29D2189ACD7766161207DBE53F8`.
Final stdout hashes are
`6B15018D1A1C7EFA831F7B3C6A6DCDBFFE2D4922A0C97B36925134DBAE55DD15`
and
`6112F31AFB76A2D7F192C0DFB8149226CD06D45C22038E7ADDB67C9F53A8881D`.

## Effects and limits

The only real effects were repository source/docs, synthetic temporary files,
short owned PowerShell test processes that completed, and the protected local
evidence directory. There were no real Docker, HTTP, CIM, TCP, Task Scheduler,
service, container, Supervisor, model, export, install, cutover, relocation or
cleanup operations. Nothing was copied to or executed from `C:\ai-lab-core`.
The original preservation set remains 203 entries with staged 0.

State: `R04 D21-P1 HOST_COEXISTENCE_AND_ABSENCE_SOURCE_READY_FOR_REVIEW /
OFFLINE_TEST_ONLY / NOT_DEPLOYED`. R04 remains `IN_PROGRESS`; R05 remains
`IN_PROGRESS`; R03 remains `WAITING_APPROVAL / WAITING_ESCROW_DECISION`.
Supervisor remains `INTENTIONALLY_STOPPED / NOT_STARTED_BY_THIS_SESSION`.

One next safe step: owner review of source
`2e69622bc6a0b4888427f8ae5be119377aed26d9` and the updated P1 evidence.
P2–P5 require a later, separate decision.
