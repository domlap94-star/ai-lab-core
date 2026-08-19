# Vision worker operator runbook

NEXT Stabil Vision is an on-demand processing bridge:

`backend -> host.docker.internal:8787 -> supervisor queue -> Playwright -> Edge -> ChatGPT Temporary Chat`.

It does not use the OpenAI API or a local Vision model. The supervisor remains
bound to `127.0.0.1:8787`; the queue concurrency is one. Never expose its
Vision endpoints through the public gateway.

## Normal health

1. `GET http://127.0.0.1:8787/health` returns supervisor liveness.
2. Use the authenticated backend Vision-health endpoint or the private
   supervisor bridge client to verify `READY` or an expected `BUSY` state.
3. Confirm queue size and active job ID metadata only. Do not inspect customer
   image content to diagnose a normal job.
4. The dedicated Edge profile is under `C:\ChatGPT-Vision-Worker`; it is not
   the user's primary Edge profile. Node 24.18.0, Playwright 1.62.1 and Edge
   channel 151 were verified at the hardening checkpoint.

## `AUTH_REQUIRED`

1. Automation pauses and qualified documents stay `pending_auth`; intake data
   must survive.
2. Open the dedicated visible Edge profile and let an operator authenticate
   manually. Never automate password, MFA, CAPTCHA, cookies or tokens.
3. Verify ChatGPT home is authenticated, close the manual tab, then call the
   authenticated private resume operation.
4. Run one synthetic Temporary Chat smoke before resuming customer jobs.
5. Confirm that no normal-chat fallback occurred.

## `UI_CHANGED`

1. Keep the queue paused. Do not click guessed selectors and do not fall back
   to a normal chat.
2. Reproduce with a synthetic fixture in visible Edge and collect only the
   allowed diagnostic metadata. Full-response debug logging is test-only and
   disabled for customer jobs.
3. Update semantic/ARIA selectors, run the worker contract tests and the 3-job
   release smoke, then explicitly resume.

## Worker or supervisor unavailable

New documents must remain persisted with pending/retryable Vision state. Do
not reset documents, enqueue historical files or run a bulk scan. Restart only
the failed component after capturing its command and logs. The supervisor is
started today by the existing `NEXT Stabil - Supervisor` scheduled task; the
Vision browser is created per job and must not remain as an uncontrolled
background process.

## Spool and retention

The only spool is `C:\ai-lab-core\data\vision-spool`. Canonical-path checks
must keep every job inside it. Terminal `COMPLETE`, `FAILED` and `CANCELLED`
jobs are eligible after 72 hours; active/queued jobs and original documents
are never TTL targets. Do not manually delete ambiguous entries.

Logs contain job IDs, hashes, types, durations, state transitions and bounded
error codes only. They must not contain cookies, access tokens, images, OCR
content, customer text or full ChatGPT responses.

## Privacy boundary

Every upload requires positive Temporary Chat verification and one job uses
one new Temporary Chat. Normal history and personalization memory are not
used. No normal-chat fallback exists. Temporary Chat is not a zero-retention
guarantee: OpenAI may retain a copy for the period defined by its current
product policy, and Library absence is not proof of immediate physical
deletion.
