# P0 Unified Assistant HTTP 422 Contract Sync Report

Date: 2026-08-25

Source baseline: `144923763ff6620cfaec6e40960dd76d9be8ec8b`

Stable: `NEXT Stabil 1.0.2+29`

Decision: `P0_UNIFIED_CONTRACT_SYNC_RESOLVED_PHYSICAL_RETEST_REQUIRED`

## Physical evidence and exact failure

Owner Android +37 evidence showed that connectivity/login and the Unified
Assistant page worked, but both an unscoped system question and the Client
quick action failed immediately with the generic 422 UI message. There was no
model delay. Backend access logs independently showed repeated
`POST /api/v1/ai/assistant/ask` HTTP 422 responses.

The +37 request body contains `question`, a bounded `conversation` list,
optional selected-scope IDs, and a non-null `attempt_id` on the first request.
The production generator uses values such as
`android-<microsecondsSinceEpoch>`: the captured structural equivalent was 24
characters and passed the 8–80 length and `[A-Za-z0-9_-]+` constraints.

## Source versus live runtime proof

At HEAD, `UnifiedAssistantRequest` allows optional `attempt_id` while retaining
`extra="forbid"`. The response also contains the bounded lifecycle fields and
the API exposes the authenticated cancel endpoint.

Before remediation, live OpenAPI proved:

- request fields: `question`, selected-scope IDs, and `conversation` only;
- `attempt_id`: absent;
- `additionalProperties`: false;
- lifecycle response fields: absent;
- cancel endpoint: absent.

The backend container used image `ai-lab-core-backend`, bind-mounted
`C:\ai-lab-core\backend` at `/app`, and its Python process had started at
2026-08-24T22:42:44Z, before commits `05df7fb` and `1449237`. Current files on
the mount therefore did not prove current imported code. The public version
endpoint does not carry a Git revision, so no nonexistent runtime revision
stamp is claimed; process start boundary plus live OpenAPI and behavior are the
conclusive loaded-contract evidence.

Direct authenticated synthetic controls returned:

- current +37 shape with `attempt_id`: HTTP 422,
  `body.attempt_id`, `extra_forbidden`, “Extra inputs are not permitted”;
- old shape without `attempt_id`: validation passed and entered the old slow
  model path; the diagnostic client timed out after 140.106 seconds;
- Client-scoped current shape: the same immediate HTTP 422 at
  `body.attempt_id`, before business logic.

This proves stale deployed backend code. Flutter request generation was not
malformed.

## Pre-deployment safety audit

Production DB head was
`followup_backup_planner_retention_20260824`; no migration was pending or
required. Active backup runs: 0. Active restore runs: 0. The private Supervisor
reported READY with no active job, queue, browser owner, waiter, or paused
state. Fifteen old `advanced_queued` DB rows last updated on 2026-08-24 were
already stale historical runtime state and had no corresponding Supervisor
queue; they were inspected but not modified.

The Supervisor process had started on 2026-08-24 at 18:15 local time, before
the `05df7fb` lifecycle changes. It therefore also required a bounded reload.

## Bounded deployment

Only the backend container was restarted. Because `/app` is a bind mount and
dependencies/schema did not change, no image rebuild or other service restart
was required. Postgres, Qdrant, Ollama, n8n, and Open WebUI were not restarted.

Only the exact owned scheduled task `NEXT Stabil - Supervisor` was stopped and
started. The replacement Node process is PID 13300, created at 2026-08-25
16:19:04 local time, after both source commits. The private architecture stayed
on loopback and health returned READY with an empty queue.

No DB row, job state, customer record, model, backup file, or network exposure
was changed.

## Post-deployment proof

Live OpenAPI now exposes:

- `attempt_id`: present;
- `additionalProperties`: false;
- response fields `current_stage`, `last_progress_at`, `can_cancel`, and
  `delayed`: present;
- `POST /api/v1/ai/assistant/{request_id}/cancel`: present.

The exact +37-shaped authenticated SYSTEM_META request returned HTTP 200 in
21.95 ms locally and HTTP 200 in 75.08 ms through the public HTTPS gateway.
Both returned `accepted_local`, `model=null`, and `current_stage=SYSTEM_META`.
No CRM retrieval or Advanced Analysis job was created.

A local-only synthetic GENERAL_KNOWLEDGE request returned HTTP 200,
`accepted_local`, `qwen3.5:9b`, two claims, zero sources, zero MISSING and no
external analysis in 100.293 seconds. This passes the contract but confirms
that physical latency remains a separate acceptance observation.

No real-customer Client or named-document model request was executed after
deployment because a failed local result could have triggered external
analysis. Their exact Flutter JSON shapes instead pass the shared FastAPI
contract fixture and remain owner physical read-only retest gates.

## Cross-stack regression and handoff gate

One shared fixture now covers:

- general request;
- Client-scoped request;
- selected/named-document request;
- retry with fresh `attempt_id`;
- conversation reset with empty effective history.

The Flutter test sends those cases through the actual
`UnifiedAssistantApi.ask()` serializer and compares the captured JSON exactly.
The backend test validates the same JSON with the actual FastAPI Pydantic
request class and verifies unknown fields still fail closed.

Results:

- backend contract plus Unified Assistant suite: 82/82 PASS in a disposable
  synthetic-config test container;
- Flutter contract plus Unified Assistant focused suite: 5/5 PASS;
- Flutter analyze: PASS, zero issues;
- full Flutter suite: 305/305 PASS;
- Supervisor queue, timeout/cancel, V2, recovery and idempotency assertions:
  PASS (the recovery fixture leaves a test-only timer and was stopped after
  emitting its terminal PASS assertion);
- post-restart authenticated read-only Clients list/search/detail, Global
  Search, Dashboard, Backup, Mail, Documents and System Control: HTTP 200;
- live post-deploy OpenAPI/current-shape SYSTEM_META: PASS.

`frontend/BUILDING.md` now requires live backend/Supervisor source loading,
live schema compatibility, and authenticated smoke before any future physical
candidate handoff. A source file on a bind mount is explicitly not sufficient.

## Android and roadmap

No Flutter production source changed. +37 is therefore reused; versionCode 38
was not consumed and no APK was rebuilt.

Roadmap:

- `P0 UNIFIED ASSISTANT FRONTEND/BACKEND CONTRACT SYNC = RESOLVED`;
- `P0 GENERAL/SYSTEM ROUTING = PHYSICAL RETEST REQUIRED`;
- `P0 DOCUMENT RETRIEVAL/LIFECYCLE = PHYSICAL RETEST REQUIRED`;
- `PRE-CHUNK23 = UNIFIED ASSISTANT IMPLEMENTED / PHYSICAL ACCEPTANCE REQUIRED`;
- `CHUNK23 = BLOCKED / NOT STARTED`.

The Release F Ignore-mail address/domain UI reminder remains mandatory.

## Production safety

DB migrations/writes, business writes, Qdrant writes/deletes, Gmail, n8n,
model changes, backup deletion, and stable publication were all zero. Only the
authorized backend and private Supervisor reloads were performed.
