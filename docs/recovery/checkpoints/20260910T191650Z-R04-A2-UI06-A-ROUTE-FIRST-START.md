# R04-20260910T191650Z-A2-UI06-A-ROUTE-FIRST-START

- UTC: `2026-09-10T19:16:50Z`.
- Branch/worktree: `recovery/next-stabil-repair-completion` /
  `C:\ai-lab-core-recovery`.
- Starting local/remote HEAD:
  `04334cc061d3e2ec0fa0c8f0262ff3ee707b84d3`.
- Accepted frontend source/test:
  `48fbecae0a76edb25f60e9dd314bb8d65bfbae4b`.
- Saved synthetic backend source:
  `f4ea20c74f92c0423db087ba8d60bb8cc7f2ec99`.
- Previous checkpoint:
  `docs/recovery/checkpoints/20260910T175215Z-R04-A2-UI06-A-REPEAT.md`.

## Owner clarification and verified wiring

The owner replaced only the remaining scenario-A procedure. A normal Dashboard
preview request is allowed; the test subject is the first `build()` of the new
`DocumentsController` instance created when the operator navigates to
`/documents`.

Static inspection at the accepted frontend commit confirmed:

- `dashboardRecentDocumentsProvider` is a `FutureProvider` that calls the shared
  `documentsRepositoryProvider.fetchDocuments(..., limit: 6)`;
- `documentsControllerProvider` is a distinct `AsyncNotifierProvider`;
- `/documents` returns a new `ProviderScope` overriding that provider with
  `DocumentsController(initialFilters: filters)`;
- the controller's first `build()` calls `_load()` with `pageSize = 50`;
- the application menu uses `context.go('/documents')`, so the required route
  transition does not require a browser reload.

The shared repository and endpoint do not imply a shared controller instance.
Caller/provider/route wiring, not the URL parameter alone, is the basis for
this distinction.

## Preserved history and current gate

Both earlier A attempts remain `NOT_VERIFIED`; their reports and procedural
deviations are unchanged. The prior global prohibition on any document-list GET
was an excessive test condition, not a requirement of the accepted UI06 fix.
The last full reload while the backend was stopped failed earlier at auth/session
restoration and therefore never exercised `DocumentsController`.

Runtime for the corrected route-first A is `NOT_RUN / WAITING_OWNER_READY`.
The owner has been asked for a current `GOTOWE` before any preserved A2 resource
is started. At this checkpoint no container, Web process or telemetry resource
was started and no database or fixture was changed.

Application tests: `NOT_RUN`; product source/tests are unchanged. R04 remains
`IN_PROGRESS`; R03 remains `WAITING_APPROVAL / WAITING_ESCROW_DECISION`;
Android remains `DEFERRED_BY_OWNER / NOT_TESTED`; D-15/D-16 AI acceptance
remains `NOT_RUN`.

One next safe step: after the owner sends a current `GOTOWE`, revalidate the
preserved resource identities and gates, start the existing monitored stack,
and execute exactly one owner-operated route-first A without reload during the
outage. Without that confirmation, stop after publishing this documentation
reconciliation.
