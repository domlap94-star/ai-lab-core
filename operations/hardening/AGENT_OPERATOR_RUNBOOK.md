# Read-only Agent operator runbook

CHUNK 16 Agent is read-only for business data. The only persistent write is a
sanitized row in `agent_executions`.

## Enforced policy

- deny by default tool registry;
- maximum 5 planning rounds, 8 tool calls and 180 seconds per request;
- strict JWT, role, Client and Inspection scope;
- no SQL, shell, PowerShell, Docker, supervisor, general browser, email send,
  CRM write or live Vision execution tool;
- no conversation persistence;
- tool results are untrusted data and deterministic source IDs are enforced.

The audit row contains request ID, user ID, status, tool count, duration,
round count and tool name/outcome/duration only. It must not contain prompts,
document/email bodies, raw LLM output, SQL, stack traces, tokens or secrets.

## Operational checks

Run `check-production-health.ps1` and inspect the bounded
`agent_orphan_started` count. A row in `started` older than four minutes is an
orphan signal because the request bound is 180 seconds. Report it; do not
delete or rewrite audit history automatically.

Expected terminal states are `completed`, `blocked`, `failed` and `cancelled`.
Mutation requests should be refused in Polish and normally produce `blocked`
with zero business writes. Unknown or hallucinated tools are also blocked.

If `llama3.2` is unavailable, return the friendly 503 path and finalize the
audit as failed. Qdrant failure must preserve structured/lexical search.
Vision worker availability does not affect reads of already persisted Vision
results; a missing result is a limitation and must not trigger a Vision job.

When investigating an Agent response, use its request ID and bounded tool
trace. Never enable raw prompt/response logging. Do not repair an orphan by
fabricating a terminal outcome; any future reconciliation policy requires a
separate reviewed change.
