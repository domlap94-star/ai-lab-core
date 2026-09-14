# R05-20260914T171601Z-A4-HOST-SERVICES-PARTIAL

## State

- Parent/checkpoint HEAD: `e63f4d1bb1a1dfe319b7789399cae2a878ba43fb` on
  `recovery/next-stabil-repair-completion`; local and tracking matched at start.
- R05-A4 remains `SOURCE_PARTIAL / LOCAL_ONLY / NOT_DEPLOYED` and is not
  accepted. R04/R05 remain `IN_PROGRESS`; R03 remains
  `WAITING_APPROVAL / WAITING_ESCROW_DECISION`.
- The four expected WIP files remain modified, unstaged and byte-identical to
  protected patch
  `81E311E7C129FC7ACC8829BC8B2E3FB31CDFEA6F800D56EE46E16E9E58A17914`.
  No A4 source was committed.

## Existing host services

The actual Windows tasks, entrypoints, Node binary, working directories and
source hashes were checked without importing the services. The active backend
remains mounted from `C:/ai-lab-core/build/deploy-main-483f9bf8/backend` and
has no recovery/WIP mount.

After a current resource gate passed (Windows physical available `7.537 GiB`,
commit headroom `37.647 GiB`, matching docker-desktop pool available
`14.012 GiB`), exactly one authorized start of
`\NEXT Stabil - Public Gateway` was issued. It produced PID `41784` running
`C:\Program Files\nodejs\node.exe` with
`C:\ai-lab-core\operations\gateway\public_web_server.cjs`, listening only on
`127.0.0.1:8789`. Gateway/backend/version/Web checks returned `200`; the
served `index.html` hash matched the existing live Web and all three
`/control*` probes returned `404`. The gateway remains running.

The Supervisor was not started. Static inspection showed that the existing
host task would use the main/original queue implementation, not the accepted
but undeployed R05-A2 replay guard. Read-only observations found:

- Vision spool: one valid `UI_CHANGED` job, no parse error, handoff marker or
  cancel marker; analysis spool: zero job directories and three incoming
  directories.
- Effective backend flags enabled Vision automation, Advanced analysis, KB
  processing/vector writes and Assistant Pipeline V2. Document preparation was
  false; Visual V2 and retention deletion were unset.
- A PostgreSQL transaction with `transaction_read_only=on` found revision
  `followup_assistant_chat_history_20260829`, `16 advanced_queued`,
  `18 document_preparation queued`, `1 assistant waiting`, and
  `5956 vision not_evaluated`. Active backup/restore runs were zero; three
  backup schedules were enabled/synced.

The first database observation recipe exited `1` before queries because the
installed psycopg connection did not expose `set_session`. The corrected
bounded command enforced read-only mode at connection time and exited `0`.
No record content, secret or customer identifier was read or published.

Starting the existing Supervisor could therefore resume or admit work outside
this authorization. No task start, queue resume, POST, spool edit, producer
change, schedule change, model call or export was performed. Status:
`SUPERVISOR_START_BLOCKED_PENDING_OWNER_DECISION`.

## Tests and evidence

Backend ASGI/CORS/API and compileall remain `NOT_RUN`: the required two-service
operational gate did not pass. Earlier Flutter results remain historical proof
for unchanged WIP, not new runs. No test container was created.

Sanitized local evidence (raw operational detail remains `LOCAL_ONLY`) is under
`C:\ai-lab-core-staging\recovery\R05_A4_PREVIEW_DECISION_20260912T140056Z\host-services-20260914T170821Z`:

- `public-gateway-observation.json`: SHA-256
  `FDDDF46E344C40A5DB792210F43C9879F0A08CD164EDC0EFA51BA9E141C7299D`;
- `supervisor-start-gate.json`: SHA-256
  `8C864EC414CAB9ABC6D3F8F2B2DBC421A91B09A4E8C3458585DA65913D1EBC57`.

## Owner installation decision

D-21 records `SINGLE_INSTALL_ROOT=C:\ai-lab-core` and one idempotent user
start entrypoint as `REQUIRED_AFTER_A4_REVIEW`. This changes requirements and
execution order only. Nothing was moved, deleted, remounted, deployed or
cleaned. Existing runtime and unfinished A4 are the explicit temporary
exception. Feature work remains blocked pending the separately approved R04
inventory/mapping/cutover/rollback work.

## One next safe step

Owner explicitly approves leaving the Supervisor `INTENTIONALLY_STOPPED` and
allows the one isolated, network-none A4 backend campaign despite that known
service state. Without that decision, do not start the Supervisor or the tests
and do not change producers, queues or schedules.
